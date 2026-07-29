# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    # Related readonly, solo para display en el form FSM: las vistas de Odoo no traversan
    # rutas con puntos (helpdesk_ticket_id.warranty_status), asi que hacen falta estos dos
    # campos "puente" sin logica propia y sin store.
    service_warranty_status = fields.Selection(
        related="helpdesk_ticket_id.warranty_status", string="Warranty Status", readonly=True,
    )
    service_warranty_expiry_date = fields.Date(
        related="helpdesk_ticket_id.warranty_expiry_date", string="Warranty Expiry Date",
        readonly=True,
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
