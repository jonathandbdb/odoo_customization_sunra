import { browser } from "@web/core/browser/browser";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";

import { PaymentForm } from "@payment/interactions/payment_form";

const SHOP_TRANSACTION_ROUTE = "/shop/payment/transaction/";
const SELECTED_OPTION_PARAM = "wspmp_pm";

patch(PaymentForm.prototype, {

    /**
     * Volver a marcar el medio elegido despues de la recarga.
     *
     * El ajuste del pedido se aplica en el servidor y el paso de pago se recarga, con lo cual la
     * seleccion del radio se perderia y el boton de pagar quedaria deshabilitado. El id viaja en la
     * URL y aca se re-marca; el rpc que dispara ese click devuelve reload=false porque el ajuste ya
     * corresponde al medio, asi que no hay bucle de recargas.
     *
     * @override
     */
    async willStart() {
        await super.willStart(...arguments);

        if (!this._wspmpIsShopCheckout()) {
            return;
        }
        const optionId = new URL(browser.location.href).searchParams.get(SELECTED_OPTION_PARAM);
        if (!optionId) {
            return;
        }
        const radio = this.el.querySelector(
            `input[name="o_payment_radio"][data-payment-option-id="${optionId}"]`
        );
        if (radio && !radio.checked) {
            radio.click();
        }
    },

    /**
     * Aplicar el ajuste del medio de pago elegido y recargar el paso de pago.
     *
     * Elegir el medio no pega al servidor, y al crear la transaccion el core aborta si el importe
     * del formulario no coincide con el total del pedido. Se recarga la pagina entera porque el
     * importe vive en el dataset del formulario, leido en el setup() de la interaccion: un refresh
     * parcial dejaria el dataset viejo.
     *
     * @override
     */
    async selectPaymentOption(ev) {
        await super.selectPaymentOption(...arguments);

        if (!this._wspmpIsShopCheckout()) {
            return;
        }

        const checkedRadio = ev.target;
        const optionId = this._getPaymentOptionId(checkedRadio);
        const params = { payment_method_id: null, token_id: null };
        if (this._getPaymentOptionType(checkedRadio) === "token") {
            params.token_id = optionId;
        } else {
            params.payment_method_id = optionId;
        }

        const result = await this.waitFor(rpc("/shop/payment/method_price", params));
        if (result?.reload) {
            const url = new URL(browser.location.href);
            url.searchParams.set(SELECTED_OPTION_PARAM, optionId);
            browser.location.assign(url.toString());
        }
    },

    /**
     * Indicar si esta interaccion es la del checkout del eCommerce.
     *
     * @return {boolean}
     */
    _wspmpIsShopCheckout() {
        return Boolean(
            this.paymentContext["transactionRoute"]?.startsWith(SHOP_TRANSACTION_ROUTE)
        );
    },

});
