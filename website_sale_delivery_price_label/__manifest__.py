# -*- coding: utf-8 -*-
{
    "name": "website_sale_delivery_price_label",
    "version": "1.0.0",
    "summary": "Texto configurable por método de envío en lugar del precio/\"Gratis\" en el checkout",
    "description": """
Permite reemplazar el precio (o el "Gratis" que muestra el core cuando la tarifa es 0) del badge de
un método de envío en el checkout del eCommerce por un texto configurable.

- Cada método de envío (`delivery.carrier`) gana un campo "Website price label" (traducible).
- Si el campo está cargado, ese texto se muestra en el badge de precio del checkout en lugar del
  precio calculado o de "Gratis" (caso de uso: "A convenir" para un método con instalación).
- Si el campo está vacío, el comportamiento es idéntico al core.
    """,
    "category": "Website/Website",
    "author": "Sunra",
    "website": "https://github.com/sunraargsh",
    "license": "LGPL-3",
    "depends": [
        "website_sale",
    ],
    "data": [
        "views/delivery_carrier_views.xml",
        "views/website_sale_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "website_sale_delivery_price_label/static/src/js/delivery_price_label.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
