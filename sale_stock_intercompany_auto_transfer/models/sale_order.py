# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import _, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _intercompany_auto_transfer(self, new_moves):
        """Valida la salida de la proveedora y, por encadenamiento, la recepcion.

        :param new_moves: stock.move (sudo) creados por el lanzamiento de reglas
        """
        Picking = self.env["stock.picking"].sudo()
        for order in self:
            order_moves = new_moves & order.stock_reference_ids.sudo().move_ids
            moves = order_moves.filtered(lambda m: order._is_intercompany_chain_source(m))
            if not moves:
                continue
            for company in moves.company_id:
                moves.filtered(lambda m: m.company_id == company).with_company(company)._action_assign()

            shortages = []
            for move in moves:
                missing = move.product_uom_qty - move.quantity
                if move.product_uom.compare(missing, 0) > 0:
                    shortages.append(
                        (move.product_id.display_name, move.product_uom.round(missing),
                         move.product_uom.name, move.company_id.name)
                    )

            pickings = moves.picking_id
            receipt_ids = moves.move_dest_ids.picking_id.ids
            to_validate = pickings.filtered(lambda p: any(m.quantity > 0 for m in p.move_ids))
            reasons = to_validate._intercompany_auto_validate()

            # Tras los savepoints se relee por id (cache invalidado en un rollback).
            pending = []
            for picking in Picking.browse(pickings.ids):
                if picking.state != "done":
                    pending.append((picking, reasons.get(picking.id)))
            for receipt in Picking.browse(receipt_ids):
                if receipt.state not in ("done", "cancel"):
                    pending.append((receipt, None))
            order._intercompany_post_notice(shortages, pending)

    def _is_intercompany_chain_source(self, move):
        """Movimiento de otra compañia que alimenta una recepcion activada de otra compañia."""
        self.ensure_one()
        return (
            move.company_id != self.company_id
            and move.state not in ("draft", "done", "cancel")
            and move._get_intercompany_auto_dests()
        )

    def _intercompany_post_notice(self, shortages, pending):
        """Un unico mensaje en el pedido con faltantes y transferencias pendientes."""
        self.ensure_one()
        if not shortages and not pending:
            return
        items = []
        for name, missing, uom, company in shortages:
            items.append(
                Markup("<li>%s</li>")
                % _(
                    "Missing %(qty)s %(uom)s of %(product)s in %(company)s.",
                    qty="%g" % missing, uom=uom, product=name, company=company,
                )
            )
        for picking, reason in pending:
            if reason:
                items.append(Markup("<li>%s: %s</li>") % (picking._get_html_link(), reason))
            else:
                items.append(
                    Markup("<li>%s: %s</li>")
                    % (picking._get_html_link(), _("Pending, to be validated manually."))
                )
        self.message_post(
            body=Markup("<p>%s</p><ul>%s</ul>")
            % (_("The inter-company transfer could not be completed automatically:"), Markup("").join(items)),
            subtype_xmlid="mail.mt_note",
        )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
