import { patch } from "@web/core/utils/patch";

import { WebsiteSale } from "@website_sale/interactions/website_sale";

patch(WebsiteSale.prototype, {

    /**
     * Repintar el recuadro de precio por medio de pago al cambiar de variante.
     *
     * Tiene que espejar el markup de views/website_sale_templates.xml. El `replaceChildren()` va
     * solo sobre `.o_wspmp_prices`: el precio del core vive dentro del recuadro y lo repinta el
     * super (variant_mixin.js:346), asi que vaciar el recuadro lo borraria. Se parchea la
     * interaccion y no VariantMixin porque el core copia el mixin al prototipo con Object.assign
     * (website_sale.js:651).
     *
     * @override
     */
    _onChangeCombination(ev, parent, combination) {
        super._onChangeCombination(...arguments);

        const prices = combination.payment_method_prices || [];
        const isDiscount = prices.length > 0 && prices[0].price_type === "discount";
        const refBadgeText = combination.payment_method_reference_badge || "";

        for (const box of parent.querySelectorAll(".o_wspmp_box")) {
            box.classList.toggle("o_wspmp_box_active", prices.length > 0);
            box.classList.toggle("o_wspmp_discounted", isDiscount);

            // Los dos pills siempre estan en el DOM (renderizados por el servidor, aunque
            // vacios/ocultos): aca solo se togglea su texto y su visibilidad, nunca se crean ni se
            // destruyen. Se buscan por su clase propia (`_pm` / `_ref`) porque desde 1.3.0 hay dos
            // (D25) y `.o_wspmp_badge` a secas devolveria el primero del DOM.
            const pmBadge = box.querySelector(".o_wspmp_badge_pm");
            if (pmBadge) {
                const badgeText = (prices.length && prices[0].badge) || "";
                pmBadge.textContent = badgeText;
                pmBadge.classList.toggle("d-none", !badgeText);
            }
            // querySelectorAll, no querySelector: la ficha renderiza DOS pills de referencia
            // (uno sobre el precio de lista y otro sobre el comparativo, excluyentes entre si) y
            // el primero del DOM suele ser justo el que esta oculto.
            for (const refBadge of box.querySelectorAll(".o_wspmp_badge_ref")) {
                refBadge.textContent = refBadgeText;
                refBadge.classList.toggle("d-none", !refBadgeText);
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

                // "Ahorras $X": un solo string ya armado y traducido por el servidor (D25), asi
                // que aca alcanza con textContent.
                const saving = document.createElement("span");
                saving.className = "o_wspmp_saving";
                saving.textContent = price.saving_label || "";
                saving.classList.toggle("d-none", !price.saving_label);

                const label = document.createElement("span");
                label.className = "o_wspmp_price_label";
                label.append(`${price.label} `);
                const name = document.createElement("b");
                name.textContent = price.name;
                label.append(name);

                row.append(amount, saving, label);
                container.append(row);
            }
        }
    },

});
