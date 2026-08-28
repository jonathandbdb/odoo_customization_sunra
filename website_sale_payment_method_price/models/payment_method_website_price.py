# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_round


class PaymentMethodWebsitePrice(models.Model):
    _name = "payment.method.website.price"
    _description = "Payment Method Website Price"
    _order = "payment_method_id, sequence, id"

    payment_method_id = fields.Many2one(
        comodel_name="payment.method",
        string="Payment Method",
        required=True,
        ondelete="cascade",
        index=True,
    )
    website_id = fields.Many2one(
        comodel_name="website",
        string="Website",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order in which the extra prices are listed on the website.",
    )
    price_type = fields.Selection(
        selection=[
            ("discount", "Discount"),
            ("surcharge", "Surcharge"),
        ],
        string="Type",
        required=True,
        default="discount",
    )
    percentage = fields.Float(
        string="Percentage",
        digits=(16, 2),
        required=True,
        default=0.0,
        help="Percentage applied to the price when this payment method is used."
             " A rule with 0 has no effect.",
    )
    applies_to = fields.Selection(
        selection=[
            ("product", "Products"),
            ("delivery", "Shipping"),
            ("all", "Products and Shipping"),
        ],
        string="Applies To",
        required=True,
        default="product",
        help="Which part of the order the percentage is computed on."
             " The website only ever shows the product price, so this only affects the checkout.",
    )
    price_round = fields.Float(
        string="Price Rounding",
        help="Sets the price so that it is a multiple of this value.\n"
             "Rounding is applied after the percentage.\n"
             "Leave it at 0 to keep the exact result.",
    )
    show_on_website = fields.Boolean(
        string="Show Price on Website",
        default=True,
        help="Display the resulting price below the regular price on the shop and product pages.",
    )

    _unique_method_website = models.Constraint(
        "UNIQUE(payment_method_id, website_id)",
        "There can only be one price rule per payment method and website.",
    )

    @api.constrains("percentage")
    def _check_percentage(self):
        # El porcentaje se expresa 0-100; un descuento del 100% deja el precio en cero
        for rule in self:
            if not 0.0 <= rule.percentage <= 100.0:
                raise ValidationError(_("The percentage must be between 0 and 100."))

    @api.constrains("price_round")
    def _check_price_round(self):
        for rule in self:
            if rule.price_round < 0.0:
                raise ValidationError(_("The price rounding cannot be negative."))

    def _apply_to_price(self, price):
        """
        Aplicar el ajuste de esta regla a un precio.

        Mismo orden que el core (`product.pricelist.item._compute_price`, rama `formula`):
        primero el porcentaje, despues el redondeo a multiplo.

        :param price: precio base, en la misma base (con o sin impuestos) que se quiera ajustar
        :type price: float
        :return: precio ajustado
        :rtype: float
        """
        self.ensure_one()
        sign = -1.0 if self.price_type == "discount" else 1.0
        new_price = price + sign * price * (self.percentage / 100.0)
        if self.price_round:
            new_price = float_round(new_price, precision_rounding=self.price_round)
        return new_price

    @api.model
    def _get_website_rules(self, website, only_visible=False):
        """
        Reglas vigentes de un sitio web, ya filtradas por disponibilidad real del medio de pago.

        Se descartan las reglas sin efecto (porcentaje 0) y las de medios que el cliente no puede
        elegir en ese sitio: mostrar un precio de un medio no disponible seria mentirle.

        :param website: sitio web para el que se resuelven las reglas
        :type website: recordset de `website`
        :param only_visible: si True, solo las marcadas para mostrarse en el sitio
        :type only_visible: bool
        :return: recordset de reglas
        :rtype: recordset de `payment.method.website.price`
        """
        domain = [
            ("website_id", "=", website.id),
            ("percentage", "!=", 0.0),
            ("payment_method_id.active", "=", True),
        ]
        if only_visible:
            domain.append(("show_on_website", "=", True))
        rules = self.sudo().search(domain)
        return rules.filtered(lambda rule: rule._is_payment_method_available())

    def _is_payment_method_available(self):
        """Indicar si el medio de pago de la regla esta disponible en el sitio de la regla."""
        self.ensure_one()
        for provider in self.payment_method_id.provider_ids:
            if provider.state == "disabled" or not provider.is_published:
                continue
            if provider.company_id != self.website_id.company_id:
                continue
            # website_id viene de website_payment (dependencia de website_sale): vacio = sin
            # restriccion de sitio
            if provider.website_id and provider.website_id != self.website_id:
                continue
            return True
        return False

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
