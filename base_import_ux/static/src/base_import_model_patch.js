import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { BaseImportModel } from "@base_import/import_model";

/**
 * Se parchea solo BaseImportModel.prototype: la subclase de extractos
 * bancarios (BankStatementCSVImportModel, enterprise) no se exporta -solo
 * su factory useBankStatementCSVImportModel- por lo que no se puede
 * parchear directo. Como esa subclase no overridea updateData(), el patch
 * de este prototipo base alcanza tambien al flujo de extractos.
 */
patch(BaseImportModel.prototype, {
    /**
     * Registra la opcion 'header_skip_rows' en el estado del cliente, solo si
     * todavia no existe (idempotente). Se invoca desde dos puntos de este
     * mismo prototipo (init() y updateData()) porque el init() de la subclase
     * de extractos no llama a super().
     */
    _registerHeaderSkipOption() {
        if (this.importOptionsValues.header_skip_rows) {
            return;
        }
        this.importOptionsValues.header_skip_rows = {
            label: _t("Header rows to skip:"),
            help: _t(
                "Number of raw lines to discard from the top of the CSV file before parsing (e.g. summary or metadata rows preceding the real header)."
            ),
            type: "input",
            value: 0,
            reloadParse: true,
        };
    },

    async init() {
        const res = await super.init(...arguments);
        // Flujo generico (cualquier modelo): la subclase de extractos no llama a
        // este init(), asi que este registro no la cubre (ver updateData()).
        this._registerHeaderSkipOption();
        return res;
    },

    async updateData(fileChanged = false) {
        // Register-if-missing: cubre el flujo de extractos, cuyo init() no llama
        // a super() pero cuyo updateData() es heredado sin override y siempre
        // corre antes de la llamada RPC parse_preview.
        this._registerHeaderSkipOption();

        // Feature 2: default de fecha DD-MM-YYYY solo en el flujo de extractos
        // bancarios (bank_stmt_import lo setea BankStatementCSVImportModel.init()).
        // One-shot: no se re-fuerza si el usuario o el server lo cambian despues
        // (_onLoadSuccess reescribe el estado con la respuesta del server).
        const dateFormat = this.importOptionsValues.date_format;
        if (
            this.importOptionsValues.bank_stmt_import?.value === true &&
            dateFormat &&
            !dateFormat.value &&
            !this._dmyPrefilled
        ) {
            dateFormat.value = "DD-MM-YYYY";
            this._dmyPrefilled = true;
        }

        return super.updateData(...arguments);
    },
});
