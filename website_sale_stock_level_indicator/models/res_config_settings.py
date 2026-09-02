# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Espejo de los campos del sitio: el formulario de ajustes de Sitio Web ya trae el selector de
    # website, asi que la configuracion queda por sitio sin trabajo extra.
    show_stock_level = fields.Boolean(
        related="website_id.show_stock_level",
        readonly=False,
    )
    stock_level_ids = fields.One2many(
        related="website_id.stock_level_ids",
        readonly=False,
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
