# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    free_battery_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Free Battery Product",
        ondelete="restrict",
        check_company=True,
        help="Battery product added to the order at no cost, but only when the chosen shipping "
             "method has 'Includes Free Batteries' enabled.",
    )
    free_battery_qty = fields.Integer(
        string="Free Batteries Quantity",
        default=0,
        help="Quantity to add for free, expressed in the battery product's own unit of measure: "
             "for batteries sold in packs of 4, 1 means one pack (4 batteries).",
    )
    # Related al campo nativo (odoo/addons/product/models/product_template.py: uom_name =
    # related='uom_id.name'), un hop mas alla via el producto de pila elegido: sirve solo para
    # mostrar la UoM al lado de la cantidad y que "1" no se lea como "una pila".
    free_battery_uom_name = fields.Char(
        string="Battery Unit",
        related="free_battery_product_id.uom_name",
        readonly=True,
    )

    @api.constrains("free_battery_product_id", "free_battery_qty")
    def _check_free_battery_config(self):
        # Los dos campos van juntos (si no, el opt-in queda a medias y nadie se entera) y un
        # producto no puede ser su propia pila.
        for template in self:
            if template.free_battery_qty < 0:
                raise ValidationError(_(
                    "The free batteries quantity of %(product)s cannot be negative.",
                    product=template.display_name,
                ))
            if bool(template.free_battery_product_id) != (template.free_battery_qty > 0):
                raise ValidationError(_(
                    "Configure both the free battery product and its quantity for %(product)s "
                    "(the quantity is expressed in the battery product's own unit of measure), "
                    "or leave both empty.",
                    product=template.display_name,
                ))
            if template.free_battery_product_id.product_tmpl_id == template:
                raise ValidationError(_(
                    "%(product)s cannot be configured as its own free battery product.",
                    product=template.display_name,
                ))

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
