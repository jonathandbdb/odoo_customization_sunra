# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Completar `location` de las citas de instalacion que ya existen al actualizar a 1.14.0 (D62).

    El core llena `location` con la ubicacion del tipo de cita al crear cada registro
    (`enterprise/appointment/models/appointment_type.py`), y los tipos de instalacion no tienen
    ubicacion, asi que las citas creadas antes de esta version quedan sin ella. La fuente, por
    cita, en orden: (a) `partner_shipping_id` del pedido no cancelado mas viejo que la origino, si
    tiene calle; (b) si no, `appointment_booker_id`, si tiene calle; (c) si no, la cita queda como
    esta. Idempotente (solo toca citas con `location` vacio) y sin nota de seguimiento
    (`mail_notrack`): es completado de datos, no un cambio de un usuario.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    carrier_type_ids = env["delivery.carrier"].with_context(active_test=False).search([
        ("installation_appointment_type_id", "!=", False),
    ]).installation_appointment_type_id.ids
    installation_types = env["appointment.type"].with_context(active_test=False).search([
        "|",
        ("installation_fsm_project_id", "!=", False),
        ("id", "in", carrier_type_ids),
    ])
    if not installation_types:
        return

    events = env["calendar.event"].search([
        ("appointment_type_id", "in", installation_types.ids),
        "|", ("location", "=", False), ("location", "=", ""),
    ])
    if not events:
        return

    lines = env["sale.order.line"].search([
        ("calendar_event_id", "in", events.ids),
        ("state", "!=", "cancel"),
    ], order="id asc")
    partner_by_event = {}
    for line in lines:
        # La primera linea (la mas vieja) gana: un pedido duplicado con la misma cita no pisa el
        # partner del original.
        partner_by_event.setdefault(line.calendar_event_id.id, line.order_id.partner_shipping_id)

    filled = 0
    for event in events:
        partner = partner_by_event.get(event.id)
        if not partner or not partner.street:
            partner = event.appointment_booker_id
        if not partner or not partner.street:
            continue
        event.with_context(mail_notrack=True)._installation_fill_location(partner)
        filled += 1

    _logger.info(
        "website_sale_installation_appointment: %s cita(s) completadas con su direccion de "
        "instalacion.", filled,
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
