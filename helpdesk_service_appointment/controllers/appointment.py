# -*- coding: utf-8 -*-
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from werkzeug.urls import url_encode

from odoo.addons.appointment.controllers.appointment import AppointmentController
from odoo.addons.appointment.controllers.calendar import AppointmentCalendarController
from odoo.http import request, route


class HelpdeskServiceAppointmentController(AppointmentController):
    """Override de _get_extra_calendar_event_params: materializa el vinculo cita <-> ticket
    en el create() del calendar.event (D13). No es una ruta HTTP: es el hook que el
    controller nativo de Citas ya llama antes de crear el evento.
    """

    def _get_extra_calendar_event_params(self, **kwargs):
        res = super()._get_extra_calendar_event_params(**kwargs)
        try:
            ticket_id = int(kwargs.get("service_ticket_id"))
        except (TypeError, ValueError):
            # No vino el param, o no es un entero: no-op, la cita se crea sin vinculo.
            return res

        ticket_sudo = request.env["helpdesk.ticket"].sudo().browse(ticket_id).exists()
        if not ticket_sudo:
            return res

        # Anti-IDOR: el commercial partner del ticket debe coincidir con el del usuario
        # logueado, salvo que sea un usuario interno agendando en nombre de un cliente.
        user = request.env.user
        if user.share and ticket_sudo.partner_id.commercial_partner_id != user.partner_id.commercial_partner_id:
            return res

        # Anti-doble-agendado (D16): un ticket con evento activo no puede agendar otro.
        if ticket_sudo.service_event_id:
            return res

        res["service_ticket_id"] = ticket_sudo.id
        return res


class HelpdeskServiceAppointmentCalendarController(AppointmentCalendarController):
    """Override de appointment_cancel: reinyecta service_ticket_id en la URL de vuelta para
    que el reagendado del cliente tras cancelar no genere una cita huerfana (D34). El nativo
    redirige a ``invite.redirect_url + '&state=cancel'``, que no lleva service_ticket_id.
    """

    @route()
    def appointment_cancel(self, access_token, partner_id=False, **kwargs):
        # Resolver el evento por access_token ANTES de delegar: el nativo lo archiva en el
        # mismo paso (D17), y una vez archivado el o2m de service_event_ids ya no lo veria.
        event_sudo = request.env["calendar.event"].sudo().search(
            [("access_token", "=", access_token)], limit=1,
        )
        ticket_id = event_sudo.service_ticket_id.id if event_sudo else False

        response = super().appointment_cancel(access_token, partner_id=partner_id, **kwargs)

        if not ticket_id:
            # No es una cita de service: no-op.
            return response

        # Solo se enriquecen redirects (3xx con Location); cualquier otra respuesta nativa
        # (ej. not_found) se devuelve intacta. Degradacion deliberada: en el peor caso, el
        # rebooking del cliente nace huerfano (comportamiento actual), nunca un error.
        status_code = getattr(response, "status_code", None)
        location = response.headers.get("Location") if hasattr(response, "headers") else None
        if not status_code or not (300 <= status_code < 400) or not location:
            return response

        url_parts = urlsplit(location)
        query_params = dict(parse_qsl(url_parts.query, keep_blank_values=True))
        if "service_ticket_id" in query_params:
            return response

        query_params["service_ticket_id"] = ticket_id
        new_location = urlunsplit(url_parts._replace(query=url_encode(query_params)))
        response.headers["Location"] = new_location
        return response

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
