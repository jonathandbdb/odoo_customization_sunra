# -*- coding: utf-8 -*-
from odoo import fields, models


class PaymentMethod(models.Model):
    _inherit = "payment.method"

    website_price_ids = fields.One2many(
        comodel_name="payment.method.website.price",
        inverse_name="payment_method_id",
        string="Website Prices",
    )

    def _get_website_price_rule(self, website):
        """
        Regla de precio de este medio de pago para un sitio web.

        Se busca SIEMPRE en el metodo primario: en el checkout el radio button es el primario
        (`card`), pero el proveedor reescribe `payment_method_id` con la marca real (`visa`) al
        procesar el feedback, asi que buscar por el metodo tal cual llega perderia la regla.

        :param website: sitio web para el que se resuelve la regla
        :type website: recordset de `website`
        :return: la regla, o un recordset vacio
        :rtype: recordset de `payment.method.website.price`
        """
        self.ensure_one()
        method = self.primary_payment_method_id or self
        rules = method.sudo().website_price_ids.filtered(
            lambda rule: rule.website_id == website and rule.percentage
        )
        return rules[:1]

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
