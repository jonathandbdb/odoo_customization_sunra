# base_import_ux

Mejoras de UX sobre el asistente de importación nativo de Odoo (`base_import`), pensadas para poder
importar el **estado de cuenta CSV de Mercado Pago** como extracto bancario sin editar el archivo a
mano.

## Objetivo de negocio

El estado de cuenta que exporta Mercado Pago trae, antes del encabezado real, 3 filas de
resumen/metadata (título, valores totales y una fila en blanco). El asistente nativo de import no
tiene forma de descartar esas filas, así que hoy hay que abrir el CSV en un editor y borrarlas a
mano antes de poder importarlo como extracto bancario — un paso manual, repetitivo y propenso a
error cada vez que se concilia una cuenta MP.

`base_import_ux` agrega dos ajustes de UX al wizard de import **sin crear modelos ni pantallas
nuevas**:

1. **"Header rows to skip"** (`header_skip_rows`): un input numérico, junto al checkbox "Use first
   row as header", que descarta las primeras N líneas **crudas** del archivo antes de parsear.
2. **Formato de fecha `DD-MM-YYYY` prefijado** al importar transacciones de un diario (extractos
   bancarios), para evitar que la autodetección nativa interprete una fecha ambigua como
   `MM-DD-YYYY`.

## Alcance

### Incluye
- Opción `header_skip_rows` (entero, default `0`), visible en el panel del asistente para **cualquier
  modelo** cuando el archivo es **CSV**.
- Recorte crudo (bytes) de las N primeras líneas antes de que el core decodifique/parsee el archivo.
- Formato de fecha `DD-MM-YYYY` prefijado (editable) **solo** en el flujo de "Importar
  transacciones" de un diario.

### No incluye
- Recorte de filas para **xlsx / xls / ods**: en esos formatos la opción es **no-op** (se mantiene
  visible mientras el gate de UI se resuelve por extensión de archivo, pero no hace nada).
- Mapeos por banco o plantillas específicas por entidad financiera (no es un módulo de tipo OCA de
  bank statement import).
- Campos ORM nuevos ni configuración en `res.config.settings`: `header_skip_rows` es una clave de
  `options` del wizard, no persiste en base de datos.
- Corrección de imports ya cargados/defectuosos.
- Cambios en la autodetección de fecha de otros imports (productos, contactos, etc.): siguen con la
  heurística nativa.

## Cómo usar: receta para el extracto CSV de Mercado Pago

1. Ir al diario del banco/billetera MP → **Importar transacciones** → seleccionar el CSV exportado
   por Mercado Pago tal cual (sin editar).
2. En el panel de opciones del asistente:
   - **Header rows to skip**: `3` (las 2 filas de resumen + la fila en blanco que las separa del
     encabezado real).
   - **Separador**: `;`
   - **Formato de miles**: `.`
   - **Formato de decimales**: `,`
   - **Formato de fecha**: ya abre prefijado en `DD-MM-YYYY` (dejarlo o ajustarlo si hace falta).
3. Mapear las columnas del preview a los campos del extracto:
   - `RELEASE_DATE` → **Fecha**
   - `TRANSACTION_TYPE` → **Etiqueta**
   - `TRANSACTION_NET_AMOUNT` → **Importe**
   - `PARTIAL_BALANCE` → **Cumulative Balance**
   - `REFERENCE_ID` → **Referencia**, o **no mapear**. **Nunca mapear a "ID externo"**: Mercado Pago
     repite el mismo `REFERENCE_ID` de forma legítima en más de una fila (no es único), y mapearlo a
     "ID externo" hace que las líneas se pisen entre sí durante el import.
4. Confirmar el import. El preview debe mostrar el encabezado real como primera fila (sin las 3
   filas de resumen) y las fechas se deben leer correctamente como día-mes-año.

## Cómo funciona (arquitectura)

El módulo no agrega modelos ni vistas XML clásicas: todo el ajuste vive en un override Python y dos
archivos de assets OWL que parchean el asistente de import existente.

- **Override Python — `_read_csv`** (`models/base_import.py`): extiende el modelo transient
  `base_import.import` (`_inherit`). Si `header_skip_rows > 0`, recorta las primeras N líneas
  **crudas** de `self.file` (bytes, `splitlines(keepends=True)`) y delega en `super()._read_csv()`
  con el archivo recortado, restaurando el archivo original en un `finally`. El recorte se hace
  **antes** de parsear porque el core filtra filas vacías y autodetecta el separador durante el
  parseo — recortar después comería la fila en blanco (off-by-one) y vería anchos de columna
  disparejos (filas de resumen de 4 columnas vs. filas de datos de 5). Si el recorte deja el
  archivo vacío (N ≥ cantidad de líneas), devuelve `(0, [])` para que el usuario vea el mensaje
  nativo "Import file has no content or is corrupt" en vez de un error de unpack.
- **Patch OWL — `base_import_model_patch.js`**: parchea `BaseImportModel.prototype` (no la subclase
  de extractos bancarios, que enterprise no exporta) en dos puntos del mismo prototipo:
  - `init()` registra la opción `header_skip_rows` para el flujo genérico (cualquier modelo).
  - `updateData()` la registra también de forma "register-if-missing" (cubre el flujo de extractos,
    cuyo `init()` no llama a `super`) y, si el import es de extractos bancarios
    (`bank_stmt_import === true`), prefija `date_format = "DD-MM-YYYY"` una sola vez (one-shot, no
    pisa un cambio posterior del usuario o del servidor).
- **Patch de template — `import_data_sidepanel_patch.xml`**: extiende `ImportDataSidepanel`
  (`t-inherit-mode="extension"`) agregando el input numérico justo después del checkbox "Use first
  row as header", visible solo cuando la extensión del archivo es `.csv`.

No hay modelos nuevos, vistas XML, menús, wizards, reportes ni scheduled actions. Tampoco hay
seguridad nueva: el modelo extendido (`base_import.import`) es transient y ya trae sus ACLs del
core; el override no usa `sudo()` ni cambia el modelo de permisos.

## Limitaciones conocidas

- Solo CSV: en xlsx/xls/ods `header_skip_rows` es no-op.
- Encodings soportados: compatibles con ASCII/UTF-8 de un byte (utf-8, latin1, windows-1252, etc.).
  **UTF-16/UTF-32 no están soportados** — `bytes.splitlines` corta en boundaries ASCII y desalinearía
  esos encodings multi-byte. Para esos casos hay que editar/convertir el archivo antes de importar.
- El recorte asume que las filas de metadata del tope no traen saltos de línea embebidos entre
  comillas.

## Dependencias

- `base_import` (core) — asistente de import genérico que se extiende.
- `account_bank_statement_import_csv` (Enterprise) — flujo de "Importar transacciones" de extractos
  bancarios sobre el que aplica el default de fecha (Feature 2).

## Mapa de archivos principales

```
base_import_ux/
    __manifest__.py                              # depends, assets (2 archivos en web.assets_backend)
    models/
        base_import.py                           # override _read_csv (base_import.import)
    static/src/
        base_import_model_patch.js                # patch de BaseImportModel (init + updateData)
        import_data_sidepanel_patch.xml            # patch del template del sidepanel
    specs/base_import_ux.md                       # spec SDD (fuente de verdad del módulo)
```

## Instalación / actualización (Docker)

Entorno: contenedor `nokey-odoo-1` (imagen `odoo_bo:19.0`), base de trabajo `nokey`.

> ⚠️ En este contenedor `odoo_runtime.sh install/upgrade` no funciona (la imagen no expone el
> binario `odoo` en el PATH): usar `odoo-bin` directo vía compose, con Odoo detenido.

```bash
cd /home/leandro/PersonalProject/Nokey && docker compose stop odoo

# Instalar el módulo por primera vez (-i) / actualizar tras un cambio de código (-u)
docker compose run --rm --no-deps odoo python3 /home/bo/odoo/odoo-bin \
    -c /etc/odoo/odoo.conf -d nokey -i base_import_ux --stop-after-init

docker compose up -d odoo
```

## Validación manual

1. Instalar/actualizar el módulo (ver arriba) y refrescar los assets del navegador.
2. **CA01/CA06/CA07 (recorte + fila en blanco + separador)**: importar el CSV crudo de Mercado Pago
   (sin editar) con `header_skip_rows = 3` y separador `;`. El preview debe mostrar el encabezado
   real (`RELEASE_DATE;TRANSACTION_TYPE;REFERENCE_ID;TRANSACTION_NET_AMOUNT;PARTIAL_BALANCE`) como
   primera fila, sin las filas de resumen ni la fila en blanco.
3. **CA02 (default = 0)**: importar cualquier CSV normal con `header_skip_rows = 0` (o sin tocar la
   opción) y verificar que el comportamiento es idéntico al nativo.
4. **CA03/CA04 (fecha en extractos, no en otros imports)**: abrir "Importar transacciones" de un
   diario y verificar que "Formato de fecha" abre en `DD-MM-YYYY`; luego abrir un import de
   productos o contactos y verificar que el formato de fecha **no** viene prefijado.
5. **CA08 (edge case)**: setear `header_skip_rows` mayor a la cantidad de líneas del archivo y
   verificar que el preview queda vacío con el mensaje nativo, sin traza de error.
6. **CA09/CA10 (visibilidad y no-op)**: confirmar que el input aparece junto al checkbox de header
   para un CSV de cualquier modelo, y que para un archivo xlsx/ods la opción no tiene efecto.

## Notas de mantenimiento

- El módulo es **SDD**: `specs/base_import_ux.md` es la fuente de verdad de decisiones (D1-D12),
  reglas de negocio (RB01-RB08) y anclajes al core. Cualquier cambio, por chico que sea, debe
  reflejarse ahí en sitio y mantener el `version` del manifest sincronizado con la `Version` de la
  spec.
- El patch JS depende de que `BankStatementCSVImportModel` (enterprise) siga sin overridear
  `updateData()` y sin exportar su clase — si `account_bank_statement_import_csv` cambia esa
  estructura en una futura versión de Odoo, hay que revisar el punto de inyección (ver D9/D10 de la
  spec).
- Si en el futuro se necesita soportar el recorte también en xlsx/ods, es un cambio de alcance (hoy
  explícitamente fuera — ver "No incluye") que debería pasar primero por la spec.

## Licencia y autoría

- **Autor**: Sunra — https://github.com/sunraargsh
- **Licencia**: LGPL-3
