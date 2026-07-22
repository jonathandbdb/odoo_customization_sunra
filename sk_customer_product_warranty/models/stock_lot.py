# -*- coding: utf-8 -*-
from odoo import models, fields, api


class StockLot(models.Model):
    _inherit = 'stock.lot'

    warranty_expiry_date = fields.Date(
        string='Warranty Expiry Date',
        help='Warranty expiry date for this serial (calculated based on customer delivery date)'
    )

