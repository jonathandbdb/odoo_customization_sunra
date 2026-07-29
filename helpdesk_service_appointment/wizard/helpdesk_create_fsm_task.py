# -*- coding: utf-8 -*-
from markupsafe import Markup, escape

from odoo import _, models


class HelpdeskCreateFsmTask(models.TransientModel):
    _inherit = "helpdesk.create.fsm.task"

    def _generate_task_values(self):
        self.ensure_one()
        values = super()._generate_task_values()
        # sudo (fix post-review, M1): product_id (helpdesk_stock) lleva
        # groups="stock.group_stock_user". El camino MANUAL del wizard lo puede abrir un agente
        # de helpdesk sin ese grupo (boton nativo "Create a Field Service task", CA22) y
        # reventaria con AccessError al leer product_id mas abajo. Es lectura puramente
        # informativa para armar el bloque de garantia (mismo criterio que D24).
        ticket = self.helpdesk_ticket_id.sudo()

        # El override de partner_id solo aplica al flujo automatico (hsa_from_appointment,
        # D33): el wizard abierto a mano por un agente desde el ticket conserva el cliente
        # que eligio (CA22). Pisarlo siempre secuestraria el camino manual del backoffice.
        if self.env.context.get("hsa_from_appointment") and ticket.service_visit_address_id:
            values["partner_id"] = ticket.service_visit_address_id.id

        # El bloque de garantia se agrega SIEMPRE (es informacion para el tecnico, no una
        # decision del agente, D33/RB23).
        if ticket.product_id or ticket.warranty_status != "unknown":
            base_description = Markup(values.get("description") or "")
            values["description"] = self._service_warranty_description(ticket) + base_description

        return values

    def _service_warranty_description(self, ticket):
        """Bloque HTML (producto + garantia) para anteponer a la descripcion de la tarea FSM.

        ``description`` es un campo Html: se arma con Markup y se escapan los valores
        interpolados, porque el nombre del producto puede traer ``&``, ``<`` o comillas.
        """
        warranty_labels = dict(ticket.fields_get(["warranty_status"])["warranty_status"]["selection"])

        rows = []
        if ticket.product_id:
            rows.append((_("Lock"), escape(ticket.product_id.display_name)))
        rows.append((
            _("Warranty status"),
            escape(warranty_labels.get(ticket.warranty_status, ticket.warranty_status)),
        ))
        if ticket.warranty_expiry_date:
            rows.append((_("Warranty expiry"), escape(str(ticket.warranty_expiry_date))))
        if ticket.warranty_delivery_date:
            rows.append((_("Delivery date used"), escape(str(ticket.warranty_delivery_date))))

        items = Markup("").join(Markup("<li>%s: %s</li>") % (label, value) for label, value in rows)
        return Markup("<p><strong>%s</strong></p><ul>%s</ul>") % (_("Service information"), items)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
