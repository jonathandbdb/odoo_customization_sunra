# -*- coding: utf-8 -*-
{
    "name": "web_notebook_wrap_fix",
    "version": "1.0.0",
    "summary": "Restaura el corte de linea dentro de las pestanas del backend (regresion de core en Odoo 19)",
    "description": """
Parche de CSS para una regresion del core de Odoo 19.

El commit de core 7d26b3444f61 ("[FIX] web: adjust SCSS for vertical notebook", odoo/odoo#279098,
mergeado a la serie 19.0 el 04/09/2026) movio la regla `white-space: nowrap` de
`.o_notebook .nav-item` (solo las solapas) a `.o_notebook.horizontal` (el notebook entero).
Como `white-space` se hereda, el CONTENIDO de las pestanas dejo de poder cortar linea.

Consecuencia visible: en cualquier pestana que mezcle elementos inline (botones) con un widget
inline-block (una lista x2many), el widget ya no baja a su propio renglon: queda al lado de los
botones y se desborda a la derecha, con scroll horizontal y columnas fuera de pantalla. El caso
reportado es la pestana "Deudas" del formulario de pagos (account_payment_pro).

Este modulo restaura el comportamiento previo: `nowrap` solo en las solapas, contenido con
`white-space: normal`.

Cuando Odoo corrija la regresion en el core, este modulo se puede desinstalar y borrar.
    """,
    "category": "Custom",
    "author": "Sunra",
    "website": "https://github.com/sunraargsh",
    "license": "LGPL-3",
    "depends": ["web"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "web_notebook_wrap_fix/static/src/scss/notebook_wrap.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
