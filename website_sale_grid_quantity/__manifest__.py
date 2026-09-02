# -*- coding: utf-8 -*-
{
    "name": "website_sale_grid_quantity",
    "version": "1.0.0",
    "summary": "eCommerce: elegir la cantidad desde el listado, sin entrar al producto",
    "description": """
Agrega los botones de mas y menos con la cantidad en cada tarjeta del listado de la tienda, para
que el cliente cargue varias unidades sin entrar y salir de cada producto.

- Pensado para venta de repuestos a concesionarios, donde un pedido son 10 o 15 articulos
  distintos y entrar a la ficha de cada uno vuelve la carga inviable.
- Se activa por sitio web: un sitio B2B lo puede tener prendido y el B2C apagado.
- No agrega JavaScript propio: reutiliza el manejador de cantidad y el alta al carrito del core.
    """,
    "category": "Website/Website",
    "author": "Sunra",
    "website": "https://github.com/sunraargsh",
    "license": "LGPL-3",
    "depends": [
        "website_sale",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "views/website_sale_templates.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
