# coca_social

Sistema web para la gestión integral de una tienda de abarrotes con múltiples sucursales.

## Objetivo

Centralizar ventas, inventario, compras, traspasos, clientes, créditos, caja y reportes en una sola aplicación web moderna, rápida y responsive.

## Stack

- Backend: Django 5
- API: Django REST Framework
- Frontend: Bootstrap 5, HTMX, Select2
- Base de datos: sqlite3

## Estado actual

La base funcional ya está iniciada y cuenta con:

- Layout general con sidebar, navbar superior y selector de sucursal.
- Dashboard visual con KPIs, tablas y paneles de resumen.
- POS con búsqueda rápida, carrito en sesión y checkout.
- Catálogos CRUD para sucursales, categorías, marcas, productos, proveedores y clientes.
- Documentos operativos para compras y traspasos con líneas embebidas.
- Registro de inventario, kardex, stock por sucursal, stock bajo y agotados.
- Ventas con registro de stock, cobro, crédito y movimiento de caja.

## Módulos principales

- Dashboard
- Ventas
- Inventario
- Compras
- Traspasos
- Clientes
- Caja
- Reportes
- Administración

## Flujo principal del sistema

1. Vender desde el POS.
2. Registrar automáticamente stock, pago o crédito.
3. Consultar inventario por sucursal.
4. Registrar compras con líneas de producto.
5. Enviar y recibir traspasos entre sucursales.
6. Revisar ventas, caja y créditos pendientes.

## Cómo ejecutar

```bash
python manage.py migrate
python manage.py runserver
```

## Rutas útiles

- `/` Dashboard
- `/pos/` Punto de venta
- `/ventas/listado/` Ventas realizadas
- `/compras/listado/` Compras
- `/traspasos/listado/` Traspasos
- `/catalogos/productos/` Productos
- `/catalogos/clientes/` Clientes

## Siguientes pasos

1. Reemplazar los KPIs y tablas del dashboard por consultas reales a la base de datos.
2. Completar la gestión de caja por turno con apertura, movimientos, gastos y cierre.
3. Agregar autenticación, roles y permisos por sucursal y por módulo.
4. Implementar devoluciones de ventas y ajuste de inventario con su flujo completo.
5. Agregar filtros, búsqueda avanzada y paginación en los listados grandes.
6. Mejorar la experiencia del POS con atajos de teclado, lector de código de barras y validaciones de cobro.
7. Crear reportes exportables de ventas, compras, inventario, caja y créditos.

## Notas

- El proyecto está pensado para crecer primero como aplicación server-rendered con HTMX.
- La API REST queda disponible para integraciones futuras o pantallas adicionales.


# Siguiente paso natural:

Convertir inventario y ajustes en pantallas reales con conteo, merma y corrección.