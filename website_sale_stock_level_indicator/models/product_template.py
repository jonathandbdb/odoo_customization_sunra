# -*- coding: utf-8 -*-
from odoo import models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    #=== BUSINESS METHODS ===#

    def _get_additionnal_combination_info(self, product_or_template, quantity, uom, date, website):
        # La pagina de producto se renderiza para la plantilla: el unico lugar donde se sabe que
        # variante quedo elegida es este payload, que el frontend vuelve a pedir cada vez que el
        # cliente cambia la seleccion (/website_sale/get_combination_info).
        combination_info = super()._get_additionnal_combination_info(
            product_or_template, quantity, uom, date, website
        )
        level = self.env["website.stock.level"]
        if product_or_template.is_product_variant:
            level = website._get_variant_stock_level(product_or_template)
        combination_info.update({
            "stock_level_name": level.name or "",
            "stock_level_class": level._get_badge_class() if level else "",
            "stock_level_style": level._get_badge_style() if level else "",
        })
        return combination_info

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
