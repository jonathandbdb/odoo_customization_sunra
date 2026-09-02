# -*- coding: utf-8 -*-
{
    "name": "website_currency_rate_header",
    "version": "1.0.0",
    "summary": "Muestra la cotizacion de una moneda en el encabezado del sitio",
    "description": """
Muestra en el encabezado del sitio web la cotizacion vigente de una moneda (tipicamente el dolar)
expresada en la moneda de la compania.

- Pensado para catalogos con precios de lista en dolares que se facturan en pesos: el cliente ve
  con que cotizacion esta mirando los precios y entiende que al facturar puede variar.
- Se activa por sitio web y se elige en que moneda se expresa la cotizacion (con la compania
  en dolares y ARS elegido, muestra los pesos por dolar).
- Se apoya en el tipo de cambio estandar de Odoo (res.currency), asi que funciona con cualquier
  origen de cotizacion (carga manual o sincronizacion automatica).
- Se engancha en el placeholder de encabezado del core, por lo que sigue apareciendo aunque se
  cambie el estilo de encabezado del sitio.
    """,
    "category": "Website/Website",
    "author": "Sunra",
    "website": "https://github.com/sunraargsh",
    "license": "LGPL-3",
    "depends": [
        "website",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "views/website_templates.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
