# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import models

from ..tools import get_request_memo


class Website(models.Model):
    _inherit = "website"

    def _get_products_free_qty(self, products):
        """
        Stock libre web de varios productos, en una sola pasada.

        Con compañias de stock web (producto o categoria): suma el stock libre de todos sus
        almacenes, o 0 si no tienen. Sin ellas: el almacen del sitio, igual que el core. Corre en
        `sudo()` porque el visitante no lee los quants de otra compañia; solo se leen cantidades.
        Memoriza por request y producto.

        :param products: productos a consultar
        :type products: recordset de `product.product`
        :return: {product.id: cantidad libre}
        :rtype: dict
        """
        self.ensure_one()
        products = products.sudo()
        memo = get_request_memo("free_qty").setdefault(self.id, {})
        missing = products.filtered(lambda product: product.id not in memo)
        if missing:
            companies_by_template = missing.product_tmpl_id._get_website_stock_companies_by_template()
            memo.update(self._compute_products_free_qty(missing, companies_by_template))
        return {product.id: memo[product.id] for product in products}

    def _compute_products_free_qty(self, products, companies_by_template):
        """
        Calcular el stock libre web con las compañias de stock indicadas por plantilla.

        :param products: productos (en `sudo()`)
        :type products: recordset de `product.product`
        :param companies_by_template: {plantilla.id: compañias de stock web}; vacio = almacen del sitio
        :type companies_by_template: dict
        :return: {product.id: cantidad libre}
        :rtype: dict
        """
        result = dict.fromkeys(products.ids, 0.0)
        company_ids = {
            company.id
            for template in products.product_tmpl_id
            for company in companies_by_template.get(template.id, ())
        }
        warehouses_by_company = defaultdict(list)
        if company_ids:
            for warehouse in self.env["stock.warehouse"].sudo().search(
                [("company_id", "in", list(company_ids))]
            ):
                warehouses_by_company[warehouse.company_id.id].append(warehouse.id)

        # Productos agrupados por el conjunto de almacenes que se consulta (False = criterio del core)
        groups = defaultdict(lambda: products.browse())
        for product in products:
            companies = companies_by_template.get(product.product_tmpl_id.id)
            if not companies:
                groups[self.warehouse_id.id or False] |= product
                continue
            warehouse_ids = tuple(sorted(
                wh_id for company in companies for wh_id in warehouses_by_company.get(company.id, ())
            ))
            # Nunca se pasa una lista vacia: el core la lee como "todos los almacenes"
            if warehouse_ids:
                groups[warehouse_ids] |= product

        for key, group in groups.items():
            warehouse = list(key) if isinstance(key, tuple) else key
            for product in group.with_context(warehouse_id=warehouse):
                result[product.id] = product.free_qty
        return result

    def _has_website_stock_companies(self, product):
        """Indica si el producto declara compañias de stock web."""
        return bool(product.sudo().product_tmpl_id._get_website_stock_companies())

    def _get_product_available_qty(self, product, **kwargs):
        if self._has_website_stock_companies(product):
            return self._get_products_free_qty(product)[product.id]
        return super()._get_product_available_qty(product, **kwargs)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
