# Spec de modulo: sale_website_company_routing

| Campo | Valor |
|-------|-------|
| **Modulo** | `sale_website_company_routing` |
| **Version** | `1.0.1` (== `version` del `__manifest__.py`, formato `x.x.x`) |
| **Serie Odoo** | `19` (informativa) |
| **Estado** | `implemented` |
| **Actualizado** | `2026-10-06` |
| **Depurado** | `2026-10-06` |

## Objetivo

En una base multi-compañia, un sitio web pertenece a una sola compañia y el core crea el carrito
siempre en esa compañia (`website.py:676`), con su almacen (`check_company` en
`sale_stock/models/sale_order.py:27-30`) y mostrando solo el stock de ese almacen. Este modulo
permite que un producto **lo venda y despache otra compañia** distinta de la del pedido, y que la
web **muestre el stock de la compañia que realmente lo tiene**:

1. **Ruteo de lineas por compañia**: cada producto (o su categoria) declara la compañia que lo
   vende/despacha. Cada linea del pedido muestra esa compañia (editable a mano) y, al **confirmar**,
   las lineas de otra compañia se mueven a un **pedido nuevo en esa compañia**, que se confirma y
   queda vinculado al original. Una factura por compañia, cada una con su almacen, lista de
   precios, moneda, impuestos y posicion fiscal. Los descuentos globales se recalculan en cada
   pedido sobre sus propias lineas.
2. **Origen del stock web**: cada producto (o su categoria) declara de que compañias se toma el
   stock que muestra el eCommerce (disponibilidad, "sin stock", tope al agregar al carrito y el
   semaforo de `website_sale_stock_level_indicator`).

Es generico (no conoce bicis ni a Sunra): sin configurar, el comportamiento es identico al core.

## Decisiones vigentes

| # | Decision | Valor vigente |
|---|----------|---------------|
| D1 | ¿Donde se declara la compañia que vende/despacha? | En `product.template.sale_company_id` y `product.category.sale_company_id`. Resolucion: producto → categoria → **estandar** (la compañia del pedido). |
| D2 | ¿La categoria hereda de su categoria padre? | `[ASUNCION]` **Si**: si la categoria del producto esta vacia se sube por `parent_path` hasta el primer ancestro con valor. Aplica igual a `sale_company_id` y a `website_stock_company_ids`. |
| D3 | ¿Que ve y edita el usuario en el pedido? | Cada linea lleva `sale_company_id` (compute almacenado, `readonly=False`, `recursive=True` por depender de la linea padre), precargado con la resolucion de D1 y **editable a mano**. El compute solo actua en pedidos `draft`/`sent`; en pedidos confirmados o cancelados conserva su valor. |
| D4 | ¿Cuando se mueven las lineas? | Al **confirmar** el pedido (`action_confirm`), venga de la web o del backoffice, **antes** de que el core confirme el original. Nunca durante el carrito. |
| D5 | ¿Como se mueven? | Se **crean lineas nuevas** en el pedido derivado y se **borran** las del original (no se reescribe `order_id`: `company_id` de la linea es related almacenado y los impuestos de origen no pasan el `check_company` de la destino). |
| D6 | ¿Un pedido por compañia destino? | **Si**: un derivado por cada compañia destino distinta de la del original. |
| D7 | Cabecera del pedido derivado | Mismo cliente, direccion de factura y de entrega, `client_order_ref`, `origin` = nombre del original. **Sin `website_id`** (si lo llevara, `website_sale_stock` le forzaria el almacen del sitio, de otra compañia). Almacen, posicion fiscal, plazo de pago y equipo salen de los computes del core **en la compañia destino**. |
| D8 | Precio de la linea derivada | **Mismo `price_unit`** (convertido segun D9) **y mismo `discount`** que la linea del carrito, escritos explicitos en el `create`: el core los trata como precio manual (`technical_price_unit` = `price_unit`) y no los recalcula. Los impuestos se recalculan en la compañia destino. |
| D9 | Lista de precios / moneda del derivado | **Siempre** la lista de precios del cliente **en la compañia destino** (`property_product_pricelist` con `with_company`); la moneda del derivado es la de esa lista (para Miluan, ARS). El `price_unit` se **convierte** de la moneda del original a la del derivado con `res.currency._convert`, a la **fecha de confirmacion** y con las cotizaciones de la compañia destino (BNA en Miluan). Misma moneda → sin conversion. Sin lista del cliente en la destino → moneda de la compañia destino. La validacion de cotizacion y el `_convert` corren en `sudo()`: el core solo lee las cotizaciones en `sudo` si la compañia esta entre las del usuario (`res_currency.py:279-280`) y sin cotizacion devuelve en silencio la mas vieja o 1 (`res_currency.py:138`). |
| D10 | Vendedor del derivado | `[ASUNCION]` Se copia `user_id` del original solo si la compañia destino esta entre las compañias permitidas del vendedor; si no, queda el que calcule el core por el cliente. |
| D11 | Plazo de pago del derivado | `[ASUNCION]` El del cliente en la compañia destino (lo que calcula el core). La cuenta corriente del concesionario se configura por compañia. |
| D12 | ¿El derivado se confirma solo? | **Si**, en la misma transaccion. Si su confirmacion falla, falla la confirmacion completa. |
| D13 | Lineas que no se mueven nunca | Secciones/notas (`display_type`), anticipos (`is_downpayment`) y lineas de recompensa de loyalty (`reward_id`): se quedan en el original, que recalcula sus descuentos (D26/D27). Las de envio siguen D15; el resto se rutea por su producto. |
| D14 | Lineas vinculadas (`linked_line_id`) | Siguen a su linea padre y se mueven juntas, re-vinculadas en el derivado. Las lineas de **producto combo** que tendrian que moverse bloquean la confirmacion (`UserError`). |
| D15 | ¿Donde va el envio y que pasa con el original? | Si hay al menos una linea ruteada, las lineas `is_delivery` van **siempre** con lo ruteado: se recrean en el derivado con `is_delivery=True` (precio convertido como D9) y el derivado recibe el `carrier_id` del original. Con **una** compañia destino van a ese derivado; con **varias**, `[ASUNCION]` al derivado de **mayor importe sin impuestos** (empate: el primero en crearse). Si al original le quedan productos se confirma **sin envio** (y sin `carrier_id`); si solo le quedan secciones, notas o recompensas se **cancela** (`_action_cancel`) con mensaje en el chatter de ambos. |
| D16 | Carrier incompatible con la compañia destino | `[ASUNCION]` Si el `carrier_id` del original (o el producto de su linea de envio) tiene una compañia distinta de la destino → `UserError` antes de crear nada. **Requisito de configuracion**: los metodos de envio que usa el sitio y sus productos de flete van **sin compañia**. |
| D17 | Envio con instalacion | Un pedido cuyo `carrier_id` tiene `installation_appointment_type_id` (`website_sale_installation_appointment`) y lineas para rutear → `UserError` claro antes de crear nada. No se rutea, asi que tampoco se trasladan las pilas sin cargo de ese envio. Lo implementa `website_sale_installation_appointment` sobreescribiendo el hook `_company_routing_validate()` de este modulo. |
| D18 | Idempotencia | Solo se procesan lineas cuya compañia ≠ la del pedido; una vez movidas ya no existen en el original. Los derivados se confirman con la clave de contexto `sale_website_company_routing_skip=True`. |
| D19 | Permisos al crear el derivado | Se crea y confirma con `sudo().with_company(destino)`: lo dispara el flujo web (publico/portal) o un usuario de backoffice que puede no tener acceso a la destino. El `check_company` del core sigue aplicando. El chatter del derivado deja quien confirmo el original. |
| D20 | Usuarios portal de concesionarios | **Configuracion, sin codigo**: deben tener las dos compañias (YG y Miluan) en `company_ids` para ver en el portal el pedido original y los derivados. |
| D21 | Pago online en el original | `[ASUNCION]` No se bloquea: se rutea igual y se avisa en el chatter de ambos que el cobro quedo en la compañia del original. El circuito previsto es cuenta corriente. |
| D22 | ¿Donde se declara el stock web? | `website_stock_company_ids` (Many2many `res.company`) en `product.template` y `product.category`, misma resolucion que D1/D2. **Vacio** = estandar (almacen del sitio). **Una** compañia = stock libre de todos sus almacenes. **Dos o mas** = suma. Compañias sin almacenes → stock **0** (nunca se pasa `warehouse_id=[]`, que el core interpretaria como "todos los almacenes de las compañias activas", `stock/models/product.py:390-392`). |
| D23 | ¿Que superficies de la web respetan el stock web? | `website._get_product_available_qty` (ficha, combinacion, listados, feeds) y `sale.order._get_free_qty` (tope y avisos del carrito). Ambas delegan en el helper por lotes `website._get_products_free_qty(products)` cuando el producto tiene compañias de stock web; si no, `super()` (con Click & Collect, D33). En `sale.order._get_free_qty`, un pedido sin `website_id` va siempre a `super()`. |
| D24 | Helper por lotes | Por llamada: **un** `stock.warehouse.search` para todas las compañias involucradas, resolucion de categorias agrupada (una lectura de ancestros por categoria distinta) y una consulta de `free_qty` por conjunto de almacenes. La resolucion de compañias de stock por plantilla y el `free_qty` por sitio y producto se **memorizan por request** (`tools.get_request_memo`; fuera de un request no memorizan): la grilla de la tienda consulta un producto por vez y la ficha lo consulta varias veces. |
| D25 | Semaforo `website_sale_stock_level_indicator` | `[ASUNCION]` **El indicador se ajusta** (version `1.1.0`): depende de este modulo, resuelve las cantidades de la pagina una sola vez y las memoriza por request (atributo `wsli_free_qty_memo` en `request`, clave = sitio + ids de las variantes de la pagina); cada tarjeta lee de esa memoria. Las variantes con compañias de stock web van al helper por lotes; el resto, al calculo estandar del sitio (`website._get_product_available_qty`), que respeta Click & Collect. Sin modulo puente. |
| D26 | Descuentos globales | Se **recalculan** en cada pedido sobre sus propias lineas, **antes** de confirmar los derivados. Mecanismo: hooks `_company_routing_pre_split()` (devuelve un `dict` de estado, antes de repartir las lineas) y `_company_routing_post_split(derived_orders, state)` (despues de repartirlas). |
| D27 | ¿Donde vive cada re-aplicado? | `[ASUNCION]` **Loyalty** (`sale_loyalty`, core, instalado): en este modulo, que depende de `sale_loyalty`. Las lineas de recompensa **no se borran ni se mueven** (D13). El original (si no queda cancelado) llama `_update_programs_and_rewards()` y recalcula sobre las lineas que conserva. En cada derivado se re-aplican **solo** los programas con `trigger == 'auto'`, que no sean de pago (`is_payment_program`: tarjeta de regalo, monedero) ni nominativos (`is_nominative`: tarjetas de cliente) y cuya compañia sea vacia o la del derivado: `_update_programs_and_rewards()` genera el cupon propio del derivado y se aplica la recompensa con `_get_claimable_rewards()` / `_apply_program_reward()`; nunca se usa un cupon del original (sin doble consumo ni cupones borrados). Codigos promocionales, cupones de un solo uso, tarjetas de regalo, monedero y tarjetas de cliente quedan en el original, con aviso en el chatter del derivado por cada recompensa del original que el derivado no recibe. **Descuento por medio de pago**: en `website_sale_payment_method_price` (pasa a depender de este modulo, version `1.4.0`), que sobreescribe los hooks: guarda `payment_price_rule_id` en `state['payment_price_rule_id']`, llama `_remove_payment_price_rule()` y luego `_apply_payment_price_rule(rule)` en cada pedido (con `wspmp_website_id` en contexto, porque el derivado no tiene sitio). Cada modulo es dueño de su descuento; este modulo no conoce los campos ajenos. |
| D28 | Validacion de impuestos | Cada linea ruteada (no nota), incluidas las de envio que viajan con el grupo, debe resolver al menos un impuesto en la compañia destino (`taxes_id` filtrado por la destino); si no, `UserError`. |
| D29 | Almacen del derivado | Lo resuelve el compute del core (`ir.default` de `sale.order.warehouse_id` en la destino, o su primer almacen). Despues de crear se valida que `warehouse_id.company_id` sea la destino; si no, `UserError`. Hoy hay un almacen por compañia (WH en YG, DEPO en Miluan). |
| D30 | Instalacion sobre datos existentes | `pre_init_hook` crea la columna `sale_order_line.sale_company_id` y la completa por SQL con `company_id`, asi el ORM no recalcula todo el historico al instalar. |
| D31 | Lectura de la compañia de la linea sin acceso a ella | Los campos Python **no** llevan `groups`: el compute y el ruteo corren para cualquier usuario sin depender de un grupo de lectura. El cliente web lee el `display_name` de los Many2one en `sudo` (`web/models/models.py:152-154`), asi que un usuario sin acceso a la compañia ve el nombre sin `AccessError`. El desplegable solo ofrece las compañias que el usuario puede leer. |
| D32 | Visibilidad e idioma | La UI oculta los campos nuevos sin `base.group_multi_company`: el grupo va **solo en las vistas**. UI en ingles con `_()`, traduccion en `i18n/es_419.po`. |
| D33 | Dependencia de `website_sale_collect` | Depende de `website_sale_collect` (instalado en produccion) para quedar **por encima** en el MRO de `website._get_product_available_qty`: con compañias de stock web gana el helper; sin configuracion `super()` aplica la logica de Click & Collect. |
| D34 | Datos de retiro en tienda | `pickup_location_data` (de `website_sale_collect`) viaja con el `carrier_id` al derivado que se queda con el envio y se limpia en el original. **Antes de crear nada** se valida que el almacen de `pickup_location_data['id']` sea de la compañia que se queda con el envio (`UserError` si no). En el derivado se imita `_set_pickup_location` de `website_sale_collect`: `warehouse_id` = el de la pickup, `_compute_fiscal_position_id()` y, si cambia la posicion fiscal, `_recompute_taxes()`; despues se valida el almacen (D29). Aplica solo a transportistas `delivery_type == "in_store"`: otros transportistas con punto de retiro guardan en `pickup_location_data` un id externo, no un `stock.warehouse` (`website_sale_collect/models/sale_order.py:L72`). |

## Alcance

### Incluye
- Campos "compañia que vende/despacha" y "compañias de stock web" en producto y categoria, con herencia por categoria padre.
- `sale_company_id` visible y editable en cada linea del pedido.
- Ruteo al confirmar: derivado por compañia destino, confirmado, con lista de precios del cliente en la destino y precio convertido, vinculado al original (campo, boton y chatter).
- Envio y carrier con lo ruteado; cancelacion del original vacio.
- Recalculo de descuentos globales de loyalty en cada pedido (programas automaticos); hooks para otros descuentos.
- Stock web por compañia en ficha, listados, tope del carrito y semaforo.
- Ajustes en otros modulos del repo: `website_sale_stock_level_indicator` (`1.1.0`), `website_sale_payment_method_price` (`1.4.0`), `website_sale_installation_appointment` (`1.17.0`).

### NO incluye
- **Partir el carrito** antes de confirmar.
- **Reglas inter-company** (compra/venta espejo entre compañias).
- Redistribuir **pagos online** entre pedidos (D21).
- Rutear lineas agregadas a un pedido ya confirmado.
- Rutear pedidos con **envio con instalacion** (D17) ni lineas de **combo** (D14).
- Carriers o productos de flete con compañia distinta de la destino (D16).
- Dar acceso multi-compañia a los usuarios portal (configuracion, D20).
- Cambiar el `company_id` del producto: los productos ruteados siguen con `company_id` vacio para verse en el sitio (`website.py:662`).
- Rutas de abastecimiento/fabricacion (estandar en la destino, ej. `mts_else_mto`).
- Selector armada/en caja (`website_sale_bike_assembly_option`).
- **Tests automatizados**: el repo no declara politica de tests (`.swarm.conf` ausente).

## Modelos

### Nuevos

No aplica: el modulo solo extiende modelos del core.

### Extendidos

| Modelo | `_inherit` | Que se agrega |
|--------|-----------|---------------|
| `product.category` | `product.category` | `sale_company_id`, `website_stock_company_ids` + resolucion por ancestros. |
| `product.template` | `product.template` | `sale_company_id`, `website_stock_company_ids` + resolucion producto → categoria. |
| `sale.order.line` | `sale.order.line` | `sale_company_id` + hooks de resolucion y de valores para recrear la linea. |
| `sale.order` | `sale.order` | Vinculo original ↔ derivados, `action_confirm()`, ruteo, hooks de validacion y descuentos, re-aplicado de loyalty, `_get_free_qty()`. |
| `website` | `website` | Helper `_get_products_free_qty()` (+ `_compute_products_free_qty()` sin memoria) y `_get_product_available_qty()`. |

Utilidad `tools.get_request_memo(name)`: diccionario que vive lo que dura el request HTTP (fuera de un request devuelve uno nuevo, sin memoria); lo usan este modulo y `website_sale_bike_assembly_option`.

## Campos

| Modelo | Campo | Tipo | String | Requerido | Default | Restricciones / notas |
|--------|-------|------|--------|-----------|---------|----------------------|
| `product.category` | `sale_company_id` | Many2one `res.company` | Selling Company | No | - | `ondelete='set null'`. Vacio = la del ancestro o la del pedido. |
| `product.category` | `website_stock_company_ids` | Many2many `res.company` | Website Stock Companies | No | - | Relacion `product_category_website_stock_company_rel`. Vacio = la del ancestro o almacen del sitio. |
| `product.template` | `sale_company_id` | Many2one `res.company` | Selling Company | No | - | `ondelete='set null'`. Vacio = la de la categoria. |
| `product.template` | `website_stock_company_ids` | Many2many `res.company` | Website Stock Companies | No | - | Relacion `product_template_website_stock_company_rel`. Vacio = la de la categoria. |
| `sale.order.line` | `sale_company_id` | Many2one `res.company` | Selling Company | No | compute | `compute='_compute_sale_company_id'`, `store=True`, `readonly=False`, `precompute=True`, `recursive=True`. Vacio en lineas `display_type`. Inicializada por `pre_init_hook` (D30). |
| `sale.order` | `company_routing_origin_id` | Many2one `sale.order` | Routed From | No | - | `readonly=True`, `copy=False`, `index='btree_not_null'`, `ondelete='set null'`. |
| `sale.order` | `company_routing_order_ids` | One2many (`sale.order`, `company_routing_origin_id`) | Routed Orders | No | - | Derivados del pedido. |
| `sale.order` | `company_routing_order_count` | Integer (compute) | Routed Orders Count | No | - | No almacenado; boton inteligente. |

## Metodos

### `pre_init_hook(env)`
- **Proposito**: D30.
- **Logica**: `ALTER TABLE sale_order_line ADD COLUMN IF NOT EXISTS sale_company_id int4` + `UPDATE sale_order_line SET sale_company_id = company_id WHERE display_type IS NULL`.

### `ProductCategory._get_sale_company()` / `_get_website_stock_companies()`
- **Logica**: recorrer la categoria y sus ancestros (`parent_path`, del mas cercano al mas lejano) y devolver el primer valor no vacio. Version por lotes `_get_routing_values_by_category()` → `dict {categ.id: (sale_company, stock_companies)}` para el helper (D24). Un recordset vacio (producto sin categoria) devuelve compañia vacia, sin `ensure_one`.
- **Retorna**: `res.company` (vacio si nadie lo define).

### `ProductTemplate._get_sale_company()` / `_get_website_stock_companies()`
- **Logica**: `self.sale_company_id or self.categ_id._get_sale_company()`; las compañias de stock web salen de la version por lotes `_get_website_stock_companies_by_template()` (memorizada por request, D24). Desde la web se invocan en `sudo()`.

### `SaleOrderLine._get_routing_product_company()`
- **Proposito**: hook de la compañia que aporta el producto (lo extiende `website_sale_bike_assembly_option`).
- **Logica**: `self.product_id.product_tmpl_id.sudo()._get_sale_company()`; una linea sin producto (recien agregada en el formulario) devuelve compañia vacia, sin `ensure_one`.

### `SaleOrderLine._compute_sale_company_id()`
- **Decoradores**: `@api.depends('product_id', 'order_id.company_id', 'linked_line_id.sale_company_id', 'display_type')`
- **Logica**: solo lineas de pedidos `draft`/`sent` (o sin pedido guardado); el resto conserva su valor. `display_type` → `False`; con `linked_line_id` → la del padre; si no, `_get_routing_product_company() or order_id.company_id`.

### `SaleOrderLine._prepare_company_routing_values(target_order, convert)`
- **Proposito**: valores para recrear la linea en el derivado. Hook extensible.
- **Logica**: `product_id`, `name`, `product_uom_qty`, `product_uom_id`, `price_unit` = `convert(price_unit)` (D9), `discount`, `sequence`, `customer_lead`, `is_delivery`, `product_no_variant_attribute_value_ids`, `product_custom_attribute_value_ids` (recreados), `route_ids` filtradas a compañia vacia o destino, `sale_company_id` = destino. Sin `tax_ids` (los recalcula el core) ni analitica.
- **Retorna**: `dict`.

### `SaleOrder.action_confirm()` (override)
- **Logica**: con `sale_website_company_routing_skip` en contexto → `super()`. Si no: `cancelled = self._company_routing_split()`; `super(SaleOrder, self - cancelled).action_confirm()`.

### `SaleOrder._company_routing_validate(groups)`
- **Proposito**: hook de validaciones extra antes de crear (lo usa `website_sale_installation_appointment`, D17).
- **Retorna**: mensaje de error o `False`.

### `SaleOrder._company_routing_pre_split()` / `_company_routing_post_split(derived_orders, state)`
- **Proposito**: hooks de descuentos globales (D26/D27).
- **Logica en este modulo (loyalty)**: *pre* guarda en `state['loyalty']` los ids de las recompensas aplicadas en el original, sin tocar lineas; *post*: el original, si conserva lineas de producto (`_company_routing_has_product_lines()`), `_update_programs_and_rewards()`; cada derivado, `_company_routing_reapply_loyalty(state['loyalty'])`.

### `SaleOrder._company_routing_split()`
- **Logica**, por cada pedido en `draft`/`sent`:
  1. Candidatas: lineas sin `display_type`, sin `is_downpayment`, sin `is_delivery`, sin `reward_id`, con `sale_company_id` ≠ `company_id`. Sin candidatas → siguiente pedido.
  2. Agrupar por compañia destino (las vinculadas con su padre); asignar las lineas `is_delivery` al grupo de D15.
  3. **Validar todo antes de crear nada**, `UserError` con linea, compañia o moneda/fecha:
     - destino con al menos un almacen; cliente y productos usables por la destino;
     - ninguna candidata de tipo combo (D14);
     - cada linea a recrear (candidatas y envio) con al menos un impuesto en la destino (D28);
     - carrier y producto de flete compatibles con la destino (D16);
     - cotizacion de la moneda del original con `company_id` vacio o la raiz de la destino y fecha ≤ fecha de confirmacion, en `sudo()` (D9);
     - si hay `carrier_id` y `pickup_location_data`, el almacen de retiro es de la compañia que se queda con el envio (D34);
     - `self._company_routing_validate(groups)` (D17).
  4. `state = self._company_routing_pre_split()`.
  5. Por grupo: crear el derivado con `sudo().with_company(destino)` y `_prepare_company_routing_order_values(destino)`; validar su almacen (D29); crear sus lineas con `_prepare_company_routing_values(derivado, convert)`, `convert` = `_convert` en `sudo()` (D9), re-vinculando `linked_line_id`; borrar las lineas del original. Si el grupo lleva el envio (`if carrier`), `carrier_id` y `pickup_location_data` del original al derivado, con `warehouse_id` de la pickup y posicion fiscal recalculada (D34), y nueva validacion del almacen y ambos vaciados en el original.
  6. `self._company_routing_post_split(derivados, state)`.
  7. `message_post` en original y derivados con los links cruzados (y el aviso de D21 si hay transacciones de pago).
  8. Confirmar los derivados con `with_context(sale_website_company_routing_skip=True).action_confirm()`, propagando `send_email`.
  9. Si al original no le queda ninguna linea de producto (solo secciones, notas o recompensas) → `_action_cancel()`.
- **Retorna**: `sale.order` cancelados.

### Auxiliares de `SaleOrder` (privados)
- `_company_routing_split_order()`: un pedido (los pasos 1 a 9 de arriba); devuelve `True` si el original quedo cancelado. `_company_routing_split()` lo recorre por pedido, de modo que los hooks de descuentos se invocan con un solo pedido en `self`.
- `_company_routing_get_groups()`: paso 1-2, agrupa por compañia destino; la compañia de una linea vinculada es la de su linea padre raiz.
- `_company_routing_get_delivery_company(groups)`: D15, compañia que se queda con el envio.
- `_company_routing_validate_group(company, lines, date)`, `_company_routing_check_rates(company, date)`, `_company_routing_validate_carrier(company)`: validaciones del paso 3 (almacen, cliente, producto, combo, impuestos, cotizacion de la moneda del pedido y de la del derivado cuando no es la de la compañia, carrier y flete).
- `_company_routing_get_pricelist(company)`: lista de precios del cliente en la destino (D9).
- `_company_routing_create_order(company, lines, date)`: paso 5; las lineas con `linked_line_id` se crean despues de su padre, con el padre ya re-vinculado en el `create`.
- `_company_routing_notify(derived_orders)`: paso 7.
- `_company_routing_has_product_lines()`: el pedido conserva alguna linea sin `display_type` ni `reward_id` (los modulos que agregan lineas de descuento propias lo extienden para excluirlas).
- `_company_routing_loyalty_skip_reason(program)`: motivo por el que un programa no se re-aplica en el derivado (D27), o `False`.
- `_company_routing_reapply_loyalty(reward_ids)`: re-aplicado de loyalty en el derivado (D27), con `with_company` del pedido; usa solo el cupon que el derivado genera para el programa (`coupon_point_ids`, `exists()`) y avisa en su chatter de cada recompensa que no recibe.
- `_company_routing_validate_pickup(company)`: el almacen de retiro es de la compañia del envio (D34); `_company_routing_set_pickup_warehouse()`: aplica la pickup al derivado (D34).
- `_company_routing_check_warehouse(company)`: el almacen del derivado es de la compañia destino (D29/D34).
- `Website._has_website_stock_companies(product)` y `ProductTemplate._get_website_stock_companies_by_template()` (version por lotes de la resolucion de D22).

### `SaleOrder._prepare_company_routing_order_values(company)`
- **Logica**: `company_id`, `partner_id`, `partner_invoice_id`, `partner_shipping_id`, `client_order_ref`, `origin`, `company_routing_origin_id`, `pricelist_id` = `partner_id.with_company(company).property_product_pricelist` (D9), `user_id` (D10). Sin `website_id`, `warehouse_id`, `fiscal_position_id`, `payment_term_id` ni `team_id`.

### `SaleOrder.action_view_company_routing_orders()`
- **Proposito**: boton inteligente: abre los derivados (o el original desde un derivado).

### `SaleOrder._get_free_qty(product)` (override de `website_sale_stock`)
- **Logica**: sin `website_id` → `super()`. Con compañias de stock web → `self.website_id._get_products_free_qty(product)[product.id]`; si no, `super()`.

### `Website._get_products_free_qty(products)`
- **Logica** (D22/D24):
  1. `products = products.sudo()`; resolver compañias de stock web en lote (plantillas + categorias agrupadas).
  2. Un `stock.warehouse.search([('company_id', 'in', todas)])` en `sudo`; mapear almacenes por compañia.
  3. Por producto: almacenes de sus compañias; si tiene compañias pero ningun almacen → `0.0` sin consultar; si no tiene compañias → `self.warehouse_id.id` (criterio del core).
  4. Agrupar por tupla ordenada de almacenes y leer `free_qty` con `with_context(warehouse_id=list(ids))` una vez por grupo.
- **Retorna**: `dict {product.id: free_qty}`.
- **Por que `sudo()`**: el visitante y la compañia del sitio no leen los quants de la otra compañia; solo lectura de cantidades, igual que el core (`product_template.py:68-70`).

### `Website._get_product_available_qty(product, **kwargs)` (override)
- **Logica**: con compañias de stock web → helper; si no, `super()`.

## Vistas

- `product_category_view_form` (hereda `product.product_category_form_view`): ambos campos despues de `parent_id`, `groups="base.group_multi_company"`.
- `product_template_view_form` (hereda `sale.product_template_form_view`): ambos campos en la pestaña **Ventas** (`page[@name='sales']`), con `placeholder` "From category", `groups="base.group_multi_company"`.
- `sale_order_view_form` (hereda `sale.view_order_form`):
  - Columna `sale_company_id` en la lista de `order_line` despues de `product_uom_qty`, `optional="show"`, `readonly="parent.state not in ('draft', 'sent')"`, `invisible="display_type"`, `groups="base.group_multi_company"`; idem en el form de linea, despues de `div[@name='ordered_qty']`.
  - Boton inteligente "Routed Orders" (`company_routing_order_count`), invisible si es 0.
  - `company_routing_origin_id` en "Other Info", junto a `origin`, invisible si esta vacio.

## Seguridad

- **Sin modelos nuevos** → sin ACLs nuevas. Sin grupos ni record rules nuevos.
- `sudo()` acotado a: lectura de stock para la web (D22-D24), creacion/confirmacion de derivados (D19) y cotizaciones (D9).
- Lectura del `display_name` de la compañia de la linea sin `AccessError` (D31).
- Requisito de configuracion de usuarios portal (D20).

## Reglas de negocio

1. **RB01**: Compañia de una linea = la de su producto; si vacia, la de su categoria o el primer ancestro con valor; si vacia, la del pedido.
2. **RB02**: La compañia de la linea se puede cambiar a mano en borrador/enviado; el cambio se respeta al confirmar.
3. **RB03**: Al confirmar, toda linea con compañia ≠ la del pedido termina en un pedido confirmado de su compañia, con la lista de precios del cliente en esa compañia y el precio unitario convertido a su moneda con la cotizacion de esa compañia a la fecha de confirmacion.
4. **RB04**: Un derivado por compañia destino, vinculado al original (campo, boton y chatter).
5. **RB05**: Secciones, notas y anticipos nunca se mueven; las lineas vinculadas siguen a su padre.
6. **RB06**: Si hay lineas ruteadas, el envio y el carrier van con ellas (con varios destinos, al de mayor importe sin impuestos); el original se confirma sin envio o se cancela si quedo sin productos.
7. **RB07**: Si una validacion falla (cliente, producto, impuestos, combo, carrier, cotizacion, envio con instalacion, almacen), no se crea ningun derivado y el pedido no se confirma.
8. **RB08**: Los descuentos globales se recalculan en cada pedido sobre sus propias lineas: loyalty en el original y, en el derivado, solo los programas automaticos (D27); el descuento por medio de pago en cada pedido.
9. **RB09**: El stock web de un producto con compañias de stock web es la suma del stock libre de todos sus almacenes (0 si no tienen almacenes); sin configurar, el del almacen del sitio.

## Edge cases

- **Producto sin configuracion**: linea con la compañia del pedido, no se mueve; stock web estandar.
- **Pedido entero de otra compañia**: el original se cancela; queda un derivado con el envio.
- **Pedido mixto con envio**: el envio y el carrier van al derivado; el original se confirma sin envio.
- **Varias compañias destino con envio**: el envio va al derivado de mayor importe sin impuestos.
- **Carrier de otra compañia** (ej. "Retira por el local", de Miluan, en un pedido que rutea a otra compañia): `UserError` (D16).
- **Envio con instalacion** con lineas para rutear: `UserError` (D17).
- **Sin cotizacion** de la moneda del carrito en la destino a la fecha: `UserError` con moneda y fecha; nada se crea.
- **Cliente sin lista de precios en la destino**: moneda de la compañia destino; el precio se convierte igual.
- **Producto sin impuestos en la destino**: `UserError` (D28).
- **Cliente o producto restringido a otra compañia**: `UserError`.
- **Compañia destino sin almacen, o almacen resultante de otra compañia**: `UserError` (D29).
- **Programa de loyalty que el derivado no puede recibir** (codigo promocional, cupon de un solo uso, tarjeta de regalo, monedero, tarjeta de cliente, o programa de la compañia del original): queda en el original; aviso en el chatter del derivado.
- **Todo el carrito se rutea**: el original se cancela y los codigos promocionales, cupones y tarjetas de regalo que quedaban en el original se pierden para esa compra (solo hay aviso en el chatter del derivado). Si ademas hay descuento por medio de pago, no se re-aplica al original cancelado (solo a pedidos con lineas de producto).
- **Programas solo-ecommerce**: no aplican al derivado (no tiene `website_id`).
- **Cupon pendiente (`_try_pending_coupon`)**: no se traslada al derivado.
- **`limit_usage`**: un programa con tope de usos puede contar doble (original y derivado) si se re-aplica automatico en ambos.
- **Retiro en tienda con almacen de otra compañia**: `UserError` antes de crear nada (D34).
- **Reconfirmar o reintentar**: sin candidatas no se crea nada (D18).
- **Usuario de backoffice sin acceso a la destino**: el derivado se crea igual; ve el nombre de la compañia en la linea y el del derivado en el chatter.
- **Pedido con pago online**: se rutea y se avisa (D21).
- **`website_sale_collect`** (dependencia, D33): para productos con compañias de stock web, el helper reemplaza el calculo de Click & Collect (maximo entre tiendas y almacen del punto de retiro elegido); la disponibilidad mostrada es la de las compañias declaradas. Los productos sin configurar siguen la logica de Click & Collect (`super()`).
- **Compañias de stock web sin almacenes**: stock 0 (D22).
- **Instalacion sobre pedidos existentes**: las lineas historicas quedan con `sale_company_id` = su `company_id`; nada confirmado se rutea.

## Criterios de aceptacion

- [ ] **CA01**: Producto sin compañia propia en una categoria hija de "Bicicletas" (Miluan) → la linea muestra Miluan.
- [ ] **CA02**: Producto con `sale_company_id` propio → prevalece sobre la categoria.
- [ ] **CA03**: Producto sin configuracion en producto ni categorias → la linea muestra la compañia del pedido.
- [ ] **CA04**: Cambiar a mano la compañia de una linea en borrador → al confirmar se rutea a la compañia elegida.
- [ ] **CA05**: Pedido web en USD del sitio de YG con una bici (Miluan) y un repuesto (YG) → original confirmado solo con el repuesto; pedido de Miluan confirmado con la bici, lista de precios del cliente en Miluan (ARS), precio unitario = el del carrito convertido con la cotizacion de Miluan a la fecha de confirmacion, mismo descuento, cliente y direcciones, almacen DEPO, impuestos y posicion fiscal de Miluan, `origin` = nombre del original.
- [ ] **CA06**: Original y derivado vinculados: boton inteligente, `company_routing_origin_id` y mensaje en ambos chatters.
- [ ] **CA07**: Lineas de dos compañias destino → dos derivados.
- [ ] **CA08**: Pedido solo con bicis + envio → derivado con bicis, linea de envio (`is_delivery`) y `carrier_id`; original cancelado.
- [ ] **CA09**: Pedido mixto con envio → envio y carrier en el derivado de Miluan; el original de YG se confirma sin envio ni carrier.
- [ ] **CA10**: Dos compañias destino y envio → el envio va al derivado de mayor importe sin impuestos.
- [ ] **CA11**: Carrier con compañia distinta de la destino → `UserError`; nada se crea.
- [ ] **CA12**: Secciones y notas quedan en el original; una linea vinculada se mueve con su padre.
- [ ] **CA13**: Cliente restringido a YG con una linea de Miluan → `UserError`; nada se crea y el original sigue sin confirmar.
- [ ] **CA14**: Linea ruteada cuyo producto no tiene impuestos en la destino → `UserError`.
- [ ] **CA15**: Sin cotizacion USD en Miluan a la fecha → `UserError` que nombra moneda y fecha; nada se crea.
- [ ] **CA16**: Pedido con carrier de instalacion y lineas para rutear → `UserError`; nada se crea.
- [ ] **CA17**: Volver a confirmar un original ya ruteado no crea derivados nuevos.
- [ ] **CA18**: Pedido con descuento por medio de pago → original y derivado quedan cada uno con su descuento calculado sobre sus propias lineas.
- [ ] **CA19**: Pedido con recompensa global de un programa automatico sin compañia → se recalcula en el original y en el derivado sobre sus lineas; con un codigo promocional, un cupon, una tarjeta de regalo o un programa de la compañia del original, la recompensa queda en el original (recalculada sobre sus lineas) y el derivado queda sin ella y con aviso. Ninguna linea de recompensa se borra y ningun cupon se usa dos veces. Si todo el carrito se rutea y hay recompensa mas descuento por medio de pago, el original se cancela (no queda confirmado con lineas de descuento) y el derivado se confirma con su descuento.
- [ ] **CA20**: Producto con stock web = Miluan, stock en DEPO y nada en WH → la ficha web lo muestra disponible con la cantidad de DEPO.
- [ ] **CA21**: Stock web de dos compañias → la web muestra la suma.
- [ ] **CA22**: Stock web de una compañia sin almacenes → la web lo muestra sin stock (0), no el stock de todas las compañias.
- [ ] **CA23**: Agregar mas unidades que el stock web resuelto (sin `allow_out_of_stock_order`) → el carrito limita y avisa, igual que el core.
- [ ] **CA24**: Producto sin stock web configurado → disponibilidad identica al core.
- [ ] **CA25**: El semaforo usa el mismo stock que la ficha y resuelve la pagina del listado en una sola llamada al helper.
- [ ] **CA26**: Las vistas no muestran los campos nuevos sin `base.group_multi_company` (los campos Python no llevan grupo, D31/D32).
- [ ] **CA27**: Al instalar, las lineas existentes quedan con `sale_company_id` = su `company_id` sin recalcular el historico.
- [ ] **CA28**: Un usuario de backoffice con `base.group_multi_company` pero sin acceso a Miluan abre un pedido con lineas de Miluan sin `AccessError` y ve el nombre de la compañia.

## Referencias al core

| Que | Anclaje (`path:L#`) | Por que importa |
|-----|---------------------|-----------------|
| Filtro de productos por compañia del sitio | `odoo/addons/website_sale/models/website.py:662` | Los productos ruteados siguen con `company_id` vacio. |
| Carrito en la compañia del sitio | `odoo/addons/website_sale/models/website.py:676` | El ruteo ocurre al confirmar. |
| Valores del carrito | `odoo/addons/website_sale/models/website.py:687-698` | `company_id`, `pricelist_id`, `team_id`, `website_id` del original. |
| `action_confirm` web | `odoo/addons/website_sale/models/sale_order.py:249-256` | Nuestro override va antes en el MRO y llama `super()`. |
| `action_confirm` del core | `odoo/addons/sale/models/sale_order.py:1167-1197` | Punto a extender. |
| Estados confirmables | `odoo/addons/sale/models/sale_order.py:1204-1217` | `draft`/`sent`. |
| Cancelacion sin wizard | `odoo/addons/sale/models/sale_order.py:1331-1334` | `_action_cancel()` (D15). |
| `origin` del pedido | `odoo/addons/sale/models/sale_order.py:97` | Referencia al original. |
| Posicion fiscal por compañia | `odoo/addons/sale/models/sale_order.py:411-428` | Se resuelve en la destino. |
| Plazo de pago por compañia | `odoo/addons/sale/models/sale_order.py:431-435` | D11. |
| Lista de precios por compañia | `odoo/addons/sale/models/sale_order.py:443-451` | Lista del cliente en la destino (D9). |
| Moneda = la de la lista | `odoo/addons/sale/models/sale_order.py:453-456` | Moneda del derivado (D9). |
| Vendedor / equipo | `odoo/addons/sale/models/sale_order.py:477-490` | D10. |
| `company_id` de la linea related almacenado | `odoo/addons/sale/models/sale_order_line.py:41-43` | D5. |
| Lineas vinculadas | `odoo/addons/sale/models/sale_order_line.py:139-150` | D14. |
| Impuestos por compañia | `odoo/addons/sale/models/sale_order_line.py:541-566` | Recalculo en la destino y validacion D28. |
| Precio manual no se recalcula | `odoo/addons/sale/models/sale_order_line.py:587-617` | D8. |
| `technical_price_unit` en create | `odoo/addons/sale/models/sale_order_line.py:1358-1362` | D8. |
| Linea de envio | `odoo/addons/delivery/models/sale_order_line.py:9` | `is_delivery` (D15). |
| Almacen con `check_company` | `odoo/addons/sale_stock/models/sale_order.py:27-30` | D29. |
| Almacen por defecto por compañia | `odoo/addons/sale_stock/models/sale_order.py:223-232` | `ir.default` o primer almacen (D29). |
| Almacen del sitio en pedidos web | `odoo/addons/website_sale_stock/models/sale_order.py:11-20` | Por eso el derivado no lleva `website_id`. |
| Tope de cantidad del carrito | `odoo/addons/website_sale_stock/models/sale_order.py:23-69` | Usa `_get_free_qty`. |
| Stock libre del carrito | `odoo/addons/website_sale_stock/models/sale_order.py:85-100` | Override de `_get_free_qty` (D23). |
| Stock libre de la web | `odoo/addons/website_sale_stock/models/website.py:11-23` | Override de `_get_product_available_qty` (D23). |
| Combinacion en `sudo` | `odoo/addons/website_sale_stock/models/product_template.py:68-70` | Consumidor del hook. |
| Tope por producto | `odoo/addons/website_sale_stock/models/product_product.py:27` | Consumidor del hook. |
| Lista de almacenes en contexto | `odoo/addons/stock/models/product.py:370-375` | Suma de almacenes (D22). |
| Sin almacenes = todas las compañias activas | `odoo/addons/stock/models/product.py:390-392` | Por eso 0 en lugar de `warehouse_id=[]` (D22). |
| Dominio de ubicaciones sin filtro de compañia | `odoo/addons/stock/models/product.py:396-398` | Lectura en `sudo`. |
| Click & Collect | `odoo/addons/website_sale_collect/models/website.py:26` | Preservado con `super()` para productos sin configurar. |
| Click & Collect en el carrito | `odoo/addons/website_sale_collect/models/sale_order.py:38` | Idem. |
| Datos de retiro en tienda | `odoo/addons/website_sale_collect/models/sale_order.py:15-29` | `pickup_location_data` fija el almacen del pedido (D34). |
| Link HTML de un registro | `odoo/addons/mail/models/models.py:850` | `_get_html_link` en el chatter. |
| Categoria con `parent_path` | `odoo/addons/product/models/product_category.py:13` | D2. |
| Form de categoria | `odoo/addons/product/views/product_category_views.xml:4` | Vista a heredar. |
| Pestaña Ventas del producto | `odoo/addons/sale/views/product_views.xml:9` | `page[@name='sales']`. |
| Lineas del pedido | `odoo/addons/sale/views/sale_order_views.xml:499` | Columna nueva. |
| `display_name` de Many2one en `sudo` | `odoo/addons/web/models/models.py:152-154` | D31. |
| Fallback silencioso de cotizacion | `odoo/odoo/addons/base/models/res_currency.py:138` | `COALESCE(..., 1.0)`: se valida antes (D9). |
| Lectura de cotizaciones por compañia del usuario | `odoo/odoo/addons/base/models/res_currency.py:279-280` | `_convert` en `sudo()` (D9). |
| Conversion de moneda | `odoo/odoo/addons/base/models/res_currency.py:284` | Precio y envio (D9, D15). |
| Lineas de recompensa | `odoo/addons/sale_loyalty/models/sale_order_line.py:12-15` | `reward_id`, `coupon_id` (D27). |
| Recompensa de pedido | `odoo/addons/loyalty/models/loyalty_reward.py:78` | `discount_applicability` (D27). |
| Compañia del programa | `odoo/addons/loyalty/models/loyalty_program.py:30` | Re-aplicado solo si es usable (D27). |
| Re-aplicado de recompensas | `odoo/addons/sale_loyalty/models/sale_order.py:945` | `_apply_program_reward`. |
| Recompensas reclamables | `odoo/addons/sale_loyalty/models/sale_order.py:980` | `_get_claimable_rewards`. |
| Recalculo de programas | `odoo/addons/sale_loyalty/models/sale_order.py:1045` | `_update_programs_and_rewards`. |
| Descuento por medio de pago (custom, mismo repo) | `website_sale_payment_method_price/models/sale_order.py`, `SaleOrder._remove_payment_price_rule` / `_apply_payment_price_rule` | D27. |
| Envio con instalacion (custom, mismo repo) | `website_sale_installation_appointment/models/delivery_carrier.py`, campo `installation_appointment_type_id` | D17. |
| Indicador de stock (custom, mismo repo) | `website_sale_stock_level_indicator/models/website.py`, `Website._get_variant_stock_level` | D25. |

## Documentacion afectada

| Archivo | Accion | Que reflejar |
|---------|--------|-------------|
| `sale_website_company_routing/README.md` | crear | Configuracion (producto/categoria, herencia), ruteo, envio, descuentos, stock web, requisitos (carriers sin compañia, usuarios portal con ambas compañias, cotizaciones) y limites. |
| `sale_website_company_routing/static/description/index.html` | crear | Idem para usuario funcional. |
| `website_sale_stock_level_indicator/README.md` + `index.html` | actualizar | El semaforo usa el stock web por compañia. |
| `website_sale_payment_method_price/README.md` + `index.html` + `specs/website_sale_payment_method_price.md` | actualizar | Recalculo del descuento por pedido al rutear. |
| `website_sale_installation_appointment/README.md` + `index.html` + `specs/website_sale_installation_appointment.md` | actualizar | Pedido con envio con instalacion no se rutea. |
| `odoo_customization_sunra/README.md` | actualizar | Fila del modulo nuevo. |

## Plan del cambio en curso

| Tarea | Descripcion | Depende de | Archivos | Cubre |
|-------|-------------|------------|----------|-------|
| **T01** | Scaffold: manifest (`depends`: `sale_stock`, `website_sale_stock`, `website_sale_collect`, `sale_loyalty`), `__init__`, `pre_init_hook`, `tools.py` | — | `__manifest__.py`, `__init__.py`, `hooks.py`, `tools.py`, `models/__init__.py` | CA27 |
| **T02** | Campos y resolucion en categoria y producto (ancestros, version por lotes) | T01 | `models/product_category.py`, `models/product_template.py` | CA01, CA02, CA03 |
| **T03** | `sale.order.line.sale_company_id` (compute recursivo, solo draft/sent), `_get_routing_product_company`, `_prepare_company_routing_values` | T02 | `models/sale_order_line.py` | CA01, CA02, CA03, CA04 |
| **T04** | Ruteo: `action_confirm`, `_company_routing_split` (validaciones, envio y carrier, lista de precios y conversion en sudo, almacen, cancelacion, chatter, confirmacion), `_prepare_company_routing_order_values`, `_company_routing_validate`, boton | T03 | `models/sale_order.py` | CA04, CA05, CA06, CA07, CA08, CA09, CA10, CA11, CA12, CA13, CA14, CA15, CA17 |
| **T05** | Hooks `_company_routing_pre_split` / `_post_split` + re-aplicado de loyalty | T04 | `models/sale_order.py` | CA19 |
| **T06** | Stock web: helper por lotes + overrides de `_get_product_available_qty` y `_get_free_qty` | T02 | `models/website.py`, `models/sale_order.py` | CA20, CA21, CA22, CA23, CA24 |
| **T07** | Vistas de categoria, producto (pestaña Ventas) y pedido | T02, T03, T04 | `views/product_category_views.xml`, `views/product_template_views.xml`, `views/sale_order_views.xml`, `__manifest__.py` | CA04, CA06, CA26, CA28 |
| **T08** | `website_sale_stock_level_indicator` `1.1.0`: dependencia + helper con memoria por request | T06 | `website_sale_stock_level_indicator/__manifest__.py`, `website_sale_stock_level_indicator/models/website.py` | CA25 |
| **T09** | `website_sale_payment_method_price` `1.4.0`: dependencia + overrides de los hooks de descuento | T05 | `website_sale_payment_method_price/__manifest__.py`, `website_sale_payment_method_price/models/sale_order.py` | CA18 |
| **T10** | `website_sale_installation_appointment` `1.17.0`: dependencia + override de `_company_routing_validate` | T04 | `website_sale_installation_appointment/__manifest__.py`, `website_sale_installation_appointment/models/sale_order.py` | CA16 |
| **T11** | Traduccion `es_419` (este modulo y textos nuevos de T09/T10) | T07, T09, T10 | `i18n/es_419.po` | — |
| **T12** | Doc de los cuatro modulos + specs de los modulos ajustados en sitio + README raiz + `version` `1.0.0` == spec | T01..T11 | `README.md`, `static/description/index.html`, `__manifest__.py`, `specs/sale_website_company_routing.md`, docs y specs de T08..T10, `../README.md` | — (anti-drift + version sync) |
