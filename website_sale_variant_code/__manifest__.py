# -*- coding: utf-8 -*-
{
    "name": "website_sale_variant_code",
    "version": "1.2.0",
    "summary": "eCommerce: muestra el codigo interno de la variante elegida, no el de todas",
    "description": """
Muestra en el eCommerce el codigo interno (referencia interna) de la variante que el cliente esta
mirando, en lugar de una leyenda fija con los codigos de todas las variantes.

- En la pagina de producto el codigo aparece debajo del titulo y cambia al elegir otra variante
  (ej. Delantero -> V8M-070, Trasero -> V8M-071).
- En el carrito cada linea muestra el codigo de su propia variante.
- Incluye la limpieza de las leyendas "Cod: ..." que se cargaban a mano en las descripciones del
  producto, que quedaban desactualizadas y no distinguian variantes (ver README.md).
- Ajuste por sitio web para ocultar la descripcion de venta en el carrito, donde repetia el codigo
  que ya se muestra en cada linea. El valor no se borra: sigue disponible para la busqueda del
  sitio y para el PDF de la cotizacion.
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
        "views/website_sale_variant_code_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "website_sale_variant_code/static/src/js/*.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
