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
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-id": "",
                "items-0-product": str(product.pk),
                "items-0-quantity": "5",
                "items-0-cost_price": "9.50",
                "items-0-line_total": "",
                "items-0-DELETE": "",
            }
        )

        self.assertTrue(form.is_valid())
        self.assertTrue(formset.is_valid())
        self.assertEqual(formset.calculate_totals(), Decimal("47.50"))

    def test_purchase_formset_ignores_blank_rows(self):
        branch = Branch.objects.create(name="Sucursal 2", code="S02")
        category = Category.objects.create(name="Bebidas")
        supplier = Supplier.objects.create(name="Proveedor XYZ", tax_id="987654321")
        product = Product.objects.create(
            name="Pepsi 600ml",
            code="PE600",
            category=category,
            purchase_price=Decimal("7.00"),
            sale_price=Decimal("10.00"),
            min_stock=Decimal("12.00"),
        )

        formset = PurchaseItemFormSet(
            data={
                "items-TOTAL_FORMS": "2",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-id": "",
                "items-0-product": str(product.pk),
                "items-0-quantity": "4",
                "items-0-cost_price": "8.00",
                "items-0-line_total": "",
                "items-0-DELETE": "",
                "items-1-id": "",
                "items-1-product": "",
                "items-1-quantity": "",
                "items-1-cost_price": "",
                "items-1-line_total": "",
                "items-1-DELETE": "on",
            }
        )

        self.assertTrue(formset.is_valid())
        self.assertEqual(formset.calculate_totals(), Decimal("32.00"))
