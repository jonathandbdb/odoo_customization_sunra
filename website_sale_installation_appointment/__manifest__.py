# -*- coding: utf-8 -*-
{
    "name": "website_sale_installation_appointment",
    "version": "1.13.0",
    "summary": "Envio con instalacion en el eCommerce: agenda la cita y pide fotos del lugar en el checkout",
    "description": """
Permite vender un envio "con instalacion incluida" desde el eCommerce y que esa venta quede agendada
como Cita (app Citas), con las fotos del lugar y los datos que cargo el cliente.

- El metodo de envio (delivery.carrier) puede exigir agendar una instalacion: se le asocia un tipo de
  cita y una cantidad minima de fotos.
- Si el cliente elige ese metodo de envio, el checkout agrega un paso "Instalacion" (si elige el
  envio normal, el paso no aparece).
- El paso "Instalacion" se organiza en 3 bloques tipo acordeon que se habilitan de a uno: direccion
  de instalacion (con "entre calles" e indicaciones para el instalador), turno y fotos, y pago.
- En el segundo bloque el cliente agenda dia y hora sobre la disponibilidad real de la cuadrilla
  (reutiliza la pagina nativa de Citas y su control de capacidad) y sube las fotos del lugar de
  instalacion, guiado por una guia visual con ejemplos de fotos correctas e incorrectas. El
  formulario de la cita NO le vuelve a pedir lo que ya cargo en el checkout: ni nombre, ni correo,
  ni las fotos.
- Los tipos de cita que se agendan FUERA del eCommerce (el link que comparte Nokey) pueden pedir la
  direccion de instalacion en el propio formulario: sin eso la tarea del instalador queda sin lugar
  al que ir.
- Al confirmarse/pagarse el pedido, el mecanismo nativo (website_appointment_sale) convierte la
  reserva en Cita y este modulo copia las fotos a la Cita y a la tarea de Field Service, con las
  indicaciones del cliente en la descripcion de la tarea.
- El metodo de envio tambien puede incluir sin cargo las pilas que necesitan los productos del
  carrito (configurables en la ficha del producto): se agrega automaticamente la linea a $0,
  sincronizada en el carrito web, en el backend y al confirmar.
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
        "views/product_template_views.xml",
        "views/res_partner_views.xml",
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
            "website_sale_installation_appointment/static/src/scss/installation_form.scss",
        ],
    },
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
