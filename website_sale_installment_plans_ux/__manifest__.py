# -*- coding: utf-8 -*-
{
    "name": "website_sale_installment_plans_ux",
    "version": "1.0.0",
    "summary": "Ajusta el texto de cuotas del eCommerce: sin el total y con importes formateados",
    "description": """
Ajustes de presentacion sobre la leyenda de cuotas que publica
`website_sale_installment_plans` en la ficha y en la grilla del eCommerce.

- Saca el "(Total $...)" del texto: queda solo "En N cuotas de $X".
- Formatea el importe con el formato de la moneda del sitio (separador de miles y
  decimales con coma), igual que el precio que se muestra arriba.
- Toma la cantidad de cuotas del campo Divisor, que es el que representa en cuantas
  cuotas se divide el total.
    """,
    "category": "Website/Website",
    "author": "Sunra",
    "website": "https://github.com/sunraargsh",
    "license": "LGPL-3",
    "depends": ["website_sale_installment_plans"],
    "data": [],
    "assets": {},
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
