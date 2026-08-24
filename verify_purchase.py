import os
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coca_social.settings")

import django

django.setup()

from apps.core.forms import PurchaseForm, PurchaseItemFormSet
from apps.core.models import Branch, Category, Product, Supplier

branch = Branch.objects.create(name="Sverify", code="SV01")
category = Category.objects.create(name="Bebidas")
supplier = Supplier.objects.create(name="Pverify", tax_id="123")
product = Product.objects.create(
    name="Pverify",
    code="PV-001",
    category=category,
    purchase_price=Decimal("8.50"),
    sale_price=Decimal("12.00"),
    min_stock=Decimal("10.00"),
)

form = PurchaseForm(
    data={
        "branch": branch.pk,
        "supplier": supplier.pk,
        "folio": "CMP-VERIFY",
        "status": "draft",
        "purchase_date": "2025-01-15",
        "subtotal": "0.00",
        "tax": "0.00",
        "total": "0.00",
        "notes": "Compra de prueba",
    }
)
formset = PurchaseItemFormSet(
    data={
        "purchaseitem_set-TOTAL_FORMS": "1",
        "purchaseitem_set-INITIAL_FORMS": "0",
        "purchaseitem_set-MIN_NUM_FORMS": "0",
        "purchaseitem_set-MAX_NUM_FORMS": "1000",
        "purchaseitem_set-0-id": "",
        "purchaseitem_set-0-product": str(product.pk),
        "purchaseitem_set-0-quantity": "5",
        "purchaseitem_set-0-cost_price": "9.50",
        "purchaseitem_set-0-line_total": "",
        "purchaseitem_set-0-DELETE": "",
    }
)

assert form.is_valid(), form.errors
assert formset.is_valid(), formset.errors
assert formset.calculate_totals() == Decimal("47.50"), formset.calculate_totals()
print("OK: form_valid=True formset_valid=True total=47.50")
