# -*- coding: utf-8 -*-
from odoo import fields, models


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    sunra_pull_kit_components = fields.Boolean(
        string="Pull Kit Component Serials", default=False,
        help="Opt-in: when checked, closing a Manufacturing Order using this BoM translates the "
             "bike components (motor, batteries, controller) mounted on the kit's chassis serial "
             "to the finished bicycle's serial, reusing the same chassis number. Without this "
             "flag the module does not intervene on this BoM's manufacturing orders at all.",
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
