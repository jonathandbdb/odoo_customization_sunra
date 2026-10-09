# -*- coding: utf-8 -*-
from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    auto_validate_intercompany_transfer = fields.Boolean(
        string="Auto-Validate Inter-Company Transfer",
        default=False,
        help="When a sale needs stock from another company through the inter-company transit, "
        "the delivery of the supplying company and this receipt are validated automatically "
        "with the available quantity. Only for receipts.",
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
