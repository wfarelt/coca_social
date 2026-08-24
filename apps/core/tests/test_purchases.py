from decimal import Decimal

from django.test import TestCase

from apps.core.forms import PurchaseForm, PurchaseItemFormSet
from apps.core.models import Branch, Category, Product, Supplier


class PurchaseTotalsTests(TestCase):
    def test_purchase_formset_calculates_totals_from_lines(self):
        branch = Branch.objects.create(name="Sucursal 1", code="S01")
        category = Category.objects.create(name="Bebidas")
        supplier = Supplier.objects.create(name="Proveedor ABC", tax_id="123456789")
        product = Product.objects.create(
            name="Coca Cola 600ml",
            code="CC600",
            category=category,
            brand=None,
            purchase_price=Decimal("8.50"),
            sale_price=Decimal("12.00"),
            min_stock=Decimal("10.00"),
        )

        form = PurchaseForm(
            data={
                "branch": branch.pk,
                "supplier": supplier.pk,
                "folio": "CMP-001",
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

        self.assertTrue(form.is_valid())
        self.assertTrue(formset.is_valid())
        self.assertEqual(formset.calculate_totals(), Decimal("47.50"))
