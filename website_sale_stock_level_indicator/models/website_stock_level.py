# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Clases contextuales de Bootstrap. Usamos las mismas que el core (`text-bg-danger` para sin stock,
# `text-bg-warning` para el umbral) para que el cartel herede el tema del sitio en lugar de traer
# colores propios que despues no acompañan un cambio de paleta.
COLOR_SELECTION = [
    ("danger", "Red"),
    ("warning", "Orange"),
    ("success", "Green"),
    ("info", "Light blue"),
    ("primary", "Blue"),
    ("secondary", "Grey"),
    ("dark", "Black"),
]


class WebsiteStockLevel(models.Model):
    _name = "website.stock.level"
    _description = "Website Stock Level"
    # De mayor a menor: la resolucion toma el primero que la disponibilidad alcanza.
    _order = "website_id, min_qty desc"

    name = fields.Char(
        string="Label",
        required=True,
        translate=True,
        help="Text shown on the product, e.g. \"Low stock\".",
    )
    website_id = fields.Many2one(
        comodel_name="website",
        string="Website",
        required=True,
        ondelete="cascade",
        index=True,
    )
    min_qty = fields.Float(
        string="From Quantity",
        required=True,
        default=0.0,
        help="This level applies when the available quantity reaches this number and does not "
             "reach the next level. Use 0 for the out of stock level.",
    )
    color = fields.Selection(
        selection=COLOR_SELECTION,
        string="Color",
        required=True,
        default="secondary",
    )
    color_custom = fields.Char(
        string="Custom Color",
        help="Optional CSS color (e.g. #B4E933) used instead of the color above, for a brand "
             "color that is not in the list.",
    )

    # v19: `_sql_constraints` fue eliminado, las constraints van como atributo de clase.
    _min_qty_uniq = models.Constraint(
        "unique (website_id, min_qty)",
        "Two stock levels of the same website cannot start at the same quantity.",
    )

    #=== CONSTRAINTS ===#

    @api.constrains("min_qty")
    def _check_min_qty(self):
        # Un nivel que arranca en negativo no se alcanza nunca: la disponibilidad se piso en 0.
        for level in self:
            if level.min_qty < 0:
                raise ValidationError(_("The quantity of a stock level cannot be negative."))

    #=== BUSINESS METHODS ===#

    def _get_badge_class(self):
        """Clase del cartel. Vacia si el nivel usa un color propio (va por style)."""
        self.ensure_one()
        return "" if self.color_custom else "text-bg-%s" % self.color

    def _get_badge_style(self):
        """Estilo inline, solo cuando el nivel define un color propio."""
        self.ensure_one()
        if not self.color_custom:
            return ""
        return "background-color: %s;" % self.color_custom

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
