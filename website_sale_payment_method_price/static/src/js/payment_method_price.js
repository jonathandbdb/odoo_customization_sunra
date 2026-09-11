import { patch } from "@web/core/utils/patch";

import { WebsiteSale } from "@website_sale/interactions/website_sale";

patch(WebsiteSale.prototype, {

    /**
     * Repintar el recuadro de precio por medio de pago al cambiar de variante (D17).
     *
     * El precio de la ficha se recalcula por jsonrpc en /website_sale/get_combination_info, que
     * devuelve JSON y no HTML: el DOM lo actualiza el cliente. Este metodo tiene que espejar el
     * markup del template (views/website_sale_templates.xml): si cambia uno, cambia el otro.
     *
     * Restriccion: `replaceChildren()` se hace UNICAMENTE sobre `.o_wspmp_prices`. Sobre el
     * recuadro (`.o_wspmp_box`) y el slot de cuotas solo se togglean clases/texto: con el `move`
     * de 1.2.0 el `span.oe_price` (ficha) o `span.fw-bold` (grilla, precio de `price_reduce`) del
     * core viven DENTRO del recuadro y los repinta `super._onChangeCombination()`
     * (variant_mixin.js:346), que corre primero. Vaciar el recuadro entero los borraria (y, con
     * el puente de cuotas instalado, tambien la linea de cuotas).
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
        const isDiscount = prices.length > 0 && prices[0].price_type === "discount";

        for (const box of parent.querySelectorAll(".o_wspmp_box")) {
            box.classList.toggle("o_wspmp_box_active", prices.length > 0);
            box.classList.toggle("o_wspmp_discounted", isDiscount);

            // El pill siempre esta en el DOM (renderizado por el servidor, aunque vacio/oculto):
            // aca solo se togglea su texto y su visibilidad, nunca se crea ni se destruye.
            const badge = box.querySelector(".o_wspmp_badge");
            if (badge) {
                const badgeText = (prices.length && prices[0].badge) || "";
                badge.textContent = badgeText;
                badge.classList.toggle("d-none", !badgeText);
            }

            const container = box.querySelector(".o_wspmp_prices");
            if (!container) {
                continue;
            }
            container.replaceChildren();
            for (const price of prices) {
                const row = document.createElement("div");
                row.className = "o_wspmp_price";

                const amount = document.createElement("span");
                amount.className = "o_wspmp_price_amount";
                amount.textContent = price.price_formatted;

                const label = document.createElement("span");
                label.className = "o_wspmp_price_label";
                label.append(`${price.label} `);
                const name = document.createElement("b");
                name.textContent = price.name;
                label.append(name);

                row.append(amount, label);
                container.append(row);
            }
        }
    },

});
