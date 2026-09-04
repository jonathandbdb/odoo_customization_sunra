# -*- coding: utf-8 -*-
import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)


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
        self._grant_portal_access_after_installation_sale()
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

    def _grant_portal_access_after_installation_sale(self):
        """ Auto-invite the customer to the portal after an installation sale is confirmed.

        helpdesk_service_appointment (sibling module) assumes that the customer who had an
        installation is a portal user, so the native portal invitation is sent right here. A
        failure must never break the order confirmation: each partner is handled in its own
        try/savepoint and any problem only leaves a note on the order's chatter.
        """
        for order in self.filtered(lambda so: so._is_installation_required()):
            partner = order.partner_id
            # sudo: la confirmacion puede dispararla el usuario publico del checkout (guest
            # checkout), sin permisos sobre res.users, portal.wizard ni para postear en el pedido.
            users = self.env["res.users"].sudo().search([("partner_id", "=", partner.id)])
            if users:
                continue  # el partner ya tiene un usuario activo (portal o interno): no-op
            archived_users = self.env["res.users"].sudo().with_context(active_test=False).search(
                [("partner_id", "=", partner.id)]
            )
            if archived_users:
                # No se reactiva en automatico: portal.wizard.user.action_grant_access()
                # reactivaria un usuario archivado sin control (ver odoo/addons/portal/wizard).
                order.sudo().message_post(body=_(
                    "Portal access was not granted automatically: the customer has an archived "
                    "user."
                ))
                continue
            if not partner.email:
                order.sudo().message_post(body=_(
                    "Portal access was not granted automatically: the customer has no email."
                ))
                continue
            try:
                with self.env.cr.savepoint():
                    wizard = self.env["portal.wizard"].sudo().create({
                        "partner_ids": [Command.link(partner.id)],
                    })
                    wizard.user_ids.action_grant_access()
            except Exception:
                # Nunca debe romper la confirmacion de la venta (ej. email duplicado en otro
                # usuario, UserError de _assert_user_email_uniqueness).
                _logger.warning(
                    "Could not grant portal access to partner %s after confirming order %s.",
                    partner.id, order.name, exc_info=True,
                )
                order.sudo().message_post(body=_(
                    "Portal access could not be granted automatically to the customer."
                ))

    # === FREE BATTERIES === #

    def _get_free_battery_needs(self):
        """ How many units of each free battery product this order should carry at no cost.

        Read-only: safe to call from an onchange, on `NewId` records. Never raises: an
        incompatible configuration (wrong company) is skipped instead of breaking the request
        of the public visitor's cart.

        :return: needs by battery product
        :rtype: dict (`product.product` -> float)
        """
        self.ensure_one()
        if not self.carrier_id.includes_free_batteries:
            return {}
        needs = {}
        for line in self.order_line:
            if (
                line.is_free_battery_line
                or line.is_delivery
                or line.display_type
                or line.is_downpayment
                or line._is_global_discount()
                or line.product_uom_qty <= 0
            ):
                continue
            template = line.product_id.product_tmpl_id
            battery_product = template.free_battery_product_id
            if not battery_product or template.free_battery_qty <= 0:
                continue
            if not battery_product.filtered_domain(
                self.env["product.product"]._check_company_domain(self.company_id)
            ):
                # Mismo criterio que check_company (product.product usa
                # check_company_domain_parent_of: una pila de la compañia PADRE es config
                # valida). Comparar solo battery_product.company_id != self.company_id seria
                # mas estricto que el check real y saltearia en silencio una pila valida en
                # una jerarquia padre/hija. Precedente identico: website_sale/models/sale_order.py
                # (_cart_accessories). Se saltea en vez de dejar que el create() de la linea
                # tire UserError de compañia (500 para el visitante publico).
                continue
            needs[battery_product] = (
                needs.get(battery_product, 0.0) + template.free_battery_qty * line.product_uom_qty
            )
        return {product: qty for product, qty in needs.items() if qty > 0}

    def _prepare_free_battery_line_vals(self, battery_product, qty):
        """ Values of a free battery line, shared by the database path and the onchange path.

        :param battery_product: battery product to add
        :type battery_product: recordset of `product.product`
        :param qty: quantity, in the battery product's own unit of measure
        :type qty: float
        :return: values ready for `sale.order.line.create()` / `Command.create()`
        :rtype: dict
        """
        self.ensure_one()
        # En el idioma del cliente (molde: `_prepare_delivery_line_vals` del core y `_get_lang()`
        # de `website_appointment_sale`): un pedido armado en el backend por otro usuario no debe
        # dejar la descripcion en un idioma distinto en la factura.
        lang = self._get_lang()
        self = self.with_context(lang=lang)
        battery_product = battery_product.with_context(lang=lang)
        # Sin el nombre del metodo de envio (D35): el sync solo escribe `product_uom_qty`, asi
        # que un nombre horneado quedaria mintiendo al pasar a otro envio que tambien incluya
        # pilas.
        name = "%s\n%s" % (
            battery_product.get_product_multiline_description_sale(),
            _("Included with your shipping method — no extra charge."),
        )
        vals = {
            "product_id": battery_product.id,
            "product_uom_qty": qty,
            "price_unit": 0.0,
            "is_free_battery_line": True,
            "name": name,
        }
        # Va al final, como `_prepare_delivery_line_vals`. Sin `product_uom_id`: el ORM toma la
        # UoM propia del producto (D15). Sin `linked_line_id` (D19) ni `order_id` (lo agrega el
        # camino de base de datos; el de onchange usa `Command.create` dentro del o2m).
        if self.order_line:
            vals["sequence"] = self.order_line[-1].sequence + 1
        return vals

    def _sync_free_battery_lines(self):
        """ Reconcile the free battery lines of the order against what should be there.

        Idempotent: recalculated from scratch on every call (create what's missing, adjust
        quantities, delete the rest) — running it twice in a row changes nothing. Only acts on
        `draft`/`sent` orders, and never touches a line already invoiced or delivered (a
        confirmed order returned to quotation keeps `qty_invoiced != 0` while back in `draft`).

        :return: None
        """
        if self.env.context.get("wsia_skip_battery_sync"):
            # Guard puramente defensivo (simetria con `wspmp_skip_recompute` del modulo
            # hermano): hoy ningun `create`/`write`/`unlink` de linea re-entra a este metodo.
            return
        precision = self.env["decimal.precision"].precision_get("Product Unit")
        for order in self:
            if order.state not in ("draft", "sent"):
                continue
            needs = order._get_free_battery_needs()
            existing = order.order_line.filtered("is_free_battery_line")
            # Las lineas ya facturadas/entregadas se congelan: no se escriben ni se borran (D36,
            # mismo criterio que `_remove_delivery_line` del core).
            frozen = existing.filtered(lambda line: line.qty_invoiced or line.qty_delivered)
            reconcilable = existing - frozen
            to_unlink = reconcilable
            for battery_product, qty in needs.items():
                line = reconcilable.filtered(lambda l: l.product_id == battery_product)[:1]
                if line:
                    to_unlink -= line
                    if float_compare(line.product_uom_qty, qty, precision_digits=precision) != 0:
                        # sudo: lo dispara el visitante publico del checkout, sin permisos de
                        # escritura sobre sale.order.line (mismo criterio que
                        # `_create_delivery_line` del core).
                        line.sudo().with_context(wsia_skip_battery_sync=True).write({
                            "product_uom_qty": qty,
                        })
                else:
                    vals = order._prepare_free_battery_line_vals(battery_product, qty)
                    vals["order_id"] = order.id
                    self.env["sale.order.line"].sudo().with_context(
                        wsia_skip_battery_sync=True
                    ).create(vals)
            if to_unlink:
                to_unlink.sudo().with_context(wsia_skip_battery_sync=True).unlink()

    def _verify_cart_after_update(self):
        # Engache canonico del carrito web (su docstring dice que es donde van los chequeos
        # globales, una vez por request): cubre alta/baja de cerraduras, cambio de cantidad y la
        # auto-curacion si el cliente manipula la linea gratis por /shop/cart/update.
        res = super()._verify_cart_after_update()
        self._sync_free_battery_lines()
        return res

    def _set_delivery_method(self, delivery_method, rate=None):
        # Embudo de la seleccion de envio del checkout: cubre pasar a un envio con pilas y salir
        # de el, incluido el camino de QUITAR el envio (donde set_delivery_line() no se llama).
        res = super()._set_delivery_method(delivery_method, rate=rate)
        self._sync_free_battery_lines()
        return res

    def set_delivery_line(self, carrier, amount):
        # Flujo real de asignacion de envio en el backoffice: el boton "Add shipping" (wizard
        # choose.delivery.carrier) escribe por write(), y los @api.onchange no corren.
        res = super().set_delivery_line(carrier, amount)
        self._sync_free_battery_lines()
        return res

    @api.onchange("order_line", "carrier_id")
    def _onchange_free_battery_lines(self):
        """ Bring the free battery lines into orders assembled in the backend (no eCommerce).

        Runs fully in memory, with `Command.*` on `self.order_line`: in an onchange `self` is a
        virtual record (`NewId`) and a real `create()`/`write()` would hit the database. Same
        pattern the core uses for combo lines (`_onchange_order_line`,
        `odoo/addons/sale/models/sale_order.py`).

        Named `_onchange_free_battery_lines` and NOT `_onchange_order_line` on purpose: that
        name would shadow (replace, not complement) the core's combo-lines onchange.
        """
        needs = self._get_free_battery_needs()
        free_lines = self.order_line.filtered("is_free_battery_line")
        to_delete = free_lines
        create_commands = []
        for battery_product, qty in needs.items():
            line = free_lines.filtered(lambda l: l.product_id == battery_product)[:1]
            if line:
                to_delete -= line
                if line.product_uom_qty != qty:
                    line.product_uom_qty = qty
            else:
                create_commands.append(
                    Command.create(self._prepare_free_battery_line_vals(battery_product, qty))
                )
        delete_commands = [Command.delete(line.id) for line in to_delete]
        if delete_commands or create_commands:
            self.order_line = delete_commands + create_commands

    def action_confirm(self):
        # Red de seguridad final (backend sin onchange disparado, importaciones, API): va ANTES
        # del super(), con el state todavia draft/sent (altas y bajas de lineas son legales
        # aca). El write(_prepare_confirmation_values()) del super() pasa el state a 'sale'
        # ANTES de _action_confirm(), asi que ahi el unlink() chocaria con
        # _unlink_except_confirmed. El override existente de _action_confirm() (fotos + portal)
        # no se toca.
        self._sync_free_battery_lines()
        return super().action_confirm()

    def _cart_find_product_line(self, *args, **kwargs):
        # El domain del core no conoce nuestro flag: sin este filtro, un alta manual de la
        # misma pila se fusionaria con la linea gratis y se perderia el precio 0 de esta ultima
        # (D24). Filtrando, el alta manual crea una linea separada y paga.
        lines = super()._cart_find_product_line(*args, **kwargs)
        return lines.filtered(lambda line: not line.is_free_battery_line)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
