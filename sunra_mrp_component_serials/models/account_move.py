# -*- coding: utf-8 -*-
from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_invoiced_lot_values(self):
        # Enriquece la tabla de series de la factura con motor/fajas/controlador/cargador (D16).
        res = super()._get_invoiced_lot_values()

        lot_ids = {values["lot_id"] for values in res if values.get("lot_id")}
        # Un solo browse + sudo() para todos los lotes (nunca browse+sudo() por fila).
        values_by_lot = {
            lot.id: lot._sunra_component_report_values()
            for lot in self.env["stock.lot"].browse(lot_ids).sudo()
        }

        # Normalizar TODAS las filas con las cuatro claves: point_of_sale agrega dicts con
        # pos_lot_id y SIN lot_id (y sale_stock_renting tambien extiende este metodo). Si el
        # QWeb indexara duro una clave ausente, la factura entera no se imprimiria.
        empty_values = {"motor_name": "", "battery_names": "", "controller_name": "", "charger_name": ""}
        for values in res:
            values.update(values_by_lot.get(values.get("lot_id"), empty_values))

        return res

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
