# -*- coding: utf-8 -*-
from odoo import fields, models


class Website(models.Model):
    _inherit = "website"

    show_grid_quantity = fields.Boolean(
        string="Quantity Selector in Product List",
        help="Show a quantity selector with plus and minus buttons on every product card of the "
             "shop, so customers can choose how many units to add without opening the product "
             "page. Useful for spare parts catalogs, where an order is made of many different "
             "items.",
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
