# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProductCategory(models.Model):
    _name = 'product.category'
    _inherit = ['product.category', 'warranty.mixin']


