import { patch } from '@web/core/utils/patch';
import { WebsiteSale } from '@website_sale/interactions/website_sale';

patch(WebsiteSale.prototype, {
    /**
     * Actualizar el codigo interno mostrado con el de la variante elegida.
     *
     * El core no lo hace: la pagina se renderiza para la plantilla y el unico lugar donde se sabe
     * que variante quedo seleccionada es el payload de /website_sale/get_combination_info, al que
     * `product.template._get_additionnal_combination_info` le agrega `default_code`.
     *
     * @override
     */
    _onChangeCombination(ev, parent, combination) {
        super._onChangeCombination(...arguments);
        // Buscamos el valor y no el contenedor: el carrito usa la misma clase de contenedor pero
        // se renderiza entero del lado del servidor, sin este span.
        const valueEl = parent.querySelector('.o_wsale_variant_code_value');
        if (!valueEl) {
            return;
        }
        const code = combination.default_code || '';
        valueEl.textContent = code;
        valueEl.closest('.o_wsale_variant_code').classList.toggle('d-none', !code);
    },
});
