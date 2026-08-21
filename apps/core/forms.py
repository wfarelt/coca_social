from django import forms

from .models import Brand, Branch, Category, Customer, Product, Supplier, Purchase, Transfer


class AppFormMixin:
    def _apply_bootstrap(self) -> None:
        for field in self.fields.values():
            widget = field.widget
            existing_class = widget.attrs.get("class", "")
            if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect)):
                widget.attrs["class"] = f"{existing_class} form-check-input".strip()
            else:
                widget.attrs["class"] = f"{existing_class} form-control".strip()


class BranchForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = Branch
        fields = ["name", "code", "address", "is_active"]
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class CategoryForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class BrandForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = Brand
        fields = ["name", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class SupplierForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "tax_id", "phone", "email", "address", "is_active"]
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class ProductForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name",
            "code",
            "barcode",
            "category",
            "brand",
            "unit",
            "purchase_price",
            "sale_price",
            "min_stock",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class CustomerForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "tax_id", "phone", "email", "credit_limit", "balance", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class PurchaseForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = Purchase
        fields = ["branch", "supplier", "folio", "status", "purchase_date", "subtotal", "tax", "total", "notes"]
        widgets = {"purchase_date": forms.DateInput(attrs={"type": "date"}), "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class TransferForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = Transfer
        fields = ["code", "from_branch", "to_branch", "status", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()
