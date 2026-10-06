# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _cart_add(self, product_id, quantity=1.0, *, uom_id=None, **kwargs):
        # Solo este metodo define la bicicleta asociada: lo que mande el cliente se descarta
        kwargs.pop("assembled_product_id", None)
        option = kwargs.pop("bike_assembly_option", None)
        if option == "boxed" and not kwargs.get("linked_line_id"):
            product = self.env["product.product"].browse(product_id)
            kit = product._get_assembly_kit_product()
            if not kit:
                raise UserError(_("This vehicle cannot be ordered in a box."))
            # Los atributos elegidos son de la bicicleta, no del kit
            kwargs.pop("no_variant_attribute_value_ids", None)
            kwargs.pop("product_custom_attribute_values", None)
            return super()._cart_add(
                kit.id, quantity, uom_id=None, assembled_product_id=product.id, **kwargs
            )
        return super()._cart_add(product_id, quantity, uom_id=uom_id, **kwargs)

    def _verify_updated_quantity(self, order_line, product_id, new_qty, uom_id, **kwargs):
        # Una linea nueva del kit todavia no existe en el pedido: la bici llega por kwargs
        if kwargs.get("assembled_product_id"):
            self = self.with_context(wsbao_assembled_product_id=kwargs["assembled_product_id"])
        return super()._verify_updated_quantity(order_line, product_id, new_qty, uom_id, **kwargs)

    def _get_free_qty(self, product):
        """
        Un kit sin compañias de stock web propias se mide con las de su bicicleta (D8), igual que
        la ficha, y no con el almacen del sitio.
        """
        website = self.website_id
        if website and not website._has_website_stock_companies(product):
            bikes = self.order_line.filtered(
                lambda line: line.product_id == product
            ).assembled_product_id | product.browse(
                self.env.context.get("wsbao_assembled_product_id")
            )
            by_template = bikes.sudo().product_tmpl_id._get_website_stock_companies_by_template()
            companies = self.env["res.company"].browse(
                {company.id for companies in by_template.values() for company in companies}
            )
            if companies:
                product = product.sudo()
                free_qty = website._compute_products_free_qty(
                    product, {product.product_tmpl_id.id: companies}
                )
                return free_qty[product.id]
        return super()._get_free_qty(product)

    def _cart_find_product_line(self, product_id, uom_id, **kwargs):
        lines = super()._cart_find_product_line(product_id, uom_id, **kwargs)
        assembled_id = kwargs.get("assembled_product_id") or False
        return lines.filtered(lambda line: (line.assembled_product_id.id or False) == assembled_id)

    def _prepare_order_line_values(self, product_id, quantity, uom_id, **kwargs):
        values = super()._prepare_order_line_values(product_id, quantity, uom_id, **kwargs)
        if kwargs.get("assembled_product_id"):
            values["assembled_product_id"] = kwargs["assembled_product_id"]
        return values

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
