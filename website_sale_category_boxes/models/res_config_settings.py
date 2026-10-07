# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    website_shop_category_boxes = fields.Boolean(
        related="website_id.shop_category_boxes",
        readonly=False,
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
