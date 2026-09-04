# -*- coding: utf-8 -*-
{
    "name": "website_sale_installation_appointment",
    "version": "1.7.0",
    "summary": "Envio con instalacion en el eCommerce: agenda la cita y pide fotos del lugar en el checkout",
    "description": """
Permite vender un envio "con instalacion incluida" desde el eCommerce y que esa venta quede agendada
como Cita (app Citas), con las fotos del lugar y los datos que cargo el cliente.

- El metodo de envio (delivery.carrier) puede exigir agendar una instalacion: se le asocia un tipo de
  cita y una cantidad minima de fotos.
- Si el cliente elige ese metodo de envio, el checkout agrega un paso "Instalacion" (si elige el
  envio normal, el paso no aparece).
- En ese paso el cliente agenda dia y hora sobre la disponibilidad real de la cuadrilla (reutiliza la
  pagina nativa de Citas y su control de capacidad) y sube las fotos del lugar de instalacion.
- Al confirmarse/pagarse el pedido, el mecanismo nativo (website_appointment_sale) convierte la
  reserva en Cita y este modulo copia las fotos a la Cita y a la tarea de Field Service.
    """,
    "category": "Website/Website",
    "author": "Sunra",
    "website": "https://github.com/sunraargsh",
    "license": "LGPL-3",
    "depends": [
        "website_sale",
        "delivery",
        "website_appointment_sale",
        "sale_project",
    ],
    "data": [
        "data/website_checkout_step_data.xml",
        "views/delivery_carrier_views.xml",
        "views/sale_order_views.xml",
        "views/website_sale_installation_templates.xml",
        "views/website_sale_templates.xml",
        "views/appointment_type_views.xml",
        "views/appointment_question_views.xml",
        "views/appointment_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "website_sale_installation_appointment/static/src/js/installation_photos.js",
        ],
    },
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
