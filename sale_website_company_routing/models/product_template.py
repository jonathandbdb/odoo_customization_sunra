# -*- coding: utf-8 -*-
from odoo import fields, models

from ..tools import get_request_memo


class ProductTemplate(models.Model):
    _inherit = "product.template"

    sale_company_id = fields.Many2one(
        comodel_name="res.company",
        string="Selling Company",
        ondelete="set null",
        help="Company that sells and ships this product. Empty: the one of its category.",
    )
    website_stock_company_ids = fields.Many2many(
        comodel_name="res.company",
        relation="product_template_website_stock_company_rel",
        column1="template_id",
        column2="company_id",
        string="Website Stock Companies",
        help="Companies whose stock is shown on the website for this product. Empty: the ones "
             "of its category.",
    )

    def _get_sale_company(self):
        """
        Resolver la compañia que vende: producto, luego categoria (y sus ancestros).

        Desde la web se invoca sobre un recordset en `sudo()`.

        :return: compañia que vende (vacia si nadie la define)
        :rtype: recordset de `res.company`
        """
        self.ensure_one()
        return self.sale_company_id or self.categ_id._get_sale_company()

    def _get_website_stock_companies(self):
        """
        Resolver las compañias de stock web: producto, luego categoria (y sus ancestros).

        :return: compañias de stock web (vacio si nadie las define)
        :rtype: recordset de `res.company`
        """
        self.ensure_one()
        return self._get_website_stock_companies_by_template()[self.id]

    def _get_website_stock_companies_by_template(self):
        """
        Version por lotes de `_get_website_stock_companies()`: resuelve las categorias agrupadas.

        Memoriza por request: la tienda consulta un producto por vez. Las plantillas sin categoria
        resuelven solo con lo propio.

        :return: {plantilla.id: compañias de stock web}
        :rtype: dict
        """
        templates = self.sudo()
        memo = get_request_memo("stock_companies")
        missing = templates.filtered(lambda template: template.id not in memo)
        if missing:
            no_companies = templates.env["res.company"]
            by_category = missing.categ_id._get_routing_values_by_category()
            for template in missing:
                companies = template.website_stock_company_ids or by_category.get(
                    template.categ_id.id, (no_companies, no_companies)
                )[1]
                memo[template.id] = companies.ids
        return {
            template.id: templates.env["res.company"].browse(memo[template.id])
            for template in templates
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
