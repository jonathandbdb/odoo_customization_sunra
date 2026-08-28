import { patch } from "@web/core/utils/patch";

import { WebsiteSale } from "@website_sale/interactions/website_sale";

patch(WebsiteSale.prototype, {

    /**
     * Repintar los precios por medio de pago al cambiar de variante.
     *
     * El precio de la ficha se recalcula por jsonrpc en /website_sale/get_combination_info, que
     * devuelve JSON y no HTML: el DOM lo actualiza el cliente. Sin este repintado el segundo
     * precio quedaria con el valor de la variante anterior.
     *
     * Se parchea la interaccion y no VariantMixin porque el core copia el mixin al prototipo con
     * Object.assign (website_sale/interactions/website_sale.js:651): un patch sobre el mixin
     * llegaria tarde y no tendria efecto.
     *
     * @override
     */
    _onChangeCombination(ev, parent, combination) {
        super._onChangeCombination(...arguments);

        const prices = combination.payment_method_prices || [];
        for (const container of parent.querySelectorAll(".o_wspmp_prices")) {
            container.replaceChildren();
            container.classList.toggle("d-none", prices.length === 0);
            for (const price of prices) {
                const row = document.createElement("div");
                row.className = "o_wspmp_price";

                const amount = document.createElement("span");
                amount.className = "o_wspmp_price_amount";
                amount.textContent = price.price_formatted;

                const label = document.createElement("span");
                label.className = "o_wspmp_price_label";
                label.textContent = price.label;

                row.append(amount, label);
                container.append(row);
            }
        }
    },

});
