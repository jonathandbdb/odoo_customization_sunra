# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.tools.misc import formatLang


class AccountCardInstallment(models.Model):
    _inherit = "account.card.installment"

    def _get_installment_currency(self):
        """
        Moneda con la que se formatea el importe de la cuota.

        :return: moneda del sitio web cuando estamos en una request del frontend,
                 y la de la compania actual en cualquier otro caso
        :rtype: res.currency
        """
        website = self.env["website"].get_current_website(fallback=False)
        return website.currency_id or self.env.company.currency_id

    def map_installment_values(self, amount_total):
        """
        Reescribe la leyenda de cuotas que se muestra en el eCommerce.

        Se diferencia de la del modulo base en tres cosas: no muestra el total,
        formatea el importe con la moneda del sitio (separador de miles) y toma la
        cantidad de cuotas del divisor, que es el campo que representa en cuantas
        cuotas se divide el total.

        :param amount_total: precio sobre el que se calcula la cuota
        :type amount_total: float
        :return: dict de valores del plan, con la clave description reescrita
        :rtype: dict
        """
        self.ensure_one()
        result = super().map_installment_values(amount_total)

        divisor = self.divisor or 1
        amount = formatLang(
            self.env, result["amount"] / divisor, currency_obj=self._get_installment_currency()
        )
        result["description"] = (
            _("In %(count)s installment of %(amount)s", count=divisor, amount=amount)
            if divisor == 1
            else _("In %(count)s installments of %(amount)s", count=divisor, amount=amount)
        )
        return result

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
