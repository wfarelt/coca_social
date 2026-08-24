from collections import defaultdict
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Q, Sum
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse, HttpResponseBadRequest
from decimal import Decimal
from django.utils import timezone

from .context_processors import selected_branch_for_request
from .forms import (
    CashCloseForm,
    CashMovementForm,
    CashShiftOpenForm,
    BrandForm,
    BranchForm,
    CategoryForm,
    CustomerForm,
    InventoryAdjustmentForm,
    GroupAdminForm,
    SaleReturnForm,
    SaleReturnItemFormSet,
    ProductForm,
    PurchaseForm,
    PurchaseItemFormSet,
    SupplierForm,
    TransferForm,
    TransferItemFormSet,
    PosCustomerForm,
    UserAdminChangeForm,
    UserAdminCreateForm,
)
from .models import Brand, Branch, CashMovement, CashShift, Category, CreditAccount, Customer, InventoryAdjustment, KardexEntry, Product, ProductStock, Purchase, Sale, SaleItem, SaleReturn, StockMovement, Supplier, Transfer


def _module_context(title, subtitle, actions, stats=None, rows=None):
    return {
        "module_title": title,
        "module_subtitle": subtitle,
        "module_actions": actions,
        "module_stats": stats or [],
        "module_rows": rows or [],
    }


def dashboard(request):
    branch = selected_branch_for_request(request)
    today = timezone.localdate()
    week_start = today - timedelta(days=6)

    sales_qs = Sale.objects.select_related("branch", "customer").prefetch_related("items__product").filter(sold_at__date__gte=week_start)
    if branch is not None:
        sales_qs = sales_qs.filter(branch=branch)

    today_sales = sales_qs.filter(sold_at__date=today)
    today_sales_total = sum((sale.total for sale in today_sales), Decimal("0.00"))
    today_sales_count = today_sales.count()
    today_cost = Decimal("0.00")
    today_revenue = Decimal("0.00")
    for sale in today_sales:
        today_revenue += sale.total
        for item in sale.items.all():
            today_cost += item.quantity * item.product.purchase_price

    utility = today_revenue - today_cost
    low_stock_qs = ProductStock.objects.select_related("branch", "product").filter(quantity__gt=0, quantity__lte=F("product__min_stock"))
    out_stock_qs = ProductStock.objects.select_related("branch", "product").filter(quantity__lte=0)
    if branch is not None:
        low_stock_qs = low_stock_qs.filter(branch=branch)
        out_stock_qs = out_stock_qs.filter(branch=branch)

    recent_sales = [
        {
            "folio": sale.folio,
            "customer": sale.customer.name if sale.customer else "Consumidor final",
            "amount": f"Bs {sale.total}",
            "status": sale.get_status_display(),
        }
        for sale in sales_qs.order_by("-sold_at", "-created_at")[:5]
    ]
    if not recent_sales:
        recent_sales = [{"folio": "Sin ventas", "customer": "-", "amount": "Bs 0", "status": "Pendiente"}]

    low_stock = [
        {
            "product": stock.product.name,
            "branch": stock.branch.name,
            "stock": str(stock.quantity),
            "state": "Agotado" if stock.quantity <= 0 else "Bajo",
        }
        for stock in low_stock_qs.order_by("product__name")[:5]
    ]
    if not low_stock:
        low_stock = [{"product": "Sin alertas", "branch": branch.name if branch else "-", "stock": "0", "state": "Normal"}]

    pending_transfers = [
        {
            "code": transfer.code,
            "from": transfer.from_branch.name,
            "to": transfer.to_branch.name,
            "state": transfer.get_status_display(),
        }
        for transfer in Transfer.objects.select_related("from_branch", "to_branch").filter(status__in=[Transfer.Status.DRAFT, Transfer.Status.SENT]).order_by("-created_at")[:5]
    ]
    if not pending_transfers:
        pending_transfers = [{"code": "Sin pendientes", "from": "-", "to": "-", "state": "OK"}]

    top_product_map = defaultdict(lambda: {"qty": Decimal("0.00"), "revenue": Decimal("0.00")})
    for sale in sales_qs:
        for item in sale.items.select_related("product"):
            bucket = top_product_map[item.product_id]
            bucket["qty"] += item.quantity
            bucket["revenue"] += item.line_total
    top_products = []
    for product in Product.objects.filter(pk__in=top_product_map.keys()).order_by("name"):
        bucket = top_product_map[product.pk]
        top_products.append({"name": product.name, "qty": bucket["qty"], "revenue": bucket["revenue"]})
    top_products = sorted(top_products, key=lambda row: row["qty"], reverse=True)[:5]
    if not top_products:
        top_products = [{"name": "Sin ventas", "qty": Decimal("0.00"), "revenue": Decimal("0.00") }]

    weekly_sales_map = {today - timedelta(days=offset): Decimal("0.00") for offset in range(6, -1, -1)}
    for sale in sales_qs:
        sale_day = sale.sold_at.date()
        weekly_sales_map[sale_day] = weekly_sales_map.get(sale_day, Decimal("0.00")) + sale.total
    weekly_sales = []
    max_weekly_sales = max(weekly_sales_map.values(), default=Decimal("1.00"))
    for day, amount in weekly_sales_map.items():
        weekly_sales.append({"label": day.strftime("%a"), "value": amount, "height": int((amount / max_weekly_sales) * 100) if max_weekly_sales > 0 else 0})

    open_shift = None
    if branch is not None:
        open_shift = CashShift.objects.select_related("user", "branch").filter(branch=branch, status=CashShift.Status.OPEN).order_by("-opened_at").first()
    if open_shift is None:
        open_shift = CashShift.objects.select_related("user", "branch").filter(status=CashShift.Status.OPEN).order_by("-opened_at").first()

    cash_income = Decimal("0.00")
    cash_expense = Decimal("0.00")
    if open_shift is not None:
        cash_income = open_shift.movements.filter(movement_type=CashMovement.Type.INCOME).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        cash_expense = open_shift.movements.filter(movement_type=CashMovement.Type.EXPENSE).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    credits_qs = CreditAccount.objects.filter(status__in=[CreditAccount.Status.OPEN, CreditAccount.Status.PARTIAL, CreditAccount.Status.OVERDUE])
    pending_credits_total = credits_qs.aggregate(total=Sum("remaining_balance"))["total"] or Decimal("0.00")

    context = {
        "branches": list(Branch.objects.filter(is_active=True).values_list("name", flat=True)) or ["Sucursal Centro"],
        "active_branch": branch.name if branch else "Sucursal Centro",
        "kpis": [
            {"label": "Ventas de hoy", "value": f"Bs {today_sales_total}", "delta": f"{today_sales_count} tickets", "tone": "success"},
            {"label": "Utilidad", "value": f"Bs {utility}", "delta": "Estimado bruto", "tone": "primary"},
            {"label": "Stock bajo", "value": str(low_stock_qs.count()), "delta": f"{out_stock_qs.count()} agotados", "tone": "warning"},
            {"label": "Créditos pendientes", "value": f"Bs {pending_credits_total}", "delta": f"{credits_qs.count()} clientes", "tone": "danger"},
        ],
        "weekly_sales": weekly_sales,
        "cash_summary": {
            "branch": branch.name if branch else "-",
            "shift_user": open_shift.user.username if open_shift and open_shift.user else "-",
            "status": open_shift.get_status_display() if open_shift else "Cerrada",
            "income": cash_income,
            "expense": cash_expense,
            "expected": open_shift.expected_cash if open_shift else Decimal("0.00"),
            "counted": open_shift.counted_cash if open_shift else Decimal("0.00"),
            "difference": open_shift.difference if open_shift else Decimal("0.00"),
        },
        "low_stock": low_stock,
        "recent_sales": recent_sales,
        "transfers": pending_transfers,
        "top_products": top_products,
    }
    return render(request, "core/dashboard.html", context)


def pos(request):
    cart_context = _cart_context(request)
    selected_customer_id = request.GET.get("customer")
    try:
        selected_customer_id = int(selected_customer_id) if selected_customer_id else None
    except (TypeError, ValueError):
        selected_customer_id = None
    customer_form = PosCustomerForm()
    context = {
        "customers": Customer.objects.filter(is_active=True).order_by("name")[:20],
        "quick_products": Product.objects.select_related("category", "brand").prefetch_related("stocks").filter(is_active=True).order_by("name")[:8],
        "customer_form": customer_form,
        "form": customer_form,
        "selected_customer_id": selected_customer_id,
        **cart_context,
    }
    return render(request, "core/pos/index.html", context)


def pos_checkout(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")
    cart = request.session.get("pos_cart", {})
    if not cart:
        return redirect("pos")

    branch = Branch.objects.filter(is_active=True).order_by("name").first()
    if branch is None:
        return HttpResponseBadRequest("No hay sucursales activas")

    customer_id = request.POST.get("customer") or None
    payment_method = request.POST.get("payment_method", Sale.PaymentMethod.CASH)
    cash_received = Decimal(request.POST.get("cash_received") or "0")
    due_date_value = request.POST.get("due_date") or None
    if payment_method == Sale.PaymentMethod.CREDIT and not customer_id:
        return HttpResponseBadRequest("El crédito requiere un cliente")
    customer = Customer.objects.filter(pk=customer_id).first() if customer_id else None
    due_date = date.fromisoformat(due_date_value) if due_date_value else None
    sale_status = Sale.Status.CREDIT if payment_method == Sale.PaymentMethod.CREDIT else Sale.Status.PAID

    with transaction.atomic():
        sale = Sale.objects.create(
            branch=branch,
            cashier=_system_user(),
            customer=customer,
            folio=f"V-{Sale.objects.count() + 1000}",
            status=sale_status,
            payment_method=payment_method,
            cash_received=cash_received if payment_method != Sale.PaymentMethod.CREDIT else Decimal("0.00"),
            change_due=Decimal("0.00"),
        )
        subtotal = Decimal("0.00")
        for product in Product.objects.filter(pk__in=[int(product_id) for product_id in cart.keys()]).order_by("name"):
            quantity = Decimal(cart.get(str(product.pk), 0))
            if quantity <= 0:
                continue
            item = SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=quantity,
                unit_price=product.sale_price,
                discount=Decimal("0.00"),
                line_total=Decimal("0.00"),
            )
            subtotal += item.line_total
        sale.subtotal = subtotal
        sale.total = subtotal
        if payment_method != Sale.PaymentMethod.CREDIT:
            sale.change_due = max(cash_received - sale.total, Decimal("0.00"))
        sale.save(update_fields=["subtotal", "total", "change_due", "cash_received", "updated_at"])
        sale.post_to_inventory(_system_user())
        if payment_method == Sale.PaymentMethod.CREDIT:
            sale.post_credit(_system_user(), due_date=due_date)
        else:
            sale.post_payment(_system_user(), amount=sale.total)
            cash_amount = sale.cash_received if sale.cash_received > 0 else sale.total
            if payment_method == Sale.PaymentMethod.CASH and cash_amount > 0:
                shift = _active_cash_shift(branch)
                if shift is not None:
                    CashMovement.objects.create(
                        shift=shift,
                        movement_type=CashMovement.Type.INCOME,
                        concept=f"Venta {sale.folio}",
                        amount=cash_amount,
                        created_by=_system_user(),
                    )
                    shift.expected_cash = shift.expected_cash + cash_amount
                    shift.save(update_fields=["expected_cash", "updated_at"])

    request.session.pop("pos_cart", None)
    request.session.modified = True
    return redirect("pos")


def pos_search(request):
    query = request.GET.get("q", "").strip()
    products = Product.objects.select_related("category").prefetch_related("stocks").filter(is_active=True)
    if query:
        products = products.filter(Q(name__icontains=query) | Q(code__icontains=query) | Q(barcode__icontains=query))
    products = products.order_by("name")[:12]
    quick_products = Product.objects.select_related("category", "brand").prefetch_related("stocks").filter(is_active=True).order_by("name")[:8]
    return render(request, "core/partials/pos_product_results.html", {"products": products, "quick_products": quick_products, "query": query})


def pos_customer_create(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")
    form = PosCustomerForm(request.POST)
    if not form.is_valid():
        return render(request, "core/partials/pos_customer_form.html", {"form": form})
    customer = form.save(commit=False)
    customer.balance = Decimal("0.00")
    customer.is_active = True
    customer.save()
    redirect_url = f"{reverse('pos')}?customer={customer.pk}"
    response = HttpResponse(status=204)
    response.headers["HX-Redirect"] = redirect_url
    return response


def pos_add_item(request, pk):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")
    product = get_object_or_404(Product, pk=pk, is_active=True)
    cart = request.session.get("pos_cart", {})
    key = str(product.pk)
    cart[key] = cart.get(key, 0) + 1
    request.session["pos_cart"] = cart
    request.session.modified = True
    return render(request, "core/partials/pos_cart_panel.html", _cart_context(request))


def pos_update_item(request, pk):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")
    action = request.POST.get("action")
    cart = request.session.get("pos_cart", {})
    key = str(pk)
    quantity = int(cart.get(key, 0))
    if action == "increase":
        quantity += 1
    elif action == "decrease":
        quantity = max(0, quantity - 1)
    elif action == "remove":
        quantity = 0
    if quantity <= 0:
        cart.pop(key, None)
    else:
        cart[key] = quantity
    request.session["pos_cart"] = cart
    request.session.modified = True
    return render(request, "core/partials/pos_cart_panel.html", _cart_context(request))


def pos_clear_cart(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")
    request.session.pop("pos_cart", None)
    request.session.modified = True
    return render(request, "core/partials/pos_cart_panel.html", _cart_context(request))


def _cart_context(request):
    cart = request.session.get("pos_cart", {})
    product_ids = [int(product_id) for product_id in cart.keys()]
    products = Product.objects.filter(pk__in=product_ids).order_by("name")
    items = []
    subtotal = Decimal("0.00")
    for product in products:
        quantity = int(cart.get(str(product.pk), 0))
        line_total = product.sale_price * quantity
        subtotal += line_total
        items.append({
            "id": product.pk,
            "name": product.name,
            "qty": quantity,
            "price": product.sale_price,
            "subtotal": line_total,
        })
    return {
        "cart": items,
        "subtotal": subtotal,
        "discount": Decimal("0.00"),
        "total": subtotal,
    }


def sales_overview(request):
    return redirect("sales_list")


def sales_list(request):
    rows = []
    sales = Sale.objects.select_related("branch", "cashier", "customer").order_by("-sold_at", "-created_at")
    for sale in sales:
        rows.append(
            {
                "cells": [sale.folio, sale.branch.name, sale.customer.name if sale.customer else "Consumidor final", sale.total, sale.get_status_display()],
                "edit_url": reverse("sale_detail", args=[sale.pk]),
                "delete_url": f"/ventas/{sale.pk}/anular/",
            }
        )
    return render(
        request,
        "core/document/list.html",
        {
            "page_title": "Ventas realizadas",
            "page_subtitle": "Historial de tickets y cobros",
            "stats": [{"label": "Ventas hoy", "value": Sale.objects.count()}, {"label": "Crédito", "value": Sale.objects.filter(status=Sale.Status.CREDIT).count()}],
            "actions": [{"label": "Punto de venta", "url": "/pos/"}],
            "headers": ["Folio", "Sucursal", "Cliente", "Total", "Estado"],
            "rows": rows,
        },
    )


def sale_detail(request, pk):
    sale = get_object_or_404(Sale.objects.select_related("branch", "cashier", "customer").prefetch_related("items__product"), pk=pk)
    return render(
        request,
        "core/sales/detail.html",
        {
            "sale": sale,
            "page_title": sale.folio,
            "page_subtitle": f"{sale.branch.name} · {sale.get_status_display()}",
        },
    )


def sale_cancel(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    if request.method == "POST":
        sale.status = Sale.Status.CANCELED
        sale.save(update_fields=["status", "updated_at"])
        return redirect("sales_list")
    return render(
        request,
        "core/document/delete.html",
        {
            "object": sale,
            "page_title": "Anular venta",
            "page_subtitle": sale.folio,
            "list_url": "/ventas/listado/",
        },
    )


def _active_cash_shift(branch):
    return CashShift.objects.filter(branch=branch, status=CashShift.Status.OPEN).order_by("-opened_at").first()


def sales_returns(request):
    returns = SaleReturn.objects.select_related("branch", "sale", "created_by").order_by("-created_at")
    rows = [
        {
            "pk": sale_return.pk,
            "a": sale_return.code,
            "b": sale_return.sale.folio,
            "c": f"Bs {sale_return.total}",
            "d": sale_return.get_status_display(),
        }
        for sale_return in returns
    ]
    return render(
        request,
        "core/document/list.html",
        {
            "page_title": "Devoluciones",
            "page_subtitle": "Control de notas de devolución y ajustes",
            "stats": [
                {"label": "Devoluciones", "value": str(returns.count())},
                {"label": "Monto", "value": f"Bs {returns.aggregate(total=Sum('total'))['total'] or 0}"},
            ],
            "actions": [{"label": "Registrar devolución", "url": "/ventas/devoluciones/nueva/"}],
            "headers": ["Código", "Venta", "Monto", "Estado"],
            "rows": [{"cells": [row["a"], row["b"], row["c"], row["d"]], "edit_url": f"/ventas/devoluciones/{row['pk']}/editar/", "delete_url": f"/ventas/devoluciones/{row['pk']}/eliminar/"} for row in rows],
        },
    )


def sale_return_create(request):
    form = SaleReturnForm(request.POST or None)
    formset = SaleReturnItemFormSet(request.POST or None)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            sale_return = form.save(commit=False)
            sale_return.created_by = request.user if request.user.is_authenticated else _system_user()
            sale_return.save()
            formset.instance = sale_return
            formset.save()
            sale_return.post_to_inventory(request.user if request.user.is_authenticated else _system_user())
        return redirect("sales_returns")
    return render(
        request,
        "core/document/items_form.html",
        {
            "form": form,
            "formset": formset,
            "page_title": "Nueva devolución",
            "page_subtitle": "Registra mercancía devuelta y ajusta inventario",
            "list_url": "/ventas/devoluciones/",
            "items_title": "Líneas de devolución",
            "items_subtitle": "Captura los productos devueltos y sus cantidades.",
            "item_headers": ["Producto", "Cantidad", "Precio unitario", "Total"],
        },
    )


def sale_return_edit(request, pk):
    sale_return = get_object_or_404(SaleReturn, pk=pk)
    form = SaleReturnForm(request.POST or None, instance=sale_return)
    formset = SaleReturnItemFormSet(request.POST or None, instance=sale_return)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            if sale_return.posted_at:
                sale_return.reverse_inventory(request.user if request.user.is_authenticated else _system_user())
            sale_return = form.save(commit=False)
            sale_return.status = SaleReturn.Status.DRAFT
            sale_return.posted_at = None
            sale_return.save()
            formset.save()
            sale_return.post_to_inventory(request.user if request.user.is_authenticated else _system_user())
        return redirect("sales_returns")
    return render(
        request,
        "core/document/items_form.html",
        {
            "form": form,
            "formset": formset,
            "page_title": "Editar devolución",
            "page_subtitle": sale_return.code,
            "list_url": "/ventas/devoluciones/",
            "items_title": "Líneas de devolución",
            "items_subtitle": "Corrige productos y cantidades.",
            "item_headers": ["Producto", "Cantidad", "Precio unitario", "Total"],
        },
    )


def sale_return_delete(request, pk):
    sale_return = get_object_or_404(SaleReturn, pk=pk)
    if request.method == "POST":
        if sale_return.posted_at:
            sale_return.reverse_inventory(request.user if request.user.is_authenticated else _system_user())
        sale_return.delete()
        return redirect("sales_returns")
    return render(request, "core/document/delete.html", {"object": sale_return, "page_title": "Eliminar devolución", "page_subtitle": sale_return.code, "list_url": "/ventas/devoluciones/"})


def inventory_overview(request):
    branch = selected_branch_for_request(request)
    stock_qs = ProductStock.objects.select_related("branch", "product").order_by("product__name")
    if branch is not None:
        stock_qs = stock_qs.filter(branch=branch)
    low_stock_count = stock_qs.filter(quantity__gt=0, quantity__lte=F("product__min_stock")).count()
    out_stock_count = stock_qs.filter(quantity__lte=0).count()
    recent_adjustments = InventoryAdjustment.objects.select_related("branch", "product", "created_by").order_by("-created_at")
    if branch is not None:
        recent_adjustments = recent_adjustments.filter(branch=branch)
    recent_adjustments = recent_adjustments[:5]
    recent_movements = StockMovement.objects.select_related("branch", "product", "created_by").order_by("-created_at")
    if branch is not None:
        recent_movements = recent_movements.filter(branch=branch)
    recent_movements = recent_movements[:5]
    return render(
        request,
        "core/inventory/overview.html",
        {
            "branch": branch,
            "stats": [
                {"label": "Productos en stock", "value": str(stock_qs.count())},
                {"label": "Bajo stock", "value": str(low_stock_count)},
                {"label": "Agotados", "value": str(out_stock_count)},
                {"label": "Ajustes aplicados", "value": str(InventoryAdjustment.objects.filter(applied_at__isnull=False).count())},
            ],
            "stock_rows": [
                {
                    "name": stock.product.name,
                    "code": stock.product.code,
                    "quantity": stock.quantity,
                    "available": stock.available_quantity,
                    "status": "Agotado" if stock.quantity <= 0 else ("Bajo" if stock.quantity <= stock.product.min_stock else "Normal"),
                    "branch": stock.branch.name,
                }
                for stock in stock_qs[:10]
            ],
            "adjustment_rows": [
                {
                    "code": f"AJ-{adjustment.pk}",
                    "reason": adjustment.get_reason_display(),
                    "product": adjustment.product.name,
                    "change": f"{adjustment.previous_quantity} → {adjustment.new_quantity}",
                    "status": "Aplicado" if adjustment.applied_at else "Borrador",
                }
                for adjustment in recent_adjustments
            ],
            "movement_rows": [
                {
                    "reference": movement.reference or "-",
                    "product": movement.product.name,
                    "type": movement.get_movement_type_display(),
                    "quantity": movement.quantity,
                    "branch": movement.branch.name,
                }
                for movement in recent_movements
            ],
        },
    )


def products(request):
    return render(request, "core/inventory/module.html", _module_context("Productos", "Alta, edición y control de artículos", ["Nuevo producto", "Importar"], [{"label": "Activos", "value": "1,201"}], [{"a": "Arroz 1 kg", "b": "ARZ-001", "c": "Bs 18 / Bs 26", "d": "Activo"}]))


def categories(request):
    return render(request, "core/inventory/module.html", _module_context("Categorías", "Estructura comercial por familias", ["Nueva categoría"], [{"label": "Categorías", "value": "38"}], [{"a": "Abarrotes", "b": "142 productos", "c": "Principal", "d": "Activa"}]))


def brands(request):
    return render(request, "core/inventory/module.html", _module_context("Marcas", "Fabricantes y marcas registradas", ["Nueva marca"], [{"label": "Marcas", "value": "52"}], [{"a": "Bimbo", "b": "Panificación", "c": "Alta", "d": "Activa"}]))


def stock_by_branch(request):
    branch = selected_branch_for_request(request)
    stock_qs = ProductStock.objects.select_related("branch", "product").order_by("product__name")
    if branch is not None:
        stock_qs = stock_qs.filter(branch=branch)
    rows = [
        {
            "cells": [
                stock.product.name,
                stock.product.code,
                stock.quantity,
                stock.reserved_quantity,
                stock.available_quantity,
                    "Agotado" if stock.quantity <= 0 else ("Bajo" if stock.quantity <= stock.product.min_stock else "Normal"),
            ],
            "edit_url": "#",
            "delete_url": "#",
        }
        for stock in stock_qs
    ]
    return render(
        request,
        "core/inventory/stock.html",
        {
            "branch": branch,
            "page_title": "Stock por sucursal",
            "page_subtitle": "Disponibilidad, reservado y disponible por producto",
            "stats": [
                {"label": "Productos", "value": str(stock_qs.count())},
                {"label": "Bajo stock", "value": str(stock_qs.filter(quantity__gt=0, quantity__lte=F("product__min_stock")).count())},
                {"label": "Agotados", "value": str(stock_qs.filter(quantity__lte=0).count())},
            ],
            "headers": ["Producto", "Código", "Cantidad", "Reservado", "Disponible", "Estado"],
            "rows": rows,
        },
    )


def kardex(request):
    branch = selected_branch_for_request(request)
    entries = KardexEntry.objects.select_related("branch", "product", "created_by").order_by("-created_at")
    if branch is not None:
        entries = entries.filter(branch=branch)
    rows = [
        {
            "cells": [entry.reference, entry.product.name, entry.movement_type, entry.quantity_in, entry.quantity_out, entry.balance, entry.unit_cost],
            "edit_url": "#",
            "delete_url": "#",
        }
        for entry in entries[:20]
    ]
    return render(
        request,
        "core/inventory/kardex.html",
        {
            "branch": branch,
            "page_title": "Kardex",
            "page_subtitle": "Entradas, salidas y saldo acumulado",
            "stats": [
                {"label": "Movimientos", "value": str(entries.count())},
                {"label": "Entradas", "value": str(entries.filter(quantity_in__gt=0).count())},
                {"label": "Salidas", "value": str(entries.filter(quantity_out__gt=0).count())},
            ],
            "headers": ["Referencia", "Producto", "Tipo", "Entrada", "Salida", "Saldo", "Costo unitario"],
            "rows": rows,
        },
    )


def inventory_adjustments(request):
    adjustments = InventoryAdjustment.objects.select_related("branch", "product", "created_by").order_by("-created_at")
    rows = [
        {
            "pk": adjustment.pk,
            "a": f"AJ-{adjustment.pk}" if adjustment.pk else "AJ",
            "b": adjustment.get_reason_display(),
            "c": f"{adjustment.previous_quantity} → {adjustment.new_quantity}",
            "d": "Aplicado" if adjustment.applied_at else "Borrador",
        }
        for adjustment in adjustments
    ]
    return render(
        request,
        "core/inventory/adjustments_list.html",
        {
            "page_title": "Ajustes de inventario",
            "page_subtitle": "Conteos, mermas y correcciones",
            "stats": [
                {"label": "Ajustes", "value": str(adjustments.count())},
                {"label": "Aplicados", "value": str(adjustments.filter(applied_at__isnull=False).count())},
            ],
            "actions": [{"label": "Nuevo ajuste", "url": "/inventario/ajustes/nuevo/"}],
            "headers": ["Código", "Motivo", "Cantidad", "Estado"],
            "rows": [{"cells": [row["a"], row["b"], row["c"], row["d"]], "edit_url": f"/inventario/ajustes/{row['pk']}/editar/", "delete_url": f"/inventario/ajustes/{row['pk']}/eliminar/"} for row in rows],
        },
    )


def inventory_adjustment_create(request):
    form = InventoryAdjustmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            adjustment = form.save(commit=False)
            adjustment.created_by = request.user if request.user.is_authenticated else _system_user()
            adjustment.save()
            adjustment.apply_to_inventory(request.user if request.user.is_authenticated else _system_user())
        return redirect("inventory_adjustments")
    return render(
        request,
        "core/inventory/adjustment_form.html",
        {
            "form": form,
            "page_title": "Nuevo ajuste",
            "page_subtitle": "Conteo, merma o corrección de stock",
            "list_url": "/inventario/ajustes/",
        },
    )


def inventory_adjustment_edit(request, pk):
    adjustment = get_object_or_404(InventoryAdjustment, pk=pk)
    form = InventoryAdjustmentForm(request.POST or None, instance=adjustment)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            if adjustment.applied_at:
                adjustment.reverse_inventory(request.user if request.user.is_authenticated else _system_user())
            adjustment = form.save(commit=False)
            adjustment.created_by = adjustment.created_by or (request.user if request.user.is_authenticated else _system_user())
            adjustment.save()
            adjustment.apply_to_inventory(request.user if request.user.is_authenticated else _system_user())
        return redirect("inventory_adjustments")
    return render(
        request,
        "core/inventory/adjustment_form.html",
        {
            "form": form,
            "page_title": "Editar ajuste",
            "page_subtitle": f"AJ-{adjustment.pk}",
            "list_url": "/inventario/ajustes/",
        },
    )


def inventory_adjustment_delete(request, pk):
    adjustment = get_object_or_404(InventoryAdjustment, pk=pk)
    if request.method == "POST":
        if adjustment.applied_at:
            adjustment.reverse_inventory(request.user if request.user.is_authenticated else _system_user())
        adjustment.delete()
        return redirect("inventory_adjustments")
    return render(
        request,
        "core/inventory/adjustment_delete.html",
        {
            "object": adjustment,
            "page_title": "Eliminar ajuste",
            "page_subtitle": f"AJ-{adjustment.pk}",
            "list_url": "/inventario/ajustes/",
        },
    )


def purchases_overview(request):
    return render(request, "core/purchases/module.html", _module_context("Compras", "Órdenes, entradas y proveedores", ["Listado", "Nueva compra", "Proveedores"], [{"label": "Compras mes", "value": "Bs 184,900"}], [{"a": "C-1209", "b": "Distribuidora XYZ", "c": "Bs 18,240", "d": "Registrada"}]))


def new_purchase(request):
    return render(request, "core/purchases/module.html", _module_context("Nueva compra", "Captura rápida por producto o proveedor", ["Guardar borrador", "Registrar"], [{"label": "Líneas", "value": "0"}], []))


def suppliers(request):
    return render(request, "core/purchases/module.html", _module_context("Proveedores", "Catálogo de abastecedores", ["Nuevo proveedor"], [{"label": "Proveedores", "value": "24"}], [{"a": "Distribuidora XYZ", "b": "Activo", "c": "555-1234", "d": "Norte"}]))


def _system_user():
    user_model = get_user_model()
    user, _ = user_model.objects.get_or_create(username="system", defaults={"is_active": True})
    return user


def purchases_list(request):
    rows = []
    for purchase in Purchase.objects.select_related("branch", "supplier").order_by("-purchase_date", "-created_at"):
        rows.append(
            {
                "cells": [purchase.folio, purchase.branch.name, purchase.supplier.name, purchase.purchase_date, purchase.total, purchase.get_status_display()],
                "edit_url": f"/compras/{purchase.pk}/editar/",
                "delete_url": f"/compras/{purchase.pk}/eliminar/",
            }
        )
    return render(
        request,
        "core/document/list.html",
        {
            "page_title": "Compras",
            "page_subtitle": "Registro de compras y entradas de mercancía",
            "stats": [{"label": "Compras", "value": Purchase.objects.count()}, {"label": "Registradas", "value": Purchase.objects.filter(status=Purchase.Status.POSTED).count()}],
            "actions": [{"label": "Nueva compra", "url": "/compras/nueva/"}, {"label": "Proveedores", "url": "/catalogos/proveedores/"}],
            "headers": ["Folio", "Sucursal", "Proveedor", "Fecha", "Total", "Estado"],
            "rows": rows,
        },
    )


def purchase_create(request):
    form = PurchaseForm(request.POST or None)
    formset = PurchaseItemFormSet(request.POST or None)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            purchase = form.save()
            formset.instance = purchase
            formset.save()
            if purchase.status == Purchase.Status.POSTED:
                purchase.post_to_inventory(_system_user())
        return redirect("purchases_list")
    return render(
        request,
        "core/document/items_form.html",
        {
            "form": form,
            "formset": formset,
            "page_title": "Nueva compra",
            "page_subtitle": "Alta de compra con líneas de producto",
            "list_url": "/compras/",
            "items_title": "Líneas de compra",
            "items_subtitle": "Agrega productos, cantidades y costos unitarios.",
            "item_headers": ["Producto", "Cantidad", "Costo unitario", "Total"],
        },
    )


def purchase_edit(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    form = PurchaseForm(request.POST or None, instance=purchase)
    formset = PurchaseItemFormSet(request.POST or None, instance=purchase)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            purchase = form.save()
            formset.save()
            if purchase.status == Purchase.Status.POSTED:
                purchase.post_to_inventory(_system_user())
        return redirect("purchases_list")
    return render(
        request,
        "core/document/items_form.html",
        {
            "form": form,
            "formset": formset,
            "page_title": "Editar compra",
            "page_subtitle": purchase.folio,
            "list_url": "/compras/",
            "items_title": "Líneas de compra",
            "items_subtitle": "Edita productos, cantidades y costos.",
            "item_headers": ["Producto", "Cantidad", "Costo unitario", "Total"],
        },
    )


def purchase_delete(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    if request.method == "POST":
        purchase.delete()
        return redirect("purchases_list")
    return render(request, "core/document/delete.html", {"object": purchase, "page_title": "Eliminar compra", "page_subtitle": purchase.folio, "list_url": "/compras/"})


def transfers_list(request):
    rows = []
    for transfer in Transfer.objects.select_related("from_branch", "to_branch").order_by("-created_at"):
        rows.append(
            {
                "cells": [transfer.code, transfer.from_branch.name, transfer.to_branch.name, transfer.get_status_display(), transfer.sent_at or "-"],
                "edit_url": f"/traspasos/{transfer.pk}/editar/",
                "delete_url": f"/traspasos/{transfer.pk}/eliminar/",
            }
        )
    return render(
        request,
        "core/document/list.html",
        {
            "page_title": "Traspasos",
            "page_subtitle": "Envíos entre sucursales y control de estado",
            "stats": [{"label": "Traspasos", "value": Transfer.objects.count()}, {"label": "Pendientes", "value": Transfer.objects.filter(status=Transfer.Status.DRAFT).count()}],
            "actions": [{"label": "Nuevo traspaso", "url": "/traspasos/nuevo/"}],
            "headers": ["Código", "Origen", "Destino", "Estado", "Enviado"],
            "rows": rows,
        },
    )


def transfer_create(request):
    form = TransferForm(request.POST or None)
    formset = TransferItemFormSet(request.POST or None)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            transfer = form.save(commit=False)
            transfer.created_by = _system_user()
            transfer.save()
            formset.instance = transfer
            formset.save()
            if transfer.status == Transfer.Status.SENT:
                transfer.send_to_inventory(_system_user())
            elif transfer.status == Transfer.Status.RECEIVED:
                transfer.send_to_inventory(_system_user())
                transfer.receive_to_inventory(_system_user())
        return redirect("transfers_list")
    return render(
        request,
        "core/document/items_form.html",
        {
            "form": form,
            "formset": formset,
            "page_title": "Nuevo traspaso",
            "page_subtitle": "Crea un envío entre sucursales",
            "list_url": "/traspasos/",
            "items_title": "Líneas de traspaso",
            "items_subtitle": "Define los productos enviados y las cantidades recibidas si aplica.",
            "item_headers": ["Producto", "Solicitado", "Recibido"],
        },
    )


def transfer_edit(request, pk):
    transfer = get_object_or_404(Transfer, pk=pk)
    form = TransferForm(request.POST or None, instance=transfer)
    formset = TransferItemFormSet(request.POST or None, instance=transfer)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            obj = form.save(commit=False)
            if not obj.created_by_id:
                obj.created_by = transfer.created_by or _system_user()
            obj.save()
            formset.save()
            if obj.status == Transfer.Status.SENT:
                obj.send_to_inventory(_system_user())
            elif obj.status == Transfer.Status.RECEIVED:
                obj.send_to_inventory(_system_user())
                obj.receive_to_inventory(_system_user())
        return redirect("transfers_list")
    return render(
        request,
        "core/document/items_form.html",
        {
            "form": form,
            "formset": formset,
            "page_title": "Editar traspaso",
            "page_subtitle": transfer.code,
            "list_url": "/traspasos/",
            "items_title": "Líneas de traspaso",
            "items_subtitle": "Ajusta los productos y confirma recepciones parciales.",
            "item_headers": ["Producto", "Solicitado", "Recibido"],
        },
    )


def transfer_delete(request, pk):
    transfer = get_object_or_404(Transfer, pk=pk)
    if request.method == "POST":
        transfer.delete()
        return redirect("transfers_list")
    return render(request, "core/document/delete.html", {"object": transfer, "page_title": "Eliminar traspaso", "page_subtitle": transfer.code, "list_url": "/traspasos/"})


def transfers_overview(request):
    return render(request, "core/transfers/module.html", _module_context("Traspasos", "Flujo entre sucursales y recepción parcial", ["Listado", "Nuevo traspaso"], [{"label": "Pendientes", "value": "7"}], [{"a": "TR-204", "b": "Centro → Norte", "c": "120 uds", "d": "Pendiente"}]))


def new_transfer(request):
    return render(request, "core/transfers/module.html", _module_context("Nuevo traspaso", "Sucursal origen, productos, cantidades y destino", ["Enviar"], [{"label": "Estado", "value": "Borrador"}], []))


def sent_transfers(request):
    return render(request, "core/transfers/module.html", _module_context("Traspasos enviados", "Despachos en tránsito", ["Ver pendientes"], [{"label": "Enviados", "value": "5"}], [{"a": "TR-203", "b": "Oriente → Centro", "c": "48 uds", "d": "Enviado"}]))


def received_transfers(request):
    return render(request, "core/transfers/module.html", _module_context("Traspasos recibidos", "Recepciones confirmadas", ["Validar recepción"], [{"label": "Recibidos", "value": "11"}], [{"a": "TR-198", "b": "Norte → Centro", "c": "50 uds", "d": "Recibido"}]))


def pending_transfers(request):
    return render(request, "core/transfers/module.html", _module_context("Traspasos pendientes", "Confirmación de cantidades recibidas", ["Recepcionar"], [{"label": "Pendientes", "value": "7"}], [{"a": "TR-204", "b": "Centro → Norte", "c": "120 uds", "d": "Pendiente"}]))


def customers_overview(request):
    return render(request, "core/clients/module.html", _module_context("Clientes", "Catálogo de clientes y consumo", ["Nuevo cliente"], [{"label": "Clientes", "value": "486"}], [{"a": "Tienda López", "b": "Activo", "c": "Bs 2,100", "d": "Crédito"}]))


def credits_overview(request):
    return render(request, "core/credits/module.html", _module_context("Créditos / Fiados", "Saldo, vencimientos y cartera", ["Cobrar"], [{"label": "Pendientes", "value": "Bs 9,240"}], [{"a": "Tienda López", "b": "Bs 860", "c": "15 días", "d": "Vencido"}]))


def collections_overview(request):
    return render(request, "core/credits/module.html", _module_context("Cobros", "Aplicación de pagos y abonos", ["Registrar cobro"], [{"label": "Cobros hoy", "value": "Bs 3,200"}], [{"a": "CO-112", "b": "Tienda López", "c": "Bs 860", "d": "Aplicado"}]))


def cash_overview(request):
    branch = selected_branch_for_request(request)
    open_shift = _active_cash_shift(branch) if branch else None
    if open_shift is None:
        open_shift = CashShift.objects.select_related("branch", "user").filter(status=CashShift.Status.OPEN).order_by("-opened_at").first()

    if branch is not None:
        shifts = CashShift.objects.select_related("branch", "user").filter(branch=branch).order_by("-opened_at")[:8]
    else:
        shifts = CashShift.objects.select_related("branch", "user").order_by("-opened_at")[:8]

    movements = open_shift.movements.select_related("created_by").order_by("-created_at")[:8] if open_shift else []
    return render(
        request,
        "core/cash/overview.html",
        {
            "branch": branch,
            "open_shift": open_shift,
            "movements": movements,
            "recent_shifts": shifts,
        },
    )


def my_shift(request):
    return render(request, "core/cash/shift.html", _module_context("Mi turno", "Caja por usuario y sucursal", ["Ver arqueo"], [{"label": "Usuario", "value": "DE"}], []))


def cash_opening(request):
    active_branch = selected_branch_for_request(request)
    form = CashShiftOpenForm(request.POST or None, initial={"branch": active_branch, "initial_amount": Decimal("0.00")})
    open_shift = _active_cash_shift(active_branch) if active_branch else None
    if request.method == "POST" and form.is_valid():
        branch = form.cleaned_data["branch"]
        if _active_cash_shift(branch):
            form.add_error(None, "Ya existe un turno abierto para esta sucursal.")
        else:
            CashShift.objects.create(
                branch=branch,
                user=request.user if request.user.is_authenticated else _system_user(),
                initial_amount=form.cleaned_data["initial_amount"],
                expected_cash=form.cleaned_data["initial_amount"],
            )
            return redirect("cash_overview")
    return render(
        request,
        "core/cash/opening.html",
        {
            "form": form,
            "active_branch": active_branch,
            "open_shift": open_shift,
        },
    )


def cash_movements(request):
    return _cash_movements(request, movement_type=CashMovement.Type.INCOME, page_title="Movimientos de caja", page_subtitle="Ingresos y egresos del turno")


def cash_expenses(request):
    return _cash_movements(request, movement_type=CashMovement.Type.EXPENSE, page_title="Gastos de caja", page_subtitle="Control de egresos operativos")


def cash_close(request):
    branch = selected_branch_for_request(request)
    open_shift = _active_cash_shift(branch) if branch else None
    if open_shift is None:
        open_shift = CashShift.objects.select_related("branch", "user").filter(status=CashShift.Status.OPEN).order_by("-opened_at").first()
    form = CashCloseForm(request.POST or None, initial={"counted_cash": open_shift.counted_cash if open_shift else Decimal("0.00")})
    if request.method == "POST" and form.is_valid():
        if open_shift is None:
            return redirect("cash_opening")
        counted_cash = form.cleaned_data["counted_cash"]
        open_shift.counted_cash = counted_cash
        open_shift.difference = counted_cash - open_shift.expected_cash
        open_shift.closed_at = timezone.now()
        open_shift.status = CashShift.Status.CLOSED
        open_shift.save(update_fields=["counted_cash", "difference", "closed_at", "status", "updated_at"])
        return redirect("cash_overview")
    movements = open_shift.movements.select_related("created_by").order_by("-created_at")[:10] if open_shift else []
    return render(
        request,
        "core/cash/close.html",
        {
            "form": form,
            "open_shift": open_shift,
            "movements": movements,
        },
    )


def _cash_movements(request, *, movement_type, page_title, page_subtitle):
    branch = selected_branch_for_request(request)
    open_shift = _active_cash_shift(branch) if branch else None
    if open_shift is None:
        open_shift = CashShift.objects.select_related("branch", "user").filter(status=CashShift.Status.OPEN).order_by("-opened_at").first()
    form = CashMovementForm(request.POST or None, initial={"movement_type": movement_type})
    if request.method == "POST" and form.is_valid():
        if open_shift is None:
            return redirect("cash_opening")
        movement = CashMovement.objects.create(
            shift=open_shift,
            created_by=request.user if request.user.is_authenticated else _system_user(),
            movement_type=form.cleaned_data["movement_type"],
            concept=form.cleaned_data["concept"],
            amount=form.cleaned_data["amount"],
        )
        if movement.movement_type == CashMovement.Type.INCOME:
            open_shift.expected_cash = open_shift.expected_cash + movement.amount
        else:
            open_shift.expected_cash = open_shift.expected_cash - movement.amount
        open_shift.save(update_fields=["expected_cash", "updated_at"])
        return redirect("cash_overview")
    movements = open_shift.movements.select_related("created_by").order_by("-created_at")[:12] if open_shift else []
    return render(
        request,
        "core/cash/movements.html",
        {
            "form": form,
            "open_shift": open_shift,
            "movements": movements,
            "page_title": page_title,
            "page_subtitle": page_subtitle,
            "movement_type": movement_type,
        },
    )


def reports_overview(request):
    sales_total = Sale.objects.exclude(status=Sale.Status.CANCELED).aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    purchases_total = Purchase.objects.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    returns_total = SaleReturn.objects.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    credits_total = CreditAccount.objects.filter(status__in=[CreditAccount.Status.OPEN, CreditAccount.Status.PARTIAL, CreditAccount.Status.OVERDUE]).aggregate(total=Sum("remaining_balance"))["total"] or Decimal("0.00")
    low_stock_count = ProductStock.objects.filter(quantity__gt=0, quantity__lte=F("product__min_stock")).count()
    out_stock_count = ProductStock.objects.filter(quantity__lte=0).count()
    return render(
        request,
        "core/reports/module.html",
        _module_context(
            "Reportes",
            "Ventas, compras, inventario, caja y devoluciones",
            ["Exportar PDF", "Exportar Excel"],
            [
                {"label": "Ventas", "value": f"Bs {sales_total}"},
                {"label": "Compras", "value": f"Bs {purchases_total}"},
                {"label": "Devoluciones", "value": f"Bs {returns_total}"},
                {"label": "Créditos", "value": f"Bs {credits_total}"},
            ],
            [
                {"a": "Inventario", "b": "Stock crítico", "c": f"{low_stock_count} bajo", "d": "Alerta"},
                {"a": "Inventario", "b": "Sin stock", "c": f"{out_stock_count} agotados", "d": "Alerta"},
            ],
        ),
    )


def admin_overview(request):
    user_count = get_user_model().objects.count()
    role_count = Group.objects.count()
    return render(
        request,
        "core/admin/index.html",
        {
            "page_title": "Administración",
            "page_subtitle": "Sucursales, usuarios, roles y configuración",
            "stats": [
                {"label": "Usuarios", "value": str(user_count)},
                {"label": "Roles", "value": str(role_count)},
            ],
            "rows": [
                {"a": "Usuarios", "b": "Altas y permisos", "c": f"{user_count} activos", "d": "Sistema"},
                {"a": "Roles", "b": "Grupos y permisos", "c": f"{role_count} grupos", "d": "Sistema"},
            ],
        },
    )


def admin_branches(request):
    branches = Branch.objects.order_by("name")
    rows = [
        {
            "pk": branch.pk,
            "a": branch.name,
            "b": branch.code,
            "c": "Activa" if branch.is_active else "Inactiva",
            "d": branch.address or "Sin dirección",
        }
        for branch in branches
    ]
    return render(
        request,
        "core/admin/branches.html",
        {
            "page_title": "Sucursales",
            "page_subtitle": "Gestión de sedes físicas",
            "stats": [
                {"label": "Sucursales", "value": str(branches.count())},
                {"label": "Activas", "value": str(branches.filter(is_active=True).count())},
            ],
            "rows": rows,
        },
    )


def admin_users(request):
    users = get_user_model().objects.prefetch_related("groups").order_by("username")
    rows = [
        {
            "pk": user.pk,
            "a": user.get_full_name() or user.username,
            "b": user.email or "-",
            "c": ", ".join(group.name for group in user.groups.all()) or "Sin rol",
            "d": "Activo" if user.is_active else "Inactivo",
        }
        for user in users
    ]
    return render(
        request,
        "core/admin/users.html",
        {
            "users": users,
            "rows": rows,
            "page_title": "Usuarios",
            "page_subtitle": "Operadores, cajeros y administradores",
        },
    )


def admin_user_create(request):
    form = UserAdminCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        form.save_m2m()
        return redirect("admin_users")
    return render(request, "core/admin/user_form.html", {"form": form, "page_title": "Nuevo usuario", "page_subtitle": "Alta de operador"})


def admin_user_edit(request, pk):
    user = get_object_or_404(get_user_model(), pk=pk)
    form = UserAdminChangeForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        form.save_m2m()
        return redirect("admin_users")
    return render(request, "core/admin/user_form.html", {"form": form, "page_title": "Editar usuario", "page_subtitle": user.username})


def admin_user_delete(request, pk):
    user = get_object_or_404(get_user_model(), pk=pk)
    if request.method == "POST":
        user.delete()
        return redirect("admin_users")
    return render(request, "core/admin/delete.html", {"object": user, "list_url": "admin_users", "page_title": "Eliminar usuario", "page_subtitle": user.username})


def admin_roles(request):
    groups = Group.objects.prefetch_related("permissions").order_by("name")
    rows = [
        {
            "pk": group.pk,
            "a": group.name,
            "b": f"{group.permissions.count()} permisos",
            "c": f"{group.user_set.count()} usuarios",
            "d": "Rol activo",
        }
        for group in groups
    ]
    return render(
        request,
        "core/admin/roles.html",
        {
            "groups": groups,
            "rows": rows,
            "page_title": "Roles",
            "page_subtitle": "Grupos y permisos del sistema",
        },
    )


def admin_role_create(request):
    form = GroupAdminForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("admin_roles")
    return render(request, "core/admin/role_form.html", {"form": form, "page_title": "Nuevo rol", "page_subtitle": "Definir permisos"})


def admin_role_edit(request, pk):
    group = get_object_or_404(Group, pk=pk)
    form = GroupAdminForm(request.POST or None, instance=group)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("admin_roles")
    return render(request, "core/admin/role_form.html", {"form": form, "page_title": "Editar rol", "page_subtitle": group.name})


def admin_role_delete(request, pk):
    group = get_object_or_404(Group, pk=pk)
    if request.method == "POST":
        group.delete()
        return redirect("admin_roles")
    return render(request, "core/admin/delete.html", {"object": group, "list_url": "admin_roles", "page_title": "Eliminar rol", "page_subtitle": group.name})


def admin_settings(request):
    branches_total = Branch.objects.count()
    active_branches = Branch.objects.filter(is_active=True).count()
    user_total = get_user_model().objects.count()
    role_total = Group.objects.count()
    return render(
        request,
        "core/admin/settings.html",
        {
            "page_title": "Configuración",
            "page_subtitle": "Parámetros generales del sistema",
            "stats": [
                {"label": "Sucursales", "value": str(branches_total)},
                {"label": "Activas", "value": str(active_branches)},
                {"label": "Usuarios", "value": str(user_total)},
                {"label": "Roles", "value": str(role_total)},
            ],
            "settings_rows": [
                {"a": "Zona horaria", "b": settings.TIME_ZONE, "c": "Operación", "d": "Sistema"},
                {"a": "Idioma", "b": settings.LANGUAGE_CODE, "c": "Interfaz", "d": "Sistema"},
                {"a": "Base de datos", "b": "sqlite3", "c": "Desarrollo", "d": "Local"},
            ],
        },
    )


def set_selected_branch(request):
    if request.method != "POST":
        return redirect("dashboard")
    branch_id = request.POST.get("branch")
    next_url = request.POST.get("next") or reverse("dashboard")
    if branch_id:
        branch = Branch.objects.filter(pk=branch_id, is_active=True).first()
        if branch is not None:
            request.session["selected_branch_id"] = branch.pk
    else:
        request.session.pop("selected_branch_id", None)
    return redirect(next_url if isinstance(next_url, str) and next_url.startswith("/") else reverse("dashboard"))


def _catalog_list(request, *, model, page_title, page_subtitle, create_url, create_label, headers, row_builder):
    rows = [row_builder(instance) for instance in model.objects.all()]
    return render(
        request,
        "core/catalog/list.html",
        {
            "page_title": page_title,
            "page_subtitle": page_subtitle,
            "create_url": create_url,
            "create_label": create_label,
            "headers": headers,
            "rows": rows,
        },
    )


def _catalog_form(request, *, form_class, page_title, page_subtitle, list_url, template_name="core/catalog/form.html", instance=None):
    form = form_class(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(list_url)
    return render(
        request,
        template_name,
        {
            "form": form,
            "page_title": page_title,
            "page_subtitle": page_subtitle,
            "list_url": list_url,
        },
    )


def _catalog_delete(request, *, instance, list_url, page_title, page_subtitle):
    if request.method == "POST":
        instance.delete()
        return redirect(list_url)
    return render(
        request,
        "core/catalog/delete.html",
        {
            "object": instance,
            "page_title": page_title,
            "page_subtitle": page_subtitle,
            "list_url": list_url,
        },
    )


def branches(request):
    return _catalog_list(
        request,
        model=Branch,
        page_title="Sucursales",
        page_subtitle="Gestión de sedes operativas",
        create_url="/catalogos/sucursales/nueva/",
        create_label="Nueva sucursal",
        headers=["Nombre", "Código", "Estado", "Dirección"],
        row_builder=lambda obj: {
            "cells": [obj.name, obj.code, "Activa" if obj.is_active else "Inactiva", obj.address or "-"],
            "edit_url": f"/catalogos/sucursales/{obj.pk}/editar/",
            "delete_url": f"/catalogos/sucursales/{obj.pk}/eliminar/",
        },
    )


def branch_create(request):
    return _catalog_form(request, form_class=BranchForm, page_title="Nueva sucursal", page_subtitle="Alta de una sede operativa", list_url="/catalogos/sucursales/")


def branch_edit(request, pk):
    return _catalog_form(request, form_class=BranchForm, instance=get_object_or_404(Branch, pk=pk), page_title="Editar sucursal", page_subtitle="Ajusta los datos de la sede", list_url="/catalogos/sucursales/")


def branch_delete(request, pk):
    return _catalog_delete(request, instance=get_object_or_404(Branch, pk=pk), list_url="/catalogos/sucursales/", page_title="Eliminar sucursal", page_subtitle="Confirma la eliminación de la sede")


def admin_branches(request):
    branches = Branch.objects.order_by("name")
    rows = [
        {
            "pk": branch.pk,
            "a": branch.name,
            "b": branch.code,
            "c": "Activa" if branch.is_active else "Inactiva",
            "d": branch.address or "Sin dirección",
        }
        for branch in branches
    ]
    return render(
        request,
        "core/admin/branches.html",
        {
            "page_title": "Sucursales",
            "page_subtitle": "Gestión de sedes físicas",
            "stats": [
                {"label": "Sucursales", "value": str(branches.count())},
                {"label": "Activas", "value": str(branches.filter(is_active=True).count())},
            ],
            "rows": rows,
        },
    )


def categories_list(request):
    return _catalog_list(
        request,
        model=Category,
        page_title="Categorías",
        page_subtitle="Clasificación de productos",
        create_url="/catalogos/categorias/nueva/",
        create_label="Nueva categoría",
        headers=["Nombre", "Estado"],
        row_builder=lambda obj: {
            "cells": [obj.name, "Activa" if obj.is_active else "Inactiva"],
            "edit_url": f"/catalogos/categorias/{obj.pk}/editar/",
            "delete_url": f"/catalogos/categorias/{obj.pk}/eliminar/",
        },
    )


def category_create(request):
    return _catalog_form(request, form_class=CategoryForm, page_title="Nueva categoría", page_subtitle="Crea una familia de productos", list_url="/catalogos/categorias/")


def category_edit(request, pk):
    return _catalog_form(request, form_class=CategoryForm, instance=get_object_or_404(Category, pk=pk), page_title="Editar categoría", page_subtitle="Ajusta el nombre o estado", list_url="/catalogos/categorias/")


def category_delete(request, pk):
    return _catalog_delete(request, instance=get_object_or_404(Category, pk=pk), list_url="/catalogos/categorias/", page_title="Eliminar categoría", page_subtitle="Confirma la eliminación de la categoría")


def products_list(request):
    return _catalog_list(
        request,
        model=Product,
        page_title="Productos",
        page_subtitle="Catálogo comercial y precios",
        create_url="/catalogos/productos/nuevo/",
        create_label="Nuevo producto",
        headers=["Código", "Nombre", "Categoría", "Precio venta", "Estado"],
        row_builder=lambda obj: {
            "cells": [obj.code, obj.name, obj.category.name, f"Bs {obj.sale_price}", "Activo" if obj.is_active else "Inactivo"],
            "edit_url": f"/catalogos/productos/{obj.pk}/editar/",
            "delete_url": f"/catalogos/productos/{obj.pk}/eliminar/",
        },
    )


def product_create(request):
    return _catalog_form(request, form_class=ProductForm, page_title="Nuevo producto", page_subtitle="Alta de artículo", list_url="/catalogos/productos/")


def product_edit(request, pk):
    return _catalog_form(request, form_class=ProductForm, instance=get_object_or_404(Product, pk=pk), page_title="Editar producto", page_subtitle="Corrige datos del artículo", list_url="/catalogos/productos/")


def product_delete(request, pk):
    return _catalog_delete(request, instance=get_object_or_404(Product, pk=pk), list_url="/catalogos/productos/", page_title="Eliminar producto", page_subtitle="Confirma la eliminación del producto")


def brands_list(request):
    return _catalog_list(
        request,
        model=Brand,
        page_title="Marcas",
        page_subtitle="Fabricantes y líneas comerciales",
        create_url="/catalogos/marcas/nueva/",
        create_label="Nueva marca",
        headers=["Nombre", "Estado"],
        row_builder=lambda obj: {
            "cells": [obj.name, "Activa" if obj.is_active else "Inactiva"],
            "edit_url": f"/catalogos/marcas/{obj.pk}/editar/",
            "delete_url": f"/catalogos/marcas/{obj.pk}/eliminar/",
        },
    )


def brand_create(request):
    return _catalog_form(request, form_class=BrandForm, page_title="Nueva marca", page_subtitle="Alta de marca comercial", list_url="/catalogos/marcas/")


def brand_edit(request, pk):
    return _catalog_form(request, form_class=BrandForm, instance=get_object_or_404(Brand, pk=pk), page_title="Editar marca", page_subtitle="Ajusta el registro", list_url="/catalogos/marcas/")


def brand_delete(request, pk):
    return _catalog_delete(request, instance=get_object_or_404(Brand, pk=pk), list_url="/catalogos/marcas/", page_title="Eliminar marca", page_subtitle="Confirma la eliminación de la marca")


def suppliers_list(request):
    return _catalog_list(
        request,
        model=Supplier,
        page_title="Proveedores",
        page_subtitle="Catálogo de abastecedores",
        create_url="/catalogos/proveedores/nuevo/",
        create_label="Nuevo proveedor",
        headers=["Nombre", "Teléfono", "Estado"],
        row_builder=lambda obj: {
            "cells": [obj.name, obj.phone or "-", "Activo" if obj.is_active else "Inactivo"],
            "edit_url": f"/catalogos/proveedores/{obj.pk}/editar/",
            "delete_url": f"/catalogos/proveedores/{obj.pk}/eliminar/",
        },
    )


def supplier_create(request):
    return _catalog_form(request, form_class=SupplierForm, page_title="Nuevo proveedor", page_subtitle="Alta de proveedor", list_url="/catalogos/proveedores/")


def supplier_edit(request, pk):
    return _catalog_form(request, form_class=SupplierForm, instance=get_object_or_404(Supplier, pk=pk), page_title="Editar proveedor", page_subtitle="Ajusta los datos del proveedor", list_url="/catalogos/proveedores/")


def supplier_delete(request, pk):
    return _catalog_delete(request, instance=get_object_or_404(Supplier, pk=pk), list_url="/catalogos/proveedores/", page_title="Eliminar proveedor", page_subtitle="Confirma la eliminación del proveedor")


def customers_list(request):
    return _catalog_list(
        request,
        model=Customer,
        page_title="Clientes",
        page_subtitle="Listado de clientes y crédito",
        create_url="/catalogos/clientes/nuevo/",
        create_label="Nuevo cliente",
        headers=["Nombre", "Teléfono", "Crédito", "Saldo"],
        row_builder=lambda obj: {
            "cells": [obj.name, obj.phone or "-", f"Bs {obj.credit_limit}", f"Bs {obj.balance}"],
            "edit_url": f"/catalogos/clientes/{obj.pk}/editar/",
            "delete_url": f"/catalogos/clientes/{obj.pk}/eliminar/",
        },
    )


def customer_create(request):
    return _catalog_form(request, form_class=CustomerForm, page_title="Nuevo cliente", page_subtitle="Alta de cliente", list_url="/catalogos/clientes/")


def customer_edit(request, pk):
    return _catalog_form(request, form_class=CustomerForm, instance=get_object_or_404(Customer, pk=pk), page_title="Editar cliente", page_subtitle="Ajusta los datos del cliente", list_url="/catalogos/clientes/")


def customer_delete(request, pk):
    return _catalog_delete(request, instance=get_object_or_404(Customer, pk=pk), list_url="/catalogos/clientes/", page_title="Eliminar cliente", page_subtitle="Confirma la eliminación del cliente")
