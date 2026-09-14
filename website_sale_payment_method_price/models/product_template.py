# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.tools import format_amount, float_round


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def _get_payment_method_price_vals(self, website, price, rules=None, reference_price=None):
        """
        Armar los precios por medio de pago que se muestran debajo del precio del producto.

        El `price` que entra ya paso por `_apply_taxes_to_price`, es decir esta en la misma base
        (con o sin impuestos, segun `website.show_line_subtotals_tax_selection`) que el precio que
        ve el cliente arriba. El ajuste se calcula sobre ese mismo numero para que los dos precios
        sean comparables.

        Se devuelve tambien el precio ya formateado porque el JS de variantes tiene que repintarlo
        sin volver a resolver la moneda ni su precision.

        `label` es el prefijo traducible (`_("paying with")`) y `name` el nombre del medio: viajan
        separados para que la vista y el JS los compongan como `prefijo` + `<b>nombre</b>` sin
        meter HTML dentro de un string traducible ni `innerHTML` en el repintado (D20). `badge` es
        el texto del pill (`-15% OFF`) y solo viaja si la regla es un descuento; con recargo viaja
        `False` (no hay pill ni tachado, D19/CA23).

        :param website: sitio web que se esta renderizando
        :type website: recordset de `website`
        :param price: precio mostrado del producto
        :type price: float
        :param rules: reglas ya resueltas, para no re-buscarlas por producto en la grilla
        :type rules: recordset de `payment.method.website.price` o None
        :param reference_price: precio tachado que el core ya publica arriba (precio de lista o
            comparativo). Es la base del ahorro: sin el, el ahorro es contra el precio mostrado.
        :type reference_price: float | None
        :return: lista de dicts con name, label, price, price_formatted, price_type, badge y saving_label
        :rtype: list
        """
        if rules is None:
            rules = self.env["payment.method.website.price"]._get_website_rules(
                website, only_visible=True
            )
        # Una regla que solo aplica al envio no cambia el precio del producto
        rules = rules.filtered(lambda rule: rule.applies_to in ("product", "all"))
        currency = website.currency_id
        # El ahorro se cuenta contra el precio tachado de mas arriba cuando existe (precio de lista
        # o comparativo): es lo que el cliente ve como "precio anterior". Sin el, contra el precio
        # mostrado, que es lo unico con lo que se puede comparar.
        reference = price
        if reference_price and currency.compare_amounts(reference_price, price) == 1:
            reference = reference_price
        vals = []
        for rule in rules:
            adjusted = rule._apply_to_price(price)
            saving = reference - adjusted
            vals.append({
                "name": rule.payment_method_id.name,
                "label": _("paying with"),
                "price": adjusted,
                "price_formatted": format_amount(self.env, adjusted, currency),
                "price_type": rule.price_type,
                "badge": _(
                    "-%(percentage)s%% OFF", percentage=rule._get_percentage_label()
                ) if rule.price_type == "discount" else False,
                # Un solo string traducible ya armado (D25): el JS de variantes lo repinta con
                # textContent, sin componer HTML ni re-resolver la moneda. Solo con descuento: con
                # un recargo el precio del medio es MAS caro y un "Ahorras" ahi seria mentira,
                # aunque el precio de referencia sea mayor que el recargado (CA23).
                "saving_label": _(
                    "You save %(amount)s", amount=format_amount(self.env, saving, currency),
                ) if rule.price_type == "discount" and currency.compare_amounts(saving, 0) == 1
                else False,
            })
        return vals

    @api.model
    def _get_payment_method_reference_badge(self, website, price, reference_price):
        """
        Pill del descuento que YA publica el core (lista de precios o precio comparativo).

        Es el primer pill de la maqueta (D25): acompana al precio tachado de arriba y no tiene nada
        que ver con el medio de pago. Se calcula aca —y no en la vista— para no meter el redondeo
        del porcentaje en QWeb.

        :param website: sitio web que se esta renderizando
        :type website: recordset de `website`
        :param price: precio mostrado del producto (ya con el descuento de la lista aplicado)
        :type price: float
        :param reference_price: precio tachado que publica el core, o None si no hay
        :type reference_price: float | None
        :return: texto del pill (ej. `-15%`), o False si no hay descuento que mostrar
        :rtype: str | bool
        """
        currency = website.currency_id
        if not reference_price or currency.compare_amounts(reference_price, price) != 1:
            return False
        # HALF-UP explicito: el `round()` de Python redondea al par (banker's rounding) y un
        # 22,5 % saldria "-22%". Mismo criterio que `_get_percentage_label()` de la regla.
        percentage = int(float_round(
            (reference_price - price) * 100.0 / reference_price, precision_digits=0,
            rounding_method="HALF-UP",
        ))
        if not percentage:
            return False
        return _("-%(percentage)s%%", percentage=percentage)

    def _get_sales_prices(self, website):
        """Override de `website_sale` para agregar los precios por medio de pago a la grilla."""
        res = super()._get_sales_prices(website)
        if not self:
            return res
        rules = self.env["payment.method.website.price"]._get_website_rules(
            website, only_visible=True
        )
        if not rules:
            return res
        for template in self:
            template_price_vals = res.get(template.id)
            if not template_price_vals:
                continue
            # Misma condicion que el `t-if` del core sobre el precio de la tarjeta
            # (`product_tile_templates.xml:195`): con precio 0 y el sitio configurado para no
            # vender a precio cero, el core **esconde** el precio y el recuadro no tiene nada que
            # decorar. Espeja la guarda que la ficha ya tenia en `_get_additionnal_combination_info`.
            if not template_price_vals["price_reduce"] and website.prevent_zero_price_sale:
                continue
            # `base_price` solo viaja cuando el core decide tachar un precio arriba
            # (`_show_discount_on_shop()` o `compare_list_price`), que es justo la condicion del
            # `t-if` de `t[name='product_base_price']`: la misma fuente para el pill y para el nodo.
            reference_price = template_price_vals.get("base_price")
            template_price_vals["payment_method_prices"] = self._get_payment_method_price_vals(
                website, template_price_vals["price_reduce"], rules=rules,
                reference_price=reference_price,
            )
            template_price_vals["payment_method_reference_badge"] = (
                self._get_payment_method_reference_badge(
                    website, template_price_vals["price_reduce"], reference_price,
                )
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
            res["payment_method_reference_badge"] = False
            return res
        # Mismo criterio que el core para el nodo tachado de la ficha, y en el mismo orden: el
        # precio de lista cuando hay descuento de lista de precios (`has_discounted_price` es lo
        # que le saca el `d-none` a `span[@name='product_list_price']`) y, si no, el precio
        # comparativo (que el core solo arma en ese caso, `product_template.py:630`). Son
        # excluyentes: nunca hay dos precios tachados a la vez.
        reference_price = res["list_price"] if res.get("has_discounted_price") else None
        if not reference_price:
            reference_price = res.get("compare_list_price") or None
        res["payment_method_prices"] = self._get_payment_method_price_vals(
            website, res["price"], reference_price=reference_price,
        )
        # El pill de referencia es decoracion de ESTE modulo: sin ninguna regla visible el recuadro
        # no se dibuja y el precio del core tiene que verse como siempre (CA19/RB08). La grilla ya
        # corta antes (`if not rules`); aca la guarda es que no haya precios por medio de pago.
        res["payment_method_reference_badge"] = self._get_payment_method_reference_badge(
            website, res["price"], reference_price,
        ) if res["payment_method_prices"] else False
        return res

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
