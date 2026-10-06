import { patch } from "@web/core/utils/patch";
import { WebsiteSale } from "@website_sale/interactions/website_sale";

patch(WebsiteSale.prototype, {
    /**
     * Agrega la opcion Armada / En caja al producto raiz, solo si el selector existe en el form.
     *
     * @param {HTMLFormElement} form - El formulario en el que esta el producto.
     */
    _updateRootProduct(form) {
        super._updateRootProduct(...arguments);
        const option = form.querySelector('input[name="bike_assembly_option"]:checked');
        if (option) {
            this.rootProduct.bike_assembly_option = option.value;
        }
    },
});
