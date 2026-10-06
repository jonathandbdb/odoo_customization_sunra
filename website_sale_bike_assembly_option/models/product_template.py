# -*- coding: utf-8 -*-
from odoo import models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _has_bike_assembly_option(self):
        """Indica si alguna variante de la plantilla tiene kit en caja."""
        self.ensure_one()
        return bool(self.sudo().product_variant_ids._get_assembly_kit_products())

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
