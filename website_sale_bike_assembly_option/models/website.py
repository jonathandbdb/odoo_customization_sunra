# -*- coding: utf-8 -*-
from odoo import models

from odoo.addons.sale_website_company_routing.tools import get_request_memo


class Website(models.Model):
    _inherit = "website"

    def _get_products_free_qty(self, products):
        """
        Suma al stock libre de cada bicicleta con compañias de stock web el de su kit en caja:
        toda caja puede armarse sobre pedido.
        """
        result = super()._get_products_free_qty(products)
        products = products.sudo()
        companies_by_template = products.product_tmpl_id._get_website_stock_companies_by_template()
        bikes = products.filtered(lambda p: companies_by_template[p.product_tmpl_id.id])
        if not bikes:
            return result
        memo = get_request_memo("assembly_kit_qty").setdefault(self.id, {})
        missing = bikes.filtered(lambda bike: bike.id not in memo)
        if missing:
            memo.update(self._get_assembly_kit_free_qty(missing, companies_by_template))
        for bike in bikes:
            result[bike.id] += memo[bike.id]
        return result

    def _get_assembly_kit_free_qty(self, bikes, companies_by_template):
        """
        Stock libre web del kit en caja de cada bicicleta.

        Un kit sin compañias de stock web propias (producto o categoria) usa las de su bicicleta.

        :param bikes: bicicletas con compañias de stock web (en `sudo()`)
        :type bikes: recordset de `product.product`
        :param companies_by_template: {plantilla.id: compañias de stock web} de las bicicletas
        :type companies_by_template: dict
        :return: {bicicleta.id: stock libre del kit (0.0 si no tiene)}
        :rtype: dict
        """
        result = dict.fromkeys(bikes.ids, 0.0)
        kits_by_bike = bikes._get_assembly_kit_products()
        if not kits_by_bike:
            return result
        kits = bikes.browse([kit.id for kit in kits_by_bike.values()])
        kit_companies = kits.product_tmpl_id._get_website_stock_companies_by_template()
        companies_for_kits = dict(kit_companies)
        for bike_id, kit in kits_by_bike.items():
            if not kit_companies[kit.product_tmpl_id.id]:
                bike_template = bikes.browse(bike_id).product_tmpl_id
                companies_for_kits[kit.product_tmpl_id.id] = companies_by_template[bike_template.id]
        kit_qty = self._compute_products_free_qty(kits, companies_for_kits)
        for bike_id, kit in kits_by_bike.items():
            result[bike_id] = kit_qty.get(kit.id, 0.0)
        return result

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
