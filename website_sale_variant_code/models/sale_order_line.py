# -*- coding: utf-8 -*-
import logging

from odoo import api, models

from .product_template import MANUAL_CODE_RE

_logger = logging.getLogger(__name__)

# Pedidos donde todavia tiene sentido reescribir la descripcion de la linea: los que el cliente aun
# no confirmo. Un pedido confirmado o facturado es un documento cerrado, no se toca.
OPEN_ORDER_STATES = ("draft", "sent")


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.model
    def _clean_manual_code_names(self, dry_run=True):
        """
        Limpiar la leyenda "Cod: ..." congelada en el nombre de las lineas de pedidos abiertos.

        Al agregar un producto al carrito, Odoo copia `description_sale` dentro del nombre de la
        linea (`product.product.get_product_multiline_description_sale`). Por eso limpiar el
        producto no alcanza: los carritos ya armados siguen mostrando la leyenda vieja.

        Solo toca pedidos **no confirmados** (ver OPEN_ORDER_STATES): un pedido confirmado es un
        documento cerrado. Es idempotente.

        :param dry_run: si es True (default) no escribe, solo informa que haria
        :type dry_run: bool
        :return: dict con 'cleaned' (lineas tocadas, con el nombre previo)
        :rtype: dict
        """
        lines = self.search([
            ("order_id.state", "in", OPEN_ORDER_STATES),
            ("name", "ilike", "cod:"),
        ])

        cleaned = []
        for line in lines:
            kept = [
                text_line for text_line in (line.name or "").splitlines()
                if not MANUAL_CODE_RE.match(text_line.strip())
            ]
            new_name = "\n".join(kept).strip()
            if not new_name:
                # La leyenda era todo el nombre: dejamos al menos como se llama el producto.
                new_name = line.product_id.display_name
            if new_name == (line.name or "").strip():
                continue

            cleaned.append({"id": line.id, "order": line.order_id.name, "previous": line.name})
            # El nombre previo va al log: es la unica copia auditable de lo que se reescribe.
            _logger.info(
                "[variant_code] sale.order.line %s (%s) previo=%r nuevo=%r%s",
                line.id, line.order_id.name, line.name, new_name,
                " (dry run)" if dry_run else "",
            )
            if not dry_run:
                line.name = new_name

        _logger.info(
            "[variant_code] limpieza de lineas: %s lineas reescritas%s",
            len(cleaned), " (dry run)" if dry_run else "",
        )
        return {"cleaned": cleaned}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
