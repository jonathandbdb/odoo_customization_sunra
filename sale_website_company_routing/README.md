# sale_website_company_routing

Ruteo de líneas de pedido entre compañías al confirmar y stock web por compañía, para bases
multi-compañía donde **un producto lo vende y despacha otra compañía** distinta de la del sitio web.

| | |
|---|---|
| **Versión** | 1.0.0 |
| **Depende de** | `sale_stock`, `website_sale_stock`, `website_sale_collect`, `sale_loyalty` |
| **Repos/entornos** | `odoo_customization_sunra`, rama `develop_19.0` |
| **Spec SDD** | `specs/sale_website_company_routing.md` |

## Para qué sirve

Un sitio web pertenece a una sola compañía y el core crea el carrito siempre en ella, con su almacén,
y muestra solo el stock de ese almacén. Este módulo agrega dos cosas:

1. **Ruteo de líneas por compañía**: cada producto (o su categoría) declara qué compañía lo vende y
   despacha. Al **confirmar** el pedido, las líneas de otra compañía se mueven a un pedido nuevo en
   esa compañía, confirmado y vinculado al original.
2. **Origen del stock web**: cada producto (o su categoría) declara de qué compañías se toma el stock
   que muestra el eCommerce.

Es genérico (no conoce bicis ni a Sunra): **sin configurar, el comportamiento es idéntico al core**.

## Configuración

Las vistas solo muestran los campos con el grupo *Multi-compañía* (`base.group_multi_company`).

- **Producto → pestaña Ventas** y **Categoría de producto**: *Compañía que vende* (`sale_company_id`)
  y *Compañías de stock web* (`website_stock_company_ids`).
- **Resolución**: producto → categoría → **categoría padre** (sube por `parent_path` hasta el primer
  ancestro con valor) → estándar (la compañía del pedido / el almacén del sitio). Aplica igual a los
  dos campos.
- Los productos ruteados siguen con `company_id` vacío, para verse en el sitio.
- **Compañía → pestaña General Information**: *Exclude from Company Routing*
  (`company_routing_excluded`, solo con el grupo *Multi-compañía*). Con la opción activa, los pedidos
  de esa compañía se confirman enteros en ella (sin derivados) y la *Compañía que vende* de sus
  líneas muestra la compañía del pedido. Útil para compañías que venden sin facturar (ej. de
  prueba). Solo mira la compañía del pedido; apagada (default), nada cambia.

### Requisitos de configuración

- Los **métodos de envío** que usa el sitio y sus **productos de flete** van **sin compañía**.
- Los **usuarios portal** de los concesionarios necesitan las dos compañías en `company_ids` para ver
  el pedido original y los derivados.
- Para convertir moneda hace falta **cotización** de la moneda del pedido en la compañía destino,
  vigente a la fecha de confirmación.
- Cada compañía destino necesita al menos un **almacén**, y el cliente y los productos deben ser
  usables en ella (compañía vacía o la destino) y tener **impuestos** en esa compañía.

## Ruteo al confirmar

- Cada línea muestra su *Compañía que vende* (precargada con la resolución anterior, **editable a
  mano** mientras el pedido está en borrador o enviado).
- Al confirmar (desde la web o el backoffice) y **antes** de confirmar el original, las líneas con
  compañía distinta a la del pedido se **recrean** en un pedido nuevo en esa compañía y se borran del
  original. Un pedido derivado por cada compañía destino.
- El derivado lleva el mismo cliente, direcciones y referencia; `origen` = nombre del original; **sin
  sitio web**. Almacén, posición fiscal, plazo de pago y equipo los calcula el core en la compañía
  destino. Se confirma solo, en la misma transacción.
- **Precio**: lista de precios del **cliente en la compañía destino** (su moneda), con el precio
  unitario **convertido** con la cotización de esa compañía a la fecha de confirmación y el mismo
  descuento. Los impuestos se recalculan en la destino.
- **Envío**: las líneas de envío y el `carrier_id` viajan con lo ruteado (con varias compañías
  destino, al derivado de mayor importe sin impuestos). Si al original le quedan productos, se
  confirma sin envío; si solo le quedan secciones, notas o recompensas, se **cancela**. El dato de
  retiro en tienda (`pickup_location_data`) viaja con el método de envío: su almacén debe ser de la
  compañía que se queda con el envío (si no, `UserError`) y se aplica al derivado, con su posición fiscal.
- Secciones, notas, anticipos y líneas de recompensa **no se mueven**; las líneas vinculadas siguen
  a su línea padre.
- **Descuentos globales**: se recalculan en cada pedido sobre sus propias líneas. El original
  conserva sus recompensas de loyalty y las recalcula sobre las líneas que le quedan. El derivado
  recibe solo los programas **automáticos** (los códigos promocionales, cupones de un solo uso,
  tarjetas de regalo, monedero y tarjetas de cliente quedan en el original, con aviso en el
  chatter del derivado). Otros módulos se enganchan con `_company_routing_pre_split()` / `_company_routing_post_split()`
  (`website_sale_payment_method_price` lo hace con el descuento por medio de pago).
- El original y los derivados quedan vinculados: botón inteligente *Routed Orders*, campo *Routed
  From* y mensaje en el chatter de ambos. Con pago online en el original, el aviso indica que el
  cobro quedó en la compañía del original.
- **Si todo el carrito se rutea**, el original se cancela y los códigos promocionales, cupones y
  tarjetas de regalo que quedaban en él **se pierden para esa compra** (solo hay aviso en el chatter
  del derivado). Los programas solo-ecommerce no aplican al derivado y un programa con tope de usos
  puede contar doble.
- Reconfirmar un original ya ruteado no crea derivados nuevos.

### Qué bloquea la confirmación (`UserError`, no se crea nada)

Cliente o producto restringido a otra compañía, producto sin impuestos en la destino, línea de
producto combo, método de envío o flete de otra compañía, falta de cotización, compañía destino sin
almacén (o almacén de otra compañía) y pedido con envío con instalación
(`website_sale_installation_appointment`).

## Stock web por compañía

`website._get_products_free_qty(products)` resuelve el stock libre de varios productos en una sola
pasada (un `search` de almacenes, una consulta de `free_qty` por conjunto de almacenes):

- Sin compañías de stock web: el almacén del sitio, como el core.
- Una compañía: stock libre de todos sus almacenes. Dos o más: suma.
- Compañías sin almacenes: **0** (nunca se pasa una lista vacía de almacenes, que el core lee como
  "todos").

Lo usan `_get_product_available_qty` (ficha, combinación, listados) y `sale.order._get_free_qty`
(tope y avisos del carrito), y el semáforo de `website_sale_stock_level_indicator`. Corre en
`sudo()` porque el visitante no lee los quants de otra compañía.

## Gotchas

- **El ruteo crea líneas nuevas**, no reasigna `order_id`: `company_id` de la línea es *related*
  almacenado y los impuestos de origen no pasan el `check_company` de la destino.
- **El derivado no lleva `website_id`**: `website_sale_stock` le forzaría el almacén del sitio.
- **`price_unit` y `discount` se escriben explícitos** en el `create` de la línea: el core los trata
  como precio manual y no los recalcula.
- **Sin cotización el core convierte en silencio** (usa la más vieja o 1): por eso se valida antes
  de crear nada.
- **Con `website_sale_collect` instalado**, para productos con compañías de stock web el helper
  reemplaza el cálculo de Click & Collect; los productos sin configurar siguen su lógica.
- **Instalación sobre datos existentes**: un `pre_init_hook` crea y completa
  `sale_order_line.sale_company_id` por SQL para no recalcular todo el histórico.

## Límites (NO incluye)

Partir el carrito antes de confirmar, reglas inter-company, redistribuir pagos online, rutear líneas
agregadas a un pedido ya confirmado, pedidos con envío con instalación o líneas de combo, y dar
acceso multi-compañía a usuarios portal.

## Validación manual

1. Configurar una categoría con *Compañía que vende* = otra compañía y un producto sin valor propio:
   la línea del pedido muestra esa compañía.
2. Confirmar un pedido web mixto: el original queda solo con las líneas propias, y el derivado se
   confirma en la otra compañía con su lista de precios, moneda convertida y almacén.
3. Pedido solo con productos de la otra compañía y envío: el derivado lleva el envío y el original
   se cancela.
4. Configurar *Compañías de stock web* en un producto: la ficha muestra el stock de esas compañías.
