# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    company_routing_excluded = fields.Boolean(
        string="Exclude from Company Routing",
        default=False,
        help="Orders of this company are confirmed whole in it: none of their lines is moved to "
             "another company.",
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
