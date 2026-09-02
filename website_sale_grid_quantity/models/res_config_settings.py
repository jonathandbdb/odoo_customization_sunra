# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Espejo del campo del sitio: el formulario de ajustes de Sitio Web ya trae el selector de
    # website, asi que el toggle queda parametrizado por sitio sin trabajo extra.
    show_grid_quantity = fields.Boolean(
        related="website_id.show_grid_quantity",
        readonly=False,
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
