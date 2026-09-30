# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Acciones de Field Service (My Tasks / All Tasks, con uno o varios proyectos FSM) que abren en
# el calendario.
FSM_CALENDAR_FIRST_ACTIONS = (
    "industry_fsm.project_task_action_fsm",
    "industry_fsm.project_task_action_fsm2",
    "industry_fsm.project_task_action_all_fsm",
    "industry_fsm.project_task_action_all_fsm2",
)


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
        help="Photos of the installed lock, uploaded by the installer. The only ones that count "
             "to close the task; the customer's site photos are shown in Site photos.",
    )
    installation_site_photo_ids = fields.Many2many(
        comodel_name="ir.attachment",
        string="Site Photos",
        compute="_compute_installation_site_photo_ids",
        readonly=True,
        help="Images of the task chatter: the photos of the place the customer uploaded and any "
             "image added later. Read-only; they do not count to close the task.",
    )

    @api.depends("installation_photo_ids")
    def _compute_installation_site_photo_ids(self):
        # Una sola busqueda para todo el recordset. Sin sudo(): el search de adjuntos ya filtra
        # por el acceso al registro referenciado.
        attachments = self.env["ir.attachment"].search([
            ("res_model", "=", "project.task"),
            ("res_id", "in", self._origin.ids),
            ("mimetype", "=like", "image/%"),
        ], order="id")
        by_task = defaultdict(lambda: self.env["ir.attachment"])
        for attachment in attachments:
            by_task[attachment.res_id] |= attachment
        for task in self:
            task.installation_site_photo_ids = by_task[task._origin.id] - task.installation_photo_ids

    def _server_action_project_task_fsm(self, xml_id_multiple_fsm_projects, xml_id_one_fsm_project,
                                        default_user_ids=False):
        """ Abre el calendario primero en las acciones de Field Service (D67).

        No se usan registros `ir.actions.act_window.view`: el indice unico (accion, tipo de vista)
        ya lo ocupa el calendario de cada accion de industry_fsm.
        """
        action = super()._server_action_project_task_fsm(
            xml_id_multiple_fsm_projects, xml_id_one_fsm_project, default_user_ids=default_user_ids,
        )
        if action.get("xml_id") in FSM_CALENDAR_FIRST_ACTIONS:
            views = action.get("views") or []
            # sorted es estable: solo adelanta el calendario, el resto conserva su orden.
            action["views"] = sorted(views, key=lambda view: view[1] != "calendar")
            # En pantalla chica el cliente web abre la vista de mobile_view_mode (default kanban).
            action["mobile_view_mode"] = "calendar"
        return action

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
