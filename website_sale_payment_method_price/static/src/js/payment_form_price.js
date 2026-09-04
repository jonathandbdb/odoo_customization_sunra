import { browser } from "@web/core/browser/browser";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";

import { PaymentForm } from "@payment/interactions/payment_form";

const SHOP_TRANSACTION_ROUTE = "/shop/payment/transaction/";
const SELECTED_OPTION_PARAM = "wspmp_pm";

patch(PaymentForm.prototype, {

    /**
     * Volver a marcar el medio elegido antes de que el core arme el formulario.
     *
     * El ajuste del pedido se aplica en el servidor y el paso de pago se recarga, con lo cual la
     * seleccion del radio se perderia y el boton de pagar quedaria deshabilitado. El id viaja en la
     * URL y aca se re-marca ANTES del super: el willStart del core, al encontrar un radio marcado,
     * despliega el formulario inline del medio y habilita el boton, igual que cuando hay un solo
     * medio de pago.
     *
     * No se puede simular la eleccion con un click(): los listeners de dynamicContent se enganchan
     * recien cuando willStart resuelve (colibri.js:L51), asi que el evento change no lo escucharia
     * nadie y el boton quedaria trabado.
     *
     * @override
     */
    async willStart() {
        try {
            this._wspmpRestoreSelectedOption();
        } catch (error) {
            // Nunca dejar que esto tumbe el willStart: si rechaza, el framework no engancha
            // NINGUN listener (colibri.js:L58) y el paso de pago queda inutilizable — el mismo
            // sintoma que este metodo viene a arreglar. Restaurar la seleccion es una comodidad;
            // el cliente siempre puede volver a elegir el medio a mano.
            console.warn("wspmp: no se pudo restaurar el medio de pago elegido", error);
        }
        await super.willStart(...arguments);
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
     * Marcar el radio del medio que viaja en la URL, sin disparar eventos.
     *
     * Se marca la propiedad `checked` a mano en vez de clickear porque el radio tiene que quedar
     * elegido para cuando corra el willStart del core, que es el que despliega el formulario inline
     * y habilita el boton de pagar.
     *
     * @return {void}
     */
    _wspmpRestoreSelectedOption() {
        if (!this._wspmpIsShopCheckout()) {
            return;
        }
        const optionId = new URL(browser.location.href).searchParams.get(SELECTED_OPTION_PARAM);
        // El valor viaja en la URL y se interpola en un selector: si no es un id, ni se intenta
        // (un valor con comillas o corchetes haria que querySelector tire SyntaxError).
        if (!optionId || !/^\d+$/.test(optionId)) {
            return;
        }
        const radio = this.el.querySelector(
            `input[name="o_payment_radio"][data-payment-option-id="${optionId}"]`
        );
        if (!radio || radio.checked) {
            return;
        }
        radio.checked = true;
        // Con tokens guardados el core colapsa la lista de medios: si el elegido es uno de esos,
        // hay que desplegarla o quedaria marcado un medio que el cliente no ve.
        const collapsedSection = radio.closest("#o_payment_methods.collapse:not(.show)");
        if (collapsedSection) {
            collapsedSection.classList.add("show");
            this.el
                .querySelector('[name="o_payment_expand_button"]')
                ?.classList.add("d-none");
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
