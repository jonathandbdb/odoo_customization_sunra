# -*- coding: utf-8 -*-
{
    "name": "website_sale_payment_method_price",
    "version": "1.0.2",
    "summary": "Descuento o recargo por medio de pago en el eCommerce, con segundo precio en la vidriera",
    "description": """
Permite configurar un descuento (o recargo) por **medio de pago** y por **sitio web**, mostrarlo como
un segundo precio debajo del precio de lista y aplicarlo de verdad al pedido en el checkout.

- Cada medio de pago (`payment.method`) gana una pestana "Website" con una linea por sitio: tipo
  (descuento/recargo), porcentaje, sobre que aplica (productos / envios / ambos), redondeo y si el
  precio se muestra en el sitio.
- En la grilla del shop, la ficha del producto y el carrito aparece "$X con TRANSFERENCIA" debajo del
  precio, con el ajuste y el redondeo ya aplicados.
- Al elegir el medio de pago en el checkout, el descuento se aplica al pedido como linea con su IVA
  (reusa el descuento global del core, que lo parte por combinacion de impuestos) y se cae solo si el
  cliente cambia de medio.
- El redondeo espeja la semantica de `price_round` del core: multiplo, al mas cercano, aplicado
  despues del porcentaje.
    """,
    "category": "Website/Website",
    "author": "Sunra",
    "website": "https://github.com/sunraargsh",
    "license": "LGPL-3",
    "depends": [
        "website_sale",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/payment_method_views.xml",
        "views/website_sale_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "website_sale_payment_method_price/static/src/scss/payment_method_price.scss",
            "website_sale_payment_method_price/static/src/js/payment_method_price.js",
            "website_sale_payment_method_price/static/src/js/payment_form_price.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
