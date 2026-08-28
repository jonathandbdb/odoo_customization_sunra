# sunra_mrp_component_serials

Trazabilidad de motor, batería(s), controlador y cargador contra el número de serie del **chasis** de las
bicicletas eléctricas Sunra, con traslado automático a la orden de fabricación e impresión sin
intervención manual en remito y factura.

- **Versión**: 1.1.0
- **Licencia**: LGPL-3
- **Depende de**: `mail`, `mrp`, `sale_stock`, `stock_account`

## Objetivo de negocio

Sunra no compra bicicletas armadas: compra **kits en caja**. Cada kit trae el número de serie del
**chasis** —que es el número de serie del producto en Odoo— más el número de **motor**, el/los
número(s) de **faja** de la(s) batería(s) y el número de **faja del cargador**. Hoy esos números se
transcriben a mano al remito y a la factura, y se equivocan; el número de faja es la evidencia
**anti-fraude de garantía**: identifica qué batería se entregó con qué bicicleta.

Este módulo hace dos cosas:

1. Da de alta un **padrón de piezas** y las **monta** contra la serie del chasis, con la garantía
   estructural de que una pieza no puede estar en dos chasis a la vez.
2. Amolda el circuito a la **fabricación estándar de Odoo**: la orden de fabricación (OF) descuenta
   un kit y suma una bicicleta armada, **trasladando** las piezas del lote del kit al de la bici,
   para que los números salgan **solos** en remito y factura, sin intervención manual.

## Prerequisitos de configuración (críticos — sin esto el módulo "no hace nada")

El módulo se instala **inerte a propósito** en tres frentes. Si después de instalar parece que "no
pasa nada", revisar esto primero:

1. **Tildar "Pull Kit Component Serials" en la Lista de Materiales (LdM) del producto armado**
   (pestaña **Varios**, debajo de *Consumo*). Es un **opt-in explícito**: sin el
   tilde, el override de cierre de la OF (`button_mark_done()`) **no hace absolutamente nada**
   distinto del core — el traslado y el guard de completitud (piezas faltantes) no se ejecutan. Esto
   es **a propósito**: es lo único que evita que el módulo trabe cualquier otra orden de fabricación
   de la base que no tenga nada que ver con bicicletas.
2. **Activar los dos grupos nativos de impresión de series** (Ajustes → Usuarios y Compañías →
   Usuarios → pestaña *Otros*, o Ajustes → Permisos de usuario):
   - **"Mostrar números de serie en el remito"** (`stock.group_lot_on_delivery_slip`)
   - **"Mostrar números de serie en la factura"** (`stock_account.group_lot_on_invoice`)

   Sin estos dos grupos, el **core** no imprime la tabla de números de serie en remito/factura, y
   por lo tanto **nuestras cuatro columnas (Motor / Batteries / Controller / Charger) tampoco aparecen** — están
   condicionadas por los mismos `t-if`/`groups` nativos. El módulo **no fuerza** estos grupos por
   diseño (activarlos afecta a toda la base, no solo a bicicletas): es responsabilidad de quien
   configura la instancia.
3. **Producto con seguimiento por número de serie + LdM de tipo "Normal"** (NO tipo **"Kit"** /
   `phantom`). Una LdM `phantom` explota los componentes directamente en la línea de venta y
   **nunca genera una orden de fabricación** — con lo cual desaparece el momento en que se capturan
   los números de motor/batería/controlador. La LdM tiene que ser del tipo normal (fabricar bajo
   pedido/stock), la que sí abre una OF.

## Modelos y su rol

| Modelo | Rol |
|--------|-----|
| `sunra.bike.component` (nuevo) | **El padrón de piezas.** Un solo modelo para motor, batería y controlador (`component_type`), con `_inherit = ['mail.thread']` para chatter. `lot_id` (M2o a `stock.lot`) es el **único origen de verdad** de qué chasis tiene montada cada pieza: vacío = pieza libre. |
| `stock.lot` (extendido) | Representa el chasis (o cualquier lote serializado). Agrega `motor_id`, `controller_id`, `charger_id` (M2o computados, `store=False`), `battery_ids` (O2m, admite N) y el helper `_sunra_component_report_values()` usado por los reportes. |
| `mrp.bom` (extendido) | Agrega el opt-in `sunra_pull_kit_components` (Boolean, default `False`) — el interruptor de todo el módulo (prerequisito 1). |
| `mrp.production` (extendido) | El traslado kit→bici: `_sunra_get_kit_lot()`, `_sunra_pull_kit_components(strict)`, el botón `action_sunra_pull_kit_components()` y el override de `button_mark_done()`. |
| `account.move` (extendido) | Override de `_get_invoiced_lot_values()` para agregar motor/fajas/controlador a la tabla de series que ya imprime la factura. |

## Flujo de usuario de punta a punta

1. **Recepción del kit**: se recibe la compra del kit en una caja, con el chasis serializado (el
   número de serie del producto kit = número de chasis).
2. **Alta de las piezas desde la serie del chasis**: se abre la ficha del lote (`stock.lot`) del
   chasis recién recibido → grupo **"Bike Components"** → se cargan el **Motor**, el **Charger**, el **Controller** (si la línea lo trae)
   y una o más **Batteries** con "Agregar línea" (quick-create: cada número nuevo que se tipea da de
   alta una `sunra.bike.component` nueva, ya montada en ese chasis). Es carga **manual** al recibir
   cada kit; no hay importador (la planilla del proveedor todavía no llegó).
3. **Orden de fabricación**: se confirma la OF que consume el kit (componente serializado) y produce
   la bicicleta armada. Al **tildar "Marcar como Terminado"**, o apretando antes el botón
   **"Pull Kit Component Serials"** del header de la OF, el módulo:
   - identifica el lote del kit entre los componentes consumidos (por ser el único con seguimiento
     por número de serie);
   - reutiliza **el mismo número de chasis** como serie de la bicicleta terminada (no genera un
     número nuevo);
   - valida que el chasis tenga **motor + al menos una batería** (si falta algo, un `UserError`
     enumera exactamente qué falta y no deja cerrar la OF). **El controlador y el cargador NO se
     exigen**: las líneas actuales no traen controlador y el cargador no siempre viene informado;
   - **traslada** (no copia) las piezas del lote del kit al lote de la bici armada.
4. **Remito**: al entregar la bicicleta (o el kit sin armar, si se vende así), el remito imprime
   automáticamente el chasis + motor + batería(s) + controlador + cargador de las piezas **montadas** en el
   lote de esa línea.
5. **Factura**: idem remito, en la tabla de números de serie de la factura.

## Comportamientos que sorprenden si no se saben

### Marcar una pieza como "Faulty" (fallada) la libera del chasis, en el mismo acto

Tildar `faulty` en una `sunra.bike.component` **limpia `lot_id`** automáticamente (tanto desde el
formulario —`_onchange_faulty`— como por `write()`/importación). Consecuencias inmediatas:

- La pieza deja de estar **montada** en ese chasis.
- **No se ofrece** en ningún desplegable (motor/controlador/batería) para ningún otro chasis — el
  domain de selección excluye explícitamente `faulty = True`.
- **No se imprime** en remito ni factura (los reportes solo leen piezas montadas, y una fallada ya
  no tiene `lot_id`).
- **No cuenta** para el guard de completitud al cerrar la OF (motor + batería).

De **qué chasis salió** una pieza fallada queda registrado en su **chatter** (`lot_id` tiene
`tracking=True`): siempre se puede reconstruir el historial "de dónde salió, cuándo, quién lo hizo".

**Destildar "Faulty" NO la devuelve sola a su chasis anterior.** La pieza queda simplemente
**libre**: hay que reasignarla a mano (desde la propia pieza, seteando `lot_id`, o desde la ficha
del chasis en el campo correspondiente). Es intencional: automatizar la reasignación asumiría que el
chasis original sigue siendo el destino correcto, lo cual no siempre es cierto.

### Cancelar la OF después del traslado NO revierte las piezas al lote del kit

`_sunra_pull_kit_components()` **no** se engancha a `action_cancel()`. Si se cancela una orden de
fabricación después de que las piezas ya viajaron al lote de la bicicleta, **quedan ahí** — no
vuelven solas al lote del kit. Esto es intencional y **no rompe el dato**: el lote de la bicicleta
lleva **el mismo número de chasis** que el lote del kit (ver más abajo), así que la información
sigue siendo correcta de cara al cliente. Si hace falta revertir manualmente, se hace desde la ficha
de cada pieza (reasignando `lot_id` de vuelta al lote del kit).

## Otros comportamientos relevantes (reglas de negocio)

- **Una pieza no puede estar en dos chasis a la vez.** `lot_id` es el único lugar donde vive la
  asignación → la duplicación es imposible por construcción. El desplegable de selección (D5) solo
  ofrece piezas **libres y no falladas** del tipo correcto (más la que ya está montada en ese mismo
  chasis, para que el campo no quede sin opción al reabrir la ficha).
- **Un motor, un controlador y un cargador como máximo por chasis; baterías, N.** Lo garantiza un
  `@api.constrains` sobre `sunra.bike.component` (`_check_single_components`), porque la
  reasignación desde la propia pieza no pasa por el domain de la vista de `stock.lot`.
- **El número de serie es único por tipo de pieza**: `(component_type, name)` tiene una constraint
  `UNIQUE`. Dar de alta dos veces el mismo número de faja falla — y por lo tanto también falla
  cualquier intento (manual o por importación) de "mover" una pieza a otro chasis creando un
  registro con el número repetido: la unicidad lo impide.
- **La bicicleta armada nunca recibe un número de serie nuevo**: reutiliza el mismo nombre del lote
  del kit. Esto funciona porque la unicidad nativa de `stock.lot` es por (compañía, **producto**,
  nombre) — el kit y la bici son productos distintos, así que el mismo nombre convive como dos
  lotes.
- **El traslado siempre mueve, nunca copia.** Copiar dejaría la misma pieza en dos lotes a la vez,
  rompiendo el domain de "libres" y la búsqueda inversa.
- El método de traslado (`_sunra_pull_kit_components`) es **idempotente**: si ya se apretó el botón
  manual y después se cierra la OF, el guard evalúa la unión de piezas del kit + la bici y no
  vuelve a fallar ni a mover nada de más.

## Modelo de seguridad

**No se crean grupos nuevos.** Se reutilizan los grupos nativos de Inventario.

| Modelo | Grupo | read | write | create | unlink |
|--------|-------|------|-------|--------|--------|
| `sunra.bike.component` | `stock.group_stock_user` | ✓ | ✓ | ✓ | — |
| `sunra.bike.component` | `stock.group_stock_manager` | ✓ | ✓ | ✓ | ✓ |

- Un usuario **Usuario de Inventario** puede leer/crear/editar piezas, pero no borrarlas (evita que
  se pierda historial por error); solo **Responsable de Inventario** puede eliminar.
- **Sin record rules**: el padrón de piezas es **global**, sin `company_id` (no es multi-compañía
  hoy — ver Gotchas). Los números de serie físicos son únicos en el mundo real, así que la unicidad
  global es el criterio conservador.
- Los reportes (remito/factura) leen las piezas con `_sunra_component_report_values()` sobre
  `self.sudo()`, para que un usuario de Ventas/Facturación **sin** permisos de Inventario pueda
  imprimir igual (mismo criterio que usa el propio core de Odoo para lotes en facturas).
- El menú **Bike Components** (Inventario → Productos → Bike Components) está condicionado al grupo
  `stock.group_production_lot` (Trazabilidad por lotes/números de serie).

## Vistas, menús y reportes

- **Bike Components** (lista/formulario/búsqueda) bajo **Inventario → Productos**: lista con
  decoración roja para piezas falladas (`decoration-danger="faulty"`), formulario con chatter, y
  filtros de búsqueda *Free* / *Assigned* / *Faulty* + agrupar por tipo o por chasis.
- **Ficha del lote** (`stock.lot`): grupo **"Bike Components"** con Motor, Controller y la lista
  editable de Batteries (sin permitir borrar líneas — `delete="0"` — para no borrar del padrón por
  error; se desmonta marcando `faulty` o reasignando desde la pieza).
- **Ficha de la LdM** (`mrp.bom`): campo **"Pull Kit Component Serials"** (el opt-in).
- **Ficha de la OF** (`mrp.production`): botón **"Pull Kit Component Serials"** en el header, visible
  solo si la LdM tiene el opt-in activo y la OF no está terminada/cancelada.
- **Factura**: cuatro columnas (Motor / Batteries / Controller / Charger) a continuación de la tabla nativa de
  números de serie (`invoice_snln_table`), dentro del `groups="stock_account.group_lot_on_invoice"`
  del core.
- **Remito**: idem, cuatro columnas después de la columna de serie nativa, dentro del
  `groups="stock.group_lot_on_delivery_slip"` del core.

## Dependencias

- `mail` — chatter/tracking de `sunra.bike.component`.
- `mrp` — `mrp.bom`, `mrp.production` (el circuito de fabricación kit → bicicleta).
- `sale_stock` — `_get_invoiced_lot_values()`, el hook que se extiende para la tabla de series de
  la factura.
- `stock_account` — template base de la tabla de series en la factura (`invoice_snln_table`) y el
  grupo `group_lot_on_invoice`.

No requiere ningún servicio externo ni configuración de integración.

## Gotchas de v19 relevantes para mantenimiento

- **`_sql_constraints` fue eliminado en v19**: la unicidad `(component_type, name)` se declara como
  atributo de clase `models.Constraint('UNIQUE(...)', mensaje)`, no como el viejo diccionario.
- **`lot_producing_ids` en `mrp.production` es Many2many** (era `lot_producing_id`, Many2one, en
  v17/v18). Se escribe con `Command.set([...])` y se lee con `[:1]`. Es el error más probable si se
  porta código de una versión vieja a este módulo.
- **`motor_id`/`controller_id` son `store=False`**: no hay ningún criterio de aceptación que pida
  buscar/agrupar lotes por motor o controlador (la búsqueda inversa "¿en qué chasis está esta
  pieza?" se hace desde el padrón, que es donde el usuario tiene el número en la mano). Un compute
  `store=True` sobre `stock.lot` forzaría recalcular toda la tabla al instalar/actualizar. El
  `tracking=True` sigue funcionando sin `store` porque `_track_get_fields()` no filtra por `store` y
  el tracking se dispara sobre los campos presentes en el `write()`.
- **`button_mark_done()` se overridea llamando al traslado ANTES de `super()`**: con una bicicleta
  por OF (`product_uom_qty == 1`), el core genera el número de serie **en silencio**
  (`_set_quantities()` → `action_generate_serial()`) dentro del mismo `button_mark_done()`, sin
  mostrar ningún asistente. Si el traslado no setea `lot_producing_ids` **antes** de llamar a
  `super()`, la bicicleta nace con un número de serie nuevo (violando la regla de "mismo chasis").
- **Multi-compañía**: fuera de alcance hoy (el padrón no lleva `company_id`). Si en el futuro hace
  falta, el cambio es acotado: agregar `company_id` a `sunra.bike.component`,
  `check_company=True` en `lot_id`, cambiar la unicidad a
  `UNIQUE(company_id, component_type, name)` y agregar la record rule estándar.
- **No incluido a propósito** (ver la spec para el detalle completo): prioridad "Crítico" en
  fabricación, números en facturas importadas de Tango, registro de incidencias/reclamos al
  proveedor, stock real de baterías sueltas, órdenes/centros de trabajo, importador de la planilla
  del proveedor, cambios de valuación/costeo, y reversión automática al cancelar la OF.

## Validación manual (sin tests automatizados)

El repo no declara política de tests (`.swarm.conf` ausente); la validación acordada con el cliente
es una **guía de pruebas manual + video** al cierre del proyecto, recorriendo los criterios de
aceptación de la spec (CA01 a CA10): alta de piezas desde la serie del chasis, intento de asignar
una pieza ya montada a otro chasis (rechazado), número de faja duplicado (rechazado), traslado por
botón y al cerrar la OF, batería fallada antes/después de armar, impresión completa en remito y
factura (bicicleta armada y kit sin armar), y bloqueo al cerrar una OF con el chasis incompleto.

## Notas de mantenimiento

- El módulo es **SDD**: `specs/sunra_mrp_component_serials.md` es la fuente de verdad de decisiones
  (D1-D20), reglas de negocio (RB01-RB12), campos, métodos, edge cases, criterios de aceptación y
  anclajes al core con `path:L#`. Cualquier cambio, por chico que sea, debe reflejarse ahí en sitio
  y mantener el `version` del manifest sincronizado con la `Version` de la spec.
- Traducción es_419 en `i18n/es_419.po` (UI en inglés con `_()`, incluidos los encabezados impresos
  Motor/Batteries/Controller y los mensajes de error del traslado).
- Si algún día Sunra empieza a comprar baterías sueltas (en vez de kits cerrados), el camino natural
  es convertir la batería en producto serializado dentro de la LdM; este módulo no lo impide.

## Licencia y autoría

LGPL-3 · Sunra · https://github.com/sunraargsh
