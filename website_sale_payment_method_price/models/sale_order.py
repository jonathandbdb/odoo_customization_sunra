# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.tools import format_amount


class SaleOrder(models.Model):
    _inherit = "sale.order"

    payment_price_rule_id = fields.Many2one(
        comodel_name="payment.method.website.price",
        string="Payment Method Price Rule",
        copy=False,
        readonly=True,
        help="Price rule currently materialised on this order as a discount line.",
    )

    def _get_payment_price_scope_lines(self, rule):
        """
        Lineas del pedido sobre las que se calcula el ajuste, segun el alcance de la regla.

        :param rule: regla de precio del medio de pago
        :type rule: recordset de `payment.method.website.price`
        :return: lineas en alcance
        :rtype: recordset de `sale.order.line`
        """
        self.ensure_one()
        lines = self.order_line.filtered(
            lambda line: not line.display_type and not line.is_payment_method_discount
        )
        if rule.applies_to == "all":
            return lines
        if rule.applies_to == "product":
            return lines.filtered(lambda line: not line.is_delivery)
        return lines.filtered(lambda line: line.is_delivery)

    def _get_payment_price_amount(self, rule):
        """
        Importe del ajuste, expresado como total CON impuestos.

        El redondeo de la regla se aplica al precio unitario en la misma base que muestra el sitio
        (`show_line_subtotals_tax_selection`), para que el total cobrado coincida con el precio que
        vio el cliente. El core espera el importe con impuestos —
        `account.tax._reduce_base_lines_to_target_amount` lo compara contra
        `total_excluded + tax_amount` — asi que si el sitio muestra precios sin impuestos se escala
        la diferencia por la relacion bruto/neto del propio pedido.

        :param rule: regla de precio del medio de pago
        :type rule: recordset de `payment.method.website.price`
        :return: importe a descontar (positivo) o a recargar (negativo)
        :rtype: float
        """
        self.ensure_one()
        lines = self._get_payment_price_scope_lines(rule)
        if not lines:
            return 0.0
        tax_excluded = self.website_id.show_line_subtotals_tax_selection == "tax_excluded"
        base_gross = sum(lines.mapped("price_total"))
        base_net = sum(lines.mapped("price_subtotal"))
        base_shown = base_net if tax_excluded else base_gross
        target_shown = 0.0
        for line in lines:
            quantity = line.product_uom_qty
            if not quantity:
                continue
            line_shown = line.price_subtotal if tax_excluded else line.price_total
            target_shown += rule._apply_to_price(line_shown / quantity) * quantity
        delta_shown = base_shown - target_shown
        if tax_excluded and base_net:
            delta_shown *= base_gross / base_net
        return self.currency_id.round(delta_shown)

    def _get_payment_method_price_totals(self):
        """
        Totales del pedido por medio de pago, para mostrarlos debajo del total del carrito.

        Si el pedido ya tiene un ajuste aplicado no se muestra nada: el total ya lo incluye y
        listar los precios de nuevo lo contaria dos veces.

        :return: lista de dicts con label, price y price_formatted
        :rtype: list
        """
        self.ensure_one()
        if self.payment_price_rule_id:
            return []
        rules = self.env["payment.method.website.price"]._get_website_rules(
            self.website_id, only_visible=True
        )
        vals = []
        for rule in rules:
            amount = self._get_payment_price_amount(rule)
            if self.currency_id.is_zero(amount):
                continue
            total = self.amount_total - amount
            vals.append({
                "label": _("with %(method)s", method=rule.payment_method_id.name),
                "price": total,
                "price_formatted": format_amount(self.env, total, self.currency_id),
            })
        return vals

    def _remove_payment_price_rule(self):
        """Quitar del pedido el ajuste por medio de pago, si estaba aplicado."""
        for order in self:
            lines = order.order_line.filtered("is_payment_method_discount")
            if lines:
                lines.unlink()
            if order.payment_price_rule_id:
                order.payment_price_rule_id = False

    def _apply_payment_price_rule(self, rule):
        """
        Materializar el ajuste de una regla sobre el pedido (o solo quitarlo si `rule` esta vacio).

        Reusa el descuento global del core (`sale.order.discount` con importe fijo), que parte el
        importe por combinacion de impuestos. La operacion es idempotente: primero se limpia lo
        que hubiera aplicado, nunca se apila.

        :param rule: regla a aplicar, o recordset vacio para dejar el pedido sin ajuste
        :type rule: recordset de `payment.method.website.price`
        :return: None
        """
        self.ensure_one()
        self._remove_payment_price_rule()
        if not rule:
            return
        amount = self._get_payment_price_amount(rule)
        if self.currency_id.is_zero(amount):
            return
        lines_before = self.order_line
        # sudo: lo dispara un visitante publico del sitio, que no puede crear el wizard ni el
        # producto de descuento de la compania. No expone datos: el wizard opera sobre este pedido.
        wizard = self.env["sale.order.discount"].sudo().create({
            "sale_order_id": self.id,
            "discount_type": "amount",
            "discount_amount": amount,
        })
        wizard.action_apply_discount()
        new_lines = self.order_line - lines_before
        # El core nombra la linea "Discount" (y le suma los impuestos si hay varias combinaciones):
        # se le agrega el medio de pago para que el cliente entienda de donde sale
        for line in new_lines:
            line.name = "%s - %s" % (line.name, rule.payment_method_id.name)
        new_lines.is_payment_method_discount = True
        self.payment_price_rule_id = rule

    def _recompute_cart(self):
        """Override de `website_sale` para reajustar el descuento cuando cambia el carrito."""
        res = super()._recompute_cart()
        if self.env.context.get("wspmp_skip_recompute"):
            return res
        for order in self:
            rule = order.payment_price_rule_id
            if rule:
                order.with_context(wspmp_skip_recompute=True)._apply_payment_price_rule(rule)
        return res

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
