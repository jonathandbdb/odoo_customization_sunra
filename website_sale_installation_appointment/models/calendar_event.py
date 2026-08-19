# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Estados cerrados de project.task (odoo/addons/project/models/project_task.py CLOSED_STATES).
TASK_CLOSED_STATES = ("1_done", "1_canceled")


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    installation_task_id = fields.Many2one(
        comodel_name="project.task",
        string="Installation Task",
        copy=False,
        index="btree_not_null",
        ondelete="set null",
        help="Field Service task generated for an installation booked outside the eCommerce.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        events = super().create(vals_list)
        for event in events:
            if not event.appointment_type_id.installation_fsm_project_id:
                continue
            try:
                with self.env.cr.savepoint():
                    event._installation_generate_fsm_task()
            except Exception:
                # La reserva del cliente ya esta hecha: un fallo generando la tarea (proyecto mal
                # configurado, permisos, datos raros) no puede traducirse en un error para el. Se
                # loguea para que el backoffice la cree a mano.
                _logger.warning(
                    "website_sale_installation_appointment: no se pudo generar la tarea FSM de la "
                    "cita %s", event.id, exc_info=True,
                )
        return events

    def write(self, vals):
        """Mantener la tarea del instalador en linea con la cita (reprogramar / cancelar)."""
        installation_events = self.filtered("installation_task_id")
        previously_active = (
            {event.id: event.active for event in installation_events} if "active" in vals else {}
        )

        res = super().write(vals)

        if "active" in vals and installation_events:
            for event in installation_events:
                was_active = previously_active.get(event.id)
                if not vals["active"] and was_active:
                    event._installation_cancel_task()
                elif vals["active"] and not was_active:
                    event._installation_restore_task()

        if installation_events and ("start" in vals or "stop" in vals):
            for event in installation_events.filtered("active"):
                task = event.installation_task_id.sudo()
                if task.state not in TASK_CLOSED_STATES:
                    # Los dos campos en el MISMO write: project_enterprise tiene el constraint SQL
                    # _planned_dates_check (planned_date_begin <= date_deadline).
                    task.write({"planned_date_begin": event.start, "date_deadline": event.stop})
        return res

    def _installation_generate_fsm_task(self):
        """Crear la tarea de Field Service de una instalacion agendada FUERA del eCommerce.

        En el circuito web la tarea la genera `sale_project` cuando se paga el pedido. Cuando Nokey
        comparte el link de la agenda (el cliente paga por fuera) no hay venta, asi que la visita no
        existiria para la cuadrilla: se crea aca con la fecha, el cliente, la direccion y las
        respuestas del formulario.

        :return: la tarea creada, o None
        :rtype: project.task | None
        """
        self.ensure_one()
        project = self.appointment_type_id.installation_fsm_project_id
        if not project or self.installation_task_id:
            return None
        customer = self.appointment_booker_id or self.partner_ids[:1]
        task = self.env["project.task"].sudo().create({
            "name": _("Installation - %(customer)s", customer=customer.display_name or self.name),
            "project_id": project.id,
            "partner_id": customer.id or False,
            "planned_date_begin": self.start,
            "date_deadline": self.stop,
            "description": self.description,
            # Explicito: el create de project.task deja como asignado al uid actual, que aca es el
            # usuario publico que agendo. El despacho lo hace el backoffice.
            "user_ids": [(6, 0, [])],
        })
        self.sudo().installation_task_id = task.id
        return task

    def _installation_cancel_task(self):
        """Cancelar la tarea del instalador cuando el cliente cancela la cita."""
        self.ensure_one()
        task = self.installation_task_id.sudo()
        if task and task.state not in TASK_CLOSED_STATES:
            task.write({"state": "1_canceled"})
            task.message_post(body=_("The customer cancelled the installation appointment."))

    def _installation_restore_task(self):
        """Reponer la tarea si la cita se desarchiva."""
        self.ensure_one()
        task = self.installation_task_id.sudo()
        if task and task.state == "1_canceled":
            task.write({
                "state": "01_in_progress",
                "planned_date_begin": self.start,
                "date_deadline": self.stop,
            })

    def _installation_post_photos(self, attachments):
        """Dejar las fotos del lugar en la cita y en la tarea del instalador.

        :param attachments: ir.attachment ya creados (sudo)
        """
        self.ensure_one()
        if not attachments:
            return
        body = _("Photos of the installation site sent by the customer.")
        # message_post REASIGNA los adjuntos al registro, asi que las originales van a la cita y la
        # tarea recibe copias (si no, se las llevaria el ultimo destino).
        self.sudo().message_post(body=body, attachment_ids=attachments.ids)
        task = self.installation_task_id.sudo()
        if task:
            copies = [
                attachment.copy({"res_model": "mail.compose.message", "res_id": 0}).id
                for attachment in attachments.sudo()
            ]
            task.message_post(body=body, attachment_ids=copies)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
