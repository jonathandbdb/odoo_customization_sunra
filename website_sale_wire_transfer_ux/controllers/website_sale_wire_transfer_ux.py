# -*- coding: utf-8 -*-
from odoo import _, http
from odoo.http import request, route

from odoo.addons.website_sale.models.website import CART_SESSION_CACHE_KEY


class WebsiteSaleWireTransferUx(http.Controller):

    @route(
        "/shop/wire-transfer/change-payment-method",
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        sitemap=False,
    )
    def shop_wire_transfer_change_payment_method(self, **kwargs):
        """
        Reabrir el paso de pago del checkout para el pedido pendiente de la sesion.

        El core no tiene vuelta atras: al elegir transferencia el pedido queda en presupuesto
        enviado (`sale/models/payment_transaction.py`, `_post_process`) y `/shop/payment/validate`
        llama `sale_reset()`, asi que la sesion pierde el carrito. Para volver al paso de pago hay
        que deshacer las tres cosas: cancelar la transaccion pendiente, devolver el pedido a
        presupuesto y volver a apuntar el carrito de la sesion. Los tres son necesarios porque
        `website.Website._get_and_cache_current_cart()` descarta el carrito si el pedido no esta en
        `draft` o si su ultima transaccion sigue en `pending`.

        Es POST (con el token CSRF que agrega el formulario del template) porque cancela un pago y
        cambia el estado del pedido: por GET, un `<img src="...">` en cualquier sitio de terceros
        alcanzaria para dispararlo sobre el visitante.

        :return: redireccion al paso de pago, o a la tienda si el pedido ya no es reabrible
        """
        order_sudo = self._get_reopenable_order()
        if not order_sudo:
            return request.redirect("/shop")
        tx_sudo = order_sudo.get_portal_last_transaction()
        if tx_sudo.state == "pending":
            tx_sudo._set_canceled(
                state_message=_("The customer chose another payment method.")
            )
        order_sudo.action_draft()
        request.session[CART_SESSION_CACHE_KEY] = order_sudo.id
        return request.redirect("/shop/payment")

    def _get_reopenable_order(self):
        """
        Devolver el pedido de la sesion si se puede reabrir su paso de pago.

        :return: el pedido, o un recordset vacio si no aplica
        :rtype: recordset de `sale.order`
        """
        SaleOrderSudo = request.env["sale.order"].sudo()
        order_id = request.session.get("sale_last_order_id")
        if not order_id:
            return SaleOrderSudo
        order_sudo = SaleOrderSudo.browse(order_id).exists()
        if not order_sudo or order_sudo.website_id != request.website:
            return SaleOrderSudo
        # `authenticate()` no limpia la sesion: en un navegador compartido, el pedido que quedo en
        # la sesion puede ser de otra persona. Si hay usuario logueado, tiene que ser el suyo.
        user = request.env.user
        if not user._is_public() and order_sudo.partner_id != user.partner_id:
            return SaleOrderSudo
        # Solo antes de cobrar: un pedido confirmado o con pago hecho no se reabre.
        if order_sudo.state not in ("draft", "sent"):
            return SaleOrderSudo
        if order_sudo.get_portal_last_transaction().state in ("authorized", "done"):
            return SaleOrderSudo
        return order_sudo

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
