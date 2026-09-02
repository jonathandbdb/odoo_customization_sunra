# -*- coding: utf-8 -*-
{
    "name": "website_sale_wire_transfer_ux",
    "version": "1.0.0",
    "summary": "Boton para copiar el CBU y link para cambiar de medio de pago en la confirmacion del eCommerce",
    "description": """
Mejoras de usabilidad en la pagina de confirmacion del eCommerce cuando el cliente elige
**Transferencia bancaria** y el pago queda pendiente.

- **Copiar CBU**: boton que copia el CBU al portapapeles. El numero sale de la cuenta bancaria de la
  compania (`res.partner.bank` con `acc_type = 'cbu'`, el tipo que agrega la localizacion argentina),
  nunca del texto libre del mensaje pendiente: asi el boton no puede copiar un dato desactualizado.
  Un boton pegado dentro del campo "Mensaje pendiente" no puede funcionar, porque ese campo es HTML
  sanitizado y Odoo le borra los botones y el JavaScript.
- **Cambiar medio de pago**: link que reabre el paso de pago del checkout para elegir otro medio
  (por ejemplo Mercado Pago). El core no ofrece vuelta atras: tras la transferencia el pedido queda
  en presupuesto enviado y la sesion pierde el carrito.
- **Datos de la transferencia en el mail** de orden pendiente (mensaje pendiente + CBU +
  Comunicacion), que el mail del core no lleva.

Requiere la **localizacion argentina** (`l10n_ar`) instalada: de ella sale el tipo de cuenta `cbu`
que identifica cual de las cuentas bancarias de la compania es el CBU. Sin ella el modulo instala
igual pero el boton no tiene numero que copiar (queda avisado en el log al instalar).
    """,
    "category": "Website/Website",
    "author": "Sunra",
    "website": "https://github.com/sunraargsh",
    "license": "LGPL-3",
    "depends": [
        "website_sale",
        "payment_custom",
    ],
    "data": [
        "views/website_sale_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "website_sale_wire_transfer_ux/static/src/js/wire_transfer_confirmation.js",
        ],
    },
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
