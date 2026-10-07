# -*- coding: utf-8 -*-
from odoo import fields, models


class Website(models.Model):
    _inherit = "website"

    shop_category_boxes = fields.Boolean(
        string="Category Boxes",
        help="Show each main shop category in its own box in the shop sidebar.",
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
