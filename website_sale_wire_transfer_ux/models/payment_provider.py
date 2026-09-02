# -*- coding: utf-8 -*-
from odoo import models


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    def _get_wire_transfer_cbu_account(self):
        """
        Devolver la cuenta bancaria con CBU de la compania del proveedor de transferencia.

        El CBU es un dato estructurado en Odoo: la localizacion argentina agrega el tipo de cuenta
        `cbu` a `res.partner.bank` y lo detecta sola cuando el numero valida como CBU
        (`l10n_ar/models/res_partner_bank.py`). Se usa esa cuenta como unica fuente del numero que
        copia el boton, en lugar de parsear el HTML del mensaje pendiente.

        :return: la primera cuenta bancaria con CBU, o un recordset vacio si no hay
        :rtype: recordset de `res.partner.bank`
        """
        self.ensure_one()
        empty = self.env["res.partner.bank"]
        if self.code != "custom" or self.custom_mode != "wire_transfer":
            return empty
        company = self.company_id or self.env.company
        accounts = company.partner_id.sudo().bank_ids
        return accounts.filtered(lambda account: account.acc_type == "cbu")[:1]

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
