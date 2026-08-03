# -*- coding: utf-8 -*-
{
    "name": "helpdesk_service_appointment",
    "version": "1.0.3",
    "summary": "Service/reparacion de cerraduras instaladas: portal -> ticket Helpdesk -> cita -> tarea FSM",
    "description": """
Permite que un cliente de Sunra pida service/reparacion de una cerradura ya instalada desde el
portal, sin pasar por el eCommerce.

- Formulario de portal (/my/service/new) que reemplaza al JotForm "Agendar service con Nokey":
  selecciona su cerradura entre las entregadas, describe la falla, sube fotos opcionales y agenda
  la visita sobre la disponibilidad real del tecnico (pagina nativa de Citas).
- El pedido queda como ticket de Helpdesk (team Service) y la cita agendada genera la tarea de
  Field Service, con fecha, direccion de la visita, fotos y el estado de garantia (informativo)
  calculado desde las entregas del cliente (sin numeros de serie).
- El agendado es siempre gratis: la garantia nunca bloquea el flujo, se presupuesta despues de la
  visita.
- No crea modelos nuevos: extiende product.product, helpdesk.ticket, calendar.event, project.task
  y el wizard helpdesk.create.fsm.task.
    """,
    "category": "Website/Website",
    "author": "Sunra",
    "website": "https://github.com/sunraargsh",
    "license": "LGPL-3",
    "depends": [
        "helpdesk_fsm",
        "helpdesk_stock",
        "website_appointment",
        "sk_customer_product_warranty",
    ],
    "data": [
        "data/helpdesk_service_appointment_data.xml",
        "views/helpdesk_ticket_views.xml",
        "views/product_views.xml",
        "views/project_task_views.xml",
        "views/helpdesk_service_appointment_templates.xml",
    ],
    "assets": {},
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
