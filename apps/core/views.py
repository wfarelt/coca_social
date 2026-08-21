from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponseBadRequest
from decimal import Decimal

from .forms import (
    BrandForm,
    BranchForm,
    CategoryForm,
    CustomerForm,
    ProductForm,
    PurchaseForm,
    PurchaseItemFormSet,
    SupplierForm,
    TransferForm,
    TransferItemFormSet,
)
from .models import Brand, Branch, Category, Customer, Product, Purchase, Sale, SaleItem, Supplier, Transfer


def _module_context(title, subtitle, actions, stats=None, rows=None):
    return {
        "module_title": title,
        "module_subtitle": subtitle,
        "module_actions": actions,
        "module_stats": stats or [],
        "module_rows": rows or [],
    }


def dashboard(request):
    context = {
        "branches": ["Sucursal Centro", "Sucursal Norte", "Sucursal Oriente"],
        "kpis": [
            {"label": "Ventas de hoy", "value": "$18,420", "delta": "+12%", "tone": "success"},
            {"label": "Utilidad", "value": "$5,860", "delta": "+8%", "tone": "primary"},
            {"label": "Stock bajo", "value": "24", "delta": "8 críticos", "tone": "warning"},
            {"label": "Créditos pendientes", "value": "$9,240", "delta": "14 clientes", "tone": "danger"},
        ],
        "recent_sales": [
            {"folio": "V-1024", "customer": "Consumidor final", "amount": "$1,120", "status": "Pagada"},
            {"folio": "V-1023", "customer": "Tienda López", "amount": "$860", "status": "Crédito"},
            {"folio": "V-1022", "customer": "Farmacia Central", "amount": "$2,430", "status": "Pagada"},
        ],
        "low_stock": [
            {"product": "Arroz 1 kg", "branch": "Sucursal Centro", "stock": "3", "state": "Bajo"},
            {"product": "Aceite 1 L", "branch": "Sucursal Norte", "stock": "0", "state": "Agotado"},
            {"product": "Frijol 500 g", "branch": "Sucursal Oriente", "stock": "5", "state": "Bajo"},
        ],
        "transfers": [
            {"code": "TR-204", "from": "Centro", "to": "Norte", "state": "Pendiente"},
            {"code": "TR-203", "from": "Oriente", "to": "Centro", "state": "Enviado"},
        ],
    }
    return render(request, "core/dashboard.html", context)


def pos(request):
    cart_context = _cart_context(request)
    context = {
        "customers": Customer.objects.filter(is_active=True).order_by("name")[:20],
        "quick_products": [
            {"name": "Coca-Cola 600ml", "price": "$18", "stock": 48},
            {"name": "Pan Bimbo grande", "price": "$42", "stock": 19},
            {"name": "Leche entera 1L", "price": "$28", "stock": 12},
            {"name": "Arroz 1kg", "price": "$26", "stock": 31},
        ],
        **cart_context,
    }
    return render(request, "core/pos.html", context)


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
    customer = Customer.objects.filter(pk=customer_id).first() if customer_id else None
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
            due_date = request.POST.get("due_date") or None
            sale.post_credit(_system_user(), due_date=due_date)
        else:
            sale.post_payment(_system_user(), amount=sale.total)

    request.session.pop("pos_cart", None)
    request.session.modified = True
    return redirect("pos")


def pos_search(request):
    query = request.GET.get("q", "").strip()
    products = Product.objects.select_related("category").filter(is_active=True)
    if query:
        products = products.filter(name__icontains=query) | products.filter(code__icontains=query) | products.filter(barcode__icontains=query)
    products = products.order_by("name")[:12]
    return render(request, "core/partials/pos_product_results.html", {"products": products, "query": query})


def pos_add_item(request, pk):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")
    product = get_object_or_404(Product, pk=pk, is_active=True)
    cart = request.session.get("pos_cart", {})
    key = str(product.pk)
    cart[key] = cart.get(key, 0) + 1
    request.session["pos_cart"] = cart
    request.session.modified = True
    return render(request, "core/partials/pos_cart.html", _cart_context(request))


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
    return render(request, "core/partials/pos_cart.html", _cart_context(request))


def pos_clear_cart(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")
    request.session.pop("pos_cart", None)
    request.session.modified = True
    return render(request, "core/partials/pos_cart.html", _cart_context(request))


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
    return render(request, "core/module.html", _module_context("Ventas realizadas", "Historial de ventas y devoluciones", ["Nuevo POS", "Devoluciones"], [{"label": "Ventas hoy", "value": "$18,420"}, {"label": "Tickets", "value": "214"}], [{"a": "V-1024", "b": "Consumidor final", "c": "$1,120", "d": "Pagada"}, {"a": "V-1023", "b": "Tienda López", "c": "$860", "d": "Crédito"}]))


def sales_returns(request):
    return render(request, "core/module.html", _module_context("Devoluciones", "Control de notas de devolución y ajustes", ["Registrar devolución", "Ver pendientes"], [{"label": "Pendientes", "value": "6"}, {"label": "Monto", "value": "$1,240"}], [{"a": "DEV-11", "b": "V-1023", "c": "$180", "d": "Pendiente"}]))


def inventory_overview(request):
    return render(request, "core/module.html", _module_context("Inventario", "Catálogo, stock por sucursal y kardex", ["Nuevo producto", "Ajuste de inventario"], [{"label": "Productos", "value": "1,248"}, {"label": "Bajo stock", "value": "24"}], [{"a": "Arroz 1 kg", "b": "ARZ-001", "c": "Centro", "d": "Bajo"}, {"a": "Aceite 1 L", "b": "ACE-014", "c": "Norte", "d": "Agotado"}]))


def products(request):
    return render(request, "core/module.html", _module_context("Productos", "Alta, edición y control de artículos", ["Nuevo producto", "Importar"], [{"label": "Activos", "value": "1,201"}], [{"a": "Arroz 1 kg", "b": "ARZ-001", "c": "$18 / $26", "d": "Activo"}]))


def categories(request):
    return render(request, "core/module.html", _module_context("Categorías", "Estructura comercial por familias", ["Nueva categoría"], [{"label": "Categorías", "value": "38"}], [{"a": "Abarrotes", "b": "142 productos", "c": "Principal", "d": "Activa"}]))


def brands(request):
    return render(request, "core/module.html", _module_context("Marcas", "Fabricantes y marcas registradas", ["Nueva marca"], [{"label": "Marcas", "value": "52"}], [{"a": "Bimbo", "b": "Panificación", "c": "Alta", "d": "Activa"}]))


def stock_by_branch(request):
    return render(request, "core/module.html", _module_context("Stock por sucursal", "Disponibilidad por sede y mínimos", ["Ver críticos"], [{"label": "Sucursales", "value": "3"}], [{"a": "Sucursal Centro", "b": "Arroz 1 kg", "c": "3", "d": "Bajo"}]))


def kardex(request):
    return render(request, "core/module.html", _module_context("Kardex", "Entradas, salidas y movimientos", ["Exportar"], [{"label": "Movimientos", "value": "8,412"}], [{"a": "Compra", "b": "ARZ-001", "c": "+100", "d": "Entrada"}]))


def inventory_adjustments(request):
    return render(request, "core/module.html", _module_context("Ajustes de inventario", "Conteos, mermas y correcciones", ["Nuevo ajuste"], [{"label": "Ajustes", "value": "16"}], [{"a": "AJ-118", "b": "Conteo", "c": "-4", "d": "Aplicado"}]))


def purchases_overview(request):
    return render(request, "core/module.html", _module_context("Compras", "Órdenes, entradas y proveedores", ["Listado", "Nueva compra", "Proveedores"], [{"label": "Compras mes", "value": "$184,900"}], [{"a": "C-1209", "b": "Distribuidora XYZ", "c": "$18,240", "d": "Registrada"}]))


def new_purchase(request):
    return render(request, "core/module.html", _module_context("Nueva compra", "Captura rápida por producto o proveedor", ["Guardar borrador", "Registrar"], [{"label": "Líneas", "value": "0"}], []))


def suppliers(request):
    return render(request, "core/module.html", _module_context("Proveedores", "Catálogo de abastecedores", ["Nuevo proveedor"], [{"label": "Proveedores", "value": "24"}], [{"a": "Distribuidora XYZ", "b": "Activo", "c": "555-1234", "d": "Norte"}]))


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
        "core/document_list.html",
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
        "core/document_items_form.html",
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
        "core/document_items_form.html",
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
    return render(request, "core/document_delete.html", {"object": purchase, "page_title": "Eliminar compra", "page_subtitle": purchase.folio, "list_url": "/compras/"})


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
        "core/document_list.html",
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
        "core/document_items_form.html",
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
        "core/document_items_form.html",
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
    return render(request, "core/document_delete.html", {"object": transfer, "page_title": "Eliminar traspaso", "page_subtitle": transfer.code, "list_url": "/traspasos/"})


def transfers_overview(request):
    return render(request, "core/module.html", _module_context("Traspasos", "Flujo entre sucursales y recepción parcial", ["Listado", "Nuevo traspaso"], [{"label": "Pendientes", "value": "7"}], [{"a": "TR-204", "b": "Centro → Norte", "c": "120 uds", "d": "Pendiente"}]))


def new_transfer(request):
    return render(request, "core/module.html", _module_context("Nuevo traspaso", "Sucursal origen, productos, cantidades y destino", ["Enviar"], [{"label": "Estado", "value": "Borrador"}], []))


def sent_transfers(request):
    return render(request, "core/module.html", _module_context("Traspasos enviados", "Despachos en tránsito", ["Ver pendientes"], [{"label": "Enviados", "value": "5"}], [{"a": "TR-203", "b": "Oriente → Centro", "c": "48 uds", "d": "Enviado"}]))


def received_transfers(request):
    return render(request, "core/module.html", _module_context("Traspasos recibidos", "Recepciones confirmadas", ["Validar recepción"], [{"label": "Recibidos", "value": "11"}], [{"a": "TR-198", "b": "Norte → Centro", "c": "50 uds", "d": "Recibido"}]))


def pending_transfers(request):
    return render(request, "core/module.html", _module_context("Traspasos pendientes", "Confirmación de cantidades recibidas", ["Recepcionar"], [{"label": "Pendientes", "value": "7"}], [{"a": "TR-204", "b": "Centro → Norte", "c": "120 uds", "d": "Pendiente"}]))


def customers_overview(request):
    return render(request, "core/module.html", _module_context("Clientes", "Catálogo de clientes y consumo", ["Nuevo cliente"], [{"label": "Clientes", "value": "486"}], [{"a": "Tienda López", "b": "Activo", "c": "$2,100", "d": "Crédito"}]))


def credits_overview(request):
    return render(request, "core/module.html", _module_context("Créditos / Fiados", "Saldo, vencimientos y cartera", ["Cobrar"], [{"label": "Pendientes", "value": "$9,240"}], [{"a": "Tienda López", "b": "$860", "c": "15 días", "d": "Vencido"}]))


def collections_overview(request):
    return render(request, "core/module.html", _module_context("Cobros", "Aplicación de pagos y abonos", ["Registrar cobro"], [{"label": "Cobros hoy", "value": "$3,200"}], [{"a": "CO-112", "b": "Tienda López", "c": "$860", "d": "Aplicado"}]))


def cash_overview(request):
    return render(request, "core/module.html", _module_context("Caja", "Turno, arqueo, gastos e ingresos", ["Mi turno", "Abrir caja", "Cierre"], [{"label": "Caja abierta", "value": "Sí"}], [{"a": "Turno matutino", "b": "Centro", "c": "$17,460", "d": "Abierta"}]))


def my_shift(request):
    return render(request, "core/module.html", _module_context("Mi turno", "Caja por usuario y sucursal", ["Ver arqueo"], [{"label": "Usuario", "value": "DE"}], []))


def cash_opening(request):
    return render(request, "core/module.html", _module_context("Apertura de caja", "Monto inicial y validación de turno", ["Abrir turno"], [{"label": "Monto inicial", "value": "$500"}], []))


def cash_movements(request):
    return render(request, "core/module.html", _module_context("Movimientos de caja", "Ingresos y egresos del turno", ["Nuevo ingreso", "Nuevo egreso"], [{"label": "Movimientos", "value": "18"}], [{"a": "Ingreso menor", "b": "$120", "c": "Efectivo", "d": "Hoy"}]))


def cash_expenses(request):
    return render(request, "core/module.html", _module_context("Gastos de caja", "Control de egresos operativos", ["Registrar gasto"], [{"label": "Gastos hoy", "value": "$420"}], [{"a": "Transporte", "b": "$120", "c": "Caja", "d": "Aplicado"}]))


def cash_close(request):
    return render(request, "core/module.html", _module_context("Arqueo y cierre", "Resumen visual del turno", ["Cerrar turno"], [{"label": "Diferencia", "value": "$0"}], []))


def reports_overview(request):
    return render(request, "core/module.html", _module_context("Reportes", "Ventas, compras, inventario y caja", ["Exportar PDF", "Exportar Excel"], [{"label": "Reportes", "value": "7"}], []))


def admin_overview(request):
    return render(request, "core/module.html", _module_context("Administración", "Sucursales, usuarios, roles y configuración", ["Sucursales", "Usuarios"], [{"label": "Roles", "value": "4"}], []))


def admin_branches(request):
    return render(request, "core/module.html", _module_context("Sucursales", "Gestión de sedes físicas", ["Nueva sucursal"], [{"label": "Sucursales", "value": "3"}], []))


def admin_users(request):
    return render(request, "core/module.html", _module_context("Usuarios", "Operadores, cajeros y administradores", ["Nuevo usuario"], [{"label": "Usuarios", "value": "12"}], []))


def admin_roles(request):
    return render(request, "core/module.html", _module_context("Roles y permisos", "Acceso por módulo y sucursal", ["Nuevo rol"], [{"label": "Roles", "value": "4"}], []))


def admin_settings(request):
    return render(request, "core/module.html", _module_context("Configuración", "Parámetros generales del sistema", ["Guardar cambios"], [{"label": "Estado", "value": "Activo"}], []))


def _catalog_list(request, *, model, page_title, page_subtitle, create_url, create_label, headers, row_builder):
    rows = [row_builder(instance) for instance in model.objects.all()]
    return render(
        request,
        "core/catalog_list.html",
        {
            "page_title": page_title,
            "page_subtitle": page_subtitle,
            "create_url": create_url,
            "create_label": create_label,
            "headers": headers,
            "rows": rows,
        },
    )


def _catalog_form(request, *, form_class, page_title, page_subtitle, list_url, template_name="core/catalog_form.html", instance=None):
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
        "core/catalog_delete.html",
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
            "cells": [obj.code, obj.name, obj.category.name, f"${obj.sale_price}", "Activo" if obj.is_active else "Inactivo"],
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
        page_subtitle="Catálogo de clientes y crédito",
        create_url="/catalogos/clientes/nuevo/",
        create_label="Nuevo cliente",
        headers=["Nombre", "Teléfono", "Crédito", "Saldo"],
        row_builder=lambda obj: {
            "cells": [obj.name, obj.phone or "-", f"${obj.credit_limit}", f"${obj.balance}"],
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
