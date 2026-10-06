# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    assembled_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Assembled Vehicle",
        readonly=True,
        ondelete="set null",
        index="btree_not_null",
        help="Assembled vehicle whose price this box kit line takes.",
    )

    @api.depends("assembled_product_id")
    def _compute_pricelist_item_id(self):
        super()._compute_pricelist_item_id()
        for line in self.filtered("assembled_product_id"):
            if line.display_type or not line.order_id.pricelist_id:
                continue
            line.pricelist_item_id = line.order_id.pricelist_id._get_product_rule(
                product=line.assembled_product_id,
                **line._get_pricelist_kwargs(),
            )

    @api.depends("assembled_product_id")
    def _compute_sale_company_id(self):
        super()._compute_sale_company_id()

    def _get_assembled_price_product(self):
        """Vehiculo armado con el contexto de precio del core (sin atributos extra)."""
        self.ensure_one()
        bike = self.assembled_product_id
        return bike.with_context(
            **bike._get_product_price_context(self.env["product.template.attribute.value"])
        )

    def _get_pricelist_price(self):
        if not self.assembled_product_id:
            return super()._get_pricelist_price()
        self.ensure_one()
        return self.pricelist_item_id._compute_price(
            product=self._get_assembled_price_product(),
            **self._get_pricelist_kwargs(),
        )

    def _get_pricelist_price_before_discount(self):
        if not self.assembled_product_id:
            return super()._get_pricelist_price_before_discount()
        self.ensure_one()
        return self.pricelist_item_id._compute_price_before_discount(
            product=self._get_assembled_price_product(),
            **self._get_pricelist_kwargs(),
        )

    def _is_sellable(self):
        if self.assembled_product_id:
            return self.assembled_product_id.is_published and not self.is_delivery
        return super()._is_sellable()

    def _get_routing_product_company(self):
        company = super()._get_routing_product_company()
        if not company and self.assembled_product_id:
            company = self.assembled_product_id.product_tmpl_id.sudo()._get_sale_company()
        return company

    def _prepare_company_routing_values(self, target_order, convert):
        values = super()._prepare_company_routing_values(target_order, convert)
        values["assembled_product_id"] = self.assembled_product_id.id
        return values

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
