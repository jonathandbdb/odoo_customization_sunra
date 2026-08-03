# -*- coding: utf-8 -*-
import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.tools.misc import format_datetime

_logger = logging.getLogger(__name__)

# Claves de contexto del create() nativo del evento (controller de Citas) que NO deben
# heredarse al instanciar el wizard FSM: si se heredan, la tarea nace sin followers ni mensaje
# de creacion y potencialmente en la compania del staff de la cita, no del ticket (ver nota de
# implementacion "Contexto limpio al crear la tarea" en la spec).
APPOINTMENT_CONTEXT_KEYS_TO_DROP = frozenset({
    "mail_notify_author",
    "mail_create_nolog",
    "mail_create_nosubscribe",
    "skip_contact_description",
    "allowed_company_ids",
})

# Estados cerrados de project.task (ver odoo/addons/project/models/project_task.py CLOSED_STATES).
TASK_CLOSED_STATES = ("1_done", "1_canceled")


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    service_ticket_id = fields.Many2one(
        "helpdesk.ticket", string="Service Ticket", copy=False, index=True,
        ondelete="set null",
        help="Set by the Appointments submit hook when the customer schedules a service "
             "visit for this ticket.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        events = super().create(vals_list)
        for event in events.filtered("service_ticket_id"):
            try:
                with self.env.cr.savepoint():
                    event._service_generate_fsm_task()
            except Exception:
                # El cliente ya reservo su lugar cuando se creo el evento: un fallo al generar
                # la tarea (team mal configurado, permisos, datos raros) no debe traducirse en
                # un error para el (D15). Se deja nota en el chatter del ticket para que el
                # backoffice lo resuelva.
                _logger.warning(
                    "helpdesk_service_appointment: no se pudo generar la tarea de service "
                    "para el ticket %s (evento %s)",
                    event.service_ticket_id.id, event.id, exc_info=True,
                )
                event.service_ticket_id.sudo().message_post(body=_(
                    "The Field Service task for this appointment could not be created "
                    "automatically. Please create it manually."
                ))
        return events

    def write(self, vals):
        """Mantener coherente la tarea FSM cuando la cita se reagenda, cancela o repone."""
        service_events = self.filtered("service_ticket_id")
        # Capturar el estado PREVIO (antes de delegar, fix post-review m4): un write redundante
        # de active=True (ya estaba activo) o active=False (ya estaba archivado) no debe volver
        # a disparar cancelar/reponer tareas.
        previously_active = (
            {event.id: event.active for event in service_events} if "active" in vals else {}
        )

        res = super().write(vals)

        if "active" in vals and service_events:
            if not vals["active"]:
                # Cancelacion portal via action_cancel_meeting -> action_archive (D17): solo para
                # los eventos que realmente ESTABAN activos antes de este write.
                for event in service_events:
                    if previously_active.get(event.id):
                        event._service_cancel_tasks()
            else:
                # Unarchive: reponer la ultima tarea cancelada del ticket (D18): solo para los
                # eventos que realmente ESTABAN inactivos antes de este write.
                for event in service_events:
                    if not previously_active.get(event.id):
                        event._service_restore_tasks()

        if service_events and ("start" in vals or "stop" in vals):
            for event in service_events.filtered("active"):
                event._service_sync_task_dates()

        return res

    def _service_generate_fsm_task(self):
        """Crear la tarea FSM del ticket con la fecha de la cita, reusando el wizard nativo
        helpdesk.create.fsm.task (D14).

        :return: project.task creada, o None si no hay ticket o no hay proyecto FSM
        """
        self.ensure_one()
        ticket = self.service_ticket_id.sudo()
        if not ticket:
            return None
        project = ticket.team_id.fsm_project_id
        if not project:
            # Sin proyecto FSM no se genera tarea; se deja nota, el cliente no ve un error
            # (D15/D29: es configuracion funcional, no semilla).
            ticket.message_post(body=_(
                "No Field Service task was created: the %(team)s team has no Field Service "
                "project configured.", team=ticket.team_id.display_name,
            ))
            return None

        clean_context = {
            key: value for key, value in self.env.context.items()
            if key not in APPOINTMENT_CONTEXT_KEYS_TO_DROP
        }
        clean_context["hsa_from_appointment"] = True
        wizard = self.env["helpdesk.create.fsm.task"].sudo().with_context(clean_context).create({
            "helpdesk_ticket_id": ticket.id,
            "name": ticket.name,
            "project_id": project.id,
            "partner_id": (ticket.service_visit_address_id or ticket.partner_id).id,
        })
        task = wizard.action_generate_task()
        # Los dos campos de fecha en el MISMO write: project_enterprise tiene el constraint SQL
        # _planned_dates_check (planned_date_begin <= date_deadline); escribirlos por separado
        # puede violarlo contra el valor viejo del otro campo.
        # user_ids en el mismo write (D35): el create de project.task deja como asignado al uid
        # actual, que aca es el CLIENTE PORTAL que agendo (sudo no cambia el uid). Se pisa con el
        # tecnico de la cita (organizador del evento) y, si la cita se agenda por recursos y no hay
        # usuario, se deja SIN asignar para que el despacho lo resuelva el backoffice.
        task.write({
            "planned_date_begin": self.start,
            "date_deadline": self.stop,
            "user_ids": [(6, 0, self._service_task_assignee_ids())],
        })
        ticket._post_service_photos(task)
        ticket.message_post(body=self._service_scheduled_message())
        return task

    def _service_task_assignee_ids(self):
        """Tecnico al que se asigna la tarea FSM del service (D35).

        Solo las citas agendadas **por usuarios** traen al tecnico que eligio el cliente en el
        organizador del evento: en las citas por **recursos** el nativo pone el `create_uid` del
        tipo de cita (ver `appointment.type._prepare_calendar_event_values`), que no es quien va a
        la visita. Sin tecnico asignable la tarea queda sin asignar y el despacho lo resuelve el
        backoffice.

        :return: ids de ``res.users`` para el ``user_ids`` de la tarea
        :rtype: list
        """
        self.ensure_one()
        if self.appointment_type_id.schedule_based_on != "users":
            return []
        staff = self.user_id
        # user_ids de project.task exige share=False: nunca el cliente portal ni el usuario publico.
        return staff.ids if staff and not staff.sudo().share else []

    def _service_scheduled_message(self):
        """Mensaje HTML para el chatter del ticket al agendar (fix post-review, M4): la fecha se
        formatea en la tz del cliente (no UTC crudo) y se agrega el link al evento
        (``/calendar/view/<access_token>``) que la spec pide.
        """
        self.ensure_one()
        ticket = self.service_ticket_id.sudo()
        partner_tz = ticket.partner_id.tz or self.env.context.get("tz") or "UTC"
        formatted_date = format_datetime(self.env, self.start, tz=partner_tz, dt_format="medium")
        sentence = Markup("%s ") % _("Service visit scheduled for %(date)s.", date=formatted_date)
        link = Markup('<a href="/calendar/view/%s">%s</a>') % (
            self.access_token, _("View appointment"),
        )
        return sentence + link

    def _service_cancel_tasks(self):
        """Cancelar las tareas FSM no cerradas del ticket cuando la cita se archiva (D17)."""
        self.ensure_one()
        ticket = self.service_ticket_id.sudo()
        if not ticket:
            return
        open_tasks = ticket.fsm_task_ids.filtered(lambda task: task.state not in TASK_CLOSED_STATES)
        if not open_tasks:
            return
        open_tasks.sudo().write({"state": "1_canceled"})
        ticket.message_post(body=_(
            "Service appointment cancelled: the related Field Service task(s) were cancelled."
        ))

    def _service_restore_tasks(self):
        """Reponer la ultima tarea cancelada del ticket cuando la cita se desarchiva (D18)."""
        self.ensure_one()
        ticket = self.service_ticket_id.sudo()
        if not ticket:
            return
        # Guard: si el ticket ya tiene OTRO evento activo o una tarea FSM abierta, no reponer
        # la cancelada. Evita que un rebooking (D18/D34) deje el ticket con 2 citas o 2 tareas
        # simultaneas cuando el evento viejo se desarchiva por error o manualmente.
        other_active_events = ticket.service_event_ids - self
        has_open_task = any(task.state not in TASK_CLOSED_STATES for task in ticket.fsm_task_ids)
        if other_active_events or has_open_task:
            return
        last_cancelled = ticket.fsm_task_ids.filtered(
            lambda task: task.state == "1_canceled"
        ).sorted("id")[-1:]
        if not last_cancelled:
            return
        last_cancelled.sudo().write({
            "state": "01_in_progress",
            "planned_date_begin": self.start,
            "date_deadline": self.stop,
        })
        ticket.message_post(body=_(
            "Service appointment re-scheduled: the Field Service task was reopened."
        ))

    def _service_sync_task_dates(self):
        """Sincronizar planned_date_begin/date_deadline de las tareas FSM abiertas del ticket
        con las fechas de la cita (D19: sync de una sola via, evento -> tarea).
        """
        self.ensure_one()
        ticket = self.service_ticket_id.sudo()
        if not ticket:
            return
        open_tasks = ticket.fsm_task_ids.filtered(lambda task: task.state not in TASK_CLOSED_STATES)
        for task in open_tasks:
            # Los dos campos en el MISMO write: constraint _planned_dates_check.
            task.sudo().write({"planned_date_begin": self.start, "date_deadline": self.stop})

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
