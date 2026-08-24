from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Sum


User = get_user_model()


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Branch(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)
    address = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Category(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Brand(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Supplier(TimeStampedModel):
    name = models.CharField(max_length=160)
    tax_id = models.CharField(max_length=40, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Product(TimeStampedModel):
    class Unit(models.TextChoices):
        PIECE = "piece", "Pieza"
        KILO = "kilo", "Kilogramo"
        LITER = "liter", "Litro"
        BOX = "box", "Caja"
        PACK = "pack", "Paquete"

    name = models.CharField(max_length=160)
    code = models.CharField(max_length=40, unique=True)
    barcode = models.CharField(max_length=80, blank=True, db_index=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="products", null=True, blank=True)
    unit = models.CharField(max_length=20, choices=Unit.choices, default=Unit.PIECE)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    min_stock = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class ProductStock(TimeStampedModel):
    class Status(models.TextChoices):
        NORMAL = "normal", "Normal"
        LOW = "low", "Bajo"
        OUT = "out", "Agotado"

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="stocks")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stocks")
    quantity = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    reserved_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        constraints = [models.UniqueConstraint(fields=["branch", "product"], name="unique_stock_by_branch_product")]
        ordering = ["branch__name", "product__name"]

    @property
    def available_quantity(self) -> Decimal:
        return self.quantity - self.reserved_quantity

    @property
    def status(self) -> str:
        if self.quantity <= 0:
            return self.Status.OUT
        if self.quantity <= self.product.min_stock:
            return self.Status.LOW
        return self.Status.NORMAL

    def __str__(self) -> str:
        return f"{self.branch} - {self.product}"

    @classmethod
    def get_or_create_stock(cls, branch: "Branch", product: "Product") -> "ProductStock":
        stock, _ = cls.objects.get_or_create(branch=branch, product=product)
        return stock

    def apply_delta(self, quantity_delta: Decimal) -> None:
        self.quantity = self.quantity + quantity_delta
        self.save(update_fields=["quantity", "updated_at"])


class Customer(TimeStampedModel):
    name = models.CharField(max_length=160)
    tax_id = models.CharField(max_length=40, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Purchase(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        POSTED = "posted", "Registrada"
        CANCELED = "canceled", "Cancelada"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="purchases")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchases")
    folio = models.CharField(max_length=40, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    purchase_date = models.DateField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True)
    stock_posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-purchase_date", "-created_at"]

    def __str__(self) -> str:
        return self.folio

    def post_to_inventory(self, created_by: User) -> None:
        from django.utils import timezone

        if self.stock_posted_at:
            return
        total_subtotal = Decimal("0.00")
        for item in self.items.select_related("product"):
            line_total = item.quantity * item.cost_price
            if item.line_total != line_total:
                item.line_total = line_total
                item.save(update_fields=["line_total"])
            total_subtotal += line_total
            stock = ProductStock.get_or_create_stock(self.branch, item.product)
            stock.apply_delta(item.quantity)
            StockMovement.objects.create(
                branch=self.branch,
                product=item.product,
                movement_type=StockMovement.Type.IN,
                quantity=item.quantity,
                reference=self.folio,
                created_by=created_by,
            )
            KardexEntry.objects.create(
                branch=self.branch,
                product=item.product,
                reference=self.folio,
                movement_type=StockMovement.Type.IN,
                quantity_in=item.quantity,
                quantity_out=Decimal("0.00"),
                balance=stock.quantity,
                unit_cost=item.cost_price,
                created_by=created_by,
            )
        self.subtotal = total_subtotal
        self.total = total_subtotal + self.tax
        self.stock_posted_at = timezone.now()
        self.status = self.Status.POSTED
        self.save(update_fields=["subtotal", "total", "stock_posted_at", "status", "updated_at"])


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self) -> str:
        return f"{self.purchase} - {self.product}"


class Sale(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        PAID = "paid", "Pagada"
        CREDIT = "credit", "Crédito"
        CANCELED = "canceled", "Cancelada"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Efectivo"
        CARD = "card", "Tarjeta"
        TRANSFER = "transfer", "Transferencia"
        MIXED = "mixed", "Mixto"
        CREDIT = "credit", "Crédito"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="sales")
    cashier = models.ForeignKey(User, on_delete=models.PROTECT, related_name="sales")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="sales", null=True, blank=True)
    folio = models.CharField(max_length=40, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    cash_received = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    change_due = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    sold_at = models.DateTimeField(auto_now_add=True)
    stock_posted_at = models.DateTimeField(null=True, blank=True)
    payment_posted_at = models.DateTimeField(null=True, blank=True)
    credit_posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-sold_at", "-created_at"]

    def __str__(self) -> str:
        return self.folio

    def post_to_inventory(self, created_by: User) -> None:
        from django.utils import timezone

        if self.stock_posted_at:
            return
        subtotal = Decimal("0.00")
        for item in self.items.select_related("product"):
            line_total = item.quantity * item.unit_price - item.discount
            if item.line_total != line_total:
                item.line_total = line_total
                item.save(update_fields=["line_total"])
            subtotal += line_total
            stock = ProductStock.get_or_create_stock(self.branch, item.product)
            stock.apply_delta(-item.quantity)
            StockMovement.objects.create(
                branch=self.branch,
                product=item.product,
                movement_type=StockMovement.Type.OUT,
                quantity=item.quantity,
                reference=self.folio,
                created_by=created_by,
            )
            KardexEntry.objects.create(
                branch=self.branch,
                product=item.product,
                reference=self.folio,
                movement_type=StockMovement.Type.OUT,
                quantity_in=Decimal("0.00"),
                quantity_out=item.quantity,
                balance=stock.quantity,
                unit_cost=item.unit_price,
                created_by=created_by,
            )
        self.subtotal = subtotal
        self.total = subtotal - self.discount + self.tax
        self.stock_posted_at = timezone.now()
        self.save(update_fields=["subtotal", "total", "stock_posted_at", "updated_at"])

    def post_payment(self, created_by: User, amount: Decimal | None = None) -> None:
        from django.utils import timezone

        if self.payment_posted_at:
            return
        Payment.objects.create(
            sale=self,
            branch=self.branch,
            received_by=created_by,
            amount=amount if amount is not None else self.total,
            method=self.payment_method,
        )
        self.payment_posted_at = timezone.now()
        self.save(update_fields=["payment_posted_at", "updated_at"])

    def post_credit(self, created_by: User, due_date=None) -> None:
        from django.utils import timezone

        if self.credit_posted_at or self.status != self.Status.CREDIT:
            return
        credit_account, _ = CreditAccount.objects.get_or_create(
            sale=self,
            defaults={
                "customer": self.customer,
                "opened_balance": self.total,
                "remaining_balance": self.total,
                "due_date": due_date,
                "status": CreditAccount.Status.OPEN,
            },
        )
        if not credit_account.customer_id and self.customer_id:
            credit_account.customer = self.customer
        credit_account.opened_balance = self.total
        credit_account.remaining_balance = self.total
        if due_date:
            credit_account.due_date = due_date
        credit_account.save()
        self.credit_posted_at = timezone.now()
        self.save(update_fields=["credit_posted_at", "updated_at"])


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self) -> str:
        return f"{self.sale} - {self.product}"

    def save(self, *args, **kwargs):
        if self.quantity is not None and self.unit_price is not None:
            self.line_total = (self.quantity * self.unit_price) - self.discount
        super().save(*args, **kwargs)


class SaleReturn(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        POSTED = "posted", "Aplicada"
        CANCELED = "canceled", "Cancelada"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="sale_returns")
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="returns")
    code = models.CharField(max_length=40, unique=True)
    reason = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    posted_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="sale_returns")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.code

    def post_to_inventory(self, created_by: User) -> None:
        from django.utils import timezone

        if self.posted_at:
            return
        subtotal = Decimal("0.00")
        for item in self.items.select_related("product"):
            line_total = item.quantity * item.unit_price
            if item.line_total != line_total:
                item.line_total = line_total
                item.save(update_fields=["line_total"])
            subtotal += line_total
            stock = ProductStock.get_or_create_stock(self.branch, item.product)
            stock.apply_delta(item.quantity)
            StockMovement.objects.create(
                branch=self.branch,
                product=item.product,
                movement_type=StockMovement.Type.IN,
                quantity=item.quantity,
                reference=self.code,
                created_by=created_by,
            )
            KardexEntry.objects.create(
                branch=self.branch,
                product=item.product,
                reference=self.code,
                movement_type=StockMovement.Type.IN,
                quantity_in=item.quantity,
                quantity_out=Decimal("0.00"),
                balance=stock.quantity,
                unit_cost=item.unit_price,
                created_by=created_by,
            )
        self.subtotal = subtotal
        self.total = subtotal
        self.status = self.Status.POSTED
        self.posted_at = timezone.now()
        self.save(update_fields=["subtotal", "total", "status", "posted_at", "updated_at"])

    def reverse_inventory(self, created_by: User) -> None:
        from django.utils import timezone

        if self.status == self.Status.CANCELED:
            return
        for item in self.items.select_related("product"):
            stock = ProductStock.get_or_create_stock(self.branch, item.product)
            stock.apply_delta(-item.quantity)
            StockMovement.objects.create(
                branch=self.branch,
                product=item.product,
                movement_type=StockMovement.Type.OUT,
                quantity=item.quantity,
                reference=f"REV-{self.code}",
                created_by=created_by,
            )
            KardexEntry.objects.create(
                branch=self.branch,
                product=item.product,
                reference=f"REV-{self.code}",
                movement_type=StockMovement.Type.OUT,
                quantity_in=Decimal("0.00"),
                quantity_out=item.quantity,
                balance=stock.quantity,
                unit_cost=item.unit_price,
                created_by=created_by,
            )
        self.status = self.Status.CANCELED
        self.save(update_fields=["status", "updated_at"])


class SaleReturnItem(models.Model):
    sale_return = models.ForeignKey(SaleReturn, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self) -> str:
        return f"{self.sale_return} - {self.product}"

    def save(self, *args, **kwargs):
        if self.quantity is not None and self.unit_price is not None:
            self.line_total = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class CreditAccount(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Abierta"
        PARTIAL = "partial", "Parcial"
        PAID = "paid", "Pagada"
        OVERDUE = "overdue", "Vencida"

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="credits")
    sale = models.OneToOneField(Sale, on_delete=models.CASCADE, related_name="credit_account")
    opened_balance = models.DecimalField(max_digits=12, decimal_places=2)
    remaining_balance = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)

    def __str__(self) -> str:
        return f"Crédito {self.customer} - {self.sale}"


class Payment(TimeStampedModel):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="payments", null=True, blank=True)
    credit_account = models.ForeignKey(CreditAccount, on_delete=models.CASCADE, related_name="payments", null=True, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="payments")
    received_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="received_payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=Sale.PaymentMethod.choices, default=Sale.PaymentMethod.CASH)
    paid_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Pago {self.amount}"


class CashShift(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Abierta"
        CLOSED = "closed", "Cerrada"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="cash_shifts")
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="cash_shifts")
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    initial_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    expected_cash = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    counted_cash = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    difference = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)

    def __str__(self) -> str:
        return f"Turno {self.branch} - {self.user}"


class CashMovement(TimeStampedModel):
    class Type(models.TextChoices):
        INCOME = "income", "Ingreso"
        EXPENSE = "expense", "Egreso"

    shift = models.ForeignKey(CashShift, on_delete=models.CASCADE, related_name="movements")
    movement_type = models.CharField(max_length=20, choices=Type.choices)
    concept = models.CharField(max_length=160)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="cash_movements")

    def __str__(self) -> str:
        return f"{self.concept} - {self.amount}"


class Expense(TimeStampedModel):
    shift = models.ForeignKey(CashShift, on_delete=models.CASCADE, related_name="expenses")
    concept = models.CharField(max_length=160)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="expenses")

    def __str__(self) -> str:
        return self.concept


class InventoryAdjustment(TimeStampedModel):
    class Reason(models.TextChoices):
        COUNT = "count", "Conteo"
        DAMAGE = "damage", "Merma"
        THEFT = "theft", "Faltante"
        CORRECTION = "correction", "Corrección"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="adjustments")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="adjustments")
    reason = models.CharField(max_length=20, choices=Reason.choices)
    previous_quantity = models.DecimalField(max_digits=14, decimal_places=2)
    new_quantity = models.DecimalField(max_digits=14, decimal_places=2)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="inventory_adjustments")
    notes = models.TextField(blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.branch} - {self.product}"

    def apply_to_inventory(self, created_by: User) -> None:
        from django.utils import timezone

        if self.applied_at:
            return
        stock = ProductStock.get_or_create_stock(self.branch, self.product)
        delta = self.new_quantity - self.previous_quantity
        stock.apply_delta(delta)
        movement_type = StockMovement.Type.IN if delta >= 0 else StockMovement.Type.OUT
        StockMovement.objects.create(
            branch=self.branch,
            product=self.product,
            movement_type=movement_type,
            quantity=abs(delta),
            reference=f"AJ-{self.pk}",
            created_by=created_by,
        )
        KardexEntry.objects.create(
            branch=self.branch,
            product=self.product,
            reference=f"AJ-{self.pk}",
            movement_type=StockMovement.Type.ADJUSTMENT,
            quantity_in=delta if delta > 0 else Decimal("0.00"),
            quantity_out=abs(delta) if delta < 0 else Decimal("0.00"),
            balance=stock.quantity,
            unit_cost=self.product.purchase_price,
            created_by=created_by,
        )
        self.applied_at = timezone.now()
        self.save(update_fields=["applied_at", "updated_at"])

    def reverse_inventory(self, created_by: User) -> None:
        from django.utils import timezone

        if not self.applied_at:
            return
        stock = ProductStock.get_or_create_stock(self.branch, self.product)
        delta = self.previous_quantity - self.new_quantity
        stock.apply_delta(delta)
        movement_type = StockMovement.Type.IN if delta >= 0 else StockMovement.Type.OUT
        StockMovement.objects.create(
            branch=self.branch,
            product=self.product,
            movement_type=movement_type,
            quantity=abs(delta),
            reference=f"REV-AJ-{self.pk}",
            created_by=created_by,
        )
        KardexEntry.objects.create(
            branch=self.branch,
            product=self.product,
            reference=f"REV-AJ-{self.pk}",
            movement_type=StockMovement.Type.ADJUSTMENT,
            quantity_in=delta if delta > 0 else Decimal("0.00"),
            quantity_out=abs(delta) if delta < 0 else Decimal("0.00"),
            balance=stock.quantity,
            unit_cost=self.product.purchase_price,
            created_by=created_by,
        )
        self.applied_at = None
        self.save(update_fields=["applied_at", "updated_at"])


class StockMovement(TimeStampedModel):
    class Type(models.TextChoices):
        IN = "in", "Entrada"
        OUT = "out", "Salida"
        ADJUSTMENT = "adjustment", "Ajuste"
        TRANSFER_IN = "transfer_in", "Traspaso recibido"
        TRANSFER_OUT = "transfer_out", "Traspaso enviado"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="stock_movements")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="stock_movements")
    movement_type = models.CharField(max_length=20, choices=Type.choices)
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    reference = models.CharField(max_length=80, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="stock_movements")

    def __str__(self) -> str:
        return f"{self.branch} - {self.product}"


class Transfer(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        SENT = "sent", "Enviado"
        RECEIVED = "received", "Recibido"
        CANCELED = "canceled", "Cancelado"

    code = models.CharField(max_length=40, unique=True)
    from_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="sent_transfers")
    to_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="received_transfers")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    stock_sent_at = models.DateTimeField(null=True, blank=True)
    stock_received_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="created_transfers")
    received_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="received_transfers_user", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.code

    def send_to_inventory(self, created_by: User) -> None:
        from django.utils import timezone

        if self.stock_sent_at:
            return
        for item in self.items.select_related("product"):
            stock = ProductStock.get_or_create_stock(self.from_branch, item.product)
            stock.apply_delta(-item.requested_quantity)
            StockMovement.objects.create(
                branch=self.from_branch,
                product=item.product,
                movement_type=StockMovement.Type.TRANSFER_OUT,
                quantity=item.requested_quantity,
                reference=self.code,
                created_by=created_by,
            )
            KardexEntry.objects.create(
                branch=self.from_branch,
                product=item.product,
                reference=self.code,
                movement_type=StockMovement.Type.TRANSFER_OUT,
                quantity_in=Decimal("0.00"),
                quantity_out=item.requested_quantity,
                balance=stock.quantity,
                unit_cost=item.product.purchase_price,
                created_by=created_by,
            )
        self.status = self.Status.SENT
        self.sent_at = self.sent_at or timezone.now()
        self.stock_sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at", "stock_sent_at", "updated_at"])

    def receive_to_inventory(self, created_by: User) -> None:
        from django.utils import timezone

        if self.stock_received_at:
            return
        for item in self.items.select_related("product"):
            received_quantity = item.received_quantity or item.requested_quantity
            stock = ProductStock.get_or_create_stock(self.to_branch, item.product)
            stock.apply_delta(received_quantity)
            StockMovement.objects.create(
                branch=self.to_branch,
                product=item.product,
                movement_type=StockMovement.Type.TRANSFER_IN,
                quantity=received_quantity,
                reference=self.code,
                created_by=created_by,
            )
            KardexEntry.objects.create(
                branch=self.to_branch,
                product=item.product,
                reference=self.code,
                movement_type=StockMovement.Type.TRANSFER_IN,
                quantity_in=received_quantity,
                quantity_out=Decimal("0.00"),
                balance=stock.quantity,
                unit_cost=item.product.purchase_price,
                created_by=created_by,
            )
        self.status = self.Status.RECEIVED
        self.received_at = self.received_at or timezone.now()
        self.stock_received_at = timezone.now()
        self.save(update_fields=["status", "received_at", "stock_received_at", "updated_at"])


class TransferItem(models.Model):
    transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    requested_quantity = models.DecimalField(max_digits=14, decimal_places=2)
    received_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    def __str__(self) -> str:
        return f"{self.transfer} - {self.product}"


class KardexEntry(TimeStampedModel):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="kardex_entries")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="kardex_entries")
    reference = models.CharField(max_length=80)
    movement_type = models.CharField(max_length=20)
    quantity_in = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    quantity_out = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="kardex_entries")

    def __str__(self) -> str:
        return f"{self.branch} - {self.product}"
