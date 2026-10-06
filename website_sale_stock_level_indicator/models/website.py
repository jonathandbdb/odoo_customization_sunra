# -*- coding: utf-8 -*-
from odoo import fields, models

from odoo.addons.sale_website_company_routing.tools import get_request_memo


class Website(models.Model):
    _inherit = "website"

    show_stock_level = fields.Boolean(
        string="Stock Level Indicator",
        help="Show a label with the stock level of each product (out of stock, low stock, normal "
             "stock...) in the shop list and on the product page. The levels are configured "
             "below, one per website.",
    )
    stock_level_ids = fields.One2many(
        comodel_name="website.stock.level",
        inverse_name="website_id",
        string="Stock Levels",
    )

    #=== BUSINESS METHODS ===#

    def _get_stock_level_for_qty(self, qty):
        """Nivel que le corresponde a una disponibilidad.

        Gana el nivel de mayor `min_qty` que la disponibilidad alcanza (los niveles vienen
        ordenados de mayor a menor por `_order`). Un solo numero por nivel, en lugar de un par
        minimo/maximo, hace imposible por construccion que queden huecos o solapamientos.

        Va con `sudo()` porque esto se renderiza para el visitante anonimo, que no tiene acceso de
        lectura a los niveles: son configuracion del sitio, no datos del visitante.
        """
        self.ensure_one()
        for level in self.sudo().stock_level_ids:
            if qty >= level.min_qty:
                return level
        return self.env["website.stock.level"]

    def _get_page_free_qtys(self, variants):
        """Stock libre web de las variantes de la pagina, pedido una sola vez por request.

        Cada tarjeta del listado llega aca con el mismo conjunto de variantes: la primera resuelve
        todas con el helper por lotes y las demas leen de la memoria del request.

        :param variants: variantes que se estan renderizando
        :type variants: recordset de `product.product`
        :return: {product.id: cantidad libre}
        :rtype: dict
        """
        self.ensure_one()
        memo = get_request_memo("wsli_free_qty")
        key = (self.id, tuple(sorted(variants.ids)))
        if key not in memo:
            memo[key] = self._compute_page_free_qtys(variants)
        return memo[key]

    def _compute_page_free_qtys(self, variants):
        """Stock libre web de las variantes: el helper por lotes para las que declaran compañias
        de stock web y el almacen del sitio para el resto.

        Las variantes sin compañias de stock se leen en lote con el almacen del sitio. Con Click &
        Collect en el sitio el stock depende de la entrega elegida (`_get_product_available_qty`
        de `website_sale_collect`): ahi se acepta el costo de consultarlas una por una.

        :param variants: variantes que se estan renderizando
        :type variants: recordset de `product.product`
        :return: {product.id: cantidad libre}
        :rtype: dict
        """
        companies_by_template = variants.sudo().product_tmpl_id._get_website_stock_companies_by_template()
        configured = variants.filtered(lambda v: companies_by_template[v.product_tmpl_id.id])
        result = self._get_products_free_qty(configured) if configured else {}
        rest = (variants - configured).sudo()
        if rest and self.warehouse_id and self.sudo().in_store_dm_id:
            for variant in rest:
                result[variant.id] = self._get_product_available_qty(variant)
        elif rest:
            for variant in rest.with_context(warehouse_id=self.warehouse_id.id):
                result[variant.id] = variant.free_qty
        return result

    def _get_variant_stock_level(self, variant, page_variants=None):
        """Nivel de semaforo de una variante, o un recordset vacio si no aplica.

        `page_variants` son TODAS las variantes que se estan renderizando (en la tienda llega el
        diccionario `product_variants` que ya arma el controller). Se usa para resolver `free_qty`
        de la pagina entera en una sola llamada al helper por lotes: resolverlo por tarjeta haria
        una consulta por producto en una grilla de repuestos.
        """
        self.ensure_one()
        if not self.show_stock_level or not variant:
            return self.env["website.stock.level"]
        # Un servicio o un consumible no lleva cartel de stock: no tiene disponibilidad que medir.
        # Es el mismo criterio del core, que condiciona su bloque de disponibilidad a `is_storable`.
        if not variant.is_storable:
            return self.env["website.stock.level"]

        if isinstance(page_variants, dict):
            # El controller de la tienda pasa {product.template: product.product}.
            page_variants = self.env["product.product"].browse(
                [record.id for record in page_variants.values() if record]
            )

        # Mismo criterio de stock que el resto del eCommerce (sale_website_company_routing)
        free_qtys = self._get_page_free_qtys(page_variants or variant)
        if variant.id not in free_qtys:
            free_qtys = self._get_page_free_qtys(variant)
        # El stock negativo (sobreventa) es, para el que compra, simplemente sin stock: si no lo
        # pisamos en cero no alcanza el nivel mas bajo y la tarjeta no muestra ningun cartel.
        qty = max(free_qtys[variant.id], 0.0)
        return self._get_stock_level_for_qty(qty)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
