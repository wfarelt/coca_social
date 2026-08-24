from decimal import Decimal

from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.contrib.auth.models import Group, Permission, User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

from .models import Brand, Branch, CashMovement, CashShift, Category, Customer, InventoryAdjustment, Product, SaleReturn, SaleReturnItem, Supplier, Purchase, PurchaseItem, Transfer, TransferItem


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
        labels = {"name": "Nombre", "code": "Código", "address": "Dirección", "is_active": "Activa"}
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class CategoryForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "is_active"]
        labels = {"name": "Nombre", "is_active": "Activa"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class BrandForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = Brand
        fields = ["name", "is_active"]
        labels = {"name": "Nombre", "is_active": "Activa"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class SupplierForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "tax_id", "phone", "email", "address", "is_active"]
        labels = {"name": "Nombre", "tax_id": "NIT", "phone": "Teléfono", "email": "Correo", "address": "Dirección", "is_active": "Activo"}
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
        labels = {
            "name": "Nombre",
            "code": "Código",
            "barcode": "Código de barras",
            "category": "Categoría",
            "brand": "Marca",
            "unit": "Unidad",
            "purchase_price": "Precio de compra",
            "sale_price": "Precio de venta",
            "min_stock": "Stock mínimo",
            "is_active": "Activo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class CustomerForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "tax_id", "phone", "email", "credit_limit", "balance", "is_active"]
        labels = {"name": "Nombre", "tax_id": "NIT", "phone": "Teléfono", "email": "Correo", "credit_limit": "Límite de crédito", "balance": "Saldo", "is_active": "Activo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class PosCustomerForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "tax_id", "phone", "email", "credit_limit"]
        labels = {
            "name": "Nombre",
            "tax_id": "NIT",
            "phone": "Teléfono",
            "email": "Correo",
            "credit_limit": "Límite de crédito",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class PurchaseForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = Purchase
        fields = ["branch", "supplier", "folio", "status", "purchase_date", "subtotal", "tax", "total", "notes"]
        labels = {"branch": "Sucursal", "supplier": "Proveedor", "folio": "Folio", "status": "Estado", "purchase_date": "Fecha de compra", "subtotal": "Subtotal", "tax": "Impuesto", "total": "Total", "notes": "Notas"}
        widgets = {"purchase_date": forms.DateInput(attrs={"type": "date"}), "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subtotal"].required = False
        self.fields["tax"].required = False
        self.fields["total"].required = False
        self.fields["subtotal"].widget.attrs["readonly"] = True
        self.fields["tax"].widget.attrs["readonly"] = True
        self.fields["total"].widget.attrs["readonly"] = True
        self._apply_bootstrap()

    def clean(self):
        cleaned_data = super().clean()
        subtotal = cleaned_data.get("subtotal") or Decimal("0.00")
        tax = cleaned_data.get("tax") or Decimal("0.00")
        cleaned_data["subtotal"] = subtotal
        cleaned_data["total"] = subtotal + tax
        return cleaned_data


class PurchaseItemForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = PurchaseItem
        fields = ["product", "quantity", "cost_price", "line_total"]
        labels = {"product": "Producto", "quantity": "Cantidad", "cost_price": "Costo unitario", "line_total": "Total"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["line_total"].required = False
        self.fields["line_total"].widget.attrs["readonly"] = True
        self._apply_bootstrap()

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get("quantity")
        cost_price = cleaned_data.get("cost_price")
        if quantity is not None and cost_price is not None:
            cleaned_data["line_total"] = quantity * cost_price
        return cleaned_data


class PurchaseItemFormSet(BaseInlineFormSet):
    def calculate_totals(self):
        total = Decimal("0.00")
        for form in self.forms:
            if not form.is_valid() or not form.cleaned_data:
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            quantity = form.cleaned_data.get("quantity")
            cost_price = form.cleaned_data.get("cost_price")
            if quantity is not None and cost_price is not None:
                total += quantity * cost_price
        return total

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        subtotal = self.calculate_totals()
        if self.instance and hasattr(self.instance, "subtotal"):
            self.instance.subtotal = subtotal
            self.instance.total = subtotal + (self.instance.tax or Decimal("0.00"))


PurchaseItemFormSet = inlineformset_factory(Purchase, PurchaseItem, form=PurchaseItemForm, formset=PurchaseItemFormSet, extra=3, can_delete=True)


class TransferForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = Transfer
        fields = ["code", "from_branch", "to_branch", "status", "notes"]
        labels = {"code": "Código", "from_branch": "Sucursal origen", "to_branch": "Sucursal destino", "status": "Estado", "notes": "Notas"}
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class TransferItemForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = TransferItem
        fields = ["product", "requested_quantity", "received_quantity"]
        labels = {"product": "Producto", "requested_quantity": "Cantidad solicitada", "received_quantity": "Cantidad recibida"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["received_quantity"].required = False
        self._apply_bootstrap()

    def clean(self):
        cleaned_data = super().clean()
        requested_quantity = cleaned_data.get("requested_quantity")
        received_quantity = cleaned_data.get("received_quantity")
        if requested_quantity is not None and received_quantity in (None, ""):
            cleaned_data["received_quantity"] = requested_quantity
        return cleaned_data


class SaleReturnForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = SaleReturn
        fields = ["branch", "sale", "code", "reason", "status"]
        labels = {"branch": "Sucursal", "sale": "Venta", "code": "Código", "reason": "Motivo", "status": "Estado"}
        widgets = {"reason": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class SaleReturnItemForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = SaleReturnItem
        fields = ["product", "quantity", "unit_price", "line_total"]
        labels = {"product": "Producto", "quantity": "Cantidad", "unit_price": "Precio unitario", "line_total": "Total"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["line_total"].required = False
        self.fields["line_total"].widget.attrs["readonly"] = True
        self._apply_bootstrap()

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get("quantity")
        unit_price = cleaned_data.get("unit_price")
        if quantity is not None and unit_price is not None:
            cleaned_data["line_total"] = quantity * unit_price
        return cleaned_data


class CashShiftOpenForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = CashShift
        fields = ["branch", "initial_amount"]
        labels = {"branch": "Sucursal", "initial_amount": "Monto inicial"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class CashMovementForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = CashMovement
        fields = ["movement_type", "concept", "amount"]
        labels = {"movement_type": "Tipo", "concept": "Concepto", "amount": "Monto"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class CashCloseForm(AppFormMixin, forms.Form):
    counted_cash = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, label="Efectivo contado")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class InventoryAdjustmentForm(AppFormMixin, forms.ModelForm):
    class Meta:
        model = InventoryAdjustment
        fields = ["branch", "product", "reason", "previous_quantity", "new_quantity", "notes"]
        labels = {"branch": "Sucursal", "product": "Producto", "reason": "Motivo", "previous_quantity": "Cantidad anterior", "new_quantity": "Cantidad nueva", "notes": "Notas"}
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class UserAdminCreateForm(AppFormMixin, UserCreationForm):
    groups = forms.ModelMultipleChoiceField(queryset=Group.objects.all(), required=False, widget=forms.SelectMultiple)
    user_permissions = forms.ModelMultipleChoiceField(queryset=Permission.objects.select_related("content_type").all(), required=False, widget=forms.SelectMultiple)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
        ]
        labels = {
            "username": "Usuario",
            "first_name": "Nombres",
            "last_name": "Apellidos",
            "email": "Correo",
            "is_active": "Activo",
            "is_staff": "Es personal",
            "is_superuser": "Es superusuario",
            "groups": "Roles",
            "user_permissions": "Permisos",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()
        self.fields["password1"].label = "Contraseña"
        self.fields["password2"].label = "Confirmar contraseña"
        self.fields["groups"].widget.attrs["class"] = "form-select select2-no-search"
        self.fields["user_permissions"].widget.attrs["class"] = "form-select select2-no-search"


class UserAdminChangeForm(AppFormMixin, UserChangeForm):
    password = None
    groups = forms.ModelMultipleChoiceField(queryset=Group.objects.all(), required=False, widget=forms.SelectMultiple)
    user_permissions = forms.ModelMultipleChoiceField(queryset=Permission.objects.select_related("content_type").all(), required=False, widget=forms.SelectMultiple)

    class Meta(UserChangeForm.Meta):
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
        ]
        labels = {
            "username": "Usuario",
            "first_name": "Nombres",
            "last_name": "Apellidos",
            "email": "Correo",
            "is_active": "Activo",
            "is_staff": "Es personal",
            "is_superuser": "Es superusuario",
            "groups": "Roles",
            "user_permissions": "Permisos",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()
        self.fields["groups"].widget.attrs["class"] = "form-select select2-no-search"
        self.fields["user_permissions"].widget.attrs["class"] = "form-select select2-no-search"


class GroupAdminForm(AppFormMixin, forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(queryset=Permission.objects.select_related("content_type").all(), required=False, widget=forms.SelectMultiple)

    class Meta:
        model = Group
        fields = ["name", "permissions"]
        labels = {"name": "Nombre", "permissions": "Permisos"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()
        self.fields["permissions"].widget.attrs["class"] = "form-select select2-no-search"


TransferItemFormSet = inlineformset_factory(Transfer, TransferItem, form=TransferItemForm, extra=3, can_delete=True)
SaleReturnItemFormSet = inlineformset_factory(SaleReturn, SaleReturnItem, form=SaleReturnItemForm, extra=3, can_delete=True)
