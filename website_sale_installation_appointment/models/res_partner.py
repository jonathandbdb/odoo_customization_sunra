# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Campo unico de "entre calles" (D46): la maqueta aprobada mostraba dos inputs, pero se
    # unifica en uno solo (es un dato que el instalador lee de corrido, y dos campos obligarian
    # a inventar la segunda esquina cuando la cuadra tiene una sola referencia). Va en el
    # partner (describe el domicilio) y no en el pedido (installation_notes, que es de ESTA
    # venta).
    between_streets = fields.Char(
        string="Between streets",
        help="Cross streets of the address, useful for the installer in areas without street "
             "numbering (e.g. \"Peru and Chile\"). Optional.",
    )

    def write(self, vals):
        # Editar el domicilio DESPUES de haber confirmado el Paso 1 del checkout de instalacion
        # tira abajo esa confirmacion (D48): mismo molde del write() de website_sale para el
        # reset por edicion del partner de envio (odoo/addons/website_sale/models/res_partner.py:L58).
        res = super().write(vals)
        address_fields = {
            "name", "street", "street2", "city", "zip", "state_id", "country_id",
            "between_streets",
        }
        if not address_fields & vals.keys():
            return res
        self.env["sale.order"].sudo().search([
            ("state", "in", ("draft", "sent")),
            ("website_id", "!=", False),
            ("partner_shipping_id", "in", self.ids),
            ("installation_address_confirmed", "=", True),
        ]).write({"installation_address_confirmed": False})
        return res

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
