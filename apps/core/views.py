from django.shortcuts import render


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
    context = {
        "quick_products": [
            {"name": "Coca-Cola 600ml", "price": "$18", "stock": 48},
            {"name": "Pan Bimbo grande", "price": "$42", "stock": 19},
            {"name": "Leche entera 1L", "price": "$28", "stock": 12},
            {"name": "Arroz 1kg", "price": "$26", "stock": 31},
        ],
        "cart": [
            {"name": "Coca-Cola 600ml", "qty": 2, "price": "$18", "subtotal": "$36"},
            {"name": "Pan Bimbo grande", "qty": 1, "price": "$42", "subtotal": "$42"},
        ],
    }
    return render(request, "core/pos.html", context)


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
    return render(request, "core/module.html", _module_context("Compras", "Órdenes, entradas y proveedores", ["Nueva compra", "Proveedores"], [{"label": "Compras mes", "value": "$184,900"}], [{"a": "C-1209", "b": "Distribuidora XYZ", "c": "$18,240", "d": "Registrada"}]))


def new_purchase(request):
    return render(request, "core/module.html", _module_context("Nueva compra", "Captura rápida por producto o proveedor", ["Guardar borrador", "Registrar"], [{"label": "Líneas", "value": "0"}], []))


def suppliers(request):
    return render(request, "core/module.html", _module_context("Proveedores", "Catálogo de abastecedores", ["Nuevo proveedor"], [{"label": "Proveedores", "value": "24"}], [{"a": "Distribuidora XYZ", "b": "Activo", "c": "555-1234", "d": "Norte"}]))


def transfers_overview(request):
    return render(request, "core/module.html", _module_context("Traspasos", "Flujo entre sucursales y recepción parcial", ["Nuevo traspaso"], [{"label": "Pendientes", "value": "7"}], [{"a": "TR-204", "b": "Centro → Norte", "c": "120 uds", "d": "Pendiente"}]))


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
