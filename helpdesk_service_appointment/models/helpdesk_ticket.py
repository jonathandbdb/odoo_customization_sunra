# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    service_visit_address_id = fields.Many2one(
        "res.partner", string="Visit Address", ondelete="set null",
        help="Address where the technician will do the service visit. Must belong to the "
             "ticket's commercial partner; used as the customer of the generated Field "
             "Service task.",
    )
    service_event_ids = fields.One2many(
        "calendar.event", "service_ticket_id", string="Service Appointments",
    )
    service_event_id = fields.Many2one(
        "calendar.event", string="Service Appointment", compute="_compute_service_event_id",
        help="Most recent active appointment linked to this ticket.",
    )
    warranty_status = fields.Selection([
        ("valid", "Under Warranty"),
        ("expired", "Out of Warranty"),
        ("unknown", "Unknown"),
    ], string="Warranty Status", compute="_compute_service_warranty", store=True,
        help="Informative only: it never blocks the scheduling of a service visit.")
    warranty_expiry_date = fields.Date(
        string="Warranty Expiry Date", compute="_compute_service_warranty", store=True,
    )
    warranty_delivery_date = fields.Date(
        string="Delivery Date", compute="_compute_service_warranty", store=True,
        help="Delivery used as the base of the warranty computation (first or last, "
             "depending on the product's warranty start type).",
    )

    @api.depends("service_event_ids")
    def _compute_service_event_id(self):
        # El o2m solo trae eventos activos: el ultimo por fecha de inicio es la cita vigente
        # (y el gate del doble agendado, D16).
        for ticket in self:
            ticket.service_event_id = ticket.service_event_ids.sorted("start")[-1:]

    @api.depends("partner_id", "product_id", "lot_id")
    def _compute_service_warranty(self):
        # sudo obligatorio (fix post-review, m7): product_id (helpdesk_stock) esta restringido
        # por groups="stock.group_stock_user" (lot_id NO lleva esa restriccion); sin sudo, un
        # usuario de helpdesk sin ese grupo (o el portal) tira AccessError al recomputar el
        # ticket al leer product_id.
        self_sudo = self.sudo()

        # Batchear por commercial partner: un unico _read_group por grupo (no uno por
        # ticket): el helper hace un _read_group sobre stock.move.line y en un recompute
        # masivo un query por ticket seria un N+1 caro.
        tickets_by_commercial = defaultdict(lambda: self.env["helpdesk.ticket"])
        for ticket_sudo in self_sudo:
            commercial = ticket_sudo.partner_id.commercial_partner_id
            if commercial:
                tickets_by_commercial[commercial] |= ticket_sudo

        products_by_commercial = {
            commercial: {
                item["product"]: item
                for item in self.env["product.product"]._get_partner_service_products(commercial)
            }
            for commercial in tickets_by_commercial
        }

        for ticket, ticket_sudo in zip(self, self_sudo):
            ticket.warranty_status = "unknown"
            ticket.warranty_expiry_date = False
            ticket.warranty_delivery_date = False
            product = ticket_sudo.product_id
            commercial = ticket_sudo.partner_id.commercial_partner_id
            item = products_by_commercial.get(commercial, {}).get(product)
            if not item:
                # Sin product_id (fallback, D8), sin partner_id, o producto comprado por otro
                # canal / entrega borrada: queda unknown.
                continue
            info = product._get_service_warranty(
                first_delivery=item["first_delivery"],
                last_delivery=item["last_delivery"],
                lot=ticket_sudo.lot_id or None,
            )
            ticket.warranty_status = info["status"]
            ticket.warranty_expiry_date = info["expiry_date"]
            ticket.warranty_delivery_date = info["delivery_date"]

    def _get_service_appointment_url(self):
        """URL de agendado del ticket (paso 2 del flujo y boton "Schedule visit" del portal).

        Se deriva de ``invite.redirect_url`` (D13): armar la URL a mano
        (``/appointment/<id>?invite_token=...``) responde 403 en cuanto hay 2+ tipos de cita
        activos (garantizado: existe el de instalacion), porque
        ``_fetch_and_check_private_appointment_types`` levanta todos los tipos activos y
        ``appointment.invite._check_appointments_params`` exige match exacto con los tipos del
        invite. ``redirect_url`` ya emite ``invite_token`` y ``filter_appointment_type_ids``.

        :return: URL absoluta relativa (con querystring) a la que redirigir al cliente
        :rtype: str
        :raises ValueError: si falta el dato semilla ``appointment_invite_service``
        """
        self.ensure_one()
        # sudo: el portal no lee appointment.invite; se lee un unico registro semilla.
        invite = self.env.ref(
            "helpdesk_service_appointment.appointment_invite_service", raise_if_not_found=True,
        ).sudo()
        return "%s&service_ticket_id=%s" % (invite.redirect_url, self.id)

    def _get_service_photo_attachments(self):
        """Fotos que el cliente subio al ticket (ya reasignadas por message_post, D11)."""
        self.ensure_one()
        # sudo: el cliente portal no lee ir.attachment libremente.
        return self.env["ir.attachment"].sudo().search([
            ("res_model", "=", "helpdesk.ticket"),
            ("res_id", "=", self.id),
            ("mimetype", "like", "image/%"),
        ])

    def _post_service_photos(self, target):
        """Copiar las fotos de la falla al chatter de ``target`` (la tarea FSM), sin mover los
        adjuntos originales del ticket.

        :param target: recordset (ej. project.task) que hereda mail.thread
        :return: adjuntos originales copiados, o None si no habia fotos
        """
        self.ensure_one()
        photos = self._get_service_photo_attachments()
        if not photos:
            return None
        # sudo: la cita la crea el cliente portal, que no escribe en project.task ni en
        # ir.attachment. Se copian sin dueño: message_post reasigna res_model/res_id al
        # destino (mismo patron que website_sale_installation_appointment._post_installation_photos).
        attachment_ids = [
            photo.sudo().copy({"res_model": "mail.compose.message", "res_id": 0}).id
            for photo in photos
        ]
        target.sudo().message_post(
            body=_("Photos of the reported issue uploaded by the customer on ticket %(ticket)s.", ticket=self.name),
            attachment_ids=attachment_ids,
        )
        return photos

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
