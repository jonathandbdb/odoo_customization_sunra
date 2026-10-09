# sale_stock_intercompany_auto_transfer

Módulo para Odoo 19 que **valida solas** las transferencias inter-company de reabastecimiento
cuando una venta necesita stock de otra compañía. Versión `1.0.0`. Depende de `sale_stock`.

## Objetivo

La ruta "Resupply From" del core arma tres pasos: salida del almacén proveedor, ubicación de
tránsito inter-company y recepción en el almacén destino. El core deja la salida y la recepción para
validar a mano, una en cada compañía. Con este módulo, al confirmar un pedido que dispara esa
cadena, la salida y la recepción quedan hechas por lo que había disponible y la entrega al cliente
queda reservada con lo recibido: el depósito solo valida la entrega al cliente.

Caso de uso: "Miluan Prueba" / "YG Prueba" venden con almacén propio; si no alcanza su stock, la
regla `mts_else_mto` pide el faltante a "Miluan SRL" / "YG S.A." y el traspaso ocurre sin
intervención.

## Uso

Tipo de operación de **recepción** de la compañía destino → opción **Auto-Validate Inter-Company
Transfer** (solo visible en tipos de recepción). Apagada (por defecto) la cadena es la estándar del
core.

## Precondiciones de configuración

El módulo **no** crea esta configuración del core; sin ella no funciona.

| # | Precondición | Por qué |
|---|--------------|---------|
| P1 | Ubicación de tránsito inter-company (`stock.stock_location_inter_company`) activa. | Sin ella no hay ruta inter-company. |
| P2 | Ruta "Resupply From <almacén proveedor>" aplicada al almacén de la compañía destino o a los productos/categorías. "Reabastecer desde" se edita con **ambas compañías activas en el selector**; el módulo quita la restricción de misma compañía del campo. | Arma la cadena salida → tránsito → recepción. |
| P3 | Regla de entrega del almacén destino en `mts_else_mto`. | Pide a la proveedora solo el faltante. |
| P4 | Tipo de **entrega** de la compañía destino con reserva `at_confirm` ("Al confirmar"). | Con otro método la entrega al cliente no se reserva sola con lo recibido. |
| P5 | Tipo de **salida** de la proveedora y tipo de **recepción** de la destino con backorder `ask` o `always`. | Con `never` el faltante de la salida se cancela y la recepción queda esperando un movimiento que no llega. |
| P6 | Opción activada en el tipo de recepción de la compañía destino. | Es el interruptor del módulo. |

## Comportamiento

- **Al confirmar el pedido** (o agregar/aumentar líneas): se reserva el stock en la proveedora y se
  valida la salida por lo reservado; al validarla, la recepción encadenada se valida por lo
  recibido. Solo actúa sobre los movimientos **nuevos** de la cadena creados en esa operación;
  editar otra línea o bajar cantidades no valida backorders preexistentes.
- **Al validar una salida a mano** (cualquier salida cuyo destino es una recepción activada de otra
  compañía), la recepción se valida sola. Alcanza también cadenas originadas por reglas de
  reabastecimiento o fabricación: la opción significa "transferencia inter-company automática" para
  esa compañía destino.
- **Stock insuficiente en la proveedora**: se valida lo disponible y el resto queda como backorder
  pendiente en la proveedora; su recepción se valida sola cuando alguien valide ese backorder. Sin
  nada disponible no se valida nada.
- **Entrega al cliente**: nunca se valida; queda reservada con lo recibido (sujeto a P4).
- **Lotes y series**: no se elige lote; viaja el reservado según la estrategia de remoción.
- Una recepción de la **misma** compañía (reabastecimiento entre almacenes propios) no se toca.
- **Cantidad entregada** del pedido: la salida de la proveedora no suma.

## Errores y avisos

- Un error de negocio al validar (lote faltante, lote vencido, control de calidad, wizard que pide
  intervención) **nunca impide confirmar el pedido** ni la validación manual que lo disparó: la
  transferencia queda pendiente, sin cambios, y se avisa.
- Aviso en el pedido: un solo mensaje con faltantes y transferencias pendientes. Si la recepción
  falla al validar una salida manual, el motivo queda en el chatter de la recepción y, si tiene
  pedido de venta, también en el pedido.
- Los errores de concurrencia o de base de datos no se capturan: se propagan para que el framework
  reintente.

## Efectos colaterales aceptados

1. Si la proveedora tiene activo el mail de confirmación de entrega y la salida es de tipo
   `outgoing`, el core envía el mail al validar la salida.
2. Si la proveedora valoriza en tiempo real, sus asientos de salida se generan sin revisión manual.
3. La opción la configura la compañía **destino** pero mueve stock de la **proveedora**: quien edita
   tipos de operación de la destino decide la salida de la otra compañía.

## Avisos de comportamiento del core

- Bajar la cantidad de una línea confirmada genera una cadena inversa (proveedora → tránsito y
  devolución hacia la recepción de la compañía del pedido) que el módulo no valida.
- Al validar la salida con "No Backorder" queda en la compañía del pedido una recepción backorder
  sin origen, que se cancela a mano.
- Aumentar una línea de un pedido confirmado puede sobre-demandar (core); el módulo valida lo que
  el core generó.
- Si la recepción falla dentro de la corrida del pedido, el motivo queda en el chatter de la recepción.
- La cantidad entregada de la línea ignora la recepción inter-company (no se resta como devolución).

## Seguridad

Sin modelos nuevos: sin ACLs, grupos ni reglas. La validación corre en `sudo()` y en la compañía de
cada transferencia, acotada a la cadena inter-company: quien confirma el pedido puede no tener
acceso a la otra compañía. La opción la edita quien puede editar tipos de operación.

## Límites

- No configura almacenes, rutas ni reglas (P1..P5).
- No crea asientos contables del traspaso.
- No cancela en cascada las transferencias si se cancela el pedido.
- No controla el stock de la proveedora antes de confirmar.
- No valida la entrega al cliente ni backorders de salida preexistentes.
- No cubre cadenas de varios pasos dentro de la proveedora (pick → out).
- Sin tests automatizados (el repo no declara política de tests).

## Traducciones

`i18n/es_AR.po`.
