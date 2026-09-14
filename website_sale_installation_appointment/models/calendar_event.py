# -*- coding: utf-8 -*-
import logging

from markupsafe import Markup

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

    # === MULTI-COMPANY BRANDING DEL CORREO (D43) === #

    def _mail_get_companies(self, default=False):
        """Override: resolvedor de la compania "dueña" de la cita, para el correo y para el fix.

        No influye en el logo/colores del layout (eso lo resuelve
        `_notify_by_email_prepare_rendering_context()`, ver mas abajo): este metodo solo pisa
        `record_company_id` del `mail.message`, el alias domain del reply-to y el Return-Path
        (`odoo/addons/mail/models/mail_thread.py:2831`, dentro de `message_notify`). Se reusa como
        resolvedor unico de "que compania es esta cita" para no duplicar la logica.

        Orden de resolucion: compania del pedido de venta que origino la cita (el primero, por
        `id`, entre los no cancelados — un pedido duplicado copia `calendar_event_id` sin
        `copy=False`, `enterprise/website_appointment_sale/models/sale_order_line.py:L11`) >
        compania del organizador (`user_id.company_id`) > compania de quien creo la cita
        (`create_uid.company_id`, mismo heuristico que usa el propio core para citas sin usuario,
        `odoo/addons/calendar/controllers/main.py:L66`) > lo que resuelva el `super()` con el
        `default` recibido.

        :param default: ver `mail.thread._mail_get_companies`
        :return: {event.id: res.company} para todos los ids de self
        :rtype: dict
        """
        companies = super()._mail_get_companies(default=default)
        if not self:
            return companies
        # sudo(): el cron de alarmas (o el request del checkout) puede no tener acceso de lectura
        # al pedido (otra compañia). El metodo soporta lote (una sola busqueda para todo self),
        # aunque el camino real de notificacion (`_notify_attendees`) llama evento por evento.
        lines = self.env["sale.order.line"].sudo().search([
            ("calendar_event_id", "in", self.ids),
            ("state", "!=", "cancel"),
        ], order="id asc")
        order_company_by_event = {}
        for line in lines:
            # La primera linea (la mas vieja) gana: un pedido duplicado con la misma cita no debe
            # pisar la compania del original.
            if line.order_id.company_id:
                order_company_by_event.setdefault(line.calendar_event_id.id, line.order_id.company_id)
        for event in self:
            if event.id in order_company_by_event:
                companies[event.id] = order_company_by_event[event.id]
            elif event.user_id.company_id:
                companies[event.id] = event.user_id.company_id
            elif event.create_uid.company_id:
                companies[event.id] = event.create_uid.company_id
        return companies

    def _notify_by_email_prepare_rendering_context(self, message, msg_vals=False, model_description=False,
                                                   force_email_company=False, force_email_lang=False,
                                                   force_record_name=False):
        """Override: la compania que pinta el logo/colores del layout de notificacion (D43).

        Este SI es el hook que importa: el core arma `render_context['company']` leyendo
        `record.company_id` **directo** (`odoo/addons/mail/models/mail_thread.py:3657-3666`), y
        como `calendar.event` no tiene ese campo, siempre cae en `env.company` — la compania de
        quien **dispara la notificacion**, no la del cliente. La confirmacion de la cita
        (`enterprise/appointment/models/calendar_attendee.py:L37-44` → `_notify_attendees` →
        `odoo/addons/calendar/models/calendar_attendee.py:L196`, el mismo camino que el
        recordatorio) sale bien porque corre dentro del **request web** del checkout, donde
        `env.company` ya es la del sitio/cliente; el recordatorio sale mal porque lo dispara el
        **cron** de alarmas (`odoo/addons/calendar/models/calendar_alarm_manager.py:L198`), cuyo
        `env.company` es la del usuario tecnico del cron. La causa raiz es esa asimetria de
        `env.company` entre el request y el cron, no (solo) la ausencia de `company_id`.

        Reusa `_mail_get_companies()` como resolvedor unico (no se duplica la logica de "que
        compania es esta cita"). Si el llamador ya fuerza una compania (`force_email_company`), no
        se toca. Molde de override (llamar a `super()` y pisar claves del dict que devuelve):
        `odoo/addons/sale/models/sale_order.py:L1758`, `odoo/addons/project/models/project_task.py:L1506`,
        `odoo/addons/crm/models/crm_lead.py:L2103` (esos overridean `subtitles`; el patron de
        llamada es el mismo).
        """
        render_context = super()._notify_by_email_prepare_rendering_context(
            message, msg_vals=msg_vals, model_description=model_description,
            force_email_company=force_email_company, force_email_lang=force_email_lang,
            force_record_name=force_record_name,
        )
        if force_email_company or not self:
            return render_context
        company = self._mail_get_companies(default=render_context["company"])[self.id]
        if company != render_context["company"]:
            # `.sudo()` igual que el core (`odoo/addons/mail/models/mail_thread.py:L3660`): QWeb va
            # a leer `company.name` / `uses_default_logo` / colores, y `res.company` tiene reglas
            # por grupo que acotan la lectura a las compañias del usuario
            # (`odoo/odoo/addons/base/security/base_security.xml:L105-125`). Sin el sudo, un
            # empleado que postea en el chatter de una cita de OTRA compañia (caso real: cita por
            # link compartido, sin pedido, con organizador de la otra compañia) se comeria un
            # AccessError al renderizar la notificacion.
            render_context["company"] = company.sudo()
            # El footer deriva el link del sitio de la compania resuelta: mismo calculo que el
            # core (`odoo/addons/mail/models/mail_thread.py:L3663-3666`), para que no quede
            # apuntando al sitio de la compania equivocada.
            if company.website:
                render_context["website_url"] = (
                    company.website if company.website.lower().startswith(("http:", "https:"))
                    else "http://%s" % company.website
                )
            else:
                render_context["website_url"] = False
        return render_context

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
            "description": self._installation_task_description(customer),
            # Explicito: el create de project.task deja como asignado al uid actual, que aca es el
            # usuario publico que agendo. El despacho lo hace el backoffice.
            "user_ids": [(6, 0, [])],
        })
        self.sudo().installation_task_id = task.id
        return task

    def _installation_task_description(self, customer):
        """ Body of the Field Service task: the answers of the form plus the cross streets (D58).

        The task shows the address through `partner_id`, but `between_streets` is a field of this
        module that no standard view of the task prints: it goes into the description so the crew
        reads it where they read everything else.

        :param customer: contact that booked the appointment
        :type customer: recordset de `res.partner`
        :return: HTML body
        :rtype: Markup
        """
        self.ensure_one()
        description = self.description or Markup()
        if not customer.between_streets:
            return description
        # Reasignar `self` (no una variable nueva): `_()` resuelve el idioma leyendo el `self` del
        # frame del LLAMADOR. Sin esto la etiqueta sale en el idioma del VISITANTE (este metodo
        # corre dentro del request publico de la cita) y el que la lee es la cuadrilla. Mismo
        # molde y mismo motivo que `sale.order._get_installation_task_notes()`.
        self = self.with_context(lang=self.env.company.partner_id.lang or self.env.lang)
        # Markup + Markup: concatenar un `str` crudo escaparia el lado derecho.
        return description + Markup("<p><strong>%s</strong> %s</p>") % (
            _("Between streets:"), customer.between_streets,
        )

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
