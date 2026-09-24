import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";
import { _t } from "@web/core/l10n/translation";

/**
 * Sube las fotos del lugar apenas el cliente las elige, para que ya cuenten en el gate de fotos
 * minimas antes de llegar al pago. Sin JS el formulario sigue funcionando con el boton de siempre
 * (el `<form>` lleva el input oculto `stay_on_step` en la propia plantilla, D44).
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
        // El cliente solo eligio los archivos: se suben y se vuelve al paso para que los revise
        // (el `<form>` ya lleva `stay_on_step` como input oculto).
        this.el.submit();
    }
}

registry
    .category("public.interactions")
    .add("website_sale_installation_appointment.installation_photos", InstallationPhotos);
