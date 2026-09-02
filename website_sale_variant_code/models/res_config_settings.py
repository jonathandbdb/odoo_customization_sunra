# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Espejo del campo del sitio. El formulario de ajustes de Sitio Web ya trae el selector de
    # website arriba, asi que el toggle queda parametrizado por sitio sin trabajo extra: Sunra lo
    # prende y Miluan queda intacto.
    hide_cart_line_description = fields.Boolean(
        related="website_id.hide_cart_line_description",
        readonly=False,
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
