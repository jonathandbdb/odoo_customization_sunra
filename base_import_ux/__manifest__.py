# -*- coding: utf-8 -*-
{
    "name": "base_import_ux",
    "version": "1.0.0",
    "summary": "Mejoras de UX del asistente de importacion (filas de cabecera a saltear y fecha DD-MM-YYYY en extractos)",
    "description": """
Mejoras de experiencia de uso sobre el asistente de importacion nativo (base_import), pensadas para
poder importar extractos de cuenta de Mercado Pago (CSV crudo) sin editar el archivo a mano.
- Opcion "filas de cabecera a saltear" (header_skip_rows): descarta las primeras N filas crudas de
  un archivo CSV (incluidas filas de resumen/metadata y la fila en blanco) antes de parsear.
- Formato de fecha DD-MM-YYYY por defecto, editable, unicamente en el flujo de importacion de
  extractos bancarios (no afecta otros imports).
    """,
    "category": "Custom",
    "author": "Sunra",
    "website": "https://github.com/sunraargsh",
    "license": "LGPL-3",
    "depends": ["base_import", "account_bank_statement_import_csv"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "base_import_ux/static/src/base_import_model_patch.js",
            "base_import_ux/static/src/import_data_sidepanel_patch.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
