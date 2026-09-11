import { patch } from "@web/core/utils/patch";
import { Checkout } from "@website_sale/interactions/checkout";

// Reemplaza el badge de precio ("Free"/precio calculado) por el texto configurado en
// delivery.carrier.website_price_label, cuando esta cargado (ver
// odoo/addons/website_sale/static/src/interactions/checkout.js:339 para el "Free" del core).
patch(Checkout.prototype, {
    /**
     * @override method from `@website_sale/interactions/checkout`
     */
    _updateAmountBadge(radio, rateData) {
        super._updateAmountBadge(...arguments);
        // Si el metodo de envio tiene un texto configurado (data-price-label, ver
        // views/website_sale_templates.xml) y la tarifa se calculo bien, ese texto reemplaza al
        // precio/"Free" que acaba de escribir el core. Sin label o con error, no se toca nada:
        // el comportamiento queda identico al de super().
        const badge = this._getDeliveryPriceBadge(radio);
        const label = badge?.dataset.priceLabel;
        if (rateData.success && label) {
            badge.textContent = label;
        }
    },
});
