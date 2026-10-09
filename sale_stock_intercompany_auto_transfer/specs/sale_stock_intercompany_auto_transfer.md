# Spec de modulo: sale_stock_intercompany_auto_transfer

| Campo | Valor |
|-------|-------|
| **Modulo** | `sale_stock_intercompany_auto_transfer` |
| **Version** | `1.0.0` (== `version` del `__manifest__.py`, formato `x.x.x`) |
| **Serie Odoo** | `19` (informativa) |
| **Estado** | `verified` |
| **Actualizado** | `2026-10-09` |
| **Depurado** | `2026-10-09` |

## Objetivo

Cuando una compañia se abastece de otra con la ruta de reabastecimiento inter-company del core
(salida del almacen proveedor → ubicacion de transito inter-company → recepcion en el almacen
destino), el core crea las dos transferencias pero las deja para validar a mano, una en cada
compañia. Este modulo las **valida solas**: al confirmar un pedido de venta que dispara esa cadena,
la salida de la compañia proveedora y la recepcion de la compañia destino quedan hechas por lo que
habia disponible, y la entrega al cliente queda reservada con lo recibido. El deposito solo valida
la entrega al cliente.

Se activa por tipo de operacion de recepcion: sin activar, la cadena es la estandar del core.

Caso de uso: "Miluan Prueba" / "YG Prueba" venden con almacen propio; si no alcanza su stock, la
regla `mts_else_mto` de su almacen pide el faltante a "Miluan SRL" / "YG S.A." por la ruta
inter-company, y el traspaso ocurre sin intervencion.

## Precondiciones de configuracion

Configuracion del core que el modulo **no** crea y de la que dependen todos los criterios de
aceptacion. Va tambien al `README.md` y al `index.html` del modulo.

| # | Precondicion | Por que |
|---|--------------|---------|
| P1 | Ubicacion de transito inter-company (`stock.stock_location_inter_company`) **activa**. | Sin ella no hay ruta inter-company. |
| P2 | Ruta "Resupply From <almacen proveedor>" aplicada al almacen de la compañia destino (`warehouse_ids` / "Resupply From" del almacen) o a los productos/categorias. | Es la que arma la cadena salida → transito → recepcion. "Reabastecer desde" se edita con **ambas compañias activas en el selector de compañias** (D20). |
| P3 | Regla de entrega del almacen de la compañia destino en `mts_else_mto`. | Pide a la proveedora solo el faltante. |
| P4 | Tipo de operacion de **entrega** de la compañia destino con `reservation_method = at_confirm`. | El `_trigger_assign()` del core solo reserva movimientos MTS con `at_confirm` o con `reservation_date` vencida (`stock_move.py:2648-2653`), y la reserva del stock propio al confirmar depende de lo mismo (`stock_move.py:1975-1976`). Con otro metodo la entrega no queda reservada sola. |
| P5 | Tipo de **salida** de la proveedora y tipo de **recepcion** de la destino con `create_backorder` en `ask` o `always`. | Con `never` el faltante de la salida se cancela y la recepcion queda esperando un movimiento que no llega (D7). |
| P6 | Flag `auto_validate_intercompany_transfer` activado en el tipo de recepcion de la compañia destino. | D1. |

## Decisiones vigentes

| # | Decision | Valor vigente |
|---|----------|---------------|
| D1 | ¿Donde se activa? | `stock.picking.type.auto_validate_intercompany_transfer` (Boolean) en el tipo de operacion de **recepcion** de la compañia destino (ej. "Recepciones" del almacen de "Miluan Prueba"). Solo tiene efecto en tipos `code == 'incoming'`; en otros tipos se ignora y la vista lo oculta. Apagado (default) = cadena estandar. |
| D2 | ¿Que es una cadena inter-company? | Un movimiento **origen** no hecho con un movimiento destino `dest` en `move_dest_ids` tal que `dest.picking_type_id.code == 'incoming'`, `dest.picking_type_id.auto_validate_intercompany_transfer` y `dest.company_id != move.company_id` (comparacion **por movimiento**), evaluada en un unico helper `stock.move._get_intercompany_auto_dests()` (sobre el movimiento origen, devuelve sus destinos que cumplen) que usan `sale.order` y `stock.picking`. Es lo que arma la ruta "Resupply From" del core: la regla transito → stock destino es MTO, asi que el movimiento de salida del proveedor lleva como destino el de la recepcion. Una recepcion de la **misma** compañia (reabastecimiento entre almacenes propios) no es cadena inter-company y no se toca. |
| D3 | ¿Cuando se dispara? | **(a)** Al final de `sale.order.line._action_launch_stock_rule()`: solo sobre los movimientos origen inter-company **creados en esa llamada** (diferencia de ids de `stock.move` de las referencias de stock de los pedidos antes y despues de `super()`). Si la llamada no genero movimientos nuevos de la cadena (ej. bajar cantidades, editar otra linea), no hace nada. **(b)** En `stock.picking._action_done()` de cualquier transferencia (la validacion automatica de (a) o una manual): tras `super()` se validan las recepciones encadenadas que cumplen D2. La salida dispara la recepcion siempre por (b); (a) solo valida la salida. |
| D4 | ¿Como se encuentran los movimientos origen del pedido? | `order.stock_reference_ids.sudo().move_ids` filtrado por `company_id != order.company_id`, `state` no en `draft`/`done`/`cancel` y D2, sin `search` propio. Toda la cadena comparte esa referencia (`stock_move.py:1866`, `stock_rule.py:368`). |
| D5 | ¿Por que cantidad se valida la salida? | Por lo **reservado** tras `_action_assign()` (en `sudo().with_company(<compañia de la salida>)`). Los movimientos con cantidad reservada se marcan `picked`. La salida se valida tal como esta: la agrupacion del core por referencia (`stock_move.py:1537-1545`) hace que contenga solo movimientos de ese pedido. |
| D6 | Stock insuficiente en la compañia proveedora | `[ASUNCION]` Se valida lo disponible y el resto queda como **backorder pendiente** en la proveedora; su recepcion se valida sola cuando alguien valide ese backorder (D3 b). Sin nada reservado, la salida no se valida y queda pendiente. En ambos casos se deja un mensaje en el chatter del pedido con producto y cantidad faltante. **Nunca** se bloquea la confirmacion del pedido. |
| D7 | Backorders | La validacion corre con `skip_backorder=True` (sin wizard): rige el `create_backorder` de cada tipo de operacion como en `button_validate()`. `ask`/`always` → backorder del resto; `never` → el resto se cancela. Requisito P5. |
| D8 | ¿Como se valida la recepcion? | Recepciones de D2 con al menos un movimiento con cantidad reservada (el core reserva el destino al validar el origen, en `sudo().with_company`, `stock_move.py:2304-2307`), no `done`/`cancel`: se validan por lo reservado, igual que D5/D7. La recepcion parcial deja backorder, que se valida cuando llegue el resto. |
| D9 | Contexto de la validacion automatica | `button_validate()` hereda el contexto del llamador, y una validacion manual con "No Backorder" trae `picking_ids_not_to_backorder` y `button_validate_picking_ids` (`stock_backorder_confirmation.py:72-74`) que el core re-incluye al validar otra transferencia (`stock_picking.py:1455`, `1462-1469`). Por eso la validacion automatica arma un contexto **saneado**: `clean_context(self.env.context)` (quita `default_*`), quita ademas `picking_ids_not_to_backorder`, `button_validate_picking_ids`, `cancel_backorder` y toda clave `active_*`, y agrega solo `skip_backorder=True`, `skip_sms=True` y la clave de reentrada `sale_stock_intercompany_auto_transfer_validating` (ids de las transferencias en validacion automatica, acumulados). `_get_intercompany_auto_receipts()` excluye esos ids. |
| D10 | Permisos | La validacion corre en `sudo().with_company(<compañia de la transferencia>)`, acotada a las transferencias de la cadena: quien confirma el pedido (o valida la salida) puede no tener acceso a la otra compañia. Es el mismo criterio del core para crear la cadena (`stock_rule.py:313-314`) y reservar el destino (`stock_move.py:2307`). El `_check_company()` del core sigue aplicando. |
| D11 | Errores al validar | Cada transferencia se valida dentro de `self.env.cr.savepoint()`. Se capturan **solo** errores de negocio: `UserError` y sus subclases (`ValidationError`, `AccessError`, `MissingError`), `RedirectWarning`, y la excepcion propia que se lanza si, tras `button_validate()`, la transferencia no queda `done` (wizard pendiente: lotes vencidos de `product_expiry`, `quality_control`, etc.). `LockError` **si** se captura (es subclase de `UserError`, `exceptions.py:109`): el framework no lo reintenta (`service/model.py:192`) y `lock_for_update` usa `SKIP LOCKED`, que no aborta la transaccion (`orm/models.py:5594-5602`), asi que dejar la transferencia pendiente es correcto. **Nunca** `Exception` a secas, ni `ConcurrencyError`, `psycopg2.OperationalError` o errores de serializacion: se propagan para que el framework reintente. El exito se decide solo por `picking.state == 'done'`: si `button_validate()` devuelve una accion de impresion posterior al `done` (`auto_print_*`, reporte de recepcion, `stock_picking.py:1472`, `2074-2123`) la validacion vale. La transferencia que falla se revierte y queda pendiente; la confirmacion del pedido o la validacion manual que lo disparo siguen. |
| D12 | ¿Donde se avisa un error o pendiente? | **(a)**: un unico `message_post` por pedido con faltantes (D6), salidas pendientes y recepciones de la cadena que no quedaron `done` (incluye las que fallaron en (b) dentro de esa misma corrida). **(b)** fuera de (a) (validacion manual de una salida): `message_post` en la recepcion con el motivo y, si la recepcion tiene pedido de venta (`sale_id`), un mensaje en el pedido con el motivo y link a la recepcion (uno por pedido). Dentro de (a) (clave de reentrada presente), (b) solo avisa en la recepcion; el pedido lo avisa (a). |
| D13 | Savepoint y cache | `cr.savepoint()` hace `flush` (y con el, el `precommit` de tracking de mail) al entrar, y en rollback `cr.clear()` invalida todo el cache ORM (`sql_db.py:132-151`). Tras cada savepoint no se reutilizan valores leidos antes sin releerlos del recordset (`browse` por ids, recomputar estados). |
| D14 | Entrega al cliente | **No** se valida. Queda reservada con lo recibido por el `_trigger_assign()` del core al validar una recepcion (`stock_picking.py:1304-1305`), sujeto a P4. |
| D15 | Lotes y series | No se elige lote: la salida reserva segun la estrategia de remocion de la proveedora y la recepcion hereda el lote reservado en el transito (`test_multicompany.py:601-690`). |
| D16 | Cantidad entregada del pedido | La salida de la proveedora no suma: el core solo cuenta movimientos de la compañia del pedido (`sale_order_line.py:338`). La recepcion en la compañia del pedido si seria restada como devolucion (entrada con `to_refund` desde transito inter-company, que `_is_outgoing()` cuenta como saliente: `sale_order_line.py:364-366`, `stock_location.py:468-474`), dejando `qty_delivered` negativo. El modulo la excluye de los movimientos entrantes en `SaleOrderLine._get_outgoing_incoming_moves()`: entrada desde transito inter-company hacia ubicacion interna y sin `origin_returned_move_id`. Sin esos movimientos el resultado es el del core. La exclusion aplica **sin importar el flag** del tipo de recepcion: el core da `qty_delivered` negativo igual en cadenas inter-company manuales. |
| D17 | Alcance de (b) | (b) valida **cualquier** recepcion con el flag alimentada por una salida de otra compañia, venga la cadena de una venta, de una regla de reabastecimiento (orderpoint) o de fabricacion: el flag significa "transferencia inter-company automatica" para esa compañia destino. |
| D18 | Efectos colaterales aceptados | (1) Si la proveedora tiene `stock_move_email_validation` y la salida es de tipo `outgoing`, el core envia el mail de confirmacion de entrega al validarla (`stock_picking.py:1325-1333`). (2) Si la proveedora valoriza en tiempo real, sus asientos de salida se generan sin revision manual. (3) El flag lo configura la compañia **destino** pero mueve stock de la **proveedora**: quien edita tipos de operacion de la destino decide la salida de la otra. Se documentan en el README. |
| D19 | Visibilidad e idioma | El campo se muestra en el formulario del tipo de operacion solo para `incoming`. UI en ingles con `_()`, traduccion `i18n/es_AR.po` (convencion del repo). |
| D20 | ¿Como se configura "Reabastecer desde" entre compañias? | La UI del core restringe `resupply_wh_ids` a almacenes de la **misma** compañia (`stock_warehouse_views.xml:43`, `domain=[('id','!=',id),('company_id','=',company_id)]`), aunque el backend soporta reabastecer entre compañias con el transito inter-company (`stock_warehouse.py:702-737`, `test_multicompany.py:601-690`). El modulo hereda `stock.view_warehouse` y reemplaza solo el atributo `domain` del campo por `[('id', '!=', id)]`. El widget `many2many_checkboxes` ofrece las opciones segun las record rules: el usuario necesita **ambas compañias activas en el selector** para ver el almacen de la proveedora (P2). |

## Alcance

### Incluye
- Opcion por tipo de operacion de recepcion para validar sola la cadena inter-company.
- Validacion automatica de la salida de la compañia proveedora al confirmar el pedido (o agregar/aumentar lineas), por lo disponible, con backorder del resto.
- Validacion automatica de la recepcion encadenada cada vez que se valida su salida, sea automatica o manual (D17).
- Aviso en el chatter del pedido y de la recepcion de faltantes y transferencias que quedaron pendientes (D12).

### NO incluye
- **Configuracion** de almacenes, rutas y reglas (Precondiciones P1..P5): es configuracion del core.
- **Asientos contables** del traspaso: los define el contador (la ubicacion de transito inter-company no tiene compañia y no se valoriza, `stock_account/models/stock_location.py:36-41`).
- **Cancelar en cascada** las transferencias inter-company si se cancela el pedido: con `mts_else_mto` el movimiento de entrega es MTS y no queda vinculado a la recepcion (`stock_rule.py:305-310`).
- **Control previo de stock** de la compañia proveedora antes de confirmar el pedido.
- Validar la **entrega al cliente** (D14).
- Validar backorders de salida **preexistentes** al editar un pedido confirmado (D3 a).
- Facturacion entre compañias (venta/compra espejo).
- Cadenas de varios pasos dentro de la proveedora (pick → out): solo se valida la transferencia cuyo destino es la recepcion de otra compañia.
- **Tests automatizados**: el repo no declara politica de tests (`.swarm.conf` ausente).

## Modelos

### Nuevos

No aplica: el modulo solo extiende modelos del core.

### Extendidos

| Modelo | `_inherit` | Que se agrega |
|--------|-----------|---------------|
| `stock.picking.type` | `stock.picking.type` | `auto_validate_intercompany_transfer` (D1). |
| `stock.picking` | `stock.picking` | Override de `_action_done()` (D3 b) + validacion automatica en savepoint con contexto saneado (D5, D7, D9..D13). |
| `stock.move` | `stock.move` | `_get_intercompany_auto_dests()` (D2). |
| `stock.warehouse` | `stock.warehouse` | Solo vista: dominio de `resupply_wh_ids` (D20). |
| `sale.order.line` | `sale.order.line` | Override de `_action_launch_stock_rule()` (D3 a). |
| `sale.order` | `sale.order` | Cadena del pedido, validacion de salidas y aviso en el chatter (D4, D6, D12). |

## Campos

| Modelo | Campo | Tipo | String | Requerido | Default | Restricciones / notas |
|--------|-------|------|--------|-----------|---------|----------------------|
| `stock.picking.type` | `auto_validate_intercompany_transfer` | Boolean | Auto-Validate Inter-Company Transfer | No | `False` | `help`: "When a sale needs stock from another company through the inter-company transit, the delivery of the supplying company and this receipt are validated automatically with the available quantity. Only for receipts." Solo efectivo con `code == 'incoming'` (D1). |

## Metodos

### `StockMove._get_intercompany_auto_dests()`
- **Proposito**: unica implementacion de D2.
- **Logica**: `self.ensure_one()`; `self.sudo().move_dest_ids` con `company_id != self.company_id`, `picking_type_id.code == 'incoming'` y `picking_type_id.auto_validate_intercompany_transfer`.
- **Retorna**: `stock.move` (en `sudo`).

### `StockPicking._action_done()` (override)
- **Proposito**: D3 b.
- **Logica**:
  1. `res = super()._action_done()`.
  2. `receipts = self._get_intercompany_auto_receipts()`; sin recepciones → `return res`.
  3. `pending = receipts._intercompany_auto_validate()`.
  4. Por cada recepcion pendiente: `message_post` con el motivo. Si el contexto **no** trae la clave de reentrada y la recepcion tiene `sale_id`: un `message_post` por pedido con el motivo y link (`_get_html_link`) a cada recepcion (D12).
- **Retorna**: lo de `super()`.

### `StockPicking._get_intercompany_auto_receipts()`
- **Proposito**: recepciones encadenadas a validar (D2, D8, D9).
- **Logica**: por cada movimiento `done` de `self` (en `sudo()`), `move._get_intercompany_auto_dests()` (D2); de ahi `picking_id`, filtrado por `state` no en `done`/`cancel`, al menos un movimiento con `quantity > 0`, e `id` fuera de `sale_stock_intercompany_auto_transfer_validating`.
- **Retorna**: `stock.picking` (en `sudo`).

### `StockPicking._intercompany_auto_validate_context()`
- **Proposito**: contexto saneado de D9.
- **Logica**: `ctx = clean_context(self.env.context)`; quitar `picking_ids_not_to_backorder`, `button_validate_picking_ids`, `cancel_backorder` y las claves que empiezan con `active_`; `ctx.update(skip_backorder=True, skip_sms=True, sale_stock_intercompany_auto_transfer_validating=<ids previos del contexto> + self.ids)`.
- **Retorna**: `dict`.

### `StockPicking._intercompany_auto_validate()`
- **Proposito**: validar transferencias de la cadena sin wizard ni bloqueo (D5, D7, D9..D13).
- **Logica**, por id de transferencia:
  1. `picking = self.env['stock.picking'].sudo().with_company(<compañia>).with_context(**self._intercompany_auto_validate_context()).browse(id)`.
  2. Dentro de `self.env.cr.savepoint()`: marcar `picked` los movimientos con `quantity > 0`; `picking.button_validate()`; si `picking.state != 'done'`, lanzar la excepcion propia para revertir el savepoint.
  3. Capturar solo las excepciones de D11 (incluido `LockError`); guardar el id y el motivo (mensaje de la excepcion o "requires manual validation").
- **Retorna**: `dict {picking_id: motivo}` de las que quedaron pendientes.
- **Errores**: los de negocio y `LockError` no salen (D11); los de concurrencia/BD se propagan.

### `SaleOrderLine._action_launch_stock_rule(*, previous_product_uom_qty=False)` (override)
- **Proposito**: D3 a.
- **Logica**: si `skip_procurement` en contexto → `super()`. Si no: `before = self.order_id.stock_reference_ids.sudo().move_ids.ids`; `res = super()...`; `new_moves = self.order_id.stock_reference_ids.sudo().move_ids - browse(before)`; si hay, `self.order_id._intercompany_auto_transfer(new_moves)`; `return res`.

### `SaleOrderLine._get_outgoing_incoming_moves(strict=True)` (override)
- **Proposito**: D16.
- **Logica**: `super()`; de los movimientos entrantes quita los que salen de una ubicacion `transit` que el core considera saliente (`_is_outgoing()`), entran a una ubicacion `internal` y no tienen `origin_returned_move_id`. Devuelve la misma tupla `(salientes, entrantes)`.

### `SaleOrder._is_intercompany_chain_source(move)`
- **Proposito**: D4. `move.company_id != order.company_id`, `state` no en `draft`/`done`/`cancel` y `move._get_intercompany_auto_dests()` no vacio.

### `SaleOrder._intercompany_post_notice(shortages, pending)`
- **Proposito**: D12 (a). Un `message_post` con faltantes y transferencias pendientes; sin ambos, no publica.

### `StockPicking._intercompany_notify_pending_receipts(pending)`
- **Proposito**: D12 (b). `message_post` en cada recepcion pendiente y, fuera de la validacion del pedido, uno por pedido con links.

### `SaleOrder._intercompany_auto_transfer(new_moves)`
- **Proposito**: validar la salida de la proveedora para los movimientos nuevos de la cadena (D3 a, D4..D7, D12).
- **Logica**, por pedido:
  1. Movimientos origen = `new_moves` del pedido que cumplen D4/D2 (`_is_intercompany_chain_source()`). Sin movimientos → siguiente pedido.
  2. Por compañia: `moves.with_company(company)._action_assign()` (D5, D10).
  3. Faltantes: por movimiento origen (releido tras la reserva), `product_uom_qty - quantity` > 0 segun `move.product_uom.compare(missing, 0)` → linea (cantidad mostrada con `move.product_uom.round(missing)`) del aviso (producto, cantidad, compañia).
  4. Salidas (`moves.picking_id`) con algo reservado → `_intercompany_auto_validate()`; su `_action_done()` valida la recepcion (D3 b).
  5. Releer por ids salidas y recepciones de la cadena (D13); las que no estan `done` → linea del aviso con su motivo.
  6. Si hubo faltantes o pendientes: un `message_post` en el pedido con links (`_get_html_link`) (D12).
- **Retorna**: `None`.

## Vistas

- `stock_warehouse_view_form` (hereda `stock.view_warehouse`): `position="attributes"` sobre `resupply_wh_ids`, `domain` = `[('id', '!=', id)]` (D20).
- `stock_picking_type_view_form` (hereda `stock.view_picking_type_form`): `auto_validate_intercompany_transfer` despues de `create_backorder`, `invisible="code != 'incoming'"`.

## Seguridad

- **Sin modelos nuevos** → sin ACLs nuevas. Sin grupos ni record rules nuevos.
- El campo lo edita quien puede editar tipos de operacion (`stock.group_stock_manager`, ACL del core).
- `sudo()` acotado a las transferencias de la cadena inter-company del pedido o de la transferencia validada (D10).

## Reglas de negocio

1. **RB01**: Con el tipo de recepcion activado, al confirmar un pedido (o agregar/aumentar lineas) que crea movimientos de la cadena inter-company, la salida de la proveedora se valida por lo disponible.
2. **RB02**: Toda salida validada (automatica o manual) cuyo destino es una recepcion activada de otra compañia valida esa recepcion por lo recibido, una sola vez.
3. **RB03**: Lo que no se pudo enviar queda como backorder pendiente en la proveedora y se avisa en el pedido.
4. **RB04**: Ningun error de negocio de la validacion automatica impide confirmar el pedido ni validar la salida manual que lo disparo.
5. **RB05**: La entrega al cliente nunca se valida automaticamente; queda reservada con lo recibido.
6. **RB06**: Con el tipo de recepcion sin activar, o recepciones de la misma compañia, el comportamiento es el del core.

## Edge cases

- **Stock propio suficiente**: `mts_else_mto` toma de stock y no crea cadena; el modulo no hace nada.
- **Faltante parcial**: la cadena es solo por el faltante; la entrega queda reservada con stock propio + recibido.
- **Proveedora sin stock**: nada se valida; salida y recepcion pendientes; aviso en el pedido. Cuando alguien valide la salida, la recepcion se valida sola.
- **Proveedora con stock parcial**: salida y recepcion hechas por lo disponible; backorders de ambas por el resto.
- **Tipo con `create_backorder = never`**: el resto se cancela (D7, fuera de P5).
- **Validacion manual de la salida con "No Backorder"**: la recepcion se valida una vez con contexto saneado; la salida no se re-valida (D9).
- **Validacion que pide wizard o falla** (lote vencido, control de calidad, lote faltante): la transferencia queda pendiente con aviso (D11, D12).
- **Error de concurrencia o de BD** durante la validacion automatica: se propaga y la operacion entera se reintenta o falla como en el core (D11).
- **Producto con lote o serie**: el lote viaja de la salida a la recepcion y a la reserva de la entrega (D15).
- **Usuario sin acceso a la proveedora**: confirma igual; la validacion corre en `sudo` (D10).
- **Pedido con varias lineas de la cadena**: una salida y una recepcion por referencia, validadas juntas.
- **Aumentar la cantidad de una linea de un pedido confirmado**: los movimientos nuevos de la cadena se validan igual (D3 a).
- **Editar un pedido confirmado con un backorder de salida pendiente** (bajar cantidad, cambiar otra linea): sin movimientos nuevos de la cadena, (a) no hace nada; el backorder lo valida el deposito a mano y su recepcion se valida sola por (b).
- **Salida editada a mano con movimientos ajenos**: se valida entera con lo reservado (D5).
- **Cadena originada por orderpoint o fabricacion** hacia una recepcion con el flag: al validar la salida, la recepcion se valida sola (D17); no hay pedido que avisar.
- **Tipo de entrega con `reservation_method` distinto de `at_confirm`**: la entrega al cliente no se reserva sola (P4); salida y recepcion se validan igual.
- **`stock.picking_no_auto_reserve` activo**: idem, comportamiento del core.
- **Transferencias de la cadena en el pedido**: el core asigna `sale_id` a la salida y a la recepcion por el `sale_line_id` heredado (`stock.py:189-195`), asi que el boton de entregas del pedido las cuenta; no afectan la cantidad entregada (D16).
- **Bajar la cantidad de una linea confirmada**: el core genera una cadena inversa (MPR → transito y devolucion hacia DEPO/IN) que el modulo no valida.
- **Salida validada con "No Backorder"**: queda en la compañia del pedido una recepcion backorder sin origen, que se cancela a mano.
- **Aumentar una linea de un pedido confirmado**: el core puede sobre-demandar; el modulo valida lo que el core genero.
- **Falla de la recepcion dentro de la corrida del pedido**: el motivo queda en el chatter de la recepcion; el pedido lo avisa (a).
- **Salida validada a mano de una cadena con el tipo apagado**: no se toca la recepcion.
- **Pedido cancelado despues de la transferencia**: las transferencias hechas quedan hechas (ver NO incluye).

## Criterios de aceptacion

Todos asumen las Precondiciones P1..P6 salvo que el criterio diga otra cosa.

- [x] **CA01**: Con stock suficiente en "Miluan Prueba", confirmar un pedido → no se crea transferencia inter-company; la entrega queda reservada con stock propio.
- [x] **CA02**: "Miluan Prueba" con 3 unidades, "Miluan SRL" con 10, pedido de 5 → salida DEPO → transito por 2 en `done`, recepcion transito → Stock Prueba por 2 en `done`, entrega al cliente por 5 reservada (`assigned`) y sin validar.
- [x] **CA03**: Mismo pedido con "Miluan SRL" con 1 unidad → salida y recepcion por 1 en `done`; backorder de salida por 1 pendiente en Miluan; recepcion por 1 pendiente; un mensaje en el chatter del pedido con el faltante; pedido confirmado.
- [x] **CA04**: Con "Miluan SRL" sin stock → pedido confirmado, salida y recepcion pendientes, mensaje en el chatter del pedido.
- [x] **CA05**: Validar a mano el backorder de salida pendiente (CA03) → su recepcion se valida sola por lo recibido y la entrega al cliente queda reservada por el total.
- [x] **CA06**: Un usuario con acceso solo a "Miluan Prueba" confirma el pedido de CA02 → mismo resultado, sin `AccessError`.
- [x] **CA07**: Con el tipo de recepcion sin activar → la cadena queda como en el core: salida y recepcion pendientes para validar a mano, sin mensajes del modulo.
- [x] **CA08**: Tras CA02, `qty_delivered` de la linea es 0; al validar la entrega al cliente por 5 pasa a 5 (la salida de Miluan no suma).
- [x] **CA09**: Producto con lote, lote "L1" en DEPO → la salida, la recepcion y la reserva de la entrega llevan "L1".
- [x] **CA10**: Reabastecimiento entre dos almacenes de la misma compañia con el flag activado → la recepcion no se valida sola.
- [x] **CA11**: Producto con stock en DEPO cargado **sin lote** y luego pasado a seguimiento por lote, con el tipo de salida de Miluan usando lotes → al confirmar el pedido la salida reserva el quant sin lote y `button_validate()` lanza el `UserError` "You need to supply a Lot/Serial number" (`stock_picking.py:1424`) → el pedido se confirma, la salida queda pendiente sin cambios (savepoint revertido) y hay un mensaje en el chatter del pedido con ese motivo.
- [x] **CA12**: El campo "Auto-Validate Inter-Company Transfer" aparece en el formulario del tipo de operacion solo cuando el tipo es Receipt.
- [x] **CA13**: Con la salida pendiente de CA04 y stock repuesto en Miluan por menos de lo pedido, validarla a mano eligiendo "No Backorder" → la recepcion se valida **una sola vez** por lo recibido, sin error, la salida no se re-valida y no hay mails de confirmacion ni mensajes duplicados.
- [x] **CA14**: Con un backorder de salida pendiente (CA03), bajar la cantidad de otra linea del pedido confirmado → el backorder no se valida solo y no hay mensaje nuevo del modulo.
- [x] **CA16**: En el formulario del almacen de la compañia "Prueba", con ambas compañias activas en el selector, "Reabastecer desde" lista el almacen de la compañia real; al tildarlo y guardar se crea la ruta "Resupply From" inter-company (D20).
- [x] **CA15**: Una regla de reabastecimiento de "Miluan Prueba" que genera la cadena desde "Miluan SRL"; al validar a mano la salida, la recepcion se valida sola; si falla, el motivo queda en el chatter de la recepcion.

## Referencias al core

| Que | Anclaje (`path:L#`) | Por que importa |
|-----|---------------------|-----------------|
| Ruta "Resupply From" entre almacenes | `odoo/addons/stock/models/stock_warehouse.py:702-737` | Arma la cadena salida → transito → recepcion (P2). |
| Ubicacion de transito inter-company | `odoo/addons/stock/data/stock_data.xml:34` | `stock.stock_location_inter_company`, sin compañia (P1). |
| `mts_else_mto` se crea como MTS | `odoo/addons/stock/models/stock_rule.py:305-310` | La entrega no queda vinculada a la recepcion (sin cancelacion en cascada). |
| Movimientos de la cadena creados en `sudo` por compañia | `odoo/addons/stock/models/stock_rule.py:313-314` | Criterio de D10. |
| Referencia propagada a la cadena | `odoo/addons/stock/models/stock_rule.py:368` | D4. |
| `reference_ids` en los valores de procurement | `odoo/addons/stock/models/stock_move.py:1866` | D4. |
| `stock.reference.move_ids` | `odoo/addons/stock/models/stock_reference.py:9` | D4 sin `search` propio. |
| `sale.order.stock_reference_ids` | `odoo/addons/sale_stock/models/sale_order.py:48` | D3 a, D4. |
| `move_dest_ids` solo en MTO | `odoo/addons/stock/models/stock_move.py:1851-1853` | La salida apunta a la recepcion (D2). |
| Cantidad del faltante en `mts_else_mto` | `odoo/addons/stock/models/stock_move.py:1792-1825` | La cadena es solo por lo que falta. |
| Agrupacion de transferencias por referencia | `odoo/addons/stock/models/stock_move.py:1537-1545` | Una salida por pedido (D5). |
| `clean_context` usado por el core | `odoo/addons/stock/models/stock_move.py:1742` | Patron de D9. |
| `clean_context` | `odoo/odoo/tools/misc.py:952-956` | Solo quita `default_*`; el resto lo quita D9. |
| `_should_assign_at_confirm` | `odoo/addons/stock/models/stock_move.py:1975-1976` | P4. |
| `reservation_method` del tipo | `odoo/addons/stock/models/stock_picking.py:68-70` | P4. |
| Cancelacion de no-picked con `cancel_backorder` | `odoo/addons/stock/models/stock_move.py:2266-2268` | Efecto de `create_backorder = never` (D7). |
| Reserva del destino en `sudo` por compañia | `odoo/addons/stock/models/stock_move.py:2304-2307` | La recepcion queda reservada al validar la salida (D8, D10). |
| Backorder al validar | `odoo/addons/stock/models/stock_move.py:2314-2315` | D7. |
| `_action_assign` | `odoo/addons/stock/models/stock_move.py:2053` | Reserva de la salida (D5). |
| `_trigger_assign` | `odoo/addons/stock/models/stock_move.py:2636-2653` | Reserva de la entrega solo MTS `at_confirm` o fecha vencida (D14, P4). |
| `stock.picking._action_done` | `odoo/addons/stock/models/stock_picking.py:1284-1310` | Punto a extender (D3 b); `_trigger_assign` en 1304-1305. |
| Mail de confirmacion de salida | `odoo/addons/stock/models/stock_picking.py:1325-1333` | D18 (1). |
| `_sanity_check`: lote faltante | `odoo/addons/stock/models/stock_picking.py:1424` | Error reproducible de CA11. |
| `button_validate` y `button_validate_picking_ids` | `odoo/addons/stock/models/stock_picking.py:1441-1471` | Re-inclusion por contexto (1455, 1462-1469) que D9 neutraliza. |
| Wizard de backorder con "No Backorder" | `odoo/addons/stock/wizard/stock_backorder_confirmation.py:72-74` | Inyecta `picking_ids_not_to_backorder` (D9, CA13). |
| Wizard de backorder y `skip_backorder` | `odoo/addons/stock/models/stock_picking.py:1516-1534` | Sin wizard (D7). |
| `create_backorder` del tipo | `odoo/addons/stock/models/stock_picking.py:133-139` | D7, P5. |
| `code` del tipo de operacion | `odoo/addons/stock/models/stock_picking.py:42` | `incoming` (D1). |
| `picking_type_code` | `odoo/addons/stock/models/stock_picking.py:625-627` | Filtro de recepciones. |
| `stock_move_email_validation` | `odoo/addons/stock/models/res_company.py:19` | D18 (1). |
| Savepoint con flush y `cr.clear()` | `odoo/odoo/sql_db.py:132-151` | D13. |
| `cr.savepoint()` | `odoo/odoo/sql_db.py:217` | D11. |
| Jerarquia de excepciones | `odoo/odoo/exceptions.py:9-128` | Que se captura y que se propaga (D11). |
| Wizard de SMS y `skip_sms` | `odoo/addons/stock_sms/models/stock_picking.py:10-15` | Contexto de D9. |
| Wizard de lotes vencidos | `odoo/addons/product_expiry/models/stock_picking.py:13-15` | Puede dejar pendiente (D11). |
| Campo `resupply_wh_ids` restringido a la compañia | `odoo/addons/stock/views/stock_warehouse_views.xml:43` | Dominio que D20 reemplaza. |
| Ruta de reabastecimiento entre compañias | `odoo/addons/stock/models/stock_warehouse.py:702-737` | El backend soporta el transito inter-company (D20). |
| `lock_for_update` con `SKIP LOCKED` | `odoo/odoo/orm/models.py:5577-5602` | Por que `LockError` se captura (D11). |
| `LockError` es `UserError` | `odoo/odoo/exceptions.py:109` | D11. |
| El framework no reintenta `LockError` | `odoo/odoo/service/model.py:192` | D11. |
| Impresion automatica posterior al `done` | `odoo/addons/stock/models/stock_picking.py:1472`, `2074-2123` | `button_validate()` puede devolver accion con la transferencia hecha (D11). |
| `uom.uom.round` / `compare` | `odoo/addons/uom/models/uom_uom.py:116-122` | Cantidad faltante (D6). |
| Formulario del tipo de operacion | `odoo/addons/stock/views/stock_picking_type_views.xml:74` | Vista a heredar; ancla `create_backorder` en la linea 106. |
| Validacion inter-company por compañia | `odoo/addons/stock/tests/test_multicompany.py:171-230` | Patron de la cadena con usuarios de una sola compañia. |
| Lote a traves del transito | `odoo/addons/stock/tests/test_multicompany.py:601-690` | D15. |
| Lanzamiento de procurements del pedido | `odoo/addons/sale_stock/models/sale_order_line.py:385-424` | Punto a extender (D3 a). |
| Llamada desde la confirmacion | `odoo/addons/sale_stock/models/sale_order.py:219-220` | `_action_confirm` → `_action_launch_stock_rule`. |
| `sale_line_id` heredado por la cadena | `odoo/addons/sale_stock/models/stock.py:139-141` | D16. |
| `sale_id` de la transferencia | `odoo/addons/sale_stock/models/stock.py:189-195` | D12 (aviso al pedido desde la recepcion). |
| Entregado: solo movimientos de la compañia del pedido | `odoo/addons/sale_stock/models/sale_order_line.py:338` | D16. |
| Transito inter-company cuenta como salida | `odoo/addons/stock/models/stock_location.py:468-474` | Por eso el core clasifica la recepcion como devolucion (D16). |
| Clasificacion de entrantes/salientes | `odoo/addons/sale_stock/models/sale_order_line.py:329-371` | Metodo extendido para D16. |
| Transito sin valorizar | `odoo/addons/stock_account/models/stock_location.py:36-41` | NO incluye asientos. |

## Documentacion afectada

| Archivo | Accion | Que reflejar |
|---------|--------|-------------|
| `sale_stock_intercompany_auto_transfer/README.md` | crear | Objetivo, Precondiciones P1..P6, flag en el tipo de recepcion, comportamiento con faltantes, errores y donde se avisan (D12), alcance de (b) (D17), efectos colaterales (D18), limites. |
| `sale_stock_intercompany_auto_transfer/static/description/index.html` | crear | Idem para usuario funcional. |
| `odoo_customization_sunra/README.md` | actualizar | Fila del modulo nuevo. |

## Plan del cambio en curso

| Tarea | Descripcion | Depende de | Archivos | Cubre |
|-------|-------------|------------|----------|-------|
| **T01** | Scaffold: manifest (`depends`: `sale_stock`, `version` `1.0.0`), `__init__` | — | `__manifest__.py`, `__init__.py`, `models/__init__.py` | — |
| **T02** | Campo `auto_validate_intercompany_transfer` en `stock.picking.type` + vista heredada | T01 | `models/stock_picking_type.py`, `views/stock_picking_type_views.xml`, `__manifest__.py` | CA07, CA12 |
| **T03** | `stock.picking`: `_get_intercompany_auto_receipts()`, `_intercompany_auto_validate_context()`, `_intercompany_auto_validate()` (savepoint, excepciones de D11, relectura de D13, sudo + with_company) y override de `_action_done()` con aviso de D12 | T02 | `models/stock_picking.py` | CA05, CA09, CA10, CA13, CA15 |
| **T04** | `sale.order._intercompany_auto_transfer(new_moves)` (cadena por referencia, reserva, validacion de salidas, aviso unico) + override de `sale.order.line._action_launch_stock_rule()` con diferencia de movimientos antes/despues | T03 | `models/sale_order.py`, `models/sale_order_line.py` | CA01, CA02, CA03, CA04, CA06, CA08, CA11, CA14 |
| **T07** | Helper `stock.move._get_intercompany_auto_dests()` usado por `stock.picking` y `sale.order`; `default=False` explicito del flag | T02 | `models/stock_move.py`, `models/__init__.py`, `models/stock_picking_type.py` | CA02, CA10 |
| **T08** | Vista heredada de `stock.view_warehouse`: dominio de `resupply_wh_ids` sin restriccion de compañia | T01 | `views/stock_warehouse_views.xml`, `__manifest__.py` | CA16 |
| **T05** | Traduccion `es_AR` | T02, T04 | `i18n/es_AR.po` | — |
| **T06** | README + `index.html` del modulo (con Precondiciones y efectos colaterales, P2 con ambas compañias activas), fila en el README raiz, `version` `1.0.0` == spec | T01..T05, T07, T08 | `README.md`, `static/description/index.html`, `../README.md`, `specs/sale_stock_intercompany_auto_transfer.md` | — (anti-drift + version sync) |
