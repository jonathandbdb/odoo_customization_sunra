# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import _, models
from odoo.exceptions import RedirectWarning, UserError
from odoo.tools.misc import clean_context

# Ids de las transferencias en validacion automatica: evita validar dos veces la misma.
REENTRY_KEY = "sale_stock_intercompany_auto_transfer_validating"


class IntercompanyAutoValidateError(UserError):
    """La transferencia pide intervencion manual (wizard) o no quedo hecha."""


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _action_done(self):
        res = super()._action_done()
        receipts = self._get_intercompany_auto_receipts()
        if not receipts:
            return res
        pending = receipts._intercompany_auto_validate()
        self._intercompany_notify_pending_receipts(pending)
        return res

    def _get_intercompany_auto_receipts(self):
        """Recepciones activadas de otra compañia alimentadas por movimientos hechos de self.

        :return: stock.picking (sudo) con algo reservado y fuera de la validacion en curso
        """
        validating = self.env.context.get(REENTRY_KEY, [])
        receipts = self.env["stock.picking"].sudo()
        for move in self.sudo().move_ids.filtered(lambda m: m.state == "done"):
            receipts |= move._get_intercompany_auto_dests().picking_id
        return receipts.filtered(
            lambda p: p.state not in ("done", "cancel")
            and p.id not in validating
            and any(m.quantity > 0 for m in p.move_ids)
        )

    def _intercompany_auto_validate_context(self):
        """Contexto saneado: no hereda claves del llamador que alteren la validacion.

        :return: dict
        :rtype: dict
        """
        ctx = clean_context(self.env.context)
        for key in ("picking_ids_not_to_backorder", "button_validate_picking_ids", "cancel_backorder"):
            ctx.pop(key, None)
        ctx = {k: v for k, v in ctx.items() if not k.startswith("active_")}
        previous = list(self.env.context.get(REENTRY_KEY, []))
        ctx.update(
            skip_backorder=True,
            skip_sms=True,
            **{REENTRY_KEY: previous + self.ids},
        )
        return ctx

    def _intercompany_auto_validate(self):
        """Valida cada transferencia por lo reservado, sin wizard y sin bloquear al llamador.

        :return: dict {picking_id: motivo} de las que quedaron pendientes
        :rtype: dict
        """
        ctx = self._intercompany_auto_validate_context()
        pending = {}
        for picking_id in self.ids:
            base = self.env["stock.picking"].sudo().browse(picking_id)
            picking = base.with_context(ctx).with_company(base.company_id)
            try:
                with self.env.cr.savepoint():
                    picking.move_ids.filtered(
                        lambda m: m.state not in ("done", "cancel") and m.quantity > 0
                    ).picked = True
                    picking.button_validate()
                    if picking.state != "done":
                        raise IntercompanyAutoValidateError(_("It requires manual validation."))
            except (UserError, RedirectWarning) as error:
                # UserError incluye LockError: lock_for_update usa SKIP LOCKED y no aborta la
                # transaccion, asi que la transferencia queda pendiente (orm/models.py:5594-5602).
                # Tras el rollback del savepoint se relee todo por id (cache invalidado).
                pending[picking_id] = error.args[0] if error.args else _("It requires manual validation.")
        return pending

    def _intercompany_notify_pending_receipts(self, pending):
        """Avisa en la recepcion (y en el pedido, fuera de la validacion del pedido) el motivo.

        :param pending: dict {picking_id: motivo}
        """
        Picking = self.env["stock.picking"].sudo()
        orders = {}
        for picking_id, reason in pending.items():
            receipt = Picking.browse(picking_id)
            receipt.message_post(
                body=Markup("<p>%s</p>") % _("Automatic validation failed: %s", reason),
                subtype_xmlid="mail.mt_note",
            )
            if not self.env.context.get(REENTRY_KEY) and receipt.sale_id:
                orders.setdefault(receipt.sale_id, []).append((receipt, reason))
        for order, items in orders.items():
            lines = Markup("").join(
                Markup("<li>%s: %s</li>") % (receipt._get_html_link(), reason)
                for receipt, reason in items
            )
            order.message_post(
                body=Markup("<p>%s</p><ul>%s</ul>")
                % (_("The following inter-company receipts could not be validated automatically:"), lines),
                subtype_xmlid="mail.mt_note",
            )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
