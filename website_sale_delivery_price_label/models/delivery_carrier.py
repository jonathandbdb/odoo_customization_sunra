# -*- coding: utf-8 -*-
from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    # Texto que reemplaza al precio/"Gratis" del badge de este metodo en el checkout (ver
    # views/website_sale_templates.xml y static/src/js/delivery_price_label.js).
    website_price_label = fields.Char(
        string="Website price label",
        translate=True,
        help="Shown in the eCommerce delivery method selector instead of the price. Leave empty "
             "to show the price.",
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
