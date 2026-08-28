# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, route

from odoo.addons.website_sale.controllers import payment as website_sale_payment


class WebsiteSalePaymentMethodPrice(http.Controller):

    @route(
        "/shop/payment/method_price",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        website=True,
    )
    def shop_payment_method_price(self, payment_method_id=None, token_id=None, **kwargs):
        """
        Aplicar o quitar el ajuste del medio de pago seleccionado sobre el carrito de la sesion.

        Elegir el medio en el checkout no pega al servidor, y al crear la transaccion el core
        aborta si el importe del formulario no coincide con el total del pedido. Por eso el ajuste
        se aplica desde aca y el paso de pago se recarga.

        Solo opera sobre `request.cart`, es decir el carrito de la propia sesion: nunca sobre un
        pedido arbitrario.

        :param payment_method_id: medio de pago seleccionado, o None para dejar el pedido sin ajuste
        :type payment_method_id: int o None
        :param token_id: token elegido, si el cliente paga con un medio guardado
        :type token_id: int o None
        :return: dict con `reload`, que indica si el total del pedido cambio
        :rtype: dict
        """
        order_sudo = request.cart
        if not order_sudo or order_sudo.state != "draft":
            return {"reload": False}
        method_id = payment_method_id or _get_token_payment_method_id(token_id)
        rule = _get_rule_for_method(method_id, order_sudo.website_id)
        if rule == order_sudo.payment_price_rule_id:
            return {"reload": False}
        order_sudo._apply_payment_price_rule(rule)
        return {"reload": True}


class PaymentPortal(website_sale_payment.PaymentPortal):

    def _get_shop_payment_values(self, order, **kwargs):
        """
        Override de `website_sale`: aplicar el ajuste del medio preseleccionado antes de renderizar.

        Cuando hay un solo medio de pago el core lo deja marcado desde el servidor
        (`payment/views/payment_form_templates.xml:38-42`), asi que el evento `change` del radio
        nunca dispara y el JS no se enteraria. Se espeja esa misma condicion aca para que el paso de
        pago ya se dibuje con el total ajustado, sin una recarga extra.

        Solo se aplica cuando el pedido NO tiene ya una regla: si la tiene es porque el cliente
        eligio un medio (via `/shop/payment/method_price`), y quitarsela aca la pelearia contra esa
        eleccion en cada recarga. Un ajuste que no corresponda al medio con el que finalmente se
        paga lo corrige `shop_payment_transaction`.

        Si el ajuste cambia hay que volver a pedir los valores: el importe del formulario y el
        resumen del pedido se calculan dentro de `super()`.
        """
        values = super()._get_shop_payment_values(order, **kwargs)
        if order.payment_price_rule_id:
            return values
        rule = _get_rule_for_preselected_option(values, order.website_id)
        if not rule:
            return values
        order._apply_payment_price_rule(rule)
        return super()._get_shop_payment_values(order, **kwargs)

    def shop_payment_transaction(self, order_id, access_token, **kwargs):
        """
        Override de `website_sale`: el ajuste del pedido debe corresponder al medio que se usa.

        Cubre el caso de una pagina de pago quedada vieja o de una seleccion que no paso por
        `/shop/payment/method_price`. Si el ajuste no corresponde se corrige el pedido, con lo cual
        el chequeo de importe del core (`compare_amounts` contra `amount_total`) pide refrescar en
        vez de cobrar un importe distinto al que se mostro.
        """
        cart_sudo = request.cart
        if cart_sudo and cart_sudo.id == order_id:
            method_id = kwargs.get("payment_method_id") or _get_token_payment_method_id(
                kwargs.get("token_id")
            )
            rule = _get_rule_for_method(method_id, cart_sudo.website_id)
            if rule != cart_sudo.payment_price_rule_id:
                cart_sudo._apply_payment_price_rule(rule)
        return super().shop_payment_transaction(order_id, access_token, **kwargs)


def _get_rule_for_preselected_option(values, website):
    """
    Regla del medio de pago que el core deja preseleccionado al renderizar el paso de pago.

    Espeja la condicion de la plantilla del core: se preselecciona el token por defecto (o el
    primero, si se permite elegir token) y, si no hay ninguno, el unico medio de pago disponible.

    :param values: valores de render devueltos por `_get_shop_payment_values`
    :type values: dict
    :param website: sitio web del pedido
    :type website: recordset de `website`
    :return: la regla, o un recordset vacio si no hay medio preseleccionado
    :rtype: recordset de `payment.method.website.price`
    """
    tokens_sudo = values.get("tokens_sudo")
    methods_sudo = values.get("payment_methods_sudo")
    allow_token_selection = values.get("allow_token_selection", True)
    selected_token = tokens_sudo[:1] if (allow_token_selection and tokens_sudo) else None
    if values.get("default_token_id") and allow_token_selection:
        selected_token = request.env["payment.token"].sudo().browse(values["default_token_id"])
    if selected_token:
        return _get_rule_for_method(selected_token.payment_method_id.id, website)
    if methods_sudo and len(methods_sudo) == 1:
        return _get_rule_for_method(methods_sudo.id, website)
    return request.env["payment.method.website.price"].sudo()


def _get_token_payment_method_id(token_id):
    """
    Medio de pago de un token guardado.

    :param token_id: id del token, o algo falsy
    :type token_id: int o None
    :return: id del medio de pago, o None
    :rtype: int o None
    """
    if not token_id:
        return None
    token_sudo = request.env["payment.token"].sudo().browse(int(token_id)).exists()
    return token_sudo.payment_method_id.id if token_sudo else None


def _get_rule_for_method(payment_method_id, website):
    """
    Resolver la regla de precio de un medio de pago para un sitio.

    :param payment_method_id: id del medio de pago, o algo falsy
    :type payment_method_id: int o None
    :param website: sitio web del pedido
    :type website: recordset de `website`
    :return: la regla, o un recordset vacio
    :rtype: recordset de `payment.method.website.price`
    """
    empty = request.env["payment.method.website.price"].sudo()
    if not payment_method_id:
        return empty
    method_sudo = request.env["payment.method"].sudo().browse(int(payment_method_id)).exists()
    if not method_sudo:
        return empty
    return method_sudo._get_website_price_rule(website)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
