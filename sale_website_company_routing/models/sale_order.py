# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

SKIP_ROUTING_KEY = "sale_website_company_routing_skip"


class SaleOrder(models.Model):
    _inherit = "sale.order"

    company_routing_origin_id = fields.Many2one(
        comodel_name="sale.order",
        string="Routed From",
        readonly=True,
        copy=False,
        index="btree_not_null",
        ondelete="set null",
        help="Order this one was split from when it was confirmed.",
    )
    company_routing_order_ids = fields.One2many(
        comodel_name="sale.order",
        inverse_name="company_routing_origin_id",
        string="Routed Orders",
        help="Orders created in other companies from the lines of this order.",
    )
    company_routing_order_count = fields.Integer(
        string="Routed Orders Count",
        compute="_compute_company_routing_order_count",
    )

    @api.depends("company_routing_order_ids", "company_routing_origin_id")
    def _compute_company_routing_order_count(self):
        for order in self:
            order.company_routing_order_count = (
                len(order.company_routing_order_ids) or (1 if order.company_routing_origin_id else 0)
            )

    # === ACTIONS === #

    def action_confirm(self):
        if self.env.context.get(SKIP_ROUTING_KEY):
            return super().action_confirm()
        cancelled = self._company_routing_split()
        return super(SaleOrder, self - cancelled).action_confirm()

    def action_view_company_routing_orders(self):
        """Abrir los pedidos derivados (o el original, desde un derivado)."""
        self.ensure_one()
        orders = self.company_routing_order_ids or self.company_routing_origin_id
        action = {
            "type": "ir.actions.act_window",
            "name": _("Routed Orders"),
            "res_model": "sale.order",
            "context": {"create": False},
        }
        if len(orders) == 1:
            action.update(view_mode="form", res_id=orders.id)
        else:
            action.update(view_mode="list,form", domain=[("id", "in", orders.ids)])
        return action

    # === STOCK === #

    def _get_free_qty(self, product):
        website = self.website_id
        if website and website._has_website_stock_companies(product):
            return website._get_products_free_qty(product)[product.id]
        return super()._get_free_qty(product)

    # === HOOKS === #

    def _company_routing_validate(self, groups):
        """
        Validaciones extra antes de crear nada (hook de extension).

        :param groups: lineas a rutear por compañia destino
        :type groups: dict {res.company: sale.order.line}
        :return: mensaje de error, o False si no hay nada que objetar
        :rtype: str | bool
        """
        self.ensure_one()
        return False

    def _company_routing_pre_split(self):
        """
        Guardar el estado de los descuentos globales antes de repartir las lineas (hook de extension).

        Las lineas de recompensa de loyalty no se mueven: esta implementacion solo anota cuales
        habia para avisar en los derivados las que no se re-aplican. Los modulos que quiten sus
        descuentos para recalcularlos extienden el dict de estado.

        :return: estado a pasar a `_company_routing_post_split()`
        :rtype: dict
        """
        self.ensure_one()
        return {"loyalty": sorted(set(self.order_line.reward_id.ids))}

    def _company_routing_post_split(self, derived_orders, state):
        """
        Recalcular los descuentos globales en cada pedido (hook de extension).

        El original recalcula sobre las lineas que conserva (salvo que quede cancelado) y cada
        derivado re-aplica sus programas automaticos.

        :param derived_orders: pedidos derivados, todavia sin confirmar
        :type derived_orders: recordset de `sale.order`
        :param state: lo devuelto por `_company_routing_pre_split()`
        :type state: dict
        """
        self.ensure_one()
        if self._company_routing_has_product_lines():
            self.with_company(self.company_id)._update_programs_and_rewards()
        for order in derived_orders:
            order.with_company(order.company_id)._company_routing_reapply_loyalty(
                state.get("loyalty", [])
            )

    def _company_routing_has_product_lines(self):
        """Indica si el pedido conserva alguna linea de producto (sin secciones, notas ni recompensas)."""
        self.ensure_one()
        return bool(self.order_line.filtered(lambda line: not line.display_type and not line.reward_id))

    def _company_routing_loyalty_skip_reason(self, program):
        """
        Motivo por el que un programa del original no se re-aplica en este pedido.

        Solo se re-aplican los programas automaticos que no consumen un cupon: los codigos, los
        cupones de un solo uso, las tarjetas de regalo, el monedero y las tarjetas de cliente
        quedan en el original.

        :param program: programa de la recompensa del original
        :type program: recordset de `loyalty.program`
        :return: motivo, o False si se puede re-aplicar
        :rtype: str | bool
        """
        self.ensure_one()
        if program.trigger != "auto" or program.is_payment_program or program.is_nominative:
            return _("it needs a code, a coupon or a customer card, which stay on the original order")
        if program.company_id and program.company_id != self.company_id:
            return _("the program belongs to %(company)s", company=program.company_id.name)
        return False

    def _company_routing_reapply_loyalty(self, reward_ids):
        """
        Re-aplicar en un derivado las recompensas del original que su programa automatico permite.

        Usa solo el cupon que el propio derivado genera para el programa; nunca el del original.

        :param reward_ids: ids de las recompensas aplicadas en el original
        :type reward_ids: list
        """
        self.ensure_one()
        self._update_programs_and_rewards()
        for reward in self.env["loyalty.reward"].browse(reward_ids).exists():
            program = reward.program_id
            error = self._company_routing_loyalty_skip_reason(program)
            if not error:
                coupon = self.coupon_point_ids.coupon_id.filtered(
                    lambda card: card.program_id == program
                )[:1].exists()
                claimable = self._get_claimable_rewards(forced_coupons=coupon) if coupon else {}
                if not coupon or reward not in claimable.get(coupon, reward.browse()):
                    error = _("the order does not meet its conditions")
                else:
                    error = self._apply_program_reward(reward, coupon).get("error")
            if error:
                self.message_post(body=_(
                    "The discount %(reward)s of the original order was not applied to this "
                    "order: %(reason)s.",
                    reward=reward.display_name,
                    reason=error,
                ))
        self._update_programs_and_rewards()

    # === ROUTING === #

    def _company_routing_split(self):
        """
        Mover las lineas de otra compañia a pedidos nuevos en esa compañia.

        :return: pedidos que quedaron cancelados por no conservar ninguna linea de producto
        :rtype: recordset de `sale.order`
        """
        cancelled = self.browse()
        for order in self.filtered(lambda so: so.state in ("draft", "sent")):
            if order._company_routing_split_order():
                cancelled |= order
        return cancelled

    def _company_routing_get_groups(self):
        """
        Agrupar por compañia destino las lineas que hay que mover.

        Las lineas vinculadas siguen a su linea padre. Secciones, notas, anticipos, recompensas y
        envios no son candidatos: las recompensas se quedan en el original y el envio lo asigna el
        llamador.

        :return: {compañia destino: lineas}
        :rtype: dict
        """
        self.ensure_one()
        groups = {}
        if self.company_id.company_routing_excluded:
            return groups
        lines = self.order_line.filtered(
            lambda line: not line.display_type
            and not line.is_downpayment
            and not line.is_delivery
            and not line.reward_id
        ).sorted(lambda line: (line.sequence, line.id))
        for line in lines:
            root = line
            while root.linked_line_id:
                root = root.linked_line_id
            company = root.sale_company_id
            if company and company != self.company_id:
                groups[company] = groups.get(company, self.env["sale.order.line"]) | line
        return groups

    def _company_routing_split_order(self):
        """
        Rutear un pedido. Valida todo antes de crear nada.

        :return: True si el pedido original quedo cancelado
        :rtype: bool
        """
        self.ensure_one()
        # sudo: lo dispara un visitante o un usuario de backoffice que puede no tener acceso a la
        # compañia destino; el check_company del core sigue aplicando
        order = self.sudo()
        groups = order._company_routing_get_groups()
        if not groups:
            return False

        delivery_lines = order.order_line.filtered("is_delivery")
        delivery_company = order._company_routing_get_delivery_company(groups)
        date = fields.Date.context_today(order)
        for company, lines in groups.items():
            group_lines = lines | (delivery_lines if company == delivery_company else delivery_lines.browse())
            order._company_routing_validate_group(company, group_lines, date)
            if company == delivery_company:
                order._company_routing_validate_carrier(company)
        error = order._company_routing_validate(groups)
        if error:
            raise UserError(error)
        # Solo el retiro en tienda guarda un stock.warehouse en pickup_location_data; otros
        # transportistas con punto de retiro guardan ids externos (website_sale_collect/models/sale_order.py:L72).
        if order.carrier_id.delivery_type == "in_store" and order.pickup_location_data:
            order._company_routing_validate_pickup(delivery_company)

        state = order._company_routing_pre_split()
        carrier = order.carrier_id
        derived_orders = order.browse()
        for company, lines in groups.items():
            group_lines = lines | (delivery_lines if company == delivery_company else delivery_lines.browse())
            derived = order._company_routing_create_order(company, group_lines, date)
            if company == delivery_company and carrier:
                derived.carrier_id = carrier
                derived.pickup_location_data = order.pickup_location_data
                derived._company_routing_set_pickup_warehouse()
                derived._company_routing_check_warehouse(company)
            derived_orders |= derived
            group_lines.unlink()
        order.carrier_id = False
        order.pickup_location_data = False
        order._company_routing_post_split(derived_orders, state)
        order._company_routing_notify(derived_orders)

        for derived in derived_orders:
            derived.with_company(derived.company_id).with_context(
                **{SKIP_ROUTING_KEY: True, "send_email": self.env.context.get("send_email")}
            ).action_confirm()

        if not order._company_routing_has_product_lines():
            order._action_cancel()
            return True
        return False

    def _company_routing_get_delivery_company(self, groups):
        """
        Compañia destino que se queda con el envio: la unica, o la de mayor importe sin impuestos.

        :param groups: lineas a rutear por compañia destino
        :type groups: dict
        :return: compañia destino del envio
        :rtype: recordset de `res.company`
        """
        self.ensure_one()
        best = self.env["res.company"]
        best_amount = None
        for company, lines in groups.items():
            amount = sum(lines.mapped("price_subtotal"))
            if best_amount is None or amount > best_amount:
                best, best_amount = company, amount
        return best

    def _company_routing_get_pricelist(self, company):
        """Lista de precios del cliente en la compañia destino."""
        self.ensure_one()
        return self.partner_id.with_company(company).property_product_pricelist

    def _company_routing_validate_group(self, company, lines, date):
        """
        Validar que el grupo se pueda crear en la compañia destino. Levanta `UserError`.

        :param company: compañia destino
        :param lines: lineas a mover a esa compañia
        :param date: fecha de confirmacion, para la cotizacion
        """
        self.ensure_one()
        if not self.env["stock.warehouse"].search_count([("company_id", "=", company.id)], limit=1):
            raise UserError(_(
                "Company %(company)s has no warehouse to ship the lines of order %(order)s.",
                company=company.name, order=self.name,
            ))
        for partner in self.partner_id | self.partner_invoice_id | self.partner_shipping_id:
            if partner.company_id and partner.company_id != company:
                raise UserError(_(
                    "Contact %(partner)s belongs to %(partner_company)s and cannot be used in "
                    "%(company)s, where the lines of order %(order)s are routed.",
                    partner=partner.display_name, partner_company=partner.company_id.name,
                    company=company.name, order=self.name,
                ))
        for line in lines:
            product = line.product_id
            if product.company_id and product.company_id != company:
                raise UserError(_(
                    "Product %(product)s belongs to %(product_company)s and cannot be sold by "
                    "%(company)s.",
                    product=product.display_name, product_company=product.company_id.name,
                    company=company.name,
                ))
            if product.type == "combo":
                raise UserError(_(
                    "Combo product %(product)s belongs to %(company)s: lines of combo products "
                    "cannot be routed to another company.",
                    product=product.display_name, company=company.name,
                ))
            if not product.taxes_id._filter_taxes_by_company(company):
                raise UserError(_(
                    "Product %(product)s has no tax in company %(company)s.",
                    product=product.display_name, company=company.name,
                ))
        self._company_routing_check_rates(company, date)

    def _company_routing_check_rates(self, company, date):
        """
        Exigir cotizacion de la moneda del pedido en la compañia destino a la fecha.

        Sin cotizacion el core convierte en silencio con la mas vieja o con 1.

        :param company: compañia destino
        :param date: fecha de confirmacion
        """
        self.ensure_one()
        pricelist = self._company_routing_get_pricelist(company)
        target_currency = pricelist.currency_id or company.currency_id
        if self.currency_id == target_currency:
            return
        # sudo: las cotizaciones de otra compañia no son legibles para el usuario
        Rate = self.env["res.currency.rate"].sudo()
        for currency in (self.currency_id, target_currency):
            if currency == company.currency_id:
                continue
            if not Rate.search_count([
                ("currency_id", "=", currency.id),
                ("company_id", "in", (False, company.root_id.id)),
                ("name", "<=", date),
            ], limit=1):
                raise UserError(_(
                    "There is no %(currency)s exchange rate in company %(company)s on or before "
                    "%(date)s to convert the lines of order %(order)s.",
                    currency=currency.name, company=company.name, date=date, order=self.name,
                ))

    def _company_routing_validate_carrier(self, company):
        """
        El metodo de envio y su producto de flete no pueden ser de otra compañia.

        :param company: compañia destino
        """
        self.ensure_one()
        delivery_products = self.order_line.filtered("is_delivery").product_id
        for record in (self.carrier_id, self.carrier_id.product_id, delivery_products):
            for item in record:
                if item.company_id and item.company_id != company:
                    raise UserError(_(
                        "Delivery method %(carrier)s (or its shipping product) belongs to "
                        "%(item_company)s and cannot be used in %(company)s, where the lines of "
                        "order %(order)s are routed.",
                        carrier=self.carrier_id.name, item_company=item.company_id.name,
                        company=company.name, order=self.name,
                    ))

    def _prepare_company_routing_order_values(self, company):
        """
        Valores del pedido derivado en la compañia destino.

        Sin `website_id` (`website_sale_stock` le forzaria el almacen del sitio), ni almacen,
        posicion fiscal, plazo de pago o equipo: los calcula el core en la compañia destino.

        :param company: compañia destino
        :type company: recordset de `res.company`
        :return: valores para `create()`
        :rtype: dict
        """
        self.ensure_one()
        values = {
            "company_id": company.id,
            "partner_id": self.partner_id.id,
            "partner_invoice_id": self.partner_invoice_id.id,
            "partner_shipping_id": self.partner_shipping_id.id,
            "client_order_ref": self.client_order_ref,
            "origin": self.name,
            "company_routing_origin_id": self.id,
            "pricelist_id": self._company_routing_get_pricelist(company).id,
        }
        if self.user_id and company in self.user_id.company_ids:
            values["user_id"] = self.user_id.id
        return values

    def _company_routing_create_order(self, company, lines, date):
        """
        Crear el pedido derivado con copias de las lineas.

        Se crean lineas nuevas (no se reasigna `order_id`: los impuestos de origen no pasan el
        `check_company` de la destino). Las lineas vinculadas se crean despues de su padre.

        :param company: compañia destino
        :param lines: lineas del original a recrear (incluye el envio si le corresponde)
        :param date: fecha de confirmacion, para la conversion
        :return: pedido derivado
        :rtype: recordset de `sale.order`
        """
        self.ensure_one()
        derived = self.env["sale.order"].with_company(company).create(
            self._prepare_company_routing_order_values(company)
        )
        derived._company_routing_check_warehouse(company)
        source_currency = self.currency_id
        target_currency = derived.currency_id

        def convert(amount):
            if source_currency == target_currency:
                return amount
            return source_currency.sudo()._convert(
                amount, target_currency, company=company, date=date, round=False
            )

        new_lines = {}
        pending = lines.sorted(lambda line: (line.sequence, line.id))
        Line = self.env["sale.order.line"].with_company(company)
        while pending:
            ready = pending.filtered(
                lambda line: not line.linked_line_id or line.linked_line_id in new_lines
            )
            if not ready:
                raise UserError(_(
                    "The linked lines of order %(order)s cannot be routed.", order=self.name
                ))
            vals_list = []
            for line in ready:
                values = line._prepare_company_routing_values(derived, convert)
                if line.linked_line_id:
                    values["linked_line_id"] = new_lines[line.linked_line_id].id
                vals_list.append(values)
            for line, new_line in zip(ready, Line.create(vals_list)):
                new_lines[line] = new_line
            pending -= ready
        return derived

    def _company_routing_validate_pickup(self, company):
        """
        El almacen de retiro elegido debe ser de la compañia que se queda con el envio.

        :param company: compañia destino del envio
        """
        self.ensure_one()
        warehouse = self.env["stock.warehouse"].browse(self.pickup_location_data.get("id")).exists()
        if warehouse.company_id != company:
            raise UserError(_(
                "The pickup location %(warehouse)s of order %(order)s does not belong to "
                "%(company)s, where the lines are routed.",
                warehouse=warehouse.display_name or "-", order=self.name, company=company.name,
            ))

    def _company_routing_set_pickup_warehouse(self):
        """Fijar en el derivado el almacen de retiro y recalcular posicion fiscal e impuestos."""
        self.ensure_one()
        if self.carrier_id.delivery_type != "in_store" or not self.pickup_location_data:
            return
        fiscal_position_before = self.fiscal_position_id
        self.warehouse_id = self.pickup_location_data["id"]
        self._compute_fiscal_position_id()
        if fiscal_position_before != self.fiscal_position_id:
            self._recompute_taxes()

    def _company_routing_check_warehouse(self, company):
        """
        El almacen del derivado debe ser de la compañia destino. Levanta `UserError`.

        :param company: compañia destino
        """
        self.ensure_one()
        if self.warehouse_id.company_id != company:
            raise UserError(_(
                "The warehouse %(warehouse)s of the order created in %(company)s belongs to "
                "another company.",
                warehouse=self.warehouse_id.display_name or "-", company=company.name,
            ))

    def _company_routing_notify(self, derived_orders):
        """Dejar en el chatter de cada pedido el vinculo con los demas."""
        self.ensure_one()
        derived_links = Markup(", ").join(order._get_html_link(title=order.name) for order in derived_orders)
        body = Markup(_("The lines of other companies were moved to: %(orders)s.")) % {
            "orders": derived_links
        }
        if self.transaction_ids.filtered(lambda tx: tx.state in ("authorized", "pending", "done")):
            body += Markup("<br/>") + _(
                "The online payment remains registered in %(company)s, the company of this order.",
                company=self.company_id.name,
            )
        self.message_post(body=body)
        link = self._get_html_link(title=self.name)
        for derived in derived_orders:
            derived.message_post(
                body=Markup(_("Order created when confirming %(order)s.")) % {"order": link}
            )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
