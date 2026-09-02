import { patch } from '@web/core/utils/patch';
import { WebsiteSale } from '@website_sale/interactions/website_sale';

patch(WebsiteSale.prototype, {
    /**
     * Actualizar el cartel de nivel de stock con el de la variante elegida.
     *
     * La pagina se renderiza para la plantilla, asi que el unico lugar donde se sabe que variante
     * quedo seleccionada es el payload de /website_sale/get_combination_info, al que
     * `product.template._get_additionnal_combination_info` le agrega `stock_level_*`.
     *
     * @override
     */
    _onChangeCombination(ev, parent, combination) {
        super._onChangeCombination(...arguments);
        // Buscamos el badge y no el contenedor: el listado usa su propia clase de contenedor y se
        // renderiza entero del lado del servidor, sin este span.
        const badgeEl = parent.querySelector('.o_wsale_stock_level_badge');
        if (!badgeEl) {
            return;
        }
        const label = combination.stock_level_name || '';
        badgeEl.textContent = label;
        // Reescribimos la lista de clases entera: el color del nivel viene en una clase
        // contextual (`text-bg-*`) y hay que sacar la del nivel anterior.
        badgeEl.className = [
            'o_wsale_stock_level_badge badge text-uppercase',
            combination.stock_level_class || '',
            label ? '' : 'd-none',
        ].filter(Boolean).join(' ');
        badgeEl.style.cssText = combination.stock_level_style || '';
    },
});
