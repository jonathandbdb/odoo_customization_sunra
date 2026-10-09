# -*- coding: utf-8 -*-
from odoo import Command, api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    sale_company_id = fields.Many2one(
        comodel_name="res.company",
        string="Selling Company",
        compute="_compute_sale_company_id",
        store=True,
        readonly=False,
        precompute=True,
        recursive=True,
        help="Company that sells and ships this line. When the order is confirmed, the lines of "
             "another company move to a new order of that company.",
    )

    @api.depends(
        "product_id",
        "order_id.company_id",
        "order_id.company_id.company_routing_excluded",
        "linked_line_id.sale_company_id",
        "display_type",
    )
    def _compute_sale_company_id(self):
        for line in self:
            # En pedidos confirmados o cancelados la linea conserva su valor
            if line.order_id and line.order_id.state not in ("draft", "sent"):
                continue
            if line.display_type:
                line.sale_company_id = False
            elif line.order_id.company_id.company_routing_excluded:
                line.sale_company_id = line.order_id.company_id
            elif line.linked_line_id:
                line.sale_company_id = line.linked_line_id.sale_company_id
            else:
                line.sale_company_id = (
                    line._get_routing_product_company() or line.order_id.company_id
                )

    def _get_routing_product_company(self):
        """
        Compañia que aporta el producto de la linea (hook de extension).

        :return: compañia que vende el producto, o vacio si no esta configurada
        :rtype: recordset de `res.company`
        """
        self.ensure_one()
        # La linea recien agregada en el formulario todavia no tiene producto
        if not self.product_id:
            return self.env["res.company"]
        return self.product_id.product_tmpl_id.sudo()._get_sale_company()

    def _prepare_company_routing_values(self, target_order, convert):
        """
        Valores para recrear la linea en el pedido derivado.

        Los impuestos no se copian: los recalcula el core en la compañia destino.

        :param target_order: pedido derivado
        :type target_order: recordset de `sale.order`
        :param convert: funcion que convierte un importe a la moneda del derivado
        :type convert: callable
        :return: valores para `create()`
        :rtype: dict
        """
        self.ensure_one()
        company = target_order.company_id
        routes = self.route_ids.filtered(lambda route: not route.company_id or route.company_id == company)
        return {
            "order_id": target_order.id,
            "product_id": self.product_id.id,
            "name": self.name,
            "product_uom_qty": self.product_uom_qty,
            "product_uom_id": self.product_uom_id.id,
            "price_unit": convert(self.price_unit),
            "discount": self.discount,
            "sequence": self.sequence,
            "customer_lead": self.customer_lead,
            "is_delivery": self.is_delivery,
            "product_no_variant_attribute_value_ids": [
                Command.set(self.product_no_variant_attribute_value_ids.ids)
            ],
            "product_custom_attribute_value_ids": [
                Command.create({
                    "custom_product_template_attribute_value_id":
                        custom_value.custom_product_template_attribute_value_id.id,
                    "custom_value": custom_value.custom_value,
                })
                for custom_value in self.product_custom_attribute_value_ids
            ],
            "route_ids": [Command.set(routes.ids)],
            "sale_company_id": company.id,
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
