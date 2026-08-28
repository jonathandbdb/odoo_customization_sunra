# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Domain de seleccion (D5): solo piezas libres y no falladas del tipo correcto, mas la que ya
# esta montada en este mismo chasis (para que el M2o no quede sin opcion al reabrir la ficha).
MOTOR_DOMAIN = "[('component_type', '=', 'motor'), ('faulty', '=', False), '|', ('lot_id', '=', False), ('lot_id', '=', id)]"
CONTROLLER_DOMAIN = "[('component_type', '=', 'controller'), ('faulty', '=', False), '|', ('lot_id', '=', False), ('lot_id', '=', id)]"
CHARGER_DOMAIN = "[('component_type', '=', 'charger'), ('faulty', '=', False), '|', ('lot_id', '=', False), ('lot_id', '=', id)]"


class StockLot(models.Model):
    _inherit = "stock.lot"

    component_ids = fields.One2many(
        "sunra.bike.component", "lot_id", string="Bike Components",
        help="All bike components (motor, batteries, controller, charger) currently mounted on this "
             "chassis. Technical field: it is the dependency of the computed component fields "
             "below and is not shown in the view.",
    )
    battery_ids = fields.One2many(
        "sunra.bike.component", "lot_id", string="Batteries", tracking=True,
        domain=[("component_type", "=", "battery")],
        context={"default_component_type": "battery"},
        help="Batteries (fajas) mounted on this chassis. A chassis admits any number of batteries.",
    )
    motor_id = fields.Many2one(
        "sunra.bike.component", string="Motor", store=False, tracking=True,
        compute="_compute_motor_id", inverse="_inverse_motor_id",
        domain=MOTOR_DOMAIN, context={"default_component_type": "motor"},
        help="Motor mounted on this chassis.",
    )
    controller_id = fields.Many2one(
        "sunra.bike.component", string="Controller", store=False, tracking=True,
        compute="_compute_controller_id", inverse="_inverse_controller_id",
        domain=CONTROLLER_DOMAIN, context={"default_component_type": "controller"},
        help="Controller mounted on this chassis.",
    )
    charger_id = fields.Many2one(
        "sunra.bike.component", string="Charger", store=False, tracking=True,
        compute="_compute_charger_id", inverse="_inverse_charger_id",
        domain=CHARGER_DOMAIN, context={"default_component_type": "charger"},
        help="Charger (faja) shipped with this chassis.",
    )

    @api.depends("component_ids.component_type")
    def _compute_motor_id(self):
        # Sin filtro de faulty: por D18 una pieza fallada ya no tiene lot_id, asi que nunca
        # esta en component_ids.
        for lot in self:
            lot.motor_id = lot.component_ids.filtered(lambda c: c.component_type == "motor")[:1]

    @api.depends("component_ids.component_type")
    def _compute_controller_id(self):
        for lot in self:
            lot.controller_id = lot.component_ids.filtered(lambda c: c.component_type == "controller")[:1]

    @api.depends("component_ids.component_type")
    def _compute_charger_id(self):
        for lot in self:
            lot.charger_id = lot.component_ids.filtered(lambda c: c.component_type == "charger")[:1]

    def _inverse_motor_id(self):
        for lot in self:
            lot._sunra_inverse_component(lot.motor_id, "motor")

    def _inverse_controller_id(self):
        for lot in self:
            lot._sunra_inverse_component(lot.controller_id, "controller")

    def _inverse_charger_id(self):
        for lot in self:
            lot._sunra_inverse_component(lot.charger_id, "charger")

    def _sunra_inverse_component(self, component, component_type):
        # Comun a motor_id/controller_id/charger_id: valida el tipo, libera la pieza anterior de ese tipo
        # montada en el chasis (si es distinta) y monta la elegida.
        self.ensure_one()
        if component and component.component_type != component_type:
            raise ValidationError(_(
                "%(component)s is not a %(type)s.",
                component=component.display_name, type=component_type,
            ))
        previous = self.component_ids.filtered(
            lambda c: c.component_type == component_type and c != component
        )
        if previous:
            previous.lot_id = False
        if component:
            component.lot_id = self

    def _sunra_component_report_values(self):
        # Unica fuente de los textos que imprimen remito y factura. sudo() para que un usuario
        # sin permisos de Inventario pueda imprimir (mismo criterio que el core).
        lot = self.sudo()
        return {
            "motor_name": lot.motor_id.name or "",
            "battery_names": ", ".join(lot.battery_ids.mapped("name")),
            "controller_name": lot.controller_id.name or "",
            "charger_name": lot.charger_id.name or "",
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
