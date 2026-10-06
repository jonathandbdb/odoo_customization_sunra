import { patch } from "@web/core/utils/patch";
import {
    ProductConfiguratorDialog,
} from "@sale/js/product_configurator_dialog/product_configurator_dialog";
import {
    ComboConfiguratorDialog,
} from "@sale/js/combo_configurator_dialog/combo_configurator_dialog";

// El cart service esparce la opcion en las props de los configuradores
for (const Dialog of [ProductConfiguratorDialog, ComboConfiguratorDialog]) {
    patch(Dialog, {
        props: {
            ...Dialog.props,
            bike_assembly_option: { type: String, optional: true },
        },
    });
}
