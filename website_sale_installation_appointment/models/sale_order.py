# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    installation_appointment_type_id = fields.Many2one(
        comodel_name="appointment.type",
        string="Installation Appointment Type",
        related="carrier_id.installation_appointment_type_id",
        readonly=True,
    )
    installation_required = fields.Boolean(
        string="Installation Required",
        compute="_compute_installation_required",
        help="Indicates if the selected delivery method includes an installation to be scheduled.",
    )
    installation_booking_id = fields.Many2one(
        comodel_name="calendar.booking",
        string="Installation Booking",
        compute="_compute_installation_booking_id",
        help="Pending booking of the installation, before the order is confirmed.",
    )
    installation_event_id = fields.Many2one(
        comodel_name="calendar.event",
        string="Installation Appointment",
        compute="_compute_installation_event_id",
        help="Appointment created from the installation booking once the order is confirmed.",
    )
    installation_photo_ids = fields.Many2many(
        comodel_name="ir.attachment",
        relation="sale_order_installation_photo_rel",
        column1="order_id",
        column2="attachment_id",
        string="Installation Photos",
        copy=False,
        help="Photos of the installation site uploaded by the customer during the checkout.",
    )
    installation_photo_count = fields.Integer(
        string="Installation Photos Count",
        compute="_compute_installation_photo_count",
    )

    @api.depends("carrier_id.installation_appointment_type_id")
    def _compute_installation_required(self):
        for order in self:
            order.installation_required = bool(order.carrier_id.installation_appointment_type_id)

    @api.depends("order_line.calendar_booking_ids", "carrier_id.installation_appointment_type_id")
    def _compute_installation_booking_id(self):
        for order in self:
            appointment_type = order.carrier_id.installation_appointment_type_id
            bookings = order.order_line.calendar_booking_ids
            if appointment_type:
                bookings = bookings.filtered(
                    lambda booking: booking.appointment_type_id == appointment_type
                )
            order.installation_booking_id = bookings[:1]

    @api.depends("order_line.calendar_event_id", "carrier_id.installation_appointment_type_id")
    def _compute_installation_event_id(self):
        for order in self:
            appointment_type = order.carrier_id.installation_appointment_type_id
            events = order.order_line.calendar_event_id
            if appointment_type:
                events = events.filtered(
                    lambda event: event.appointment_type_id == appointment_type
                )
            order.installation_event_id = events[:1]

    @api.depends("installation_photo_ids")
    def _compute_installation_photo_count(self):
        for order in self:
            order.installation_photo_count = len(order.installation_photo_ids)

    def _is_installation_required(self):
        """ Whether any order of the recordset needs an installation to be scheduled.

        :return: True if the selected delivery method includes an installation
        :rtype: bool
        """
        return any(order.installation_required for order in self)

    def _is_installation_scheduled(self):
        """ Whether the installation is already booked (pending order) or scheduled (confirmed order).

        :rtype: bool
        """
        self.ensure_one()
        return bool(self.installation_booking_id or self.installation_event_id)

    def _get_installation_errors(self):
        """ Missing requirements that prevent the customer from paying the order.

        :return: list of messages to display to the customer
        :rtype: list
        """
        self.ensure_one()
        if not self.installation_required:
            return []
        errors = []
        if not self._is_installation_scheduled():
            errors.append(_("Please schedule the date and time of the installation."))
        min_photos = self.carrier_id.installation_min_photos
        missing_photos = min_photos - self.installation_photo_count
        if missing_photos > 0:
            errors.append(_(
                "Please upload at least %(min_photos)s photo(s) of the installation site "
                "(%(missing)s missing).",
                min_photos=min_photos,
                missing=missing_photos,
            ))
        return errors

    def _check_cart_is_ready_to_be_paid(self):
        # Gate de pago: sin cita agendada (o sin las fotos minimas) el pedido no puede pagarse,
        # porque la instalacion quedaria vendida sin fecha ni datos del lugar.
        self.ensure_one()
        errors = self._get_installation_errors()
        if errors:
            raise ValidationError("\n".join(errors))
        return super()._check_cart_is_ready_to_be_paid()

    def _action_confirm(self):
        # Al confirmar, el flujo nativo (website_appointment_sale) convierte la reserva en Cita y
        # sale_project genera la tarea: recien despues de super() existen ambas para copiarles las fotos.
        res = super()._action_confirm()
        self._sync_installation_photos()
        return res

    def _sync_installation_photos(self):
        """ Copy the installation photos to the appointment and to the generated task(s).

        The customer uploads the photos on the order, but the crew works from the appointment
        (Calendar) and from the Field Service task, so the photos are copied to both chatters.
        """
        for order in self.filtered(lambda so: so.installation_photo_ids):
            # La Cita y las tareas son modelos distintos: se recorren por separado.
            for targets in (order.installation_event_id, order.order_line.task_id):
                for target in targets:
                    order._post_installation_photos(target)

    def _post_installation_photos(self, target):
        """ Post the installation photos on the chatter of the given record.

        :param target: recordset (calendar.event or project.task) inheriting mail.thread
        """
        self.ensure_one()
        # sudo: la confirmacion la dispara el cliente del eCommerce al pagar, y no tiene permisos
        # sobre calendar.event ni project.task (ni sobre ir.attachment).
        target_sudo = target.sudo()
        attachment_ids = []
        for photo in self.installation_photo_ids.sudo():
            # Se copia sin dueño: message_post reasigna res_model/res_id al registro destino.
            copy = photo.copy({"res_model": "mail.compose.message", "res_id": 0})
            attachment_ids.append(copy.id)
        if not attachment_ids:
            return
        target_sudo.message_post(
            body=_(
                "Photos of the installation site uploaded by the customer on order %(order)s.",
                order=self.name,
            ),
            attachment_ids=attachment_ids,
        )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
