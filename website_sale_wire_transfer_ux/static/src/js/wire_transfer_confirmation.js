import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";
import { _t } from "@web/core/l10n/translation";

/**
 * Copia el CBU al portapapeles desde la pagina de confirmacion del eCommerce.
 *
 * El numero viene en el dataset del boton, puesto por el template desde la cuenta bancaria de la
 * compania. Sin JS el bloque sigue mostrando el CBU en pantalla, listo para seleccionarlo a mano.
 */
export class WireTransferConfirmation extends Interaction {
    static selector = ".o_swt_transfer_data";

    dynamicContent = {
        ".o_swt_copy": {
            "t-on-click": this.onCopyClick,
            "t-out": () => this.copyLabel,
        },
    };

    setup() {
        // INITIAL_VALUE deja la etiqueta que trae el template ("Copiar CBU").
        this.copyLabel = Interaction.INITIAL_VALUE;
        this.resetTimeout = null;
    }

    async onCopyClick(ev) {
        const value = ev.currentTarget.dataset.swtValue;
        if (!value) {
            return;
        }
        const copied = await this.waitFor(this.copyToClipboard(value));
        this.copyLabel = copied ? _t("Copied!") : _t("Press Ctrl+C to copy");
        // Dos clicks seguidos no tienen que cortarle el aviso al segundo.
        clearTimeout(this.resetTimeout);
        this.resetTimeout = this.waitForTimeout(() => {
            this.copyLabel = Interaction.INITIAL_VALUE;
            this.resetTimeout = null;
        }, 2000);
    }

    /**
     * Copia un texto al portapapeles.
     *
     * La Clipboard API solo existe en contextos seguros (https o localhost), asi que se deja el
     * camino viejo del textarea como reserva.
     *
     * @param {string} value
     * @returns {Promise<boolean>} si se pudo copiar
     */
    async copyToClipboard(value) {
        if (navigator.clipboard && window.isSecureContext) {
            try {
                await navigator.clipboard.writeText(value);
                return true;
            } catch {
                // Sin permiso del navegador: se intenta el camino viejo.
            }
        }
        const textarea = document.createElement("textarea");
        textarea.value = value;
        textarea.setAttribute("readonly", "readonly");
        textarea.classList.add("position-fixed", "opacity-0");
        this.el.appendChild(textarea);
        textarea.select();
        let copied = false;
        try {
            copied = document.execCommand("copy");
        } catch {
            copied = false;
        }
        textarea.remove();
        return copied;
    }
}

registry
    .category("public.interactions")
    .add("website_sale_wire_transfer_ux.wire_transfer_confirmation", WireTransferConfirmation);
