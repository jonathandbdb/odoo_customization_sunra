# -*- coding: utf-8 -*-
from odoo import fields, models


class Website(models.Model):
    _inherit = "website"

    hide_cart_line_description = fields.Boolean(
        string="Hide Sales Description in Cart",
        help="Do not display the sales description of the order line in the shopping cart.\n"
             "The value is not removed: it stays on the product and on the order line, so it "
             "remains available for the website search and for the quotation PDF. It is only "
             "hidden from the cart summary, where it duplicates the internal reference already "
             "shown for each line.",
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
