# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    _inherit = "project.task"

    installation_product_ids = fields.Many2many(
        comodel_name="product.product",
        relation="project_task_installation_product_rel",
        column1="task_id",
        column2="product_id",
        string="Installed Models",
        copy=False,
        help="Lock models the crew installed during this visit. No quantity: a single visit can "
             "install more than one lock.",
    )
    installation_amount = fields.Monetary(
        string="Amount to Charge",
        currency_field="installation_currency_id",
        copy=False,
        help="Amount to collect for this visit, one per task. Loaded by the back office before "
             "the visit; the installer sees it read-only.",
    )
    installation_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Installation Currency",
        related="company_id.currency_id",
    )
    installation_photo_ids = fields.Many2many(
        comodel_name="ir.attachment",
        relation="project_task_installation_photo_rel",
        column1="task_id",
        column2="attachment_id",
        string="Installation Photos",
        copy=False,
        help="Photos of the installed lock, uploaded by the installer. The customer's site "
             "photos are kept on the order and appointment chatter instead.",
    )

    def write(self, vals):
        # El gate va DESPUES del super() (D63): el formulario manda en un solo write() las fotos
        # y el cambio de estado juntos, asi que el chequeo tiene que ver la foto ya guardada. Si
        # falta, el UserError revierte la transaccion entera, super() incluido.
        res = super().write(vals)
        if "state" not in vals and "installation_photo_ids" not in vals:
            return res
        missing_photos = self.filtered(
            lambda task: task.state == "1_done"
            and task.project_id.is_fsm
            and task.project_id.installation_require_photos
            and not task.installation_photo_ids
        )
        if missing_photos:
            raise UserError(_(
                "Upload at least one photo of the installed lock before marking the task as done."
            ))
        return res

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
