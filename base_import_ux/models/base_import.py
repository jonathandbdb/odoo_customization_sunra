# -*- coding: utf-8 -*-
from odoo import models


class BaseImportImport(models.TransientModel):
    _inherit = "base_import.import"

    def _read_csv(self, options):
        """
        Recorta las primeras N lineas crudas del archivo CSV antes de delegar el
        parseo en el metodo nativo, segun la opcion de wizard 'header_skip_rows'
        (filas de resumen/metadata que preceden al encabezado real, caso Mercado
        Pago). El recorte se hace en crudo (bytes, ANTES de decodificar/parsear)
        para que la fila en blanco se cuente correctamente y la autodeteccion de
        separador del core opere sobre filas de ancho uniforme (ver D3/D4 de la
        spec del modulo).
        """
        header_skip = int(options.get("header_skip_rows") or 0)
        if header_skip <= 0 or not self.file:
            # Opcion inactiva o sin archivo: comportamiento nativo intacto (RB01).
            return super()._read_csv(options)

        original_file = self.file
        # bytes.splitlines corta solo en saltos de linea ASCII (\n/\r/\r\n); no
        # soporta encodings multi-byte alineados a otros boundaries (UTF-16/32).
        lines = original_file.splitlines(keepends=True)
        trimmed = b"".join(lines[header_skip:])
        if not trimmed:
            # El recorte dejo el archivo vacio (N >= cantidad de lineas): se
            # normaliza a (0, []) para que el usuario vea el mensaje nativo
            # "Import file has no content or is corrupt" en vez de un error de
            # unpack (super()._read_csv devolveria () al recibir un archivo
            # vacio, ver base_import.py:542-543).
            return 0, []

        # Swap temporal de self.file (registro transient, costo despreciable) y
        # restauracion garantizada en finally: el mismo wizard se reusa en mas
        # de una llamada dentro del flujo (parse_preview y _convert_import_data).
        self.file = trimmed
        try:
            res = super()._read_csv(options)
        finally:
            self.file = original_file
        return res
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
