# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.tools import format_amount


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def _get_payment_method_price_vals(self, website, price, rules=None):
        """
        Armar los precios por medio de pago que se muestran debajo del precio del producto.

        El `price` que entra ya paso por `_apply_taxes_to_price`, es decir esta en la misma base
        (con o sin impuestos, segun `website.show_line_subtotals_tax_selection`) que el precio que
        ve el cliente arriba. El ajuste se calcula sobre ese mismo numero para que los dos precios
        sean comparables.

        Se devuelve tambien el precio ya formateado porque el JS de variantes tiene que repintarlo
        sin volver a resolver la moneda ni su precision.

        :param website: sitio web que se esta renderizando
        :type website: recordset de `website`
        :param price: precio mostrado del producto
        :type price: float
        :param rules: reglas ya resueltas, para no re-buscarlas por producto en la grilla
        :type rules: recordset de `payment.method.website.price` o None
        :return: lista de dicts con name, label, price y price_formatted
        :rtype: list
        """
        if rules is None:
            rules = self.env["payment.method.website.price"]._get_website_rules(
                website, only_visible=True
            )
        # Una regla que solo aplica al envio no cambia el precio del producto
        rules = rules.filtered(lambda rule: rule.applies_to in ("product", "all"))
        currency = website.currency_id
        vals = []
        for rule in rules:
            adjusted = rule._apply_to_price(price)
            vals.append({
                "name": rule.payment_method_id.name,
                "label": _("with %(method)s", method=rule.payment_method_id.name),
                "price": adjusted,
                "price_formatted": format_amount(self.env, adjusted, currency),
            })
        return vals

    def _get_sales_prices(self, website):
        """Override de `website_sale` para agregar los precios por medio de pago a la grilla."""
        res = super()._get_sales_prices(website)
        rules = self.env["payment.method.website.price"]._get_website_rules(
            website, only_visible=True
        )
        if not rules:
            return res
        for template in self:
            template_price_vals = res.get(template.id)
            if not template_price_vals:
                continue
            template_price_vals["payment_method_prices"] = self._get_payment_method_price_vals(
                website, template_price_vals["price_reduce"], rules=rules
            )
        return res

    def _get_additionnal_combination_info(self, product_or_template, quantity, uom, date, website):
        """Override de `website_sale` para agregar los precios por medio de pago a la ficha.

        La clave viaja tambien por la ruta jsonrpc `/website_sale/get_combination_info` (no esta
        entre las que ese controller descarta), asi que el JS de variantes puede repintarla.
        """
        res = super()._get_additionnal_combination_info(
            product_or_template, quantity, uom, date, website
        )
        if res.get("prevent_zero_price_sale"):
            res["payment_method_prices"] = []
            return res
        res["payment_method_prices"] = self._get_payment_method_price_vals(website, res["price"])
        return res

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
