# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# RB12: tipos que admiten UNA sola pieza por chasis (las baterias son N, D11).
SINGLE_COMPONENT_TYPES = ("motor", "controller", "charger")


class SunraBikeComponent(models.Model):
    _name = "sunra.bike.component"
    _description = "Bike Component"
    _inherit = ["mail.thread"]
    _order = "component_type, name"
    _rec_names_search = ["name"]

    name = fields.Char(
        string="Serial Number", required=True, index=True, tracking=True,
        help="Serial number printed on the component (motor, battery/faja, controller or charger).",
    )
    component_type = fields.Selection(
        [
            ("motor", "Motor"),
            ("battery", "Battery"),
            ("controller", "Controller"),
            ("charger", "Charger"),
        ],
        string="Type", required=True, tracking=True,
        help="Kind of component this serial number identifies.",
    )
    lot_id = fields.Many2one(
        "stock.lot", string="Assigned Chassis", index=True, tracking=True, ondelete="set null",
        help="Chassis serial (stock.lot) this component is currently mounted on. Empty means "
             "the component is free. This is the single source of truth for the assignment.",
    )
    faulty = fields.Boolean(
        string="Faulty", default=False, tracking=True,
        help="Marking a component as faulty releases it from its chassis: it is no longer "
             "offered in selection fields, printed, or counted towards the completeness guard.",
    )
    display_name = fields.Char(string="Display Name", compute="_compute_display_name")

    _component_type_name_uniq = models.Constraint(
        "UNIQUE(component_type, name)",
        "This serial number already exists for that component type.",
    )

    @api.depends("name", "component_type")
    def _compute_display_name(self):
        # Etiqueta legible en desplegables y busquedas: "<Tipo> / <numero>".
        type_labels = dict(self._fields["component_type"].selection)
        for component in self:
            component.display_name = "%s / %s" % (
                type_labels.get(component.component_type, ""), component.name or "",
            )

    @api.constrains("lot_id", "component_type")
    def _check_single_components(self):
        # RB12: un chasis admite como maximo un motor, un controlador y un cargador (las baterias
        # son N, D11). El domain de la vista no alcanza porque la reasignacion desde la pieza (D10)
        # no pasa por el.
        for component in self.filtered(lambda c: c.lot_id and c.component_type in SINGLE_COMPONENT_TYPES):
            same_type_count = self.env["sunra.bike.component"].search_count([
                ("lot_id", "=", component.lot_id.id),
                ("component_type", "=", component.component_type),
            ])
            if same_type_count > 1:
                type_labels = dict(self._fields["component_type"].selection)
                raise ValidationError(_(
                    "Chassis %(chassis)s already has a %(type)s assigned.",
                    chassis=component.lot_id.display_name,
                    type=type_labels.get(component.component_type, component.component_type),
                ))

    @api.constrains("faulty", "lot_id")
    def _check_faulty_not_assigned(self):
        # D18: una pieza fallada nunca esta montada. El override de write y el onchange son
        # comodidad de UX; este constraint es la garantia, y cubre tambien create() e importacion
        # (ej. alta de una bateria con "faulty" tildado desde la lista embebida del chasis).
        for component in self:
            if component.faulty and component.lot_id:
                raise ValidationError(_(
                    "Component %(component)s is marked as faulty and cannot stay assigned to "
                    "chassis %(chassis)s.",
                    component=component.display_name,
                    chassis=component.lot_id.display_name,
                ))

    @api.onchange("faulty")
    def _onchange_faulty(self):
        # Al tildar "Faulty" en el formulario, vaciar lot_id en pantalla para que el usuario vea
        # el efecto (D18) antes de guardar.
        if self.faulty:
            self.lot_id = False

    def write(self, vals):
        # D18: marcar una pieza como fallada libera el chasis en el mismo acto, tambien cuando
        # el cambio viene por codigo/importacion y no solo desde la UI (el onchange no alcanza).
        if vals.get("faulty") and "lot_id" not in vals:
            vals = dict(vals, lot_id=False)
        return super().write(vals)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
