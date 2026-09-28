# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    installation_require_photos = fields.Boolean(
        string="Require Installation Photos",
        default=False,
        help="Tasks of this project cannot be marked as done without at least one photo of the "
             "installed lock.",
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
