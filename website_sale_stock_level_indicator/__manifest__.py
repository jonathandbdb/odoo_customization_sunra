# -*- coding: utf-8 -*-
{
    "name": "website_sale_stock_level_indicator",
    "version": "1.0.0",
    "summary": "eCommerce: semaforo de stock con niveles configurables por sitio web",
    "description": """
Muestra en el eCommerce un cartel con el nivel de stock del producto (sin stock, poco stock, stock
normal, stock alto) en el listado de la tienda y en la pagina de producto.

- Los niveles se configuran por sitio web: texto, color y cantidad a partir de la cual aplica.
- La cantidad de niveles es libre: se pueden usar cuatro, dos o siete, y agregar mas mas adelante
  sin tocar codigo.
- El texto de cada nivel es traducible, asi que se puede decir "Poco stock" o lo que use el
  negocio.
- La disponibilidad se mide con el deposito del sitio, igual que el resto del eCommerce.
- El core solo trae dos estados (sin stock y un umbral), y en el listado no muestra nada.
    """,
    "category": "Website/Website",
    "author": "Sunra",
    "website": "https://github.com/sunraargsh",
    "license": "LGPL-3",
    "depends": [
        "website_sale_stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/website_stock_level_views.xml",
        "views/res_config_settings_views.xml",
        "views/website_sale_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "website_sale_stock_level_indicator/static/src/js/*.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
