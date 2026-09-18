# -*- coding: utf-8 -*-
from odoo import models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _get_published_installments(self):
        """
        Planes de cuotas publicados que le corresponden al sitio web en curso.

        El modulo base devuelve TODOS los planes publicados, sin mirar sitio ni compania:
        con dos sitios sobre la misma base eso filtra los planes de una compania al sitio
        de la otra. Aca se acota al sitio en dos pasos: primero el interruptor por sitio
        (`show_installment_plans`) y despues la compania del sitio, respetando el criterio
        de la record rule multi-compania del modulo base (compania propia o sin compania).

        Fuera del frontend (llamadas de backend, sin sitio en contexto) se delega al
        super() para no cambiar el comportamiento existente.

        :return: planes de cuotas a publicar
        :rtype: account.card.installment
        """
        website = self.env["website"].get_current_website(fallback=False)
        if not website:
            return super()._get_published_installments()
        if not website.show_installment_plans:
            return self.env["account.card.installment"]
        # Va con sudo() porque esto se renderiza para el visitante anonimo, que no tiene acceso
        # de lectura a los planes: son configuracion del sitio, no datos del visitante.
        return self.env["account.card.installment"].sudo().search([
            ("is_published", "=", True),
            ("card_id.company_id", "in", [website.company_id.id, False]),
        ])

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
