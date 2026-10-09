# -*- coding: utf-8 -*-
{
    "name": "sale_stock_intercompany_auto_transfer",
    "version": "1.0.0",
    "summary": "Valida solas las transferencias inter-company de reabastecimiento al vender",
    "description": """
Cuando una compañia se abastece de otra con la ruta de reabastecimiento inter-company del core
(salida del almacen proveedor, transito, recepcion en el almacen destino), el core deja las dos
transferencias para validar a mano. Este modulo las valida solas.

- Opcion por tipo de operacion de recepcion de la compañia destino.
- Al confirmar el pedido, la salida de la compañia proveedora se valida por lo disponible y la
  recepcion encadenada se valida por lo recibido; el deposito solo valida la entrega al cliente.
- Lo que no se pudo enviar queda como backorder pendiente y se avisa en el chatter del pedido.
- Un error de negocio al validar nunca impide confirmar el pedido.
- Sin activar la opcion, el comportamiento es identico al core.
    """,
    "category": "Inventory/Inventory",
    "author": "Sunra",
    "website": "https://github.com/sunraargsh",
    "license": "LGPL-3",
    "depends": ["sale_stock"],
    "data": [
        "views/stock_picking_type_views.xml",
        "views/stock_warehouse_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
