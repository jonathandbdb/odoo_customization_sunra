# -*- coding: utf-8 -*-
{
    "name": "website_sale_bike_assembly_option",
    "version": "1.0.0",
    "summary": "Selector Armada / En caja en la ficha web de la bicicleta, con el kit al precio de la armada",
    "description": """
Cada bicicleta electrica existe como producto armado y como kit en caja, unidos por la LdM de
fabricacion marcada con "traer componentes del kit". Este modulo agrega a la ficha web un selector
Armada / En caja.

- Con "En caja" el carrito recibe el kit, al mismo precio que el vehículo armado en la lista de
  precios del sitio. El kit no necesita estar publicado.
- La disponibilidad web de la armada suma el stock libre de su kit.
- El kit se vende por la compañia de la bicicleta si no tiene configuracion propia.
- La linea del pedido muestra la bicicleta asociada al kit.
    """,
    "category": "Website/Website",
    "author": "Sunra",
    "website": "https://github.com/sunraargsh",
    "license": "LGPL-3",
    "depends": [
        "sale_website_company_routing",
        "sunra_mrp_component_serials",
    ],
    "data": [
        "views/website_sale_templates.xml",
        "views/sale_order_views.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "website_sale_bike_assembly_option/static/src/interactions/website_sale.js",
            "website_sale_bike_assembly_option/static/src/js/configurator_props_patch.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
