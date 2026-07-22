# Spec de modulo: base_import_ux

| Campo | Valor |
|-------|-------|
| **Modulo** | `base_import_ux` |
| **Version** | `1.0.0` (== `version` del `__manifest__.py`, formato `x.x.x`) |
| **Serie Odoo** | `19` (informativa — serie de `ODOO_VERSION`, no es la version de la spec) |
| **Estado** | `verified` |
| **Actualizado** | `2026-07-22` |

## Objetivo

Mejorar la experiencia del asistente de importacion nativo de Odoo (`base_import`) para que los
extractos de cuenta de **Mercado Pago** (CSV crudo) puedan importarse como extracto bancario **sin
editar el archivo a mano**. Agrega dos ajustes de UX sobre el wizard de import:

1. **Filas de cabecera a saltear** (`header_skip_rows`): opcion generica del panel de import que
   descarta las primeras N filas *crudas* del archivo CSV antes de parsear, para archivos que traen
   filas de resumen/metadata antes del encabezado real (caso MP: 3 filas antes del header).
2. **Default de formato de fecha `DD-MM-YYYY`** solo en el flujo de importacion de extractos
   bancarios, para evitar que la autodeteccion de Odoo invierta fechas ambiguas (`02-01-2026`
   interpretado como MM-DD-YYYY).

El modulo no crea modelos ni tablas nuevas: extiende el modelo transient `base_import.import` (un
override Python) y parchea la clase OWL `BaseImportModel` del asistente (un patch JS sobre `init` y
`updateData` + un patch de template).

## Decisiones vigentes

> Decisiones de diseño que rigen HOY. Lo marcado `[ASUNCION]` se asumio con criterio conservador
> (sin respuesta explicita del usuario) y queda auditable.

| # | Decision | Valor vigente |
|---|----------|---------------|
| D1 | ¿Como se expone la opcion "filas a saltear"? | Como **opcion del wizard** (`header_skip_rows`, clave de `options`), NO como campo ORM ni configuracion en `res.config`. Tipo entero, default `0`. |
| D2 | Semantica de `header_skip_rows` | "Cantidad de filas del **archivo tal como lo ve el usuario** (incluida la fila en blanco) antes del encabezado real". Para MP el usuario carga **3**. |
| D3 | ¿Donde se recorta para respetar esa semantica? (trampa: filtro de filas vacias) | El recorte se hace sobre las **lineas crudas del archivo (bytes) ANTES de parsear**, en un override de `_read_csv` que quita las primeras N lineas y delega en `super()`. NO se recorta post-parseo (el core filtra las filas vacias en el parseo — recortar despues comeria la fila en blanco y correria el header un lugar, off-by-one). |
| D4 | Autodeteccion de separador con filas de resumen de MP (4 col vs 5 col) | Se sanea sola: al recortar las lineas de resumen en crudo antes de `super()._read_csv`, la deteccion de separador del core corre solo sobre filas de ancho uniforme. Igual se documenta que para archivos exoticos conviene fijar el separador a mano. |
| D5 | Alcance multi-formato (csv/xlsx/xls/ods) | **Solo CSV**. El recorte crudo se implementa unicamente en `_read_csv`. Para xlsx/xls/ods el recorte de filas queda **fuera de alcance** (ver NO incluye); si el usuario setea `header_skip_rows > 0` sobre un archivo no-CSV, es **no-op** (comportamiento nativo). Justificado en Notas de implementacion (minimal footprint). |
| D6 | Robustez del recorte crudo sobre bytes (trampa: encoding se resuelve dentro de `_read_csv`) | Se usa `bytes.splitlines(keepends=True)` sobre `self.file` (bytes) y se re-unen las lineas restantes; `bytes.splitlines` corta solo en `\n`/`\r`/`\r\n` (ASCII), no en boundaries unicode. `[ASUNCION]` Las filas del tope de un CSV real no traen saltos de linea embebidos entre comillas — asumible para el caso MP y anotado. El recorte asume ademas un encoding de un byte / compatible ASCII-UTF-8 (utf-8, latin1, windows-1252, etc.): **UTF-16/UTF-32 NO estan soportados** por este override, porque `splitlines` sobre esos bytes desalinearia los code units (los saltos de linea no caen en boundaries de un byte). Para esos encodings el usuario debe editar el archivo a mano o convertirlo antes de importar. |
| D7 | Feature 2 (default de fecha) — alcance | Solo el flujo de **extractos bancarios** (wizard abierto desde "Importar transacciones" de un diario; el subclase JS setea `bank_stmt_import`). Los demas imports (productos, partners, etc.) conservan la autodeteccion nativa. |
| D8 | Feature 2 — valor y editabilidad | Se prefija `date_format = "DD-MM-YYYY"` (formato humano; el core lo convierte a `%d-%m-%Y`). Queda **editable** en el panel; si los datos no matchean, la heuristica nativa del core sigue como fallback (el core prueba el patron del usuario primero y, si no matchea todo el preview, cae a `DATE_PATTERNS`). |
| D9 | Punto de inyeccion JS de `header_skip_rows` (trampa: `init()` del subclase de extractos NO llama `super`) | Se parchea **solo `BaseImportModel.prototype`** (un unico archivo JS). La subclase `BankStatementCSVImportModel` **no se exporta** desde enterprise — solo su factory `useBankStatementCSVImportModel` —, asi que no se puede parchear directo. La opcion se registra en dos puntos del mismo prototipo: (a) en `init()` (cubre el flujo generico) y (b) en `updateData()` **register-if-missing** (idempotente) — este segundo punto cubre el flujo de extractos, cuyo `init()` no llama `super` pero cuyo `updateData()` es **heredado sin override** (el action de extractos hereda de `ImportAction` y llama `this.model.updateData()`). NO se usa `_getCSVFormattingOptions()` porque corre en el constructor, antes de que `bank_stmt_import` exista (Feature 2 lo necesita). |
| D10 | Punto de inyeccion JS de Feature 2 | Se defaultea `date_format` dentro del patch de `BaseImportModel.updateData()` (ahi ya corre el flujo de extractos con `bank_stmt_import` seteado), **antes** de delegar en `super.updateData(...)`: si `this.importOptionsValues.bank_stmt_import?.value === true`, la opcion `date_format` existe con valor vacio y aun **no se prefijo en esta instancia** (flag one-shot `this._dmyPrefilled`), setear `date_format.value = "DD-MM-YYYY"`. El one-shot evita re-forzar el valor si el server/usuario lo cambia despues (`_onLoadSuccess` reescribe el estado con la respuesta del server). |
| D11 | Visibilidad de `header_skip_rows` en el panel | Input numerico junto al checkbox "Use first row as header", visible para imports de **cualquier modelo** cuando el archivo es **CSV** (`t-if` sobre extension `.csv`). Se gatea a CSV porque para otros formatos es no-op (D5). |
| D12 | ¿Se toca el import defectuoso de staging / mapeos por banco tipo OCA? | No. Ver NO incluye. |

## Alcance

### Incluye
- Opcion `header_skip_rows` (entero, default 0) en el panel del asistente de import, generica por
  modelo, que descarta las primeras N filas crudas de un **CSV** antes de parsear.
- Override Python de `base_import.import._read_csv` que hace el recorte crudo (bytes) y delega en
  `super()`.
- Registro de la opcion en el estado del cliente (patch de `init()` + `updateData()` de
  `BaseImportModel`) con `reloadParse: true` (re-parsea el preview al cambiar).
- Patch del template del sidepanel para mostrar el input numerico junto al checkbox de header.
- Default de `date_format = "DD-MM-YYYY"` (editable, one-shot) SOLO en el flujo de extractos
  bancarios CSV, inyectado en el mismo patch de `updateData()`.
- Documentacion del modulo (`README.md` + `static/description/index.html`) y fila en el README raiz
  del repo.

### NO incluye
- Recorte de filas para formatos **xlsx / xls / ods** (solo CSV — D5). Sobre esos formatos la opcion
  es no-op.
- **Mapeos por banco / plantillas por entidad** (estilo modulos OCA de bank statement import). No se
  crea configuracion por banco ni parsers dedicados por formato de extracto.
- **Campos ORM nuevos** ni configuracion en `res.config.settings`. La opcion vive como clave de
  `options` del wizard, no persiste.
- Corregir/retocar el import **defectuoso ya cargado en staging** (fuera de alcance de este modulo).
- Cambiar la autodeteccion de fecha de **otros imports** (productos, partners, etc.): siguen con la
  heuristica nativa (D7).
- Modificar core/enterprise: todo es via `_inherit` (Python) y `patch()` + `t-inherit` (OWL).

## Modelos

### Nuevos

No aplica. El modulo no define modelos nuevos (no crea tablas ni `_name`).

### Extendidos

| Modelo | _inherit | Que se agrega |
|--------|----------|--------------|
| `base_import.import` | `base_import.import` (TransientModel del core) | Override de `_read_csv(self, options)` para recortar las primeras `header_skip_rows` lineas crudas del CSV antes de delegar en `super()`. |

> Ademas se parchea 1 clase **OWL** (`BaseImportModel`, no un modelo Odoo) y 1 template — ver
> seccion "Assets y JS (OWL)".

## Campos

No aplica. `header_skip_rows` **no es un campo ORM**: es una clave del diccionario `options` del
asistente (opcion de cliente que el getter `importOptions` reenvia al servidor en la llamada RPC de
`parse_preview` / `execute_import`, y que el override de `_read_csv` lee via `options.get(...)`). No
persiste en base de datos y no requiere columna ni default a nivel modelo.

## Metodos

### `BaseImport._read_csv(self, options)` (override)

- **Modelo**: `base_import.import` (`_inherit`).
- **Proposito**: recortar las primeras N filas crudas del CSV (segun `options['header_skip_rows']`)
  **antes** de que el parser nativo decodifique, autodetecte separador y filtre filas vacias.
- **Decoradores**: ninguno (metodo de instancia; opera sobre `self.file`).
- **Logica**:
  1. `header_skip = int(options.get('header_skip_rows') or 0)`.
  2. Si `header_skip <= 0` o `not self.file` → `return super()._read_csv(options)` (comportamiento
     nativo intacto).
  3. `original = self.file`; `lines = original.splitlines(keepends=True)` (bytes, corte ASCII).
  4. `trimmed = b"".join(lines[header_skip:])` (descarta las primeras `header_skip` lineas,
     incluida la fila en blanco si esta entre ellas — semantica D2).
  5. Si `not trimmed` (el recorte dejo el archivo vacio, `header_skip >=` cantidad de lineas) →
     `return 0, []` **sin llamar a `super()`**. Esto normaliza el caso borde: `super()._read_csv`
     devuelve `()` (tupla vacia) cuando `self.file` es vacio/falsy
     (`/home/leandro/projects/nexit/19.0/odoo/addons/base_import/models/base_import.py:L542`), y ese
     `()` rompe el unpack `file_length, data_rows = self._read_file(options)` de `parse_preview`
     (`/home/leandro/projects/nexit/19.0/odoo/addons/base_import/models/base_import.py:L1022`) con un
     `ValueError` crudo. Devolver `(0, [])` en cambio hace que
     `parse_preview` vea `file_length <= 0` y muestre el mensaje nativo amable
     `"Import file has no content or is corrupt"` (CA08).
  6. Setear temporalmente `self.file = trimmed`, ejecutar `res = super()._read_csv(options)` dentro
     de `try`, y **restaurar** `self.file = original` en `finally` (idempotente entre las dos
     llamadas del flujo: `parse_preview` y `_convert_import_data`).
  7. `return res`.
- **Retorna**: `(len(content), content)` — misma firma que el core (`content` = lista de filas ya
  parseadas, sin las N filas recortadas); `(0, [])` en el caso borde de recorte vacio (paso 5).
- **Errores**: delega en `super()` (p. ej. `ImportValidationError` por encoding/quoting invalido); no
  agrega excepciones propias.
- **Nota**: `self.file` es un `TransientModel` (registro efimero); el set/restore es barato y no deja
  drift. El recorte crudo antes de `super()` resuelve las trampas D3 (filtro de filas vacias) y D4
  (autodeteccion de separador con anchos disparejos).

## Assets y JS (OWL)

> Feature 1 y Feature 2 se resuelven en el cliente con `patch()` de `@web/core/utils/patch` sobre los
> prototipos y `t-inherit ... t-inherit-mode="extension"` para el template (precedente en el core:
> `calendar/.../activity_patch.js` + `activity_list_popover_item_patch.xml`).

### `base_import_model_patch.js` — patch (unico) de `BaseImportModel.prototype`

> Se parchea **solo** `BaseImportModel.prototype` porque la subclase de extractos
> `BankStatementCSVImportModel` **no se exporta** desde enterprise (solo su factory
> `useBankStatementCSVImportModel`). Como `BankStatementCSVImportModel extends BaseImportModel` y
> **no overridea** `updateData` (solo `init` y `_onLoadSuccess`), el patch del prototipo base alcanza
> tambien al flujo de extractos.

- Define un helper `_registerHeaderSkipOption()` que agrega a `this.importOptionsValues` (solo si no
  existe ya):
  `header_skip_rows: { label: _t("Header rows to skip:"), help: _t(...), type: "input", value: 0, reloadParse: true }`.
- Parchea `init()`: `const res = await super.init(...arguments); this._registerHeaderSkipOption(); return res;`
  → registra la opcion en el **flujo generico** (cualquier modelo). `reloadParse: true` hace que
  cambiar el valor re-dispare `parse_preview` (via `updateData`).
- Parchea `updateData(fileChanged)`: **antes** de delegar en `super.updateData(...arguments)`:
  1. `this._registerHeaderSkipOption();` → **register-if-missing** idempotente; cubre el flujo de
     **extractos**, cuyo `init()` no llama `super` (D9) pero cuyo `updateData()` es heredado sin
     override y siempre corre antes de la llamada RPC `parse_preview`.
  2. Feature 2 (one-shot): si `this.importOptionsValues.bank_stmt_import?.value === true`,
     `this.importOptionsValues.date_format` existe con `value` vacio y `!this._dmyPrefilled`, entonces
     `this.importOptionsValues.date_format.value = "DD-MM-YYYY"` y `this._dmyPrefilled = true`.
     El flag one-shot evita re-forzar el valor si el server/usuario lo cambia despues (D8/D10).
  3. `return super.updateData(...arguments);`

### `import_data_sidepanel_patch.xml` — patch del template `ImportDataSidepanel`

- `t-inherit="ImportDataSidepanel"`, `t-inherit-mode="extension"`.
- Xpath: el template base tiene **3** `<CheckBox>` (el de "Use first row as header" en `L26`, y
  otros 2 dentro del bloque `env.debug` "Advanced" en `L134`/`L138`) — un xpath posicional o por
  texto seria ambiguo. Se ancla de forma **inequivoca** por el atributo `value` propio de ese
  checkbox: `expr="//CheckBox[@value='props.options.has_headers']"`, `position="after"` (unico en
  todo el template).
- Agrega un `<input type="number" min="0">` gateado con
  `t-if="fileExtension.toLowerCase() === '.csv'"` (sin el `min="0"`, un valor negativo como `-1`
  llegaria igual al servidor, donde es no-op pero deberia bloquearse en la UI), con `label` =
  "Header rows to skip:", `t-att-value="props.options.header_skip_rows"` y
  `t-on-change="(ev) => this.setOptionValue('header_skip_rows', ev.target.value)"` — reusa el
  metodo del componente `setOptionValue(name, value)` (`import_data_sidepanel.js:L36-38`, mismo
  patron que los inputs de "Formatting" del core), que convierte a Number del lado cliente.
  **Gotcha OWL**: las expresiones de template NO tienen acceso a globals de JS (`Math`, `Number` se
  compilan como lookups del contexto del componente → `undefined` → "TypeError: v4 is not a
  function" al disparar el evento); toda logica va en metodos del componente. Un valor negativo
  tipeado a mano pasa igual al server, donde el guard `header_skip <= 0 → super()` lo hace no-op
  (RB01).

### Declaracion en el manifest

`web.assets_backend` incluye los **2** archivos:
`base_import_ux/static/src/base_import_model_patch.js`,
`base_import_ux/static/src/import_data_sidepanel_patch.xml`.

## Vistas

No aplica. El asistente de import es OWL (componentes/templates JS), no vistas XML clasicas
(`ir.ui.view`). La superficie visible del modulo se describe en "Assets y JS (OWL)".

## Seguridad

No aplica. No hay modelos nuevos → no hay `ir.model.access.csv` ni `ir.rule` nuevos. El modelo
extendido `base_import.import` es transient y ya trae sus ACLs del core (`base_import`); el override
de `_read_csv` no cambia el modelo de permisos ni usa `sudo()`.

## Reglas de negocio

1. **RB01**: Si `header_skip_rows = 0` (o vacio/ausente), el comportamiento del import es **identico
   al nativo** (no se toca el archivo).
2. **RB02**: Si `header_skip_rows = N > 0` y el archivo es CSV, se descartan las **primeras N lineas
   crudas** del archivo (contando la fila en blanco) antes de parsear; la linea N+1 pasa a ser la
   primera fila (header real si `has_headers` esta activo).
3. **RB03**: El recorte se aplica en `_read_csv` (crudo, antes de decodificar/parsear), no post-parseo
   → la fila en blanco se cuenta correctamente y el separador se autodetecta sobre filas uniformes.
4. **RB04**: `header_skip_rows` es independiente de la opcion nativa `skip` (batch-resume): `skip`
   opera despues del header sobre las filas de datos; `header_skip_rows` opera sobre las lineas crudas
   antes del parseo. Se componen sin conflicto.
5. **RB05**: Para formatos no-CSV (xlsx/xls/ods), `header_skip_rows` es **no-op** (D5).
6. **RB06**: En el flujo de extractos bancarios CSV, el panel abre con `date_format = DD-MM-YYYY`
   prefijado y editable; el usuario puede borrarlo o cambiarlo.
7. **RB07**: El default de fecha **no se aplica** a imports que no sean de extractos bancarios.
8. **RB08**: Si los datos no matchean `DD-MM-YYYY`, el core cae a su heuristica nativa
   (`DATE_PATTERNS`) — el prefijado no rompe archivos con otro formato de fecha.

## Edge cases

- **N = 0 / vacio**: no se recorta nada; import nativo (RB01).
- **N > cantidad de lineas del archivo**: `lines[N:]` = `[]` → `trimmed = b""` → el override
  devuelve `(0, [])` directamente (sin llamar a `super()`, ver Metodos paso 5); preview vacio /
  "sin datos" (sin crash). Documentar que el usuario debe ajustar N.
- **Archivo solo-header** (`has_headers=True`, sin filas de datos tras el recorte): preview con header
  y sin filas; import 0 registros (comportamiento nativo, no error).
- **`has_headers` apagado + N > 0**: se recortan N lineas crudas igual; como no hay pop de header,
  todas las lineas restantes son datos.
- **Batch import con `skip` existente + `header_skip_rows` a la vez**: se componen (RB04); el recorte
  crudo ocurre antes; `skip` sigue aplicandose sobre las filas de datos resultantes.
- **Fila en blanco incluida en el conteo** (caso MP: filas 1,2 de resumen + fila 3 en blanco): N=3
  descarta las tres y deja el header real (fila 4) como primera fila — sin off-by-one (D3).
- **xlsx/xls/ods con N > 0**: no-op (RB05); el import se comporta como nativo.
- **CSV MP con anchos disparejos** (resumen 4 col, datos 5 col): tras recortar en crudo, la
  autodeteccion de separador del core opera sobre filas de 5 columnas uniformes → separador `;`
  detectado (o fijado a mano).

## Criterios de aceptacion

- [ ] **CA01**: CSV crudo de MP (3 filas antes del header, incluida 1 en blanco) + `header_skip_rows = 3`
  + separador `;` → el preview muestra el encabezado real (`RELEASE_DATE;TRANSACTION_TYPE;REFERENCE_ID;TRANSACTION_NET_AMOUNT;PARTIAL_BALANCE`)
  y el import de las 47 lineas de datos succeeds con montos AR y fechas dd-mm correctas.
- [ ] **CA02**: `header_skip_rows = 0` (default) → comportamiento **identico al nativo** (ningun
  archivo se altera).
- [ ] **CA03**: El wizard de extractos bancarios abre con "Formato de fecha" = `DD-MM-YYYY` prefijado
  y editable.
- [ ] **CA04**: Los imports de **otros modelos** (productos, partners) NO cambian su deteccion de
  fecha (siguen con la autodeteccion nativa, sin prefijado).
- [ ] **CA05**: Con el default `DD-MM-YYYY`, un archivo cuyas fechas NO matchean ese patron sigue
  importando via la heuristica nativa del core (el prefijado no rompe esos archivos).
- [ ] **CA06**: `header_skip_rows` cuenta la **fila en blanco** como una de las N saltadas: con N=3
  sobre el CSV de MP, la primera fila resultante es el header real (fila 4), no la fila en blanco
  (sin off-by-one).
- [ ] **CA07**: La autodeteccion de separador **no se rompe** con las filas de resumen de MP (ancho
  distinto): tras el recorte crudo el preview parsea limpio.
- [ ] **CA08**: `header_skip_rows` >= cantidad de lineas del archivo → preview vacio / "sin datos",
  sin excepcion (el override devuelve `(0, [])` directamente, sin delegar en `super()` — ver
  Metodos, paso 5).
- [ ] **CA09**: El input `header_skip_rows` aparece en el panel del asistente para imports de
  **cualquier modelo** cuando el archivo es CSV, junto al checkbox "Use first row as header".
- [ ] **CA10**: Para un archivo **xlsx/ods** con `header_skip_rows > 0`, la opcion es no-op (import
  nativo) — el alcance CSV-only se respeta.

## Referencias al core

> Anclajes `path:L#` verificados por @researcher sobre el checkout de v19
> (`/home/leandro/projects/nexit/19.0`). Rutas absolutas porque en este workspace el core no vive
> bajo el root del enjambre.

| Que | Anclaje (`path:L#`) | Por que importa |
|-----|---------------------|-----------------|
| `_read_csv` (target del override) | `/home/leandro/projects/nexit/19.0/odoo/addons/base_import/models/base_import.py:L536` | Metodo a heredar; retorna `(len(content), content)`; NO es generator. |
| Filtro de filas vacias (trampa D3) | `/home/leandro/projects/nexit/19.0/odoo/addons/base_import/models/base_import.py:L595` | El core descarta filas vacias en el parseo → obliga a recortar en crudo antes. |
| Autodeteccion de separador (trampa D4) | `/home/leandro/projects/nexit/19.0/odoo/addons/base_import/models/base_import.py:L567` | Corre sobre todas las filas y exige ancho uniforme; se sanea recortando antes. |
| Dispatcher `_read_file` | `/home/leandro/projects/nexit/19.0/odoo/addons/base_import/models/base_import.py:L374` | Unico choke point comun; llama al handler por extension (`_read_csv`). |
| `parse_preview` (pop del header) | `/home/leandro/projects/nexit/19.0/odoo/addons/base_import/models/base_import.py:L1004` | `headers = preview.pop(0)` — fila 0 como header si `has_headers`. |
| `_convert_import_data` (`skip`) | `/home/leandro/projects/nexit/19.0/odoo/addons/base_import/models/base_import.py:L1127` | `skip` nativo aplica DESPUES del header; no reusar (RB04). |
| `_try_match_date_time` | `/home/leandro/projects/nexit/19.0/odoo/addons/base_import/models/base_import.py:L696` | Si el cliente manda `date_format`, se prueba PRIMERO; si no matchea, cae a `DATE_PATTERNS` (fallback, D8). |
| `_parse_date_from_data` | `/home/leandro/projects/nexit/19.0/odoo/addons/base_import/models/base_import.py:L1315` | Usa `options['date_format']` verbatim en el import real. |
| `importOptionsValues` (constructor) | `/home/leandro/projects/nexit/19.0/odoo/addons/base_import/static/src/import_model.js:L98` | Donde se declaran las opciones del cliente. |
| `importOptions` getter | `/home/leandro/projects/nexit/19.0/odoo/addons/base_import/static/src/import_model.js:L181` | Reenvia TODAS las claves de `importOptionsValues` al servidor → `header_skip_rows` llega a `options` sin plumbing. |
| `formattedImportOptions` | `/home/leandro/projects/nexit/19.0/odoo/addons/base_import/static/src/import_model.js:L167` | Convierte `date_format` humano → strftime (`DD-MM-YYYY` → `%d-%m-%Y`). |
| `_getCSVFormattingOptions` | `/home/leandro/projects/nexit/19.0/odoo/addons/base_import/static/src/import_model.js:L778` | `date_format.value = ""` (default nativo). Corre en el constructor (antes de `init` → no sirve para Feature 2, D9). |
| `init()` de `BaseImportModel` | `/home/leandro/projects/nexit/19.0/odoo/addons/base_import/static/src/import_model.js:L236` | Punto de inyeccion de `header_skip_rows` en el flujo generico. |
| `updateData()` de `BaseImportModel` | `/home/leandro/projects/nexit/19.0/odoo/addons/base_import/static/src/import_model.js:L316` | Unico metodo que llama `parse_preview` (RPC en L322); heredado sin override por el flujo de extractos. Punto de inyeccion register-if-missing de `header_skip_rows` + default de Feature 2 (D9/D10). |
| Call-sites de `updateData()` en el action | `/home/leandro/projects/nexit/19.0/odoo/addons/base_import/static/src/import_action/import_action.js:L202` | `this.model.updateData()` (y otro en L219, `updateData(true)`); el `ImportAction` generico dispara el re-parse. |
| `BankStatementImportAction` hereda de `ImportAction` | `/home/leandro/projects/nexit/19.0/enterprise/account_bank_statement_import_csv/static/src/bank_statement_csv_import_action.js:L10` | `setup()` llama `super.setup()` → hereda los call-sites de `updateData` → el patch de `BaseImportModel.updateData` corre tambien en el flujo de extractos. |
| Checkbox "Use first row as header" | `/home/leandro/projects/nexit/19.0/odoo/addons/base_import/static/src/import_data_sidepanel/import_data_sidepanel.xml:L26` | Ancla del template patch (input al lado). |
| Componente `ImportDataSidepanel` | `/home/leandro/projects/nexit/19.0/odoo/addons/base_import/static/src/import_data_sidepanel/import_data_sidepanel.js:L6` | Componente cuyo template se extiende. |
| `BankStatementCSVImportModel` (clase NO exportada) | `/home/leandro/projects/nexit/19.0/enterprise/account_bank_statement_import_csv/static/src/bank_statement_csv_import_model.js:L5` | Subclase del flujo de extractos; su `init()` setea `bank_stmt_import` y NO llama `super`. La clase **no se exporta** (solo la factory `useBankStatementCSVImportModel`, L34) → por eso se patchea solo `BaseImportModel.prototype` (D9). |
| Action tag `import_bank_stmt` | `/home/leandro/projects/nexit/19.0/enterprise/account_bank_statement_import_csv/static/src/bank_statement_csv_import_action.js:L74` | Identifica el flujo de extractos en el cliente. |
| `_parse_import_data` (extractos) | `/home/leandro/projects/nexit/19.0/enterprise/account_bank_statement_import_csv/wizard/account_bank_statement_import_csv.py:L55` | Override del wizard de extractos; contexto donde aplica Feature 2. |
| `_import_bank_statement` (abre wizard) | `/home/leandro/projects/nexit/19.0/enterprise/account_bank_statement_import_csv/models/account_journal.py:L19` | Punto de entrada del flujo de extractos desde el diario. |
| Precedente patch de prototipo | `/home/leandro/projects/nexit/19.0/odoo/addons/calendar/static/src/activity/activity_patch.js:L1` | Patron real de `patch()` sobre prototipo OWL. |
| Precedente patch de template | `/home/leandro/projects/nexit/19.0/odoo/addons/calendar/static/src/activity/activity_list_popover_item_patch.xml:L1` | Patron real de `t-inherit ... t-inherit-mode="extension"`. |

## Documentacion afectada

| Archivo | Accion | Que reflejar |
|---------|--------|-------------|
| `base_import_ux/README.md` | crear | Objetivo, las 2 features, como usar `header_skip_rows` (caso MP = 3 + separador `;`), default de fecha en extractos, alcance CSV-only, gotchas. |
| `base_import_ux/static/description/index.html` | crear | Presentacion de las 2 features (screenshots del panel con el input y el default de fecha). |
| `odoo_customization_sunra/README.md` (raiz del repo) | actualizar | Agregar fila del modulo `base_import_ux` al indice del repo. |

## Plan del cambio en curso

> Build inicial del modulo (spec-first: hoy solo existe esta spec). @scaffold arma la estructura;
> @code-dev implementa Python + JS (un unico patch JS + un template patch) y cierra doc + version.
> El repo NO tiene `.swarm.conf` → sin tarea de tests por politica.

| Tarea | Descripcion | Depende de | Archivos | Cubre |
|-------|-------------|------------|----------|-------|
| **T01** | Scaffold del modulo estilo Sunra (`author="Sunra"`, `license="LGPL-3"`, `version="1.0.0"`, `depends=["base_import","account_bank_statement_import_csv"]`, `category="Custom"`). Estructura de carpetas, `__init__` de raiz y `models/`, esqueleto de `static/description/`. | — | `__manifest__.py`, `__init__.py`, `models/__init__.py`, `static/description/` | — (infra) |
| **T02** | Override `_read_csv` en `base_import.import`: recorte crudo de N lineas (bytes, `splitlines(keepends=True)`) + swap/restore de `self.file` + delegacion en `super()`. | T01 | `models/base_import.py`, `models/__init__.py` | CA01, CA02, CA06, CA07, CA08, CA10 |
| **T03** | Patch JS (unico) de `BaseImportModel`: helper `_registerHeaderSkipOption()` + patch de `init()` (registro en flujo generico) + patch de `updateData()` (register-if-missing para extractos + default `date_format="DD-MM-YYYY"` one-shot gateado por `bank_stmt_import`). | T01 | `static/src/base_import_model_patch.js` | CA01, CA02, CA03, CA04, CA05, CA09 |
| **T04** | Patch de template del sidepanel: input numerico `header_skip_rows` junto al checkbox "Use first row as header", gateado a `.csv`. | T03 | `static/src/import_data_sidepanel_patch.xml` | CA09 |
| **T05** | Declarar los **2** assets en `web.assets_backend` del manifest y confirmar `depends`. | T02, T03, T04 | `__manifest__.py` | CA01, CA03, CA09 |
| **T06** | Doc (`README.md` del modulo + `static/description/index.html` + fila en el README raiz del repo) + fijar `version="1.0.0"` en el manifest == `Version` de esta spec + estado spec → `implemented`. | T01, T02, T03, T04, T05 | `README.md`, `static/description/index.html`, `../README.md`, `__manifest__.py`, `specs/base_import_ux.md` | — (doc + version sync) |

## Notas de implementacion

- **Multi-formato (D5, minimal footprint)**: el caso de uso real es CSV; xlsx/xls/ods no tienen el
  problema de "filas de resumen + fila en blanco antes del header" de MP y traen su propia semantica
  de hojas/encabezado. Implementar recorte por formato seria sobre-construir. Se opta por CSV-only:
  un unico override de `_read_csv`. La opcion sigue visible (generica) pero es no-op para no-CSV
  (y el template la gatea a `.csv` para no confundir — D11).
- **Recorte crudo vs post-parseo (D3)**: el core filtra filas vacias en `_read_csv` (L595). Si se
  recortara despues del parseo, la fila 3 en blanco de MP ya no existiria y N=3 comeria el header
  real (off-by-one respecto de lo que ve el usuario). Por eso el recorte va sobre bytes antes de
  `super()`, lo que ademas sanea la autodeteccion de separador (D4).
- **Por que `updateData` y no un patch del subclase (D9)**: la subclase de extractos
  `BankStatementCSVImportModel` **no se exporta** desde enterprise (solo su factory), por lo que no se
  puede parchear directo — se descarta el patch de `bank_statement_csv_import_model.js`. Su `init()`
  ademas no llama `super` (saltea el `create`/`get_import_templates` del base), asi que un patch de
  `init()` del prototipo base no cubriria el flujo de extractos. La salida es parchear un unico punto
  compartido y siempre-corrido: `BaseImportModel.updateData()` (heredado sin override por el flujo de
  extractos, y unico call-site de `parse_preview`). Ahi se hace el **register-if-missing** de
  `header_skip_rows` (idempotente) y el default de Feature 2. Se descarto inyectar en
  `_getCSVFormattingOptions()` porque corre en el constructor, antes de que `bank_stmt_import` este
  seteado (Feature 2 lo necesita).
- **Por que el one-shot de Feature 2 (D10)**: `updateData()` corre en cada re-parse y su
  `_onLoadSuccess` reescribe el estado con la respuesta del server (incluido `date_format`). Sin el
  flag `this._dmyPrefilled`, el patch re-forzaria `DD-MM-YYYY` en cada re-parse y pisaria un cambio
  posterior del usuario/server. El flag lo prefija una sola vez por instancia (cuando aun esta vacio),
  dejandolo editable despues.
- **`self.file` es transient**: el swap/restore escribe bytes en un registro efimero; costo
  despreciable y sin drift gracias al `finally`. Alternativa considerada (reimplementar el parseo sin
  `super()`) descartada por duplicar la deteccion de separador/encoding del core.
- **`depends` (D7 / Feature 2)**: se mantiene `["base_import", "account_bank_statement_import_csv"]`.
  Aunque el patch JS **ya no importa** codigo de enterprise (se patchea solo `BaseImportModel` de
  `base_import`), CA03 requiere que el flujo de extractos exista: el gate `bank_stmt_import?.value`
  solo es `true` porque ese modulo lo setea. Sin la dependencia, Feature 2 seria codigo muerto.
- **Version / manifest**: el modulo aun no tiene `__manifest__.py` (spec-first). @scaffold lo crea en
  T01 con `version="1.0.0"`; @code-dev lo confirma en T06 == `Version` de esta spec.
