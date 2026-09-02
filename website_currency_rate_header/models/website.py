# -*- coding: utf-8 -*-
from odoo import fields, models


class Website(models.Model):
    _inherit = "website"

    show_currency_rate = fields.Boolean(
        string="Exchange Rate in Header",
        help="Show the current exchange rate of a currency in the website header. Useful when "
             "prices are listed in a foreign currency but invoiced in the company currency.",
    )
    currency_rate_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Rate Currency",
        help="Currency the rate is expressed in. The header shows how much one unit of the "
             "company currency is worth in this currency: with the company in USD and this set "
             "to ARS, it shows the pesos per dollar.",
    )

    currency_rate_label = fields.Char(
        string="Rate Label",
        translate=True,
        default="Official Exchange Rate:",
        help="Text shown before the rate in the header, e.g. \"Official Exchange Rate:\".",
    )

    #=== BUSINESS METHODS ===#

    def _get_currency_rate_display(self):
        """Cotizacion a mostrar en el encabezado, expresada en la moneda elegida. 0 si no aplica.

        En la semantica de Odoo, `rate` es cuantas unidades de ESTA moneda vale una unidad de la
        moneda de la compania — `rate_string` lo dice literal: "1 USD = 1480.000000 ARS". Sunra
        tiene la compania y las listas en dolares, asi que eligiendo ARS sale directo los pesos por
        dolar, que es lo que el concesionario necesita ver.

        Va con `sudo()` porque esto se renderiza para el visitante anonimo, que no tiene acceso de
        lectura a las cotizaciones (`res.currency.rate`).
        """
        self.ensure_one()
        currency = self.currency_rate_currency_id
        company = self.company_id
        if not self.show_currency_rate or not currency or not company:
            return 0.0
        # Cotizar la moneda de la compania contra si misma daria siempre 1: no aporta nada.
        if currency == company.currency_id:
            return 0.0
        return currency.sudo().with_company(company).rate

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
