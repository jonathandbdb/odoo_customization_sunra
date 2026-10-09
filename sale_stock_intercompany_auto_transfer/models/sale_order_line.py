# -*- coding: utf-8 -*-
from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _action_launch_stock_rule(self, *, previous_product_uom_qty=False):
        if self.env.context.get("skip_procurement"):
            return super()._action_launch_stock_rule(previous_product_uom_qty=previous_product_uom_qty)
        orders = self.order_id
        before = set(orders.stock_reference_ids.sudo().move_ids.ids)
        res = super()._action_launch_stock_rule(previous_product_uom_qty=previous_product_uom_qty)
        # El many2many inverso no se refresca solo al crear movimientos con sus referencias.
        orders.invalidate_recordset(["stock_reference_ids"])
        orders.stock_reference_ids.invalidate_recordset(["move_ids"])
        new_moves = orders.stock_reference_ids.sudo().move_ids.filtered(lambda m: m.id not in before)
        if new_moves:
            orders._intercompany_auto_transfer(new_moves)
        return res

    def _get_outgoing_incoming_moves(self, strict=True):
        outgoing_moves, incoming_moves = super()._get_outgoing_incoming_moves(strict=strict)
        # El core trata como devolucion toda entrada desde transito inter-company
        # (_is_outgoing(), stock_location.py:468-474; sale_order_line.py:364-366) y resta lo recibido.
        replenishment = incoming_moves.filtered(
            lambda m: m.location_id.usage == "transit"
            and m.location_id._is_outgoing()
            and m.location_dest_id.usage == "internal"
            and not m.origin_returned_move_id
        )
        return outgoing_moves, incoming_moves - replenishment

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
