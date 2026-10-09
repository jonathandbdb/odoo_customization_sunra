# -*- coding: utf-8 -*-
from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_intercompany_auto_dests(self):
        """Movimientos destino que hacen de self el origen de una cadena inter-company activada.

        :return: stock.move (sudo) de move_dest_ids de otra compañia, de un tipo de recepcion activado
        """
        self.ensure_one()
        return self.sudo().move_dest_ids.filtered(
            lambda dest: dest.company_id != self.company_id
            and dest.picking_type_id.code == "incoming"
            and dest.picking_type_id.auto_validate_intercompany_transfer
        )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
