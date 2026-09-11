# -*- coding: utf-8 -*-
{
    "name": "website_sale_installment_plans_ux",
    "version": "1.1.0",
    "summary": "Ajusta el texto de cuotas del eCommerce y las mueve dentro del recuadro de precio",
    "description": """
Ajustes de presentacion sobre la leyenda de cuotas que publica
`website_sale_installment_plans` en la ficha y en la grilla del eCommerce.

- Saca el "(Total $...)" del texto: queda solo "En N cuotas de $X".
- Formatea el importe con el formato de la moneda del sitio (separador de miles y
  decimales con coma), igual que el precio que se muestra arriba.
- Toma la cantidad de cuotas del campo Divisor, que es el que representa en cuantas
  cuotas se divide el total.
- Mueve la leyenda de cuotas dentro del recuadro de precio de
  `website_sale_payment_method_price` (slot `wspmp_installments`, dependencia dura
  desde 1.1.0), en vez de dejarla suelta debajo del precio.
    """,
    "category": "Website/Website",
    "author": "Sunra",
    "website": "https://github.com/sunraargsh",
    "license": "LGPL-3",
    "depends": ["website_sale_installment_plans", "website_sale_payment_method_price"],
    "data": [
        "views/website_templates.xml",
    ],
    "assets": {},
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
