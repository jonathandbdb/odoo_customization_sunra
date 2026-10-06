# -*- coding: utf-8 -*-
from odoo import models
from odoo.fields import Domain

from odoo.addons.sale_website_company_routing.tools import get_request_memo


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _get_assembly_kit_products(self):
        """
        Kit en caja de cada bicicleta, deducido de su LdM de kit.

        La LdM se busca en `sudo()` y sin filtrar por compañia: la fabrica otra compañia distinta
        de la del sitio y el visitante no accede a fabricacion.

        :return: {product.id: kit}; sin entrada = la bicicleta no ofrece la opcion
        :rtype: dict
        """
        result = {}
        if not self:
            return result
        memo = get_request_memo("assembly_kits")
        missing = self.filtered(lambda product: product.id not in memo)
        if missing:
            memo.update(missing._find_assembly_kits())
        for product in self:
            if memo[product.id]:
                result[product.id] = self.browse(memo[product.id]).sudo()
        return result

    def _find_assembly_kits(self):
        """
        Buscar en la LdM el kit de cada bicicleta, sin memoria.

        :return: {product.id: id del kit o False}
        :rtype: dict
        """
        result = {}
        Bom = self.env["mrp.bom"].sudo().with_context(company_id=False)
        boms = Bom.search(
            Domain.AND([
                Bom._bom_find_domain(self, bom_type="normal"),
                [("sunra_pull_kit_components", "=", True)],
            ]),
            order="sequence, product_id, id",
        )
        for product in self:
            # La LdM de variante gana a la de plantilla
            bom = (
                boms.filtered(lambda b: b.product_id == product)[:1]
                or boms.filtered(
                    lambda b: not b.product_id and b.product_tmpl_id == product.product_tmpl_id
                )[:1]
            )
            components = bom.bom_line_ids.filtered(
                lambda line: not line._skip_bom_line(product)
                and line.product_id.tracking == "serial"
            ).product_id
            result[product.id] = components.id if len(components) == 1 else False
        return result

    def _get_assembly_kit_product(self):
        """Kit en caja de una bicicleta, o vacio si no tiene."""
        self.ensure_one()
        return self._get_assembly_kit_products().get(self.id, self.browse())

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
