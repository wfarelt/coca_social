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
- Inventario con pantallas reales de stock por sucursal, kardex y ajustes de conteo, merma, faltante y corrección.
- Ventas con registro de stock, cobro, crédito y movimiento de caja.
- Devoluciones de ventas y ajustes de inventario con reversa de stock y kardex.

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
python manage.py seed_default_users
python manage.py runserver
```

## Usuarios por defecto

Después de ejecutar la semilla, quedan creadas estas cuentas base:

- `admin` / `Admin123!`
- `gerente` / `Gerente123!`
- `caja` / `Caja123!`
- `ventas` / `Ventas123!`

Todos los usuarios quedan activos; `admin` además es superusuario.

## Rutas útiles

- `/` Dashboard
- `/pos/` Punto de venta
- `/ventas/listado/` Ventas realizadas
- `/compras/listado/` Compras
- `/traspasos/listado/` Traspasos
- `/catalogos/productos/` Productos
- `/catalogos/clientes/` Clientes

## Siguientes pasos

1. Agregar filtros, búsqueda avanzada y paginación en los listados grandes.
2. Mejorar la experiencia del POS con atajos de teclado, lector de código de barras y validaciones de cobro.
3. Crear reportes exportables de ventas, compras, inventario, caja y créditos.
4. Afinar permisos por sucursal y por módulo con reglas más granulares.
5. Conectar integración API/REST para escenarios de consumo externo.
6. Seguir afinando inventario con exportación y movimientos más detallados por producto.

## Notas

- El proyecto está pensado para crecer primero como aplicación server-rendered con HTMX.
- La API REST queda disponible para integraciones futuras o pantallas adicionales.


# Siguiente paso natural:

Mejorar inventario con filtros, exportación y detalle por producto/sucursal.