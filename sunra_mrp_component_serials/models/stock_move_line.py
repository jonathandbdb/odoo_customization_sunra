# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    sunra_motor_name = fields.Char(
        string="Motor", compute="_compute_sunra_component_names",
        help="Serial number of the motor mounted on the chassis being moved.",
    )
    sunra_battery_names = fields.Char(
        string="Batteries", compute="_compute_sunra_component_names",
        help="Serial numbers (fajas) of the batteries mounted on the chassis being moved.",
    )
    sunra_controller_name = fields.Char(
        string="Controller", compute="_compute_sunra_component_names",
        help="Serial number of the controller mounted on the chassis being moved.",
    )
    sunra_charger_name = fields.Char(
        string="Charger", compute="_compute_sunra_component_names",
        help="Serial number (faja) of the charger shipped with the chassis being moved.",
    )

    @api.depends(
        "lot_id",
        "lot_id.component_ids.name",
        "lot_id.component_ids.component_type",
    )
    def _compute_sunra_component_names(self):
        # Un solo compute para las cuatro columnas: reusa el helper que ya alimenta remito y
        # factura, asi la pantalla y el papel no pueden decir cosas distintas. Un lote vacio
        # devuelve el dict con los cuatro valores en "".
        for line in self:
            values = line.lot_id._sunra_component_report_values()
            line.sunra_motor_name = values["motor_name"]
            line.sunra_battery_names = values["battery_names"]
            line.sunra_controller_name = values["controller_name"]
            line.sunra_charger_name = values["charger_name"]

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
