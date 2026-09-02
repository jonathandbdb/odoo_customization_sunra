# -*- coding: utf-8 -*-
{
    "name": "sunra_mrp_component_serials",
    "version": "1.2.0",
    "summary": "Trazabilidad de numeros de serie de motor/bateria/controlador/cargador contra el chasis",
    "description": """
Trazabilidad de piezas de bicicleta electrica contra el numero de serie del chasis.
- Padron de piezas (motor, bateria/faja, controlador, cargador) montadas contra la serie del chasis (stock.lot).
- Traslado automatico de las piezas del lote del kit al lote de la bicicleta armada al procesar la Orden de Fabricacion.
- Reutilizacion del mismo numero de chasis para la bicicleta armada (sin numero nuevo).
- Impresion automatica de los numeros de motor, bateria(s), controlador y cargador en remito y factura.
- Visualizacion de motor, faja(s) de bateria y cargador en el detalle de operaciones del albaran, al momento de entregar.
    """,
    "category": "Manufacturing",
    "author": "Sunra",
    "website": "https://github.com/sunraargsh",
    "license": "LGPL-3",
    "depends": ["mail", "mrp", "sale_stock", "stock_account"],
    "data": [
        "security/ir.model.access.csv",
        "views/sunra_bike_component_views.xml",
        "views/sunra_mrp_component_serials_menus.xml",
        "views/stock_lot_views.xml",
        "views/stock_move_line_views.xml",
        "views/mrp_production_views.xml",
        "views/mrp_bom_views.xml",
        "report/account_move_templates.xml",
        "report/stock_picking_templates.xml",
    ],
    "assets": {
        # Sin assets JS/CSS previstos por la spec.
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
