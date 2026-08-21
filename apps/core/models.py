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

    class Meta:
        ordering = ["-purchase_date", "-created_at"]

    def __str__(self) -> str:
        return self.folio


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

    class Meta:
        ordering = ["-sold_at", "-created_at"]

    def __str__(self) -> str:
        return self.folio


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self) -> str:
        return f"{self.sale} - {self.product}"


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

    def __str__(self) -> str:
        return f"{self.branch} - {self.product}"


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
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="created_transfers")
    received_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="received_transfers_user", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.code


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
