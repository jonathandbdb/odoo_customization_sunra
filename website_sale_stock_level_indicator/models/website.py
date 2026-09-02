# -*- coding: utf-8 -*-
from odoo import fields, models


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

    def _get_variant_stock_level(self, variant, page_variants=None):
        """Nivel de semaforo de una variante, o un recordset vacio si no aplica.

        `page_variants` son TODAS las variantes que se estan renderizando (en la tienda llega el
        diccionario `product_variants` que ya arma el controller). Se usa para resolver `free_qty`
        de la pagina entera en una sola consulta: llamar al helper del core por tarjeta rompe el
        prefetch, porque cada `with_context()` sobre un registro suelto abre su propio bucket de
        cache, y una grilla de repuestos termina haciendo una consulta por producto.
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

        # Mismo deposito que usa el resto del eCommerce (website_sale_stock).
        scoped = (page_variants or variant).with_context(warehouse_id=self.warehouse_id.id)
        scoped.mapped("free_qty")  # una sola consulta; las tarjetas siguientes salen de cache
        # El stock negativo (sobreventa) es, para el que compra, simplemente sin stock: si no lo
        # pisamos en cero no alcanza el nivel mas bajo y la tarjeta no muestra ningun cartel.
        qty = max(scoped.browse(variant.id).free_qty, 0.0)
        return self._get_stock_level_for_qty(qty)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
