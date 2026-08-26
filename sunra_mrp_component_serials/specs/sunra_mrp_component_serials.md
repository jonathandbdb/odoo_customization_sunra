# Spec de modulo: sunra_mrp_component_serials

| Campo | Valor |
|-------|-------|
| **Modulo** | `sunra_mrp_component_serials` |
| **Version** | `1.0.0` (== `version` del `__manifest__.py`, formato `x.x.x`) |
| **Serie Odoo** | `19` (informativa) |
| **Estado** | `verified` |
| **Actualizado** | `2026-08-25` |

## Objetivo

Sunra no compra bicicletas armadas: compra **kits en caja**. Cada kit trae el numero de serie del
**chasis** —que es el numero de serie del producto— mas el numero de **motor**, el/los numero(s) de
**faja** de la(s) bateria(s) y el numero de **controlador**. Hoy esos numeros se transcriben a mano
al remito y a la factura, y se equivocan; el numero de faja es la evidencia anti-fraude de garantia
(identifica que bateria se entrego con que bicicleta).

Este modulo hace dos cosas: (1) da de alta un **padron de piezas** y las **monta** contra la serie
del chasis, con la garantia estructural de que una pieza no puede estar en dos chasis a la vez; y
(2) amolda el circuito a la **fabricacion estandar de Odoo** (la OF descuenta un kit y suma una
bicicleta armada, **trasladando** las piezas del lote del kit al de la bici) para que los numeros
salgan **solos** en remito y factura, sin intervencion manual.

## Decisiones vigentes

> Decisiones de diseño que rigen HOY. Las marcadas `[ASUNCION]` se tomaron sin respuesta explicita
> del usuario, con criterio conservador, y quedan auditables.

| # | Decision | Valor vigente |
|---|----------|---------------|
| D1 | ¿Motor, bateria y controlador son productos de inventario? | **No**: se registran contra la serie del chasis. El kit viene cerrado en una caja; serializar los componentes obligaria a recepciones fantasma. |
| D2 | ¿BoM con la bateria como producto serializado (propuesta de Luis)? | **Descartada por ahora**. Es el camino de escalada si algun dia compran baterias sueltas. |
| D3 | ¿Como se modela el padron de piezas? | **UN** modelo `sunra.bike.component` con `component_type` (motor/battery/controller). NO tres modelos gemelos ni campos Char. Unicidad por `(component_type, name)`. |
| D4 | ¿Donde vive la asignacion pieza→chasis? | En `sunra.bike.component.lot_id` (M2o a `stock.lot`) como **unico origen de verdad** → una pieza en dos chasis es imposible por construccion. **No hace falta constraint extra** para eso (la unicidad de motor/controlador por chasis si la exige D18/RB12, que es otra cosa). |
| D5 | Domain de seleccion de piezas | `[('component_type','=','<tipo>'), ('faulty','=',False), '|', ('lot_id','=',False), ('lot_id','=',id)]`. La rama `lot_id = id` NO es excepcion a la regla: solo re-ofrece la pieza al chasis que **ya la tiene** (sin ella el M2o queda sin opcion al reabrir la ficha). Otro chasis nunca la ve, y una pieza fallada no la ve **nadie** (D18). |
| D6 | ¿Filtrar el desplegable por stock disponible? | **Descartado.** Es viable (`_search_product_qty` soporta `[('product_qty','>',0)]` y ya acota a internas/transito de `env.companies`), pero exigiria que las baterias entren por recepcion propia → descomponer la compra de kits o duplicar la valuacion (el costo de la bateria ya esta en el del kit). |
| D7 | ¿La OF copia o traslada las piezas? | **Traslada** del lote del kit al lote de la bici. Copiar dejaria la pieza en dos lotes, rompiendo el domain de libres y la busqueda inversa. La historia vive en el chatter de la pieza. |
| D8 | ¿Se bloquea la asignacion despues de armar? | **No, nada readonly**: la asignacion se edita siempre. Bateria fallada = marcarla `faulty` (se libera sola, D18) + montar la nueva. El motivo va como comentario en el chatter, **sin campo propio**. |
| D9 | ¿Que numero de serie lleva la bicicleta armada? | **El mismo del kit** (mismo numero de chasis). La OF no genera numero nuevo. `_check_unique_lot` valida por (compañia, producto, nombre), asi que el mismo nombre convive como lote del kit y de la bici. |
| D10 | ¿Como se reasigna una pieza existente y libre? | **Desde la pieza** (abrir el componente y setear `lot_id`). `battery_ids` es One2many → "Agregar linea" crea un numero nuevo, que es el caso del 95% (la bateria llega en la caja del kit). |
| D11 | ¿La bici de dos baterias es otro producto? | `[ASUNCION]` **No**: es el MISMO producto con dos fajas cargadas. |
| D12 | ¿Como se cargan los numeros la primera vez? | `[ASUNCION]` **Carga manual** al recibir cada kit (quick-create desde el desplegable). No se construye importador: la planilla del proveedor todavia no llego. |
| D13 | ¿`sunra.bike.component` es multi-compañia? | `[ASUNCION]` **No lleva `company_id`**: el padron es global. Los numeros de serie fisicos son unicos en el mundo, asi que la unicidad global es lo conservador. Si aparece multi-compañia, se agrega `company_id` + `check_company` sobre `lot_id` (cambio menor, ver Notas). |
| D14 | ¿El modulo fuerza los grupos nativos de impresion de series? | `[ASUNCION]` **No.** `stock.group_lot_on_delivery_slip` y `stock_account.group_lot_on_invoice` son **prerequisito de configuracion**: sin ellos el core no imprime la tabla de series y nuestras columnas tampoco. Se documenta en el README en vez de tocar grupos de usuarios. |
| D15 | ¿Que pasa si la OF ya tiene otra serie en `lot_producing_ids`? | `[ASUNCION]` Se **reemplaza** por el lote del chasis (D9 manda: no hay numero nuevo) y el hecho se asienta con `message_post` en la OF. El lote huerfano no se borra. |
| D16 | ¿Como se imprimen las piezas en remito y factura? | `[ASUNCION]` **Tres columnas** (Motor / Batteries / Controller) a continuacion de la columna de serie que ya imprime el core. Varias fajas se listan separadas por coma en una sola celda. |
| D17 | ¿Como sabe el modulo que una OF es "de kit"? | `[ASUNCION]` Por un **opt-in explicito en la LdM**: `mrp.bom.sunra_pull_kit_components` (Boolean, default `False`). Sin el flag, el override de cierre no hace absolutamente nada → cero impacto sobre cualquier otra fabricacion de la base. Es la unica forma de exigir el guard de completitud (CA10) sin trabar OF ajenas. |
| D18 | ¿Marcar una pieza como fallada la libera del chasis? | **Si: `faulty = True` limpia `lot_id`** en el mismo acto. `lot_id` significa **una sola cosa** —"la pieza montada AHORA"— para que ninguna lectura futura tenga que acordarse de filtrar `faulty`. La historia no se pierde: el chatter de la pieza deja el rastro (`CHASIS-001 → vacio`) y de ahi se responde "¿de que chasis salio?". Consecuencia: una pieza fallada no se ofrece (D5), no se imprime, no cuenta para el guard de completitud y no se traslada. |
| D19 | Idioma | UI en **ingles** con `_()`, traduccion en `i18n/es_419.po` (mismo criterio que `helpdesk_service_appointment` y `website_sale_installation_appointment`). Incluye los encabezados **impresos** en remito y factura (Motor / Batteries / Controller), que el cliente ve en castellano. |
| D20 | ¿Cancelar la OF despues del traslado devuelve las piezas al lote del kit? | `[ASUNCION]` **No.** No se engancha `action_cancel`: las piezas quedan montadas en el lote de la bicicleta, que lleva **el mismo numero de chasis** que el del kit (D9), asi que el dato sigue siendo correcto de cara al cliente. Si hay que revertir, se hace a mano desde la pieza. Se documenta en el README. |

## Alcance

### Incluye
- Padron de piezas (`sunra.bike.component`) con motor, bateria y controlador, y su **montaje** contra la serie del chasis (`stock.lot`).
- **Traslado** de las piezas del lote del kit al lote de la bicicleta armada al procesar la Orden de Fabricacion (boton manual + automatico al cerrar).
- Reutilizacion del **mismo numero de chasis** para la bicicleta armada (sin numero nuevo).
- Impresion automatica de los numeros en **remito** y **factura**, tanto para la bicicleta armada como para el **kit vendido sin armar**.
- Registro del cambio de asignacion en el **chatter** de la pieza (de donde salio, a donde entro, cuando, quien).

### NO incluye
- **Prioridad "Critico"** en fabricacion: extender `PROCUREMENT_PRIORITIES` impacta `stock.move` y `stock.picking` de toda la base; el propio Luis lo relativizo.
- **Numeros en facturas importadas de Tango**: bloqueado, falta saber de que campo salen.
- **Registro de incidencias/reclamos a proveedor**: hoy no llevan ese proceso.
- **Stock real de baterias** (ver D6) ni recepcion desagregada de los componentes del kit.
- **Ordenes de trabajo / centros de trabajo**: arma una sola persona.
- **Importador de la planilla del proveedor** (ver D12).
- Cambios en la valuacion / costeo del kit o de la bicicleta.
- **Tests automatizados**: el repo no declara politica de tests (`.swarm.conf` ausente) y el usuario opto por **guia de pruebas manual + video** al cierre del proyecto.
- **Reversion automatica al cancelar la OF** (D20).

## Modelos

### Nuevos

| Modelo (`_name`) | `_description` | Hereda de |
|------------------|----------------|-----------|
| `sunra.bike.component` | Bike Component | `models.Model` + `_inherit = ['mail.thread']` |

Atributos: `_order = 'component_type, name'`, `_rec_names_search = ['name']`.

### Extendidos

| Modelo | `_inherit` | Que se agrega |
|--------|-----------|---------------|
| `stock.lot` | `stock.lot` | Piezas montadas en el chasis: `component_ids`, `battery_ids`, `motor_id`, `controller_id` + helper de reporte. Ya hereda `mail.thread` (chatter gratis). |
| `mrp.bom` | `mrp.bom` | Opt-in `sunra_pull_kit_components` (D17). |
| `mrp.production` | `mrp.production` | Traslado kit→bici: metodos + boton + override de `button_mark_done()` + `related` del opt-in para la visibilidad del boton. |
| `account.move` | `account.move` | Override de `_get_invoiced_lot_values()` para enriquecer la tabla de series de la factura. |

## Campos

| Modelo | Campo | Tipo | String | Requerido | Default | Restricciones / notas |
|--------|-------|------|--------|-----------|---------|----------------------|
| `sunra.bike.component` | `name` | Char | Serial Number | Si | - | `tracking=True`, `index=True`. Parte de la unicidad `(component_type, name)`. |
| `sunra.bike.component` | `component_type` | Selection `[('motor','Motor'),('battery','Battery'),('controller','Controller')]` | Type | Si | - | `tracking=True`. Se precarga por contexto (`default_component_type`) desde cada campo del chasis. |
| `sunra.bike.component` | `lot_id` | Many2one `stock.lot` | Assigned Chassis | No | - | `tracking=True`, `index=True`, `ondelete='set null'`. **Unico origen de verdad de la asignacion (D4)**. Vacio = pieza libre. Lo limpia `_onchange`/`write` cuando `faulty` pasa a `True` (D18). |
| `sunra.bike.component` | `faulty` | Boolean | Faulty | No | `False` | `tracking=True`. **Marcar fallada libera el chasis** (D18/RB09): la pieza deja de estar montada, no se ofrece, no se imprime y no cuenta para el guard de completitud. |
| `sunra.bike.component` | `display_name` | Char (compute) | - | - | - | `_compute_display_name`: `"<Tipo> / <name>"`. No almacenado. |
| `stock.lot` | `component_ids` | One2many (`sunra.bike.component`, `lot_id`) | Bike Components | No | - | Tecnico (todas las piezas montadas, sin filtrar por tipo). Es la dependencia de los computes y evita tres One2many gemelos. Sin `tracking` (lo cubren los tres campos de abajo). No se muestra en la vista. |
| `stock.lot` | `battery_ids` | One2many (`sunra.bike.component`, `lot_id`) | Batteries | No | - | `domain=[('component_type','=','battery')]`, `context={'default_component_type': 'battery'}`, `tracking=True`. Admite N fajas (D11). |
| `stock.lot` | `motor_id` | Many2one `sunra.bike.component` | Motor | No | - | `compute='_compute_motor_id'`, **`store=False`** (ver M2 en Notas), `inverse='_inverse_motor_id'`, `tracking=True`, `@api.depends('component_ids.component_type')`. Domain D5 + `context={'default_component_type': 'motor'}`. |
| `stock.lot` | `controller_id` | Many2one `sunra.bike.component` | Controller | No | - | Idem `motor_id` con `component_type='controller'`. |
| `mrp.bom` | `sunra_pull_kit_components` | Boolean | Pull Kit Component Serials | No | `False` | D17. Opt-in por LdM: habilita el traslado automatico y el guard de completitud. |
| `mrp.production` | `sunra_pull_kit_components` | Boolean (related) | Pull Kit Component Serials | No | - | `related='bom_id.sunra_pull_kit_components'`, `readonly=True`, sin store. **Existe solo para la visibilidad del boton**: un `invisible=` de vista NO atraviesa relaciones, asi que el campo tiene que estar en el modelo y en el arch. |

> **Nota v19**: `_sql_constraints` fue **eliminado** en Odoo 19 → la unicidad se declara como atributo
> de clase: `_component_type_name_uniq = models.Constraint('UNIQUE(component_type, name)', 'This
> serial number already exists for that component type.')` (patron del core en
> `/home/leandro/projects/nexit/19.0/odoo/addons/stock/models/stock_package_type.py:41`).

## Metodos

### `SunraBikeComponent._compute_display_name()`
- **Proposito**: mostrar tipo + numero en desplegables y busquedas.
- **Decoradores**: `@api.depends('name', 'component_type')`
- **Logica**: `rec.display_name = "%s / %s" % (label_del_selection, rec.name)`.
- **Retorna**: `None` (campo computado, no almacenado).

### `SunraBikeComponent.write()` (override) + `_onchange_faulty()`
- **Proposito**: materializar D18 — marcar fallada **libera** el chasis, en un solo acto del usuario.
- **Logica**:
  1. En `write`: si `vals.get('faulty')` es verdadero y no se esta escribiendo `lot_id` en el mismo `vals`, forzar `vals['lot_id'] = False`. Asi tambien queda cubierta la importacion y la escritura por codigo, no solo la UI.
  2. `@api.onchange('faulty')`: al tildar en el formulario, vaciar `lot_id` en pantalla para que el usuario vea el efecto antes de guardar.
- **Retorna**: lo que devuelva `super().write(vals)`.

### `SunraBikeComponent._check_faulty_not_assigned()`
- **Proposito**: hacer **estructural** el invariante de D18 — una pieza fallada nunca esta montada.
  Es la garantia sobre la que se apoyan RB08/RB09/CA08/CA10 (por eso ningun consumidor filtra
  `faulty`). El override de `write` y el `_onchange_faulty` son comodidad de UX; esto es la red.
- **Decoradores**: `@api.constrains("faulty", "lot_id")`
- **Logica**: si `faulty` y `lot_id` → `ValidationError`.
- **Por que hace falta ademas del override**: el override solo cubre `write`. Cierra dos agujeros
  reales: (a) `create()` — la lista embebida de baterias del chasis expone la columna `faulty`, y si
  el usuario agrega la linea y la tilda en el mismo guardado, el ORM crea la pieza con el `lot_id`
  del chasis padre; (b) `write({'faulty': True, 'lot_id': X})` en el mismo vals, por codigo o
  importacion. Hallazgo I1 del review de implementacion.
- **Retorna**: `None`
- **Errores**: `ValidationError`

### `SunraBikeComponent._check_single_motor_and_controller()`
- **Proposito**: un chasis no puede tener dos motores ni dos controladores (las baterias si son N, D11). El domain de la vista no alcanza: D10 reasigna **desde la pieza**, que no pasa por ese domain.
- **Decoradores**: `@api.constrains('lot_id', 'component_type')`
- **Logica**: para las piezas afectadas con `lot_id` y `component_type in ('motor', 'controller')`, contar las piezas de ese tipo montadas en el mismo lote; si hay mas de una → `ValidationError`.
- **Errores**: `ValidationError` — `_("Chassis %(chassis)s already has a %(type)s assigned.", ...)`.
- **Nota**: no contradice D4 (una pieza sigue teniendo un solo chasis) ni D8 (reasignar entre chasis sigue permitido).

### `StockLot._compute_motor_id()` / `StockLot._compute_controller_id()`
- **Proposito**: derivar el M2o desde las piezas montadas (unica columna de asignacion, D4).
- **Decoradores**: `@api.depends('component_ids.component_type')`
- **Logica**: `lot.motor_id = lot.component_ids.filtered(lambda c: c.component_type == 'motor')[:1]`.
  **Sin filtro de `faulty`**: por D18 una pieza fallada ya no tiene `lot_id`, asi que nunca esta en `component_ids`.
- **Store**: `False` (ver M2 en Notas de implementacion).
- **Retorna**: `None`

### `StockLot._inverse_motor_id()` / `StockLot._inverse_controller_id()`
- **Proposito**: escribir la asignacion en la pieza (y solo ahi).
- **Logica**: ambos delegan en `_sunra_inverse_component(component, component_type)` — la logica es
  identica salvo el tipo, asi que vive en un solo lugar.
- **Retorna**: `None`
- **Errores**: `ValidationError` si el componente elegido no es del tipo del campo.

### `StockLot._sunra_inverse_component(component, component_type)`
- **Proposito**: helper privado comun de los dos inverse anteriores (DRY). Unico punto donde se
  escribe la asignacion desde el lado del chasis.
- **Decoradores**: ninguno
- **Logica**:
  1. Validar el tipo de la pieza elegida; si no coincide → `ValidationError`.
  2. Liberar la anterior: las piezas de ese tipo montadas en el chasis y distintas de la elegida → `lot_id = False`.
  3. Montar la nueva: `component.lot_id = lot` (si hay).
- **Retorna**: `None`
- **Errores**: `ValidationError` si el componente elegido no es del tipo del campo.

### `StockLot._sunra_component_report_values()`
- **Proposito**: unica fuente de los textos que imprimen remito y factura (evita duplicar el join en dos QWeb).
- **Decoradores**: ninguno
- **Logica**: sobre `self.sudo()` (mismo criterio que el core, que hace `lot.sudo()` para que un usuario sin permisos de stock pueda imprimir) devuelve
  `{'motor_name': ..., 'battery_names': ', '.join(...), 'controller_name': ...}`, con `''` donde no hay pieza.
  **Sin filtro de `faulty`** (D18: la fallada no esta montada).
- **Retorna**: `dict` (recordset vacio → dict con los tres valores en `''`).

### `MrpProduction._sunra_get_kit_lot()`
- **Proposito**: identificar el lote del kit consumido por la OF.
- **Decoradores**: ninguno (`ensure_one()`)
- **Logica**: `self.move_raw_ids.move_line_ids.lot_id.filtered(lambda l: l.product_id.tracking == 'serial')`.
- **Retorna**: recordset `stock.lot` (0, 1 o N registros — la desambiguacion la hace el llamador).

### `MrpProduction._sunra_pull_kit_components(strict=False)`
- **Proposito**: **trasladar** (D7) las piezas del lote del kit al lote de la bicicleta, reutilizando el numero de chasis (D9).
- **Decoradores**: ninguno (opera sobre el recordset).
- **Logica** (por cada OF):
  1. Si `not production.bom_id.sunra_pull_kit_components` (D17): si `strict` → `UserError`; si no → **saltar** (cero impacto en OF ajenas).
  2. Si `production.product_id.tracking != 'serial'` → `UserError` (LdM marcada pero producto terminado sin numero de serie: configuracion invalida).
  3. `kit_lots = production._sunra_get_kit_lot()`; si `0` o `>1` → `UserError` indicando que no puede identificar el kit (con los nombres encontrados).
  4. Buscar el lote destino: `stock.lot` con `product_id == production.product_id`,
     `name == kit_lot.name` y **`company_id in (production.company_id, False)`**; si no existe,
     crearlo **sin `company_id` explicito** (lo computa el core, igual que un lote creado a mano).
     D9 — `_check_unique_lot` valida por compañia+producto+nombre, asi que el mismo nombre convive.
     ⚠️ El `in (..., False)` **no es defensivo, es necesario**: `stock.lot.company_id` es computado
     desde `product_id.company_id` (`/home/leandro/projects/nexit/19.0/odoo/addons/stock/models/stock_lot.py:56`) y en la practica
     queda en `False` (los productos no suelen restringirse por compañia). Con el filtro estricto no
     se encontraba un lote preexistente con ese chasis, se creaba un duplicado y reventaba el
     `_check_unique_lot` del core con un error que no menciona ni el kit ni la OF. Hallazgo I2 del
     review de implementacion, reproducido en la base local.
  5. **Guard de completitud (CA10)**: sobre la **union** de `component_ids` del lote del kit y del lote destino, exigir motor + al menos una bateria + controlador. Si falta alguna → `UserError` enumerando exactamente que falta. (Union ⇒ el metodo es **idempotente**: si ya se trasladaron, no vuelve a fallar. **Sin filtro de `faulty`**: por D18 una pieza fallada ya no esta en `component_ids`, asi que no puede tapar un faltante.)
  6. Si `production.lot_producing_ids` esta vacio o difiere del lote destino → `lot_producing_ids = [Command.set(finished_lot.ids)]` + `message_post` dejando rastro del reemplazo (D15).
  7. **Trasladar**: `kit_lot.component_ids.write({'lot_id': finished_lot.id})` — una sola escritura; el chatter de cada pieza registra origen y destino (CA07).
- **Mensajes**: todos en ingles con `_()` y placeholders `%(name)s` (nunca concatenacion) — D19.
- **Retorna**: `None`
- **Errores**: `UserError` en los casos 1 (solo `strict`), 2, 3 y 5.

### `MrpProduction.action_sunra_pull_kit_components()`
- **Proposito**: boton "Pull Kit Component Serials" del formulario de la OF.
- **Logica**: `self.ensure_one()` → `self._sunra_pull_kit_components(strict=True)`.
- **Retorna**: `None`

### `MrpProduction.button_mark_done()`
- **Proposito**: garantizar el traslado aunque el usuario no haya usado el boton.
- **Logica**: `self._sunra_pull_kit_components(strict=False)` **antes** de `return super().button_mark_done()`.
- **Por que antes**: el core genera la serie del producto terminado **solo** por dos caminos, y los dos ocurren dentro de `button_mark_done()`. Con una bici por OF (`product_uom_qty == 1`) `_auto_production_checks()` devuelve `True`
  (`/home/leandro/projects/nexit/19.0/odoo/addons/mrp/models/mrp_production.py:2393`), asi que **no aparece ningun asistente**: el numero lo crea **en silencio** `_set_quantities()`
  (`/home/leandro/projects/nexit/19.0/odoo/addons/mrp/models/mrp_production.py:2932`) llamando a `action_generate_serial()`, que hace `Command.create` de un lote nuevo
  (`/home/leandro/projects/nexit/19.0/odoo/addons/mrp/models/mrp_production.py:1610`). En el otro camino (OF no "auto") el core devuelve el asistente de serie. Seteando nosotros `lot_producing_ids` antes del `super()`, **las dos ramas quedan neutralizadas** y no aparece un numero nuevo (D9).
- **Retorna**: lo que devuelva `super()`.

### `AccountMove._get_invoiced_lot_values()`
- **Proposito**: agregar motor/fajas/controlador a la tabla de series de la factura.
- **Logica**:
  1. `res = super()`.
  2. Juntar los ids: `lot_ids = {v['lot_id'] for v in res if v.get('lot_id')}` y **browse de una sola vez**: `self.env['stock.lot'].browse(lot_ids).sudo()`, armando `values_by_lot = {lot.id: lot._sunra_component_report_values()}` (nada de `browse` + `sudo()` por fila).
  3. **Normalizar TODOS los dicts**: cada entrada de `res` recibe las tres claves; las que no tienen `lot_id` reciben `''`. Es obligatorio: `point_of_sale` agrega dicts con `pos_lot_id` y **sin** `lot_id` (`/home/leandro/projects/nexit/19.0/odoo/addons/point_of_sale/models/account_move.py:55`) y `sale_stock_renting` tambien extiende el metodo; si el QWeb indexara duro una clave ausente, la factura entera no se imprimiria.
  4. Cinturon y tiradores: ademas, el QWeb usa `.get('motor_name', '')` (idem las otras dos).
  **No se reimplementa el metodo** (el core devuelve `lot_id` explicitamente para esto).
- **Retorna**: `list[dict]` — los mismos dicts, todos con `motor_name`, `battery_names` y `controller_name`.
- **Errores**: ninguno.

## Vistas

> Convenciones que @code-dev debe respetar (v18/v19): las listas se declaran con `<list>` (**nunca**
> `<tree>`), `editable` solo acepta `top` o `bottom`, y las search views **no** llevan
> `<group expand="0" string="Group By">` (eliminado en v18+): los `<filter context="{'group_by': ...}">`
> van sueltos. Las vistas **heredadas** reusan el XML ID de la original (AGENTS.md § *Herencia de vistas*)
> y el `name` agrega `.inherit.sunra_mrp_component_serials`.

### `sunra_bike_component_view_list`
- **Columnas**: `name`, `component_type`, `lot_id`, `faulty`.
- **Decoration**: `decoration-danger="faulty"`.

### `sunra_bike_component_view_form`
- **Sheet**: titulo con `name`; grupo con `component_type`, `lot_id`, `faulty`.
- **Chatter**: `<chatter/>` (historial de asignaciones — CA07).

### `sunra_bike_component_view_search`
- **Busqueda**: `name`, `lot_id`.
- **Filtros**: `Free` (`lot_id = False`), `Assigned` (`lot_id != False`), `Faulty`.
- **Group by**: `component_type`, `lot_id` (filters sueltos, sin `<group>`).

### `sunra_bike_component_action` + `sunra_bike_component_menu`
- Accion `ir.actions.act_window` (`view_mode="list,form"`, name "Bike Components").
- Menu bajo Inventario → Productos (`parent="stock.menu_stock_inventory_control"`, `groups="stock.group_production_lot"`).

### `view_production_lot_form` (herencia de `stock.view_production_lot_form`)
- `name` = `stock.lot.view.form.inherit.sunra_mrp_component_serials`.
- **xpath** sobre `//group[@name='main_group']` `position="after"`: grupo `sunra_components` "Bike Components" con `motor_id`, `controller_id` y `battery_ids`.
- `motor_id` / `controller_id`: `domain="[('component_type','=','motor'), ('faulty','=',False), '|', ('lot_id','=',False), ('lot_id','=',id)]"` (D5) + `context="{'default_component_type': 'motor'}"` para el quick-create (D12).
- `battery_ids`: `<list editable="bottom" delete="0">` con `name` y `faulty` — sacar una bateria del chasis se hace desde la pieza (D10) o marcandola fallada (D18), asi no se borra del padron por error.

### `mrp_production_form_view` (herencia de `mrp.mrp_production_form_view`)
- `<field name="sunra_pull_kit_components" invisible="1"/>` en el `<header>` **antes** del boton (un `invisible=` no atraviesa relaciones: el campo tiene que estar en el arch).
- Boton `action_sunra_pull_kit_components`, string **"Pull Kit Component Serials"**, `type="object"`,
  `invisible="not sunra_pull_kit_components or state in ('done', 'cancel')"`.

### `mrp_bom_form_view` (herencia de `mrp.mrp_bom_form_view`)
- Campo `sunra_pull_kit_components` en la pestaña de opciones/miscelaneos de la LdM.

### Reportes (QWeb)
- **Factura** — herencia de `stock_account.stock_account_report_invoice_document`: `<th>` "Motor" / "Batteries" / "Controller" despues de la columna SN/LN del `thead` de `invoice_snln_table`, y las tres `<td>` correspondientes en el `t-foreach`, leidas con `snln_line.get('motor_name', '')` (idem las otras dos). Queda dentro del `t groups="stock_account.group_lot_on_invoice"` del core (D14).
- **Remito** — dos herencias:
  1. `stock.report_delivery_document`: tres `<th>` con `t-if="has_serial_number"` despues de `//th[@name='lot_serial']` (no se rompe la cadena `t-if`/`t-else` nativa porque las nuevas columnas llevan su propia condicion).
  2. `stock.stock_report_delivery_has_serial_move_line`: tres `<td>` con `t-if="has_serial_number"` despues de `<t name="move_line_lot">`, alimentadas por `move_line.lot_id._sunra_component_report_values()`.
  `has_serial_number` ya viene gateado por `groups="stock.group_lot_on_delivery_slip"` en el core (D14).

## Seguridad

| Modelo | Grupo | read | write | create | unlink |
|--------|-------|------|-------|--------|--------|
| `sunra.bike.component` | `stock.group_stock_user` | 1 | 1 | 1 | 0 |
| `sunra.bike.component` | `stock.group_stock_manager` | 1 | 1 | 1 | 1 |

### Grupos
- **No se crean grupos nuevos.** Se reutilizan los de Inventario.
- **Prerequisito de configuracion (D14)**: para que los numeros se impriman hay que tener activos
  `stock.group_lot_on_delivery_slip` ("Display Serial & Lot Number in Delivery Slips") y
  `stock_account.group_lot_on_invoice` ("Display Serial & Lot Number on Invoices"). El modulo **no**
  los fuerza; se documentan en el README.

### Record rules
- No aplica: el padron es global (D13), sin `company_id`.

### Acceso desde los reportes
- `_sunra_component_report_values()` lee con `sudo()` para que un usuario de Facturacion/Ventas sin
  permisos de Inventario pueda imprimir. Es el mismo criterio del core, que hace `lot.sudo()` con el
  comentario "access the lot as a superuser in order to avoid an error when a user prints an invoice
  without having the stock access" (`/home/leandro/projects/nexit/19.0/odoo/addons/sale_stock/models/account_move.py:98`).

## Reglas de negocio

1. **RB01**: Una pieza pertenece **a lo sumo a un chasis**. `sunra.bike.component.lot_id` es el unico lugar donde vive la asignacion (D4) → la duplicacion es imposible por construccion.
2. **RB02**: `(component_type, name)` es **unico**. Dar de alta dos veces el mismo numero de faja falla (y por eso una importacion que intente montar en otro chasis una faja ya existente tambien falla: crea un registro nuevo con un numero repetido).
3. **RB03**: El desplegable de motor/controlador solo ofrece piezas **libres, no falladas** y del tipo correcto, mas la que ya esta montada en ese mismo chasis (D5, D18).
4. **RB04**: La OF **traslada** las piezas del lote del kit al lote de la bici; nunca las copia (D7).
5. **RB05**: La bicicleta armada lleva el **mismo numero de chasis** que el kit; la OF no genera numero nuevo (D9, D15).
6. **RB06**: No se puede cerrar una OF cuya LdM tenga el opt-in (D17) si el chasis no reune **motor + al menos una bateria + controlador**; el error enumera lo que falta.
7. **RB07**: El historial de la asignacion vive en el **chatter de la pieza** (`lot_id` con `tracking=True`), que registra siempre de donde salio y a donde entro, venga el cambio de la ficha del chasis, de la pieza o del traslado de la OF. El chatter del **lote** registra ademas las ediciones hechas desde la ficha del chasis (`motor_id`, `controller_id`, `battery_ids` con `tracking=True`).
8. **RB08**: Remito y factura imprimen las piezas **montadas** en el lote de la linea, sea el lote de la bicicleta armada o el del kit vendido sin armar. No hace falta ningun filtro especial: por D18 una pieza fallada ya no tiene `lot_id`.
9. **RB09**: Marcar una pieza como `faulty` **la libera del chasis en el mismo acto** (D18). A partir de ahi: no se ofrece en ningun desplegable, no se imprime, no cuenta para el guard de completitud y no se traslada en la OF. El rastro de de que chasis salio queda en su chatter.
10. **RB10**: Sin los dos grupos nativos de impresion activos, el core no imprime la tabla de series y estas columnas tampoco (D14).
11. **RB11**: Sin el opt-in en la LdM, el modulo **no interviene** en el cierre de ninguna OF (D17).
12. **RB12**: Un chasis tiene **como maximo un motor y un controlador**; baterias, N (D11). Lo garantiza un `@api.constrains`, porque la reasignacion desde la pieza (D10) no pasa por el domain de la vista.

## Edge cases

- **OF que no es de kit** (LdM sin opt-in): `button_mark_done()` no hace nada distinto del core. Cero impacto sobre el resto de la fabricacion de la base.
- **OF de kit con mas de un componente serializado**: no se puede decidir cual es el kit → `UserError` con los lotes encontrados (tanto en el boton como al cerrar; la LdM esta marcada, asi que el caso es nuestro).
- **OF de kit sin ningun componente serializado**: `UserError` ("no encuentro el lote del kit").
- **LdM marcada con producto terminado sin numero de serie**: `UserError` de configuracion invalida.
- **Traslado ya hecho** (se apreto el boton y despues se cierra la OF): el guard evalua la **union** kit+bici, no falla, y el `write` no mueve nada → idempotente.
- **Traslado parcial / asistente en el medio**: si `button_mark_done()` devuelve un asistente (consumo o backorder), las piezas **ya viajaron** al lote de la bici y la transaccion commitea igual al devolver la accion. No es un problema: el metodo es idempotente y el lote destino lleva el mismo numero de chasis. Si despues la OF se **cancela**, las piezas **quedan** en el lote de la bicicleta (D20): no se revierten solas; revertir es manual, desde la pieza.
- **La OF ya tenia otra serie generada**: se reemplaza por la del chasis y se deja `message_post` (D15). El lote huerfano no se borra.
- **Chasis incompleto al cerrar**: `UserError` enumerando que falta (CA10) — es un **guard de completitud**, no un lock: el usuario carga la pieza y vuelve a cerrar.
- **Kit vendido sin armar**: el remito imprime las piezas del lote del kit (nunca se trasladaron) — CA09.
- **Bicicleta de dos baterias**: `battery_ids` acepta N; ambas fajas se imprimen separadas por coma (D11, D16).
- **Segundo motor/controlador en el mismo chasis** (tipicamente desde la pieza, que no pasa por el domain): `ValidationError` (RB12).
- **Pieza fallada que se vuelve a marcar como NO fallada**: queda **libre** (su `lot_id` ya se limpio al marcarla). **No vuelve sola a su chasis anterior**: hay que reasignarla a mano, desde la pieza o desde la ficha del chasis. El chatter permite reconstruir de donde salio.
- **Chasis sin piezas al imprimir**: las columnas salen vacias; no rompe el reporte.
- **Factura con lineas de Punto de Venta o de alquiler**: esos dicts no traen `lot_id` (POS trae `pos_lot_id`); el override los normaliza con `''` y el QWeb usa `.get()` → la factura imprime igual.
- **Usuario sin permisos de Inventario imprimiendo factura/remito**: resuelto con `sudo()` en el helper de reporte.
- **Borrar un lote**: `lot_id` de la pieza pasa a `False` (`ondelete='set null'`) → la pieza vuelve al padron como libre, no se pierde el numero.
- **Multi-compañia**: fuera de alcance por D13; si aparece, hay que agregar `company_id` + `check_company` (ver Notas de implementacion).
- **Reasignacion deliberada de una pieza montada** (D8): permitida; **traslada**, no duplica — el chasis anterior queda sin ella y el chatter de la pieza lo registra.

## Criterios de aceptacion

- [ ] **CA01**: Se recibe un kit con numero de chasis y se dan de alta, **desde su propia serie**, el motor, DOS baterias y el controlador.
- [ ] **CA02**: Se intenta asignar a otra bicicleta una bateria, un motor y un controlador ya montados en la primera: el desplegable **no los ofrece** (RB03) y forzarlo por importacion tambien **falla** (RB02: el numero repetido choca contra la unicidad). Una pieza nunca queda en dos chasis (RB01).
- [ ] **CA03**: Se intenta dar de alta dos veces el mismo numero de faja: el sistema lo **rechaza**.
- [ ] **CA04**: Al traer las piezas del kit (boton), la bicicleta queda con el **mismo numero de chasis** y con las cuatro piezas montadas.
- [ ] **CA05**: Al cerrar la orden, las piezas quedan montadas en la serie de la bicicleta y **ninguna figura en dos chasis a la vez** (el lote del kit queda sin piezas).
- [ ] **CA06**: Bateria fallada **antes** de armar: se marca fallada la vieja —con lo que **queda liberada del chasis sola**— y se monta la buena en la serie del kit; la bici se arma con la buena. La fallada no vuelve a aparecer en ningun desplegable.
- [ ] **CA07**: Bateria reemplazada **despues** de armada: se marca fallada la vieja (se libera del chasis) y se monta la nueva en la misma serie; el historial de la pieza muestra de que chasis salio, cuando y quien lo hizo.
- [ ] **CA08**: Se entrega y factura la bicicleta: remito y factura salen con chasis + motor + dos fajas + controlador —solo las piezas **montadas**, una fallada no se imprime—, sin intervencion manual.
- [ ] **CA09**: Se vende un kit **sin armar** y el remito sale igual de completo.
- [ ] **CA10**: Se intenta cerrar una OF con la serie del kit **sin piezas cargadas**: el sistema lo impide **indicando que falta**.

## Referencias al core

> Anclajes verificados sobre el checkout de v19 (core/enterprise en `/home/leandro/projects/nexit/19.0`,
> fuera del root del enjambre → rutas absolutas).

| Que | Anclaje (`path:L#`) | Por que importa |
|-----|---------------------|-----------------|
| `stock.lot` — modelo base a heredar | `/home/leandro/projects/nexit/19.0/odoo/addons/stock/models/stock_lot.py:25` | `_name = 'stock.lot'` — es el chasis. |
| `stock.lot` ya hereda `mail.thread` | `/home/leandro/projects/nexit/19.0/odoo/addons/stock/models/stock_lot.py:26` | Chatter del chasis gratis: no hay que agregar el mixin. |
| Unicidad de lote por (compañia, producto, nombre) | `/home/leandro/projects/nexit/19.0/odoo/addons/stock/models/stock_lot.py:104` | `_check_unique_lot` → habilita **D9**: el mismo nombre convive como lote del kit y de la bici (productos distintos). |
| Domain por stock disponible (descartado) | `/home/leandro/projects/nexit/19.0/odoo/addons/stock/models/stock_lot.py:237` | `_search_product_qty` soporta `[('product_qty','>',0)]` — viable pero descartado en **D6**. |
| Tracking nativo de x2many en el chatter | `/home/leandro/projects/nexit/19.0/odoo/addons/mail/models/mail_tracking_value.py:136` | Habilita `tracking=True` sobre `battery_ids` (RB07). |
| El tracking se resuelve sobre los campos **escritos** | `/home/leandro/projects/nexit/19.0/odoo/addons/mail/models/mail_thread.py:531` | `_track_get_fields().intersection(fields_iter)` y `_track_get_fields` (`:615`) **no** filtra por `store` → `motor_id`/`controller_id` se trackean aunque sean `store=False`, siempre que el cambio venga de un `write` (la edicion desde la ficha del chasis). |
| Patron v19 de constraint SQL | `/home/leandro/projects/nexit/19.0/odoo/addons/stock/models/stock_package_type.py:41` | `models.Constraint('unique(...)', msg)` — en v19 **no** existe `_sql_constraints`. |
| ⚠️ v19: `lot_producing_ids` es **Many2many** | `/home/leandro/projects/nexit/19.0/odoo/addons/mrp/models/mrp_production.py:120` | Breaking change vs v17/v18 (`lot_producing_id`): se escribe con `Command.set([...])` y se lee con `[:1]`. |
| Componentes consumidos de la OF | `/home/leandro/projects/nexit/19.0/odoo/addons/mrp/models/mrp_production.py:203` | `move_raw_ids` → de ahi sale el lote del kit (`.move_line_ids.lot_id`). |
| Hook de cierre de OF a overridear | `/home/leandro/projects/nexit/19.0/odoo/addons/mrp/models/mrp_production.py:2218` | `button_mark_done()` — el traslado va **antes** del `super()`. |
| Con una bici por OF **no** aparece asistente | `/home/leandro/projects/nexit/19.0/odoo/addons/mrp/models/mrp_production.py:2393` | `_auto_production_checks()` devuelve `True` si `product_uom_qty == 1` → el caso de Sunra va por la rama "auto". |
| …y el serial se crea **en silencio** | `/home/leandro/projects/nexit/19.0/odoo/addons/mrp/models/mrp_production.py:2932` | `_set_quantities()` llama a `action_generate_serial()` si no hay `lot_producing_ids`: sin nuestro traslado previo, la bici nace con un numero nuevo (viola D9). |
| Creacion del lote nuevo (rama serial) | `/home/leandro/projects/nexit/19.0/odoo/addons/mrp/models/mrp_production.py:1610` | `if self.product_qty == 1 and not self.lot_producing_ids: ... Command.create(...)` — exactamente lo que neutralizamos seteando el lote antes. |
| El lote producido viaja al movimiento terminado | `/home/leandro/projects/nexit/19.0/odoo/addons/mrp/models/mrp_production.py:1930` | `move.lot_ids = order.lot_producing_ids.ids` en `_post_inventory` → alcanza con setear `lot_producing_ids`. |
| Reusar el numero del kit no choca con el chequeo nativo | `/home/leandro/projects/nexit/19.0/odoo/addons/mrp/models/mrp_production.py:2783` | `_check_sn_uniqueness` compara **registros** de lote (y excluye los consumidos), no nombres → D9 es seguro. |
| BoM tipo `phantom` = Kit — **NO usar** | `/home/leandro/projects/nexit/19.0/odoo/addons/mrp/models/mrp_bom.py:29` | Una LdM `phantom` no genera OF: rompe todo el circuito. La LdM es `normal`. |
| Hook a overridear para la factura | `/home/leandro/projects/nexit/19.0/odoo/addons/sale_stock/models/account_move.py:31` | `_get_invoiced_lot_values()` — se hace `super()` y se enriquece; su base vacia esta en `/home/leandro/projects/nexit/19.0/odoo/addons/stock_account/models/account_move.py:175`. |
| El core YA devuelve `lot_id` en el dict **para esto** | `/home/leandro/projects/nexit/19.0/odoo/addons/sale_stock/models/account_move.py:111` | `'lot_id': lot.id`, precedido del comentario que dice que esta ahi para que las localizaciones hereden y agreguen campos (`:110`). |
| ⚠️ Hay dicts **sin** `lot_id` en la lista | `/home/leandro/projects/nexit/19.0/odoo/addons/point_of_sale/models/account_move.py:55` | POS agrega entradas con `pos_lot_id` y sin `lot_id` (y `enterprise/sale_stock_renting` tambien extiende el metodo) → hay que **normalizar las tres claves en todos los dicts** y usar `.get()` en el QWeb. |
| El core imprime con `sudo()` | `/home/leandro/projects/nexit/19.0/odoo/addons/sale_stock/models/account_move.py:98` | Justifica el `sudo()` del helper: un usuario sin permisos de stock tiene que poder imprimir. |
| Template de factura a heredar | `/home/leandro/projects/nexit/19.0/odoo/addons/stock_account/views/report_invoice.xml:3` | `stock_account_report_invoice_document`; la tabla es `invoice_snln_table` (`:8`). |
| Grupo que muestra series en la factura | `/home/leandro/projects/nexit/19.0/odoo/addons/stock_account/security/stock_account_security.xml:4` | `group_lot_on_invoice` — prerequisito de D14. |
| Template de remito (fila) a heredar | `/home/leandro/projects/nexit/19.0/odoo/addons/stock/report/report_deliveryslip.xml:232` | `stock_report_delivery_has_serial_move_line`; el xpath va sobre `<t name="move_line_lot">` (`:254`). |
| Encabezado de la tabla del remito | `/home/leandro/projects/nexit/19.0/odoo/addons/stock/report/report_deliveryslip.xml:120` | `<th name="lot_serial">` dentro de un `t-else` → las columnas nuevas llevan su propio `t-if="has_serial_number"`. |
| Grupo que muestra series en el remito | `/home/leandro/projects/nexit/19.0/odoo/addons/stock/security/stock_security.xml:42` | `group_lot_on_delivery_slip` — prerequisito de D14. |
| Prioridad Normal/Urgente (fuera de alcance) | `/home/leandro/projects/nexit/19.0/odoo/addons/stock/models/stock_move.py:15` | `PROCUREMENT_PRIORITIES` vive en `stock.move`: agregar "Critico" impactaria movimientos y transferencias de toda la base. |

## Documentacion afectada

| Archivo | Accion | Que reflejar |
|---------|--------|--------------|
| `sunra_mrp_component_serials/README.md` | **crear** | Objetivo de negocio, modelos, flujo (recepcion del kit → carga de piezas → OF → remito/factura), seguridad, **prerequisitos de configuracion** (los dos grupos de D14 + el opt-in de la LdM de D17), el comportamiento de "fallada libera" (D18), la no-reversion al cancelar (D20) y gotchas de v19. |
| `sunra_mrp_component_serials/static/description/index.html` | **crear** | Funcionalidad visible: padron de piezas, montaje contra el chasis, traslado automatico en la OF, numeros en remito y factura. |
| `sunra_mrp_component_serials/i18n/es_419.po` | **crear** | Traduccion es_419 de los strings de UI y, sobre todo, de los **encabezados impresos** en remito y factura (Motor / Batteries / Controller) y de los `UserError` del traslado (D19). |
| `extra-addons/odoo_customization_sunra/README.md` | **actualizar** | Agregar la fila del modulo al indice de modulos del repo (es modulo nuevo). |

## Plan del cambio en curso

> Build inicial del modulo. `version` del manifest nace en `1.0.0` y la `Version` de esta spec ya lo
> espeja; T12 verifica el sync. **Sin tarea de tests**: el repo no declara politica (`.swarm.conf`
> ausente) y la validacion acordada es guia de pruebas manual + video al cierre del proyecto.

| Tarea | Descripcion | Depende de | Archivos | Cubre |
|-------|-------------|------------|----------|-------|
| **T01** | Esqueleto: `__init__.py`, `__manifest__.py` (`version` 1.0.0, `depends = ["mail", "mrp", "sale_stock", "stock_account"]`, author/website/license Sunra, `data` a completar), `models/__init__.py` | — | `__init__.py`, `__manifest__.py`, `models/__init__.py` | — |
| **T02** | Modelo `sunra.bike.component`: campos, `models.Constraint` de unicidad (v19, NO `_sql_constraints`), `_inherit = ['mail.thread']` con tracking, `_order`, `_rec_names_search`, `_compute_display_name`, **override de `write` + `_onchange_faulty` + `@api.constrains` `_check_faulty_not_assigned` (D18: fallada libera el chasis; el constraint es la garantia estructural, cubre `create` e importacion)** y `@api.constrains` de un motor / un controlador por chasis (RB12) | T01 | `models/sunra_bike_component.py` | CA02, CA03, CA06 |
| **T03** | Extension `stock.lot`: `component_ids`, `battery_ids` (`tracking`), `motor_id`/`controller_id` (compute `store=False` + inverse + `tracking` + domain D5 con `faulty=False` + contexts) y helper `_sunra_component_report_values()` con `sudo()` | T02 | `models/stock_lot.py` | CA01, CA02, CA07 |
| **T04** | Seguridad: ACLs de `sunra.bike.component` (stock user r/w/c, stock manager r/w/c/u) | T02 | `security/ir.model.access.csv` | CA01 |
| **T05** | Vistas de `sunra.bike.component` (list/form con chatter/search sin `<group>`) + accion + menu bajo Inventario → Productos | T02, T04 | `views/sunra_bike_component_views.xml`, `views/sunra_mrp_component_serials_menus.xml` | CA06, CA07 |
| **T06** | Herencia del form de `stock.lot` (mismo XML ID `view_production_lot_form`): grupo "Bike Components" con motor/controlador (domain D5 + quick-create) y `battery_ids` como `<list editable="bottom" delete="0">` | T03, T05 | `views/stock_lot_views.xml` | CA01, CA02, CA06 |
| **T07** | Opt-in `mrp.bom.sunra_pull_kit_components` + `related` en `mrp.production` (I1) + `_sunra_get_kit_lot()`, `_sunra_pull_kit_components(strict)`, `action_sunra_pull_kit_components()`, override de `button_mark_done()`. Todos los `UserError` en ingles con `_()` y `%(name)s` | T03 | `models/mrp_bom.py`, `models/mrp_production.py` | CA04, CA05, CA10 |
| **T08** | Vistas heredadas (mismos XML IDs `mrp_production_form_view` / `mrp_bom_form_view`): `<field name="sunra_pull_kit_components" invisible="1"/>` + boton "Pull Kit Component Serials" en el header de la OF, y el campo opt-in en el form de la LdM | T07 | `views/mrp_production_views.xml`, `views/mrp_bom_views.xml` | CA04 |
| **T09** | Factura: override de `_get_invoiced_lot_values()` (super + browse unico + **normalizar las tres claves en TODOS los dicts**) + herencia del template `invoice_snln_table` con las tres columnas leidas con `.get()` | T03 | `models/account_move.py`, `report/account_move_templates.xml` | CA08 |
| **T10** | Remito: herencia del `thead` de `report_delivery_document` y de `stock_report_delivery_has_serial_move_line` con las tres columnas | T03 | `report/stock_picking_templates.xml` | CA08, CA09 |
| **T11** | Traduccion `i18n/es_419.po`: strings de UI, encabezados impresos (Motor / Batteries / Controller) y mensajes de error del traslado (D19) | T05, T07, T08, T09, T10 | `i18n/es_419.po` | — |
| **T12** | Doc y cierre: README del modulo (incluidos los prerequisitos de D14/D17 y el comportamiento de D18/D20) + `static/description/index.html` + fila en el README raiz del repo; verificar `version` del manifest == `Version` de la spec (`1.0.0`) | T01, T02, T03, T04, T05, T06, T07, T08, T09, T10, T11 | `README.md`, `static/description/index.html`, `../README.md`, `__manifest__.py`, `specs/sunra_mrp_component_serials.md` | — |

## Notas de implementacion

- **v19 — `_sql_constraints` eliminado**: la unicidad se declara como atributo de clase
  (`models.Constraint`). El hook `check_breaking_changes.sh` bloquea el patron viejo.
- **v19 — `lot_producing_ids` es Many2many** (era `lot_producing_id` en v17/v18): se escribe con
  `Command.set([...])` y se lee con `[:1]`. Es el error mas probable al portar codigo viejo.
- **`store=False` en `motor_id`/`controller_id`**: ningun criterio de aceptacion pide buscar ni
  agrupar lotes por motor/controlador —la busqueda inversa ("¿en que chasis esta esta pieza?") se
  hace desde el padron, que es donde el usuario tiene el numero en la mano—, y un computed **stored**
  sobre `stock.lot` forzaria el recalculo de toda la tabla al instalar. El `tracking=True` sigue
  funcionando sin store: `_track_get_fields()` no filtra por `store` y el tracking se dispara sobre
  los campos presentes en el `write` (que es exactamente la edicion desde la ficha del chasis).
  `readonly=False` es redundante habiendo `inverse` (el ORM ya lo hace escribible): no se declara.
  Contrapartida aceptada: no se puede filtrar/agrupar lotes por motor en la vista de lotes.
- **Por que `component_ids` (One2many "tecnico")**: los computes de `motor_id`/`controller_id`
  necesitan un `@api.depends` sobre la relacion inversa completa. Con un solo One2many sin domain
  alcanza para los tres tipos; declarar tres One2many gemelos seria mas ruido (D3 en espiritu).
- **D18 no obliga a filtrar `faulty` en ningun lado**: como marcar fallada limpia `lot_id`, ni
  `_compute_motor_id`/`_compute_controller_id`, ni `_sunra_component_report_values()`, ni el guard de
  completitud, ni `_sunra_pull_kit_components()` necesitan `filtered(lambda c: not c.faulty)`. El
  unico lugar donde `faulty` aparece explicito es el **domain** de seleccion (D5), para que una pieza
  fallada que quedo libre no vuelva a ofrecerse. Si alguna vez se agrega una lectura nueva sobre
  `component_ids`, hereda la garantia sin acordarse de nada.
- **Por que un helper de reporte y no logica en QWeb**: el join de las fajas y el `sudo()` se
  escriben una sola vez; los dos QWeb quedan tontos.
- **Alternativa descartada — constraint anti-reasignacion entre chasis**: se evaluo prohibir mover
  una pieza directamente de un chasis a otro. Se descarto porque **D4** dice que no hace falta
  constraint extra para la unicidad de asignacion y **D8** exige que siga siendo editable. La
  duplicacion sigue siendo imposible por construccion.
- **Alternativa descartada — `battery_ids` con `delete="1"`**: quitar una linea del One2many
  **borraria** la pieza del padron (y para un usuario de stock, sin permiso de unlink, fallaria con
  AccessError). Por eso se desmonta desde la pieza (D10) o marcandola fallada (D18).
- **Validacion del modulo (sin tests automatizados)**: el repo no tiene `.swarm.conf` y el usuario
  decidio no formalizar politica de tests. El cierre del proyecto entrega una **guia de pruebas
  manual** (recorriendo CA01..CA10) **+ un video** de la corrida. Si mas adelante se agrega
  `.swarm.conf` con `TESTS=required`, los candidatos naturales a automatizar son el traslado
  kit→bici (idempotencia incluida), el guard de completitud y la unicidad del padron.
- **Multi-compañia (D13)**: si algun dia hace falta, el cambio es acotado: `company_id` en
  `sunra.bike.component`, `check_company=True` en `lot_id`, la unicidad pasa a
  `UNIQUE(company_id, component_type, name)` y se agrega la record rule estandar.
- **Escalada a D2**: si Sunra empieza a comprar baterias sueltas, el camino es convertir la bateria
  en producto serializado dentro de la LdM; este modulo no lo impide (las piezas seguirian siendo el
  padron documental, o se retiraria el tipo `battery`).
