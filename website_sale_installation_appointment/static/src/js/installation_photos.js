import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";
import { _t } from "@web/core/l10n/translation";

/**
 * Sube las fotos del lugar apenas el cliente las elige.
 *
 * Antes habia que elegir los archivos y ADEMAS apretar "Continuar" para que se subieran: si el
 * cliente iba directo al pago, el paso lo rebotaba diciendo que faltaban fotos aunque las tuviera
 * seleccionadas en pantalla. Sin JS el formulario sigue funcionando con el boton de siempre.
 */
export class InstallationPhotos extends Interaction {
    static selector = "#shop_installation form[data-installation-photos]";

    dynamicContent = {
        "input[type='file']": { "t-on-change": this.onFilesSelected },
    };

    onFilesSelected(ev) {
        const input = ev.currentTarget;
        if (!input.files || !input.files.length) {
            return;
        }
        const feedback = this.el.querySelector("[data-installation-photos-feedback]");
        if (feedback) {
            feedback.textContent = _t("Uploading photos…");
            feedback.classList.remove("d-none");
        }
        const button = this.el.querySelector("button[name='installation_continue']");
        if (button) {
            button.disabled = true;
        }
        // El cliente solo eligio los archivos: se suben y se vuelve al paso para que los revise,
        // sin saltar al pago.
        const stay = document.createElement("input");
        stay.type = "hidden";
        stay.name = "stay_on_step";
        stay.value = "1";
        this.el.appendChild(stay);
        this.el.submit();
    }
}

registry
    .category("public.interactions")
    .add("website_sale_installation_appointment.installation_photos", InstallationPhotos);
