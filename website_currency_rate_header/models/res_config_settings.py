# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Espejo de los campos del sitio: el formulario de ajustes de Sitio Web ya trae el selector de
    # website, asi que la configuracion queda por sitio sin trabajo extra.
    show_currency_rate = fields.Boolean(
        related="website_id.show_currency_rate",
        readonly=False,
    )
    currency_rate_currency_id = fields.Many2one(
        related="website_id.currency_rate_currency_id",
        readonly=False,
    )
    currency_rate_label = fields.Char(
        related="website_id.currency_rate_label",
        readonly=False,
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
