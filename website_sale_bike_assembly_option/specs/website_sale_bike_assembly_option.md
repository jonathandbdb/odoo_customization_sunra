# Spec de modulo: website_sale_bike_assembly_option

| Campo | Valor |
|-------|-------|
| **Modulo** | `website_sale_bike_assembly_option` |
| **Version** | `1.0.0` (== `version` del `__manifest__.py`, formato `x.x.x`) |
| **Serie Odoo** | `19` (informativa) |
| **Estado** | `implemented` |
| **Actualizado** | `2026-10-06` |
| **Depurado** | `2026-10-06` |

## Objetivo

Aplica a **todo vehiculo** que se venda en caja (bicicletas, motos, monopatines) y a **cualquier compañia** (YG o Miluan): no hay condicion por categoria ni por compañia, solo la LdM con `sunra_pull_kit_components` y un kit serial como unico componente (D1). La compañia que vende sale de la configuracion de `sale_website_company_routing`.

Cada bicicleta electrica existe como dos productos con el mismo numero de chasis: la **bicicleta
armada** ("Bicicleta X", publicada) y el **kit en caja** ("Kit para armar - Bici X", no publicado),
unidos por la LdM de fabricacion que `sunra_mrp_component_serials` marca con
`sunra_pull_kit_components`. Este modulo agrega en la ficha web de la bici armada un selector
**"Armada / En caja"**: con "En caja" el carrito recibe el kit, **al mismo precio** que la bici
armada segun la lista de precios del sitio. El concesionario elige como recibe la bici sin que el
kit tenga que publicarse como producto aparte.

## Decisiones vigentes

| # | Decision | Valor vigente |
|---|----------|---------------|
| D1 | ¿Como se deduce el kit de una bici armada? | LdM activa de tipo `normal` del producto (variante o plantilla) con `sunra_pull_kit_components = True`, la primera por `sequence, product_id, id` **entre las de la variante**; solo si la variante no tiene ninguna se toma la primera de la plantilla (la de variante gana siempre, aunque la de plantilla tenga menor `sequence`). Entre sus lineas aplicables a la variante (`_skip_bom_line`), el **unico** componente con `tracking = 'serial'` es el kit. Ninguno o mas de uno → la bici no ofrece la opcion. Version por lotes: **un** `search` de LdM con `_bom_find_domain` para todas las bicis pedidas, memorizada por request (la tienda consulta una bici por vez). |
| D2 | ¿La LdM se filtra por compañia? | **No**: se busca con `sudo()` y `with_context(company_id=False)` (si el contexto trae `company_id`, `_bom_find_domain` filtraria por esa compañia, `mrp_bom.py:376-377`). La LdM es de la compañia que fabrica (Miluan) y el sitio es de otra (YG). |
| D3 | ¿Cuando y donde se muestra el selector? | Si la plantilla tiene al menos una variante con kit (D1). Va **dentro del formulario del producto y fuera de la seccion de atributos** (esa seccion lleva `d-none` cuando la plantilla no tiene atributos). Opcion por defecto: **Armada**. |
| D4 | ¿Como viaja la eleccion? | Patch del interaction `WebsiteSale._updateRootProduct`: agrega `bike_assembly_option` (`assembled`/`boxed`) al producto raiz **solo si el radio existe** en el formulario. El `cart` service lo reenvia como kwarg (`...rest`) a `/shop/cart/add` → `sale.order._cart_add(**kwargs)`. Como el `cart` service tambien esparce ese dato en las props de `ProductConfiguratorDialog` y `ComboConfiguratorDialog`, el patch declara `bike_assembly_option: { type: String, optional: true }` en las `static props` de ambos. Sin controller propio. |
| D5 | ¿Donde se cambia la bici por el kit? | En el servidor, en `sale.order._cart_add`: con `boxed` y sin `linked_line_id` se resuelve el kit de la variante elegida y se agrega el kit con `assembled_product_id` = la bici, **descartando** `no_variant_attribute_value_ids` y `product_custom_attribute_values` (son atributos de la bici, no del kit). El controller del core ya valido `_is_add_to_cart_allowed` sobre la bici publicada, asi que el kit **no** necesita publicarse. Nunca se confia en un id de kit enviado por el navegador: `_cart_add` descarta siempre un `assembled_product_id` que llegue en los kwargs; solo la llamada interna con el kit lo setea. |
| D6 | ¿Como toma el kit el precio de la bici armada? | Para lineas con `assembled_product_id`, la regla de lista de precios (`pricelist_item_id`), el precio de lista y el precio antes de descuento se calculan **con la bici armada**. Respeta lista del sitio, escalas, fecha, moneda y la visualizacion de descuento del core en cada recalculo. |
| D7 | ¿Se fusionan lineas de kit en el carrito? | Solo con otra linea del mismo kit y la misma `assembled_product_id`. |
| D8 | Disponibilidad de la bici armada en la web | **Stock libre de la armada + stock libre de su kit**: toda bici en caja puede armarse sobre pedido (`mts_else_mto` en la compañia que fabrica). Se suma en el helper `website._get_products_free_qty` de `sale_website_company_routing` **solo para bicis con compañias de stock web**, con los kits resueltos en lote (D1); aplica a ficha, tope del carrito y semaforo. Un kit sin compañias de stock web propias (producto o categoria) usa las de su bici; el kit se lee con esas compañias, no con el almacen del sitio (tambien en el tope del carrito, D9). El resultado se memoriza por request y bici. |
| D9 | Disponibilidad de "En caja" | El tope del carrito se calcula sobre el **kit** por `_verify_updated_quantity`; un kit sin compañias de stock web propias se mide con las de su bici, igual que la ficha (D8), y no con el almacen del sitio. Se resuelve en `sale.order._get_free_qty` (bici de las lineas del kit en el pedido, o de `assembled_product_id` cuando la linea todavia no existe, via el contexto `wsbao_assembled_product_id` que fija `_verify_updated_quantity`). Limitación aceptada: un kit compartido por bicis que venden compañías distintas se mide contra la unión de sus compañías de stock; el tope del carrito puede aceptar más de lo que tiene la compañía que finalmente lo despacha (misma familia que D10). |
| D10 | Limitacion aceptada: doble conteo | La armada cuenta los kits libres y "En caja" tambien: un carrito con armadas y kits de la misma bici puede superar los kits fisicos. Se acepta; la confirmacion y la fabricacion lo resuelven con el estandar. |
| D11 | Compañia de la linea del kit | La linea con `assembled_product_id` resuelve `sale_company_id` por la configuracion del **kit**; si el kit no tiene configuracion propia (ni en producto ni en categoria), por la de la **bici** (override de `_get_routing_product_company`). **Requisito de configuracion**: kit con `company_id` vacio, para que pueda venderse desde el sitio y moverse al derivado. |
| D12 | Ruteo del kit a otra compañia | Al moverse a un pedido derivado conserva `assembled_product_id` (extension de `_prepare_company_routing_values`); el precio viaja explicito. |
| D13 | El kit en el carrito | La linea es "vendible" si la bici esta publicada (override de `_is_sellable`), y el nombre del carrito enlaza a la **ficha de la bici**. |
| D14 | Impuestos | El kit toma el **precio** de la bici pero sus **propios impuestos**. **Requisito de configuracion**: kit y bici con los mismos impuestos de venta; si difieren, el total del kit difiere del de la bici. |
| D15 | Backoffice | `assembled_product_id` en la linea del pedido (columna opcional oculta, solo lectura). El kit vendido desde el backoffice sin bici asociada usa su precio propio. |
| D16 | Grilla de la tienda / agregado rapido | `[ASUNCION]` Sin selector: agregan la bici armada (opcion por defecto). |
| D17 | Productos opcionales y combos | La opcion solo afecta al producto principal; las lineas con `linked_line_id` la ignoran. |
| D18 | Dependencias | `sale_website_company_routing` (helper de stock y hooks de ruteo) y `sunra_mrp_component_serials` (`sunra_pull_kit_components`, trae `mrp`). |
| D19 | Idioma | UI en ingles con `_()`, traduccion en `i18n/es_419.po` ("Assembled" → "Armada", "In box" → "En caja"). |

## Alcance

### Incluye
- Selector "Armada / En caja" en la ficha web de las bicis cuya LdM de kit lo permite.
- Agregado del kit al carrito con el precio de la bici armada, enlazado a la ficha de la bici.
- Disponibilidad web de la bici armada sumando el stock de su kit.
- Compañia de venta del kit resuelta por la bici cuando el kit no tiene configuracion propia.
- `assembled_product_id` visible en la linea del pedido.

### NO incluye
- Publicar el kit ni crear una pagina de producto para el.
- Selector en la grilla, el agregado rapido o el configurador de opcionales.
- Elegir el numero de chasis en la web.
- Crear o mantener LdM y productos kit.
- Precio distinto entre armada y en caja; igualar impuestos del kit con los de la bici (configuracion, D14).
- Evitar el doble conteo de kits entre armada y en caja (D10).
- **Tests automatizados**: el repo no declara politica de tests (`.swarm.conf` ausente).

## Modelos

### Nuevos

No aplica.

### Extendidos

| Modelo | `_inherit` | Que se agrega |
|--------|-----------|---------------|
| `product.product` | `product.product` | `_get_assembly_kit_products()` (D1/D2, por lotes). |
| `product.template` | `product.template` | `_has_bike_assembly_option()` para el QWeb (D3). |
| `sale.order` | `sale.order` | Overrides de `_cart_add`, `_cart_find_product_line`, `_prepare_order_line_values`. |
| `sale.order.line` | `sale.order.line` | `assembled_product_id`, precio con la bici, `_is_sellable`, compañia de ruteo, extension del hook de ruteo. |
| `website` | `website` | Extension de `_get_products_free_qty` (D8). |

## Campos

| Modelo | Campo | Tipo | String | Requerido | Default | Restricciones / notas |
|--------|-------|------|--------|-----------|---------|----------------------|
| `sale.order.line` | `assembled_product_id` | Many2one `product.product` | Assembled Vehicle | No | - | `readonly=True`, `ondelete='set null'`, `index='btree_not_null'`. Lo setea el carrito web (D5) o el ruteo (D12). |

## Metodos

### `ProductProduct._get_assembly_kit_products()`
- **Proposito**: kit de cada bici (D1/D2).
- **Logica**: `Bom = env['mrp.bom'].sudo().with_context(company_id=False)`; un `search` con `Domain.AND([Bom._bom_find_domain(self, bom_type='normal'), [('sunra_pull_kit_components', '=', True)]])`, `order='sequence, product_id, id'`; por producto, la primera LdM de variante o, si no hay, la de plantilla; lineas no salteadas por `_skip_bom_line(product)` con `product_id.tracking == 'serial'`; kit = el componente si es exactamente uno.
- **Retorna**: `dict {product.id: kit product.product}` (sin entrada = sin opcion). `_get_assembly_kit_product()` es el atajo `ensure_one()`.

### `ProductTemplate._has_bike_assembly_option()`
- **Logica**: `bool(self.sudo().product_variant_ids._get_assembly_kit_products())`.

### `SaleOrder._cart_add(product_id, quantity=1.0, *, uom_id=None, **kwargs)` (override de `website_sale`)
- **Logica**:
  1. `kwargs.pop('assembled_product_id', None)` (nunca se acepta del cliente) y `option = kwargs.pop('bike_assembly_option', None)`.
  2. Con `option == 'boxed'` y sin `linked_line_id`: `kit = product._get_assembly_kit_product()`; sin kit → `UserError`. Quitar de kwargs `no_variant_attribute_value_ids` y `product_custom_attribute_values`, y llamar `super()._cart_add(kit.id, quantity, uom_id=None, assembled_product_id=product.id, **kwargs)`.
  3. Si no, `super()`.
- **Errores**: `UserError(_("This vehicle cannot be ordered in a box."))`.

### `SaleOrder._verify_updated_quantity(...)` / `SaleOrder._get_free_qty(product)` (overrides de `website_sale_stock`)
- **Logica**: `_verify_updated_quantity` fija el contexto `wsbao_assembled_product_id` con `kwargs['assembled_product_id']` (linea nueva del kit) y llama `super()`. `_get_free_qty`: si el pedido tiene sitio y el producto no declara compañias de stock web, toma las bicis (`assembled_product_id` de las lineas con ese producto, mas la del contexto) y, si alguna declara compañias, lee el stock libre del producto con `website._compute_products_free_qty` y esas compañias (D9); si no, `super()`.

### `SaleOrder._cart_find_product_line(..., **kwargs)` (override)
- **Logica**: `super()` filtrado por `assembled_product_id == kwargs.get('assembled_product_id', False)` (D7).

### `SaleOrder._prepare_order_line_values(product_id, quantity, uom_id, **kwargs)` (override)
- **Logica**: `super()` + `assembled_product_id` si viene en kwargs.

### `SaleOrderLine._compute_pricelist_item_id()` (override)
- **Decoradores**: agrega `assembled_product_id` a los `@api.depends`.
- **Logica**: con `assembled_product_id` → `pricelist_id._get_product_rule(product=assembled_product_id, **_get_pricelist_kwargs())`; si no, `super()`.

### `SaleOrderLine._get_pricelist_price()` / `_get_pricelist_price_before_discount()` (overrides)
- **Logica**: con `assembled_product_id`, el calculo del core pasando la bici con su contexto de precio; si no, `super()`.

### `SaleOrderLine._is_sellable()` (override de `website_sale`)
- **Logica**: con `assembled_product_id` → `assembled_product_id.is_published and not self.is_delivery`; si no, `super()`.

### `SaleOrderLine._get_routing_product_company()` (extension) + `_compute_sale_company_id()`
- **Logica**: `super()`; si vacio y hay `assembled_product_id`, `assembled_product_id.product_tmpl_id.sudo()._get_sale_company()` (D11). El compute agrega `assembled_product_id` a sus `@api.depends` y llama `super()`.

### `SaleOrderLine._prepare_company_routing_values(target_order, convert)` (extension)
- **Logica**: `super()` + `assembled_product_id` (D12).

### `Website._get_products_free_qty(products)` (extension)
- **Logica**: `res = super()`; bicis con compañias de stock web → `kits = bicis._get_assembly_kit_products()`; las compañias de cada kit son las suyas o, si no tiene, las de su bici; `kit_qty = _compute_products_free_qty(kits, compañias)` (una llamada, del helper de `sale_website_company_routing`); `res[bici.id] += kit_qty[kit.id]`. Memoriza el stock del kit por request, sitio y bici.
- **Retorna**: `dict {product.id: free_qty}`.

## Vistas

- `website_sale.product` (QWeb, herencia `product_bike_assembly_option`): si `product._has_bike_assembly_option()`, un grupo de radios `name="bike_assembly_option"` con "Assembled" (marcado) e "In box", **dentro del formulario y despues** de la seccion de atributos (no dentro de ella).
- `website_sale.cart_line_product_link` (QWeb): el `href` usa `(line.assembled_product_id or line.product_id).website_url`.
- JS `static/src/interactions/website_sale.js`: `patch(WebsiteSale.prototype, { _updateRootProduct(form) })`, que agrega `bike_assembly_option` solo si hay un radio marcado. `static/src/js/configurator_props_patch.js`: agrega `bike_assembly_option` opcional a las `static props` de `ProductConfiguratorDialog` y `ComboConfiguratorDialog`. Assets en `web.assets_frontend`.
- `sale_order_view_form` (hereda `sale.view_order_form`): columna `assembled_product_id` en las lineas, `optional="hide"`, solo lectura.

## Seguridad

- Sin modelos ni grupos nuevos.
- `sudo()` solo para leer LdM y sus lineas desde la web (D2): el visitante no tiene acceso a fabricacion.

## Reglas de negocio

1. **RB01**: Una bici ofrece "En caja" solo si su LdM con `sunra_pull_kit_components` tiene exactamente un componente serializado aplicable a la variante.
2. **RB02**: "En caja" agrega el kit; "Armada" (por defecto) agrega la bici.
3. **RB03**: La linea del kit agregada desde la web cuesta lo mismo que la bici armada en la lista de precios del pedido, en todo recalculo.
4. **RB04**: El kit se agrega aunque no este publicado; nunca se acepta un kit pedido directamente por el navegador.
5. **RB05**: La disponibilidad web de una bici armada con stock web configurado = stock libre de la armada + stock libre de su kit.
6. **RB06**: Sin configuracion propia, el kit se vende por la compañia de la bici.

## Edge cases

- **Bici sin LdM de kit o con varios componentes serializados**: no se muestra el selector; si llega `boxed` igual → `UserError`.
- **Variante sin kit en una plantilla con kit**: el selector se ve; "En caja" con esa variante → `UserError`.
- **Plantilla sin atributos**: el selector se ve igual (no vive en la seccion de atributos).
- **Bici con atributos `no_variant` o personalizados**: con "En caja" no se trasladan al kit.
- **Kit sin compañias de stock web propias**: su stock se lee de las compañias de la bici (D8).
- **Sin kits pero con armadas**: "En caja" queda limitado por el stock del kit.
- **Armadas y kits de la misma bici en el mismo carrito**: posible doble conteo (D10).
- **Impuestos del kit distintos de los de la bici**: mismo precio unitario, total distinto (D14).
- **Cambio de cantidad o de lista de precios**: la linea del kit sigue con el precio de la armada.
- **LdM archivada despues de agregar**: la linea conserva `assembled_product_id` y su precio.
- **Ruteo a otra compañia**: el derivado recibe el kit con el precio convertido y el vinculo.
- **Configurador de opcionales**: la opcion llega como prop declarada (sin error de props) y solo se aplica al producto principal.

## Criterios de aceptacion

- [ ] **CA01**: Ficha de "Bicicleta GT2000" (LdM con el tilde y un unico componente serial "Kit para armar - Bici GT2000") → se ve el selector con "Armada" marcado, aunque la plantilla no tenga atributos.
- [ ] **CA02**: Bici sin LdM con el tilde → no se ve el selector y el payload de agregar al carrito no lleva `bike_assembly_option`.
- [ ] **CA03**: "En caja" → el carrito tiene el kit con `assembled_product_id` = la bici y sin atributos de la bici.
- [ ] **CA04**: El precio unitario del kit en el carrito es igual al de la bici armada en la lista de precios del sitio, tambien despues de cambiar la cantidad.
- [ ] **CA05**: "Armada" → se agrega la bici, sin cambios respecto del core.
- [ ] **CA06**: Dos veces "En caja" → una sola linea de kit con cantidad 2.
- [ ] **CA07**: `boxed` para una bici sin kit (llamada directa a `/shop/cart/add`) → `UserError`.
- [ ] **CA08**: Kit sin stock web y sin `allow_out_of_stock_order` → "En caja" rechazado con el aviso estandar.
- [ ] **CA09**: Bici armada con 0 armadas y 3 kits libres (stock web configurado) → la ficha la muestra disponible con 3.
- [ ] **CA10**: En el carrito, el kit muestra enlace a la ficha de la bici publicada.
- [ ] **CA11b**: Kit sin configuracion de stock y bici con compañias de stock web = [Miluan] → el tope del carrito del sitio es el stock de kits de Miluan, no el del almacen del sitio.
- [ ] **CA11**: Kit sin configuracion de compañia y bici de Miluan → la linea del kit muestra Miluan y al confirmar el derivado tiene el kit con `assembled_product_id`.
- [ ] **CA12**: En el backoffice, la columna opcional "Assembled Vehicle" muestra la bici en la linea del kit.
- [ ] **CA13**: Bici con productos opcionales: el configurador abre sin error de props y "En caja" aplica solo a la bici.

## Referencias al core

| Que | Anclaje (`path:L#`) | Por que importa |
|-----|---------------------|-----------------|
| Ruta `/shop/cart/add` | `odoo/addons/website_sale/controllers/cart.py:75-131` | Valida la bici publicada y pasa `**kwargs` a `_cart_add`. |
| Chequeo de producto publicado | `odoo/addons/website_sale/models/product_product.py:141-151` | Por eso el cambio a kit ocurre en `_cart_add` (D5). |
| `_cart_add` | `odoo/addons/website_sale/models/sale_order.py:347-401` | Punto del cambio bici → kit. |
| `_cart_find_product_line` | `odoo/addons/website_sale/models/sale_order.py:403-453` | Fusion de lineas (D7). |
| `_create_new_cart_line` | `odoo/addons/website_sale/models/sale_order.py:569-576` | Pasa `**kwargs` a `_prepare_order_line_values`. |
| `_prepare_order_line_values` | `odoo/addons/website_sale/models/sale_order.py:581-591` | Agrega `assembled_product_id`. |
| Linea vendible | `odoo/addons/website_sale/models/sale_order_line.py:124-132` | `_is_sellable` (D13). |
| Enlace de la linea del carrito | `odoo/addons/website_sale/views/templates.xml:2826-2836` | `cart_line_product_link` (D13). |
| `cart` service reenvia `...rest` | `odoo/addons/website_sale/static/src/js/cart_service.js:112-123` | D4. |
| Props del configurador de combos | `odoo/addons/website_sale/static/src/js/cart_service.js:267-274` | `...additionalData` en las props (D4). |
| Props del configurador de opcionales | `odoo/addons/website_sale/static/src/js/cart_service.js:324-337` | Idem. |
| `_makeRequest` | `odoo/addons/website_sale/static/src/js/cart_service.js:445-463` | `...rest` → payload. |
| `ProductConfiguratorDialog.props` | `odoo/addons/sale/static/src/js/product_configurator_dialog/product_configurator_dialog.js:11` | Prop opcional nueva. |
| `ComboConfiguratorDialog.props` | `odoo/addons/sale/static/src/js/combo_configurator_dialog/combo_configurator_dialog.js:18` | Prop opcional nueva. |
| Interaction de la ficha | `odoo/addons/website_sale/static/src/interactions/website_sale.js:13` | Clase `WebsiteSale`. |
| Producto raiz | `odoo/addons/website_sale/static/src/interactions/website_sale.js:562-580` | `_updateRootProduct`. |
| Ficha de producto | `odoo/addons/website_sale/views/templates.xml:1967` | Template `website_sale.product`. |
| Seccion de atributos | `odoo/addons/website_sale/views/templates.xml:2126` | Ancla; lleva `d-none` sin atributos (D3). |
| Regla de lista de precios de la linea | `odoo/addons/sale/models/sale_order_line.py:575-584` | D6. |
| Precio de lista de la linea | `odoo/addons/sale/models/sale_order_line.py:676-688` | D6. |
| Precio antes de descuento | `odoo/addons/sale/models/sale_order_line.py:719-730` | D6. |
| Busqueda de LdM | `odoo/addons/mrp/models/mrp_bom.py:370-382` | `_bom_find_domain` (D1). |
| Filtro de compañia por contexto | `odoo/addons/mrp/models/mrp_bom.py:376-377` | `with_context(company_id=False)` (D2). |
| Linea de LdM aplicable a la variante | `odoo/addons/mrp/models/mrp_bom.py:771` | `_skip_bom_line`. |
| Supply method `mts_else_mto` | `odoo/addons/stock/models/stock_rule.py:81` | Fundamento de D8. |
| Opt-in de LdM de kit (custom, mismo repo) | `sunra_mrp_component_serials/models/mrp_bom.py`, campo `sunra_pull_kit_components` | Identifica la LdM kit → bici. |
| Helper de stock web (custom, mismo repo) | `sale_website_company_routing/models/website.py`, `Website._get_products_free_qty` | D8. |
| Hooks de ruteo (custom, mismo repo) | `sale_website_company_routing/models/sale_order_line.py`, `SaleOrderLine._get_routing_product_company` / `_prepare_company_routing_values` | D11, D12. |

## Documentacion afectada

| Archivo | Accion | Que reflejar |
|---------|--------|-------------|
| `website_sale_bike_assembly_option/README.md` | crear | Requisitos (LdM con el tilde y un unico kit serial, kit sin compañia, mismos impuestos), precio, disponibilidad, doble conteo, limites. |
| `website_sale_bike_assembly_option/static/description/index.html` | crear | Idem para usuario funcional. |
| `odoo_customization_sunra/README.md` | actualizar | Fila del modulo nuevo. |
