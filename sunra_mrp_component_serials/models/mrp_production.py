# -*- coding: utf-8 -*-
from odoo import Command, _, fields, models
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    # Related solo para la visibilidad del boton en la vista (D17): un invisible= de vista no
    # atraviesa relaciones, asi que el campo tiene que estar tambien en este modelo.
    sunra_pull_kit_components = fields.Boolean(
        string="Pull Kit Component Serials", related="bom_id.sunra_pull_kit_components", readonly=True,
    )

    def _sunra_get_kit_lot(self):
        # Identifica el lote del kit consumido por la OF: el lote serializado entre los
        # componentes crudos.
        self.ensure_one()
        return self.move_raw_ids.move_line_ids.lot_id.filtered(lambda l: l.product_id.tracking == "serial")

    def _sunra_pull_kit_components(self, strict=False):
        # Traslada (D7) las piezas del lote del kit al lote de la bicicleta, reutilizando el
        # numero de chasis (D9). Idempotente: se puede llamar por boton y de nuevo al cerrar.
        for production in self:
            if not production.bom_id.sunra_pull_kit_components:
                if strict:
                    raise UserError(_(
                        "The Bill of Materials %(bom)s is not marked to pull kit component "
                        "serials.", bom=production.bom_id.display_name or _("(none)"),
                    ))
                continue

            if production.product_id.tracking != "serial":
                raise UserError(_(
                    "%(product)s must be tracked by serial number to pull kit component "
                    "serials.", product=production.product_id.display_name,
                ))

            kit_lots = production._sunra_get_kit_lot()
            if len(kit_lots) != 1:
                # M6: el mensaje orienta los dos casos frecuentes — kit sin reservar (0 lotes)
                # y OF de mas de una bicicleta (N lotes). El modulo asume una bici por OF.
                raise UserError(_(
                    "Cannot identify the kit chassis serial for %(production)s. Serial numbers "
                    "found among the components: %(lots)s. Reserve and set the serial number of "
                    "exactly one kit: this flow builds one bike per manufacturing order.",
                    production=production.display_name,
                    lots=", ".join(kit_lots.mapped("name")) or _("none"),
                ))
            kit_lot = kit_lots

            finished_lot = self.env["stock.lot"].search([
                ("product_id", "=", production.product_id.id),
                ("name", "=", kit_lot.name),
                # stock.lot.company_id se computa desde product_id.company_id y suele quedar
                # en False (producto sin compañia). Filtrar estricto no encontraria un lote
                # preexistente con ese chasis y terminariamos creando un duplicado que revienta
                # contra _check_unique_lot del core.
                ("company_id", "in", [production.company_id.id, False]),
            ], limit=1)
            if not finished_lot:
                # Sin company_id explicito: lo computa el core, igual que un lote creado a mano.
                finished_lot = self.env["stock.lot"].create({
                    "product_id": production.product_id.id,
                    "name": kit_lot.name,
                })

            # Guard de completitud (CA10): union kit + destino -> idempotente, no se traba si
            # el traslado ya se hizo antes (boton apretado y despues se cierra la OF).
            components = kit_lot.component_ids | finished_lot.component_ids
            missing = []
            if not components.filtered(lambda c: c.component_type == "motor"):
                missing.append(_("motor"))
            if not components.filtered(lambda c: c.component_type == "battery"):
                missing.append(_("at least one battery"))
            # Controlador y cargador NO se exigen: las lineas actuales no traen controlador y el
            # cargador no siempre viene informado. Ver D21.
            if missing:
                raise UserError(_(
                    "Chassis %(chassis)s is missing: %(missing)s.",
                    chassis=kit_lot.name, missing=", ".join(missing),
                ))

            if production.lot_producing_ids != finished_lot:
                production.lot_producing_ids = [Command.set(finished_lot.ids)]
                production.message_post(body=_(
                    "Finished product serial set to %(name)s (reused from the kit chassis).",
                    name=finished_lot.name,
                ))

            # Trasladar: una sola escritura, el chatter de cada pieza registra origen y destino.
            kit_lot.component_ids.write({"lot_id": finished_lot.id})

    def action_sunra_pull_kit_components(self):
        self.ensure_one()
        self._sunra_pull_kit_components(strict=True)

    def button_mark_done(self):
        # El traslado va ANTES del super(): con una bici por OF (product_uom_qty == 1),
        # _auto_production_checks() devuelve True y el core genera el numero de serie EN
        # SILENCIO dentro de este mismo metodo (_set_quantities -> action_generate_serial).
        # Seteando lot_producing_ids antes, esa rama queda neutralizada y no aparece un numero
        # nuevo (D9). Sin el opt-in de la LdM (D17) este metodo no hace nada distinto del core.
        self._sunra_pull_kit_components(strict=False)
        return super().button_mark_done()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
