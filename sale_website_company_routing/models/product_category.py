# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = "product.category"

    sale_company_id = fields.Many2one(
        comodel_name="res.company",
        string="Selling Company",
        ondelete="set null",
        help="Company that sells and ships the products of this category. Empty: the one of the "
             "parent category or, if none defines it, the company of the order.",
    )
    website_stock_company_ids = fields.Many2many(
        comodel_name="res.company",
        relation="product_category_website_stock_company_rel",
        column1="category_id",
        column2="company_id",
        string="Website Stock Companies",
        help="Companies whose stock is shown on the website for the products of this category. "
             "Empty: the ones of the parent category or, if none defines it, the website warehouse.",
    )

    def _get_routing_values_by_category(self):
        """
        Resolver, por categoria, la compañia que vende y las compañias de stock web.

        Recorre la categoria y sus ancestros (del mas cercano al mas lejano) y toma el primer valor
        no vacio de cada campo. Lee los ancestros una sola vez por categoria distinta.

        :return: {categoria.id: (compañia que vende, compañias de stock web)}
        :rtype: dict
        """
        categories = self.sudo()
        chains = {
            categ.id: [int(cid) for cid in reversed((categ.parent_path or "").split("/")[:-1])]
            or [categ.id]
            for categ in categories
        }
        ancestor_ids = {cid for chain in chains.values() for cid in chain}
        ancestors = {anc.id: anc for anc in categories.browse(ancestor_ids)}
        empty_company = self.env["res.company"]
        result = {}
        for categ_id, chain in chains.items():
            sale_company = empty_company
            stock_companies = empty_company
            for ancestor_id in chain:
                ancestor = ancestors[ancestor_id]
                sale_company = sale_company or ancestor.sale_company_id
                stock_companies = stock_companies or ancestor.website_stock_company_ids
                if sale_company and stock_companies:
                    break
            result[categ_id] = (sale_company, stock_companies)
        return result

    def _get_sale_company(self):
        """
        :return: compañia que vende (vacia si nadie la define o si no hay categoria)
        :rtype: recordset de `res.company`
        """
        if not self:
            return self.env["res.company"]
        self.ensure_one()
        return self._get_routing_values_by_category()[self.id][0]

    def _get_website_stock_companies(self):
        """
        :return: compañias de stock web (vacio si nadie las define o si no hay categoria)
        :rtype: recordset de `res.company`
        """
        if not self:
            return self.env["res.company"]
        self.ensure_one()
        return self._get_routing_values_by_category()[self.id][1]

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
