from django.contrib import admin

from .models import (
    Brand,
    Branch,
    CashMovement,
    CashShift,
    Category,
    CreditAccount,
    Customer,
    Expense,
    InventoryAdjustment,
    KardexEntry,
    Payment,
    Product,
    ProductStock,
    Purchase,
    PurchaseItem,
    Sale,
    SaleItem,
    SaleReturn,
    SaleReturnItem,
    StockMovement,
    Supplier,
    Transfer,
    TransferItem,
)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "address")
    search_fields = ("name", "code")
    list_filter = ("is_active",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "tax_id", "phone", "is_active")
    search_fields = ("name", "tax_id", "phone")
    list_filter = ("is_active",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "brand", "sale_price", "min_stock", "is_active")
    search_fields = ("code", "name", "barcode")
    list_filter = ("is_active", "category", "brand")


@admin.register(ProductStock)
class ProductStockAdmin(admin.ModelAdmin):
    list_display = ("branch", "product", "quantity", "reserved_quantity")
    search_fields = ("branch__name", "product__name", "product__code")
    list_filter = ("branch",)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "credit_limit", "balance", "is_active")
    search_fields = ("name", "tax_id", "phone")
    list_filter = ("is_active",)


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("folio", "branch", "supplier", "status", "purchase_date", "total")
    search_fields = ("folio", "supplier__name")
    list_filter = ("status", "branch", "purchase_date")
    inlines = [PurchaseItemInline]


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0


class SaleReturnItemInline(admin.TabularInline):
    model = SaleReturnItem
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("folio", "branch", "cashier", "customer", "status", "payment_method", "total")
    search_fields = ("folio", "customer__name")
    list_filter = ("status", "payment_method", "branch")
    inlines = [SaleItemInline]


@admin.register(SaleReturn)
class SaleReturnAdmin(admin.ModelAdmin):
    list_display = ("code", "branch", "sale", "status", "total", "posted_at")
    search_fields = ("code", "sale__folio", "branch__name")
    list_filter = ("status", "branch")
    inlines = [SaleReturnItemInline]


@admin.register(CreditAccount)
class CreditAccountAdmin(admin.ModelAdmin):
    list_display = ("customer", "sale", "opened_balance", "remaining_balance", "status", "due_date")
    search_fields = ("customer__name", "sale__folio")
    list_filter = ("status",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("amount", "method", "branch", "received_by", "sale", "credit_account", "paid_at")
    search_fields = ("branch__name", "sale__folio", "credit_account__customer__name")
    list_filter = ("method", "branch")


@admin.register(CashShift)
class CashShiftAdmin(admin.ModelAdmin):
    list_display = ("branch", "user", "status", "initial_amount", "expected_cash", "counted_cash", "difference")
    search_fields = ("branch__name", "user__username")
    list_filter = ("status", "branch")


@admin.register(CashMovement)
class CashMovementAdmin(admin.ModelAdmin):
    list_display = ("movement_type", "concept", "amount", "shift", "created_by", "created_at")
    search_fields = ("concept",)
    list_filter = ("movement_type",)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("concept", "amount", "shift", "created_by", "created_at")
    search_fields = ("concept",)


@admin.register(InventoryAdjustment)
class InventoryAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("branch", "product", "reason", "previous_quantity", "new_quantity", "created_by")
    search_fields = ("branch__name", "product__name")
    list_filter = ("reason", "branch")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("branch", "product", "movement_type", "quantity", "reference", "created_by")
    search_fields = ("reference", "product__name")
    list_filter = ("movement_type", "branch")


class TransferItemInline(admin.TabularInline):
    model = TransferItem
    extra = 0


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ("code", "from_branch", "to_branch", "status", "sent_at", "received_at")
    search_fields = ("code", "from_branch__name", "to_branch__name")
    list_filter = ("status", "from_branch", "to_branch")
    inlines = [TransferItemInline]
