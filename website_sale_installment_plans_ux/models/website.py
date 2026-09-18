# -*- coding: utf-8 -*-
from odoo import fields, models


class Website(models.Model):
    _inherit = "website"

    show_installment_plans = fields.Boolean(
        string="Installment Plans",
        default=True,
        help="Show the installment legend below the price, both in the shop list and on the "
             "product page. The plans themselves are configured per card in Accounting "
             "(Payments > Cards); only the ones belonging to this website's company are shown.",
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
