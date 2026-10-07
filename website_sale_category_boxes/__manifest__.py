# -*- coding: utf-8 -*-
{
    "name": "website_sale_category_boxes",
    "version": "1.0.0",
    "summary": "Categorías de la tienda en formato cajas, configurable por sitio web",
    "description": """
Muestra las categorías del lateral de la tienda web (/shop) en cajas desplegables.

- Se activa por sitio web desde Ajustes de eCommerce
- Usa el color principal del tema de cada sitio
    """,
    "category": "Website/Website",
    "author": "Sunra",
    "website": "https://github.com/sunraargsh",
    "license": "LGPL-3",
    "depends": ["website_sale"],
    "data": [
        "views/res_config_settings_views.xml",
        "views/website_sale_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "website_sale_category_boxes/static/src/scss/category_boxes.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
