# Spec de modulo: website_sale_payment_method_price

| Campo | Valor |
|-------|-------|
| **Modulo** | `website_sale_payment_method_price` |
| **Version** | `1.0.1` (== `version` del `__manifest__.py`, formato `x.x.x`) |
| **Serie Odoo** | `19` (informativa) |
| **Estado** | `implemented` (validado end-to-end a mano; falta pasada de @reviewer) |
| **Actualizado** | `2026-09-04` |

## Objetivo

Permitir un **descuento o recargo por medio de pago** en el eCommerce, con dos entregables:

1. **Vidriera**: debajo del precio del producto se publica un segundo precio por cada medio de pago
   configurado (`$ 133.705,00 con Transferencia bancaria`), en la grilla del shop, en la ficha del
   producto y como fila extra debajo del Total del carrito.
2. **Cobro**: al elegir ese medio en el checkout, el descuento se aplica **de verdad** al pedido como
   linea con su IVA, de modo que el total cobrado coincida con el precio publicado.

Motivo: Nokey vende hoy en Tiendanube, donde esa funcion es nativa y el 15 % por transferencia es el
argumento de venta principal del sitio (verificado sobre 22 productos de `www.nokey.com.ar`). Odoo 19
no tiene equivalente: los `fees` de `payment.provider` existieron hasta la v15 y fueron eliminados, y
el precio del carrito se calcula antes de que el cliente elija como pagar.

## Decisiones vigentes

| # | Decision | Valor vigente |
|---|----------|---------------|
| D1 | ¿Donde vive la configuracion? | En **`payment.method`** (pestana "Website"), NO en `payment.provider`. Lo fuerza el requerimiento del cliente: transferencia lleva descuento y tarjeta no, pero **ambas cuelgan del mismo proveedor** cuando el medio es Mercado Pago (`mercado_pago_wallet` vs `card`). A nivel proveedor no se pueden separar. |
| D2 | Granularidad | **Una linea por (medio, sitio)** en un modelo hijo, no un m2m de sitios con un porcentaje unico: soporta otro porcentaje en otro sitio sin rediseñar. |
| D3 | ¿Medios de pago en la lista de precios? | **No.** Decision explicita del dev: las lineas por sitio son la unica fuente, para que no se solapen dos configuraciones que pueden contradecirse. |
| D4 | Semantica del redondeo | Espeja `product.pricelist.item.price_round`: multiplo, `float_round` al mas cercano, aplicado **despues** del porcentaje. En 0 no redondea. |
| D5 | Base del calculo en la vidriera | Sobre el precio **ya mostrado** (post `_apply_taxes_to_price`, con o sin IVA segun `website.show_line_subtotals_tax_selection`). Verificado contra el sitio real: 664.936,10 es con IVA y 565.195,69 es el 85 % de ese numero, no del neto. |
| D6 | ¿Como se materializa el ajuste en el pedido? | Reusando `sale.order.discount` con `discount_type='amount'` (importe fijo) → `account.tax._prepare_global_discount_lines`, que parte el importe por combinacion de impuestos. **No** se reimplementa la matematica del IVA. |
| D7 | ¿Importe fijo o porcentaje? | **Importe fijo.** Con porcentaje el total no coincidiria con los precios redondeados que promete la vidriera, que es justamente el punto. El objetivo se calcula igual que en el sitio (por precio unitario) y el ajuste es la diferencia. Ademas `_reduce_base_lines_to_target_amount` interpreta el importe fijo como **total con impuestos**, la misma base que muestra el sitio. |
| D8 | ¿Por que medio se busca la regla? | Por **`primary_payment_method_id`**. En el checkout el radio es siempre el primario (`card`), pero el proveedor **reescribe** `payment_method_id` con la marca real (`visa`) al procesar el feedback. Buscar por el medio tal cual llega perderia la configuracion. |
| D9 | ¿Como se sincroniza el medio preseleccionado? | En el servidor, dentro de `_get_shop_payment_values`, espejando la condicion del core (`/home/leandro/projects/nexit/19.0/odoo/addons/payment/views/payment_form_templates.xml:L38`), y **solo si el pedido no tiene ya una regla**. Si la tiene es porque el cliente eligio un medio, y quitarsela pelearia contra esa eleccion en cada recarga. |
| D10 | ¿Por que se recarga el paso de pago? | El importe se lee del `dataset` del formulario en el `setup()` de la interaccion (`/home/leandro/projects/nexit/19.0/odoo/addons/payment/static/src/interactions/payment_form.js:L23`), asi que un refresh parcial dejaria un numero viejo. Atajo deliberado; la seleccion del radio se conserva con el parametro `wspmp_pm`. |
| D15 | ¿Como se restaura la seleccion tras la recarga? | Marcando `radio.checked` **antes** de `super.willStart()`, sin disparar eventos: el `willStart` del core, al encontrar un radio marcado, despliega el formulario inline y habilita el boton (`/home/leandro/projects/nexit/19.0/odoo/addons/payment/static/src/interactions/payment_form.js:L36`). **No** con `radio.click()`: los listeners de `dynamicContent` se enganchan recien cuando `willStart` resuelve (`/home/leandro/projects/nexit/19.0/odoo/addons/web/static/src/public/colibri.js:L51`), asi que el `change` no lo escucha nadie y el boton de pagar queda deshabilitado. |
| D11 | ¿Donde se cuelga el JS de la ficha? | En **`WebsiteSale.prototype`**, no en `VariantMixin`: el core copia el mixin al prototipo con `Object.assign` (`/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/static/src/interactions/website_sale.js:L651`), asi que un `patch()` sobre el mixin llega tarde. Comprobado en vivo: la primera version parcheaba el mixin y no repintaba. |
| D12 | ¿Reserva de stock al pagar por transferencia? | **Como lo hace Odoo** (pedido en presupuesto, sin reserva). Decision explicita de la cliente → sin desarrollo. |
| D13 | Convivencia con otras promociones | El ajuste **se suma** a lo que haya (decision comercial de la cliente). El objetivo se calcula sobre el precio final de cada linea, ya con sus descuentos. |
| D14 | ¿Se publican precios de medios no disponibles? | No. Se descartan reglas de medios archivados y de proveedores deshabilitados, sin publicar, de otra compania o restringidos a otro sitio. |

## Alcance

### Incluye
- Modelo `payment.method.website.price` con tipo, porcentaje, alcance, redondeo y visibilidad, unico
  por (medio, sitio), y su pestana "Website" en el formulario del medio de pago.
- Segundo precio en la grilla del shop, en la ficha del producto (con repintado JS al cambiar de
  variante) y como fila por medio debajo del Total del carrito/checkout.
- Aplicacion real del ajuste al pedido en el checkout, con su IVA repartido por grupo de impuesto.
- Caida del ajuste al cambiar de medio y recalculo al cambiar el carrito.
- Revalidacion al crear la transaccion, para no cobrar nunca un importe distinto al mostrado.
- Traduccion `es_AR` de las cadenas visibles (incluida la etiqueta `con <medio>`).
- Documentacion (`README.md` + `static/description/index.html`) y fila en el README raiz del repo.

### NO incluye
- **Campo de medios de pago en la lista de precios** (D3).
- **Exclusion por producto o categoria**: el alcance es el sitio. Si se publica algo que no deba
  llevar descuento, hoy no hay donde excluirlo.
- **Minimos de compra ni topes de descuento** (la cliente los descarto).
- **Cambios en la reserva de stock** ni en el circuito de acreditacion de la transferencia (D12).
- **Habilitar `mercado_pago_wallet`**: existe en el catalogo del core pero nace inactivo y el modulo
  de MP activa solo tarjetas. Es configuracion + verificacion en staging, no codigo.
- Modificar core/enterprise: todo es `_inherit`, `t-inherit` y `patch()`.

## Modelos

### Nuevos

| Modelo | _description | Para que |
|--------|--------------|----------|
| `payment.method.website.price` | Payment Method Website Price | Una linea de precio por medio de pago y sitio web |

### Extendidos

| Modelo | Que se agrega |
|--------|--------------|
| `payment.method` | `website_price_ids` + `_get_website_price_rule(website)` |
| `product.template` | `_get_payment_method_price_vals()` + overrides de `_get_sales_prices` y `_get_additionnal_combination_info` |
| `sale.order` | `payment_price_rule_id`, calculo y aplicacion del ajuste, override de `_recompute_cart` |
| `sale.order.line` | `is_payment_method_discount` |

## Campos

### `payment.method.website.price`

| Campo | Tipo | Notas |
|-------|------|-------|
| `payment_method_id` | Many2one `payment.method` | required, `ondelete='cascade'`, index |
| `website_id` | Many2one `website` | required, `ondelete='cascade'` |
| `sequence` | Integer | default 10, orden de los precios extra |
| `price_type` | Selection `discount`/`surcharge` | required, default `discount` |
| `percentage` | Float `(16,2)` | required, default 0; constraint 0..100 |
| `applies_to` | Selection `product`/`delivery`/`all` | required, default `product` |
| `price_round` | Float | constraint >= 0; help espeja el del core |
| `show_on_website` | Boolean | default True |

Constraint SQL: `UNIQUE(payment_method_id, website_id)`.

### Otros

| Modelo | Campo | Tipo | Notas |
|--------|-------|------|-------|
| `payment.method` | `website_price_ids` | One2many | inverso `payment_method_id` |
| `sale.order` | `payment_price_rule_id` | Many2one | `copy=False`, `readonly=True` |
| `sale.order.line` | `is_payment_method_discount` | Boolean | `copy=False`, tecnico |

## Metodos

### `PaymentMethodWebsitePrice._apply_to_price(self, price)`
Unico lugar donde se calcula el precio ajustado. Signo por `price_type`, luego
`float_round(price, precision_rounding=price_round)` si hay redondeo. Espeja
`product.pricelist.item._compute_price` (rama `formula`).

### `PaymentMethodWebsitePrice._get_website_rules(self, website, only_visible=False)`
Reglas vigentes del sitio: descarta porcentaje 0, medios archivados y medios sin proveedor usable
(via `_is_payment_method_available`).

### `PaymentMethod._get_website_price_rule(self, website)`
Resuelve la regla **subiendo al metodo primario** (D8).

### `ProductTemplate._get_payment_method_price_vals(self, website, price, rules=None)`
Devuelve `[{name, label, price, price_formatted}]`. `label` se arma con `_()` en Python para que sea
un solo string traducible; `price_formatted` viaja porque el JS de variantes no debe re-resolver la
moneda ni su precision. Descarta reglas con `applies_to='delivery'` (no afectan el precio del producto).

### `SaleOrder._get_payment_price_amount(self, rule)`
Importe del ajuste **con impuestos**. Redondea por precio unitario en la base que muestra el sitio y
devuelve la diferencia contra el subtotal base; si el sitio muestra sin impuestos, escala por la
relacion bruto/neto del propio pedido.

### `SaleOrder._apply_payment_price_rule(self, rule)` / `_remove_payment_price_rule(self)`
Idempotente: limpia lo aplicado y vuelve a crear via `sale.order.discount`. Marca las lineas nuevas
con `is_payment_method_discount` y les agrega el nombre del medio.

### `SaleOrder._recompute_cart(self)` (override)
Reajusta el descuento cuando cambia el carrito, con guarda de contexto `wspmp_skip_recompute`.

### Controllers
- `WebsiteSalePaymentMethodPrice.shop_payment_method_price` — `POST /shop/payment/method_price`.
  Opera **solo** sobre `request.cart`. Devuelve `{'reload': bool}`.
- `PaymentPortal._get_shop_payment_values` (override) — sincroniza el medio preseleccionado (D9).
- `PaymentPortal.shop_payment_transaction` (override) — revalida el ajuste contra el medio real.

## Assets y JS

| Archivo | Que hace |
|---------|----------|
| `static/src/js/payment_method_price.js` | `patch(WebsiteSale.prototype)` → `_onChangeCombination` repinta los `.o_wspmp_prices` |
| `static/src/js/payment_form_price.js` | `patch(PaymentForm.prototype)` → `selectPaymentOption` llama la ruta y recarga; `willStart` re-marca el radio desde `wspmp_pm` **antes del super** (D15) via `_wspmpRestoreSelectedOption` |
| `static/src/scss/payment_method_price.scss` | Estilo del segundo precio (etiqueta en mayusculas, importe en negrita) |

Todos en `web.assets_frontend`.

## Vistas

| XML ID | Hereda | Que agrega |
|--------|--------|-----------|
| `payment_method_form` | `payment.payment_method_form` | Pestana "Website" con la lista editable de `website_price_ids` |
| `product_price` | `website_sale.product_price` | Precios por medio en la ficha |
| `products_item` | `website_sale.products_item` | Precios por medio en la tarjeta del listado |
| `total` | `website_sale.total` | Fila por medio debajo del Total |

## Seguridad

`payment.method.website.price`: lectura para `base.group_user`; lectura/escritura/creacion/borrado
para `base.group_system`. La lectura desde el frontend publico va por `sudo()` (es configuracion, no
hay dato de terceros). No hacen falta record rules: el filtro real es `website_id`.

## Reglas de negocio

1. Una regla con porcentaje 0 no tiene efecto y no se publica.
2. `applies_to` solo afecta al checkout; la vidriera muestra siempre el precio del producto.
3. El ajuste del pedido es unico: al reaplicar se borra el anterior, nunca se apila.
4. Al cambiar de medio de pago el ajuste se cae.
5. Al cambiar el carrito el ajuste se recalcula.
6. Si el ajuste no corresponde al medio con el que se paga, se corrige y el core pide refrescar.
7. Nunca se cobra un importe distinto al que se mostro.

## Edge cases

| Caso | Comportamiento |
|------|----------------|
| Un solo medio de pago (el core lo preselecciona) | El servidor aplica el ajuste antes de renderizar: no hay recarga extra ni error de importe |
| Varios medios, ninguno preseleccionado | Se muestra el total de lista mas la fila "con &lt;medio&gt;"; el ajuste se aplica al elegir |
| El cliente recarga el paso de pago con un ajuste aplicado | El ajuste se conserva (D9); el radio se re-marca via `wspmp_pm` y el core despliega el formulario inline y habilita el boton (D15) |
| El medio elegido cae en la lista colapsada de "otros medios" (hay tokens guardados) | Al restaurar la seleccion se despliega la lista y se oculta el boton de expandir, para no dejar marcado un medio invisible |
| Pago con token guardado | El medio se resuelve desde `token.payment_method_id` |
| Producto con precio 0 / `prevent_zero_price_sale` | No se publican precios por medio de pago |
| Carrito con solo linea de envio y `applies_to='product'` | Ajuste 0, no se crea linea |
| Impuestos mixtos (21 % y 10,5 %) | El total cierra exacto; puede haber centavos de diferencia en el reparto entre grupos |
| Medio archivado o proveedor deshabilitado | La regla no se publica ni se aplica |

## Criterios de aceptacion

| # | Criterio | Estado |
|---|----------|--------|
| **CA01** | La pestana Website permite cargar una linea por sitio con los 6 campos | OK |
| **CA02** | `_apply_to_price(664936.10)` con 15 % da 565.195,685; con redondeo 100 da 565.200,00; con 1000 da 565.000,00 | OK |
| **CA03** | Con `price_type='surcharge'` el signo se invierte | OK |
| **CA04** | El porcentaje fuera de 0..100 se rechaza | OK |
| **CA05** | La regla se resuelve desde una marca (`visa`) hacia el primario (`card`) | OK |
| **CA06** | La grilla del shop publica el segundo precio | OK |
| **CA07** | La ficha del producto publica el segundo precio | OK |
| **CA08** | Al cambiar de variante el segundo precio se repinta desde el servidor | OK |
| **CA09** | El carrito muestra una fila por medio debajo del Total | OK |
| **CA10** | Con un solo medio, el paso de pago ya se dibuja con el descuento aplicado y su linea de IVA | OK |
| **CA11** | Con varios medios, elegir el del descuento aplica el ajuste y conserva la seleccion | OK |
| **CA12** | Cambiar a otro medio quita el descuento y devuelve el total de lista | OK |
| **CA13** | Cambiar cantidades recalcula el ajuste (15 % del nuevo total) | OK |
| **CA14** | El total cobrado coincide con el precio publicado en la vidriera | OK |
| **CA15** | Las cadenas visibles salen en castellano (`con <medio>`) | OK |
| **CA16** | Tras la recarga por cambio de medio, el boton de pagar queda habilitado y el formulario inline del medio (p. ej. la tarjeta de Mercado Pago) se despliega, sin volver a tocar el radio | OK (reproducido y verificado en el navegador local, 4-sep-2026) |

## Referencias al core

> Anclajes `path:L#` verificados sobre el checkout de v19 (`/home/leandro/projects/nexit/19.0`).
> Rutas absolutas porque en este workspace el core no vive bajo el root del enjambre.

| Que | Anclaje (`path:L#`) | Por que importa |
|-----|---------------------|-----------------|
| Modelo del medio de pago | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/models/payment_method.py:L12` | No tiene `company_id` ni `website_id`: es catalogo global, de ahi la linea por sitio (D2). |
| Form del medio de pago | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/views/payment_method_views.xml:L4` | Tiene `<sheet>` + `<notebook>`: la pestana Website cuelga por herencia. |
| Accion del medio de pago | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/views/payment_method_views.xml:L133` | Filtra `is_primary = True`: la pestana solo se ve en primarios. |
| Datos del catalogo | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/data/payment_method_data.xml:L2` | `noupdate="1"`: la configuracion sobre esos registros sobrevive los upgrades. |
| Reescritura del medio con la marca real | `/home/leandro/projects/nexit/19.0/odoo/addons/payment_mercado_pago/models/payment_transaction.py:L230` | Fundamenta D8: la transaccion puede terminar en `visa`, no en `card`. |
| Medio primario derivado | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/models/payment_transaction.py:L47` | Campo a usar para resolver la regla (compute en L142). |
| Preseleccion del radio | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/views/payment_form_templates.xml:L38` | Condicion que espeja el sync del servidor (D9). |
| Interaccion del formulario de pago | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/static/src/interactions/payment_form.js:L23` | El importe se lee del `dataset` en el setup: fundamenta la recarga (D10). |
| Handler del radio | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/static/src/interactions/payment_form.js:L55` | `selectPaymentOption`, el metodo que se parchea. |
| `willStart` del formulario de pago | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/static/src/interactions/payment_form.js:L36` | Si encuentra un radio marcado despliega el inline form y habilita el boton: es el camino que usa la restauracion (D15). |
| Arranque de una Interaction | `/home/leandro/projects/nexit/19.0/odoo/addons/web/static/src/public/colibri.js:L51` | Los listeners se enganchan **despues** de `willStart`: fundamenta D15. |
| Colapso de la lista de medios | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/views/payment_form_templates.xml:L91` | `#o_payment_methods` nace `collapse` cuando hay tokens. |
| Chequeo de importe al crear la transaccion | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/controllers/payment.py:L64` | Aborta si el form y `amount_total` difieren: es el candado que obliga al flujo. |
| Precio de la grilla | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/models/product_template.py:L389` | Hook de la vidriera en el listado. |
| Precio de la ficha | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/models/product_template.py:L584` | `_get_additionnal_combination_info`, marcado por el core como punto de override. |
| Impuestos del precio del sitio | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/models/product_template.py:L693` | `_apply_taxes_to_price`: fundamenta D5. |
| Config de IVA del sitio | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/models/website.py:L70` | `show_line_subtotals_tax_selection`. |
| jsonrpc de variantes | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/controllers/variant.py:L8` | Descarta claves (L33): `payment_method_prices` sobrevive. |
| Mixin copiado al prototipo | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/static/src/interactions/website_sale.js:L651` | `Object.assign`: fundamenta D11. |
| Repintado de precios en JS | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/static/src/js/variant_mixin.js:L269` | `_onChangeCombination`; patron a copiar en L346. |
| Template de precio de la ficha | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/templates.xml:L2696` | `website_sale.product_price`. |
| Template de la tarjeta | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/product_tile_templates.xml:L186` | Bloque de precio del listado. |
| Template de totales | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/templates.xml:L4085` | `website_sale.total`, fila por medio debajo del Total. |
| Descuento global (wizard) | `/home/leandro/projects/nexit/19.0/odoo/addons/sale/wizard/sale_order_discount.py:L147` | `_prepare_global_discount_lines`: reparto por combinacion de impuestos (D6). |
| Reparto del importe fijo | `/home/leandro/projects/nexit/19.0/odoo/addons/account/models/account_tax.py:L3659` | El importe fijo se compara contra `total_excluded + tax_amount`: es total CON impuestos (D7). |
| Redondeo de listas de precios | `/home/leandro/projects/nexit/19.0/odoo/addons/product/models/product_pricelist_item.py:L126` | Semantica de `price_round` que se espeja (D4). |
| Orden del calculo | `/home/leandro/projects/nexit/19.0/odoo/addons/product/models/product_pricelist_item.py:L606` | descuento -> redondeo -> recargo. |
| Linea de envio | `/home/leandro/projects/nexit/19.0/odoo/addons/delivery/models/sale_order_line.py:L9` | `is_delivery`, usado por `applies_to`. |
| Recompute del carrito | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/models/sale_order.py:L932` | `_recompute_cart`, hook del reajuste. |

## Documentacion afectada

- `README.md` del modulo — creado.
- `static/description/index.html` — creado.
- `README.md` raiz de `odoo_customization_sunra` — fila agregada.

## Plan del cambio en curso

| Tarea | Descripcion | Depende de | Archivos | Cubre |
|-------|-------------|-----------|----------|-------|
| **T01** | Esqueleto del modulo y manifest | — | `__init__.py`, `__manifest__.py` | — |
| **T02** | Modelo `payment.method.website.price`, constraints y `_apply_to_price` | T01 | `models/payment_method_website_price.py` | CA02, CA03, CA04 |
| **T03** | `website_price_ids` + `_get_website_price_rule` (resuelve por primario) | T02 | `models/payment_method.py` | CA05 |
| **T04** | ACL del modelo nuevo | T02 | `security/ir.model.access.csv` | — |
| **T05** | Pestana Website en el formulario del medio de pago | T03, T04 | `views/payment_method_views.xml` | CA01 |
| **T06** | Vidriera: helper y overrides de grilla y ficha | T03 | `models/product_template.py` | CA06, CA07 |
| **T07** | Templates de grilla, ficha y total del carrito | T06 | `views/website_sale_templates.xml`, `static/src/scss/payment_method_price.scss` | CA09 |
| **T08** | Repintado del segundo precio al cambiar de variante | T07 | `static/src/js/payment_method_price.js` | CA08 |
| **T09** | Checkout: campos del pedido, calculo y aplicacion del ajuste | T03 | `models/sale_order.py`, `models/sale_order_line.py` | CA14 |
| **T10** | Ruta `/shop/payment/method_price` y JS del formulario de pago | T09 | `controllers/website_sale_payment_method_price.py`, `static/src/js/payment_form_price.js` | CA11 |
| **T11** | Sync del medio preseleccionado y revalidacion en la transaccion | T10 | `controllers/website_sale_payment_method_price.py` | CA10, CA12 |
| **T12** | Recalculo del ajuste al cambiar el carrito | T09 | `models/sale_order.py` | CA13 |
| **T13** | Traduccion `es_AR` | T07, T09 | `i18n/es_AR.po` | CA15 |
| **T14** | Documentacion del modulo y fila en el README del repo | T13 | `README.md`, `static/description/index.html` | — |
| **T15** | Validacion manual end-to-end en la base local | T14 | — | — |
| **T16** | Pasada de @reviewer | T15 | — | — |
| **T17** | Fix del boton de pagar trabado tras la recarga: restaurar la seleccion antes del super (D15) | T10 | `static/src/js/payment_form_price.js` | CA16 |

> T01..T15 y T17 cerradas. T16 pendiente.

## Notas de implementacion

- **Minimal footprint**: no se reimplementa nada que el core ya haga. El reparto del descuento por
  grupo de impuesto, el redondeo, el formateo de moneda y la deteccion de medios compatibles son
  todos del core; el modulo aporta la configuracion, el calculo del objetivo y el pegamento.
- **Atajo deliberado (D10)**: recargar el paso de pago completo en vez de re-renderizar el fragmento.
  La alternativa es reconstruir a mano el contexto de pago del formulario, mucho mas fragil por poco
  beneficio.
- **Tercera trampa, encontrada en produccion (4-sep-2026)**: la restauracion de la seleccion se hacia
  con `radio.click()` **despues** del `super.willStart()`. Como los listeners de la interaccion se
  enganchan recien cuando `willStart` resuelve, ese click no ejecutaba `selectPaymentOption`: el radio
  quedaba marcado pero el boton de pagar deshabilitado y el formulario de tarjeta sin montar. El
  cliente lo vivia como "el boton de pagar queda trabado"; se destrababa eligiendo otro medio y
  volviendo (ese segundo click si tiene listener). Corregido en 1.0.1 (D15).
- **Dos trampas encontradas en vivo, no por lectura**: el patch del mixin que no tenia efecto (D11) y
  la pelea entre el sync del servidor y la eleccion del cliente (D9). Las dos aparecieron probando en
  el navegador, no revisando codigo: cualquier cambio en esta zona se valida en el sitio, no solo en
  el shell.
- **Tests automaticos**: `odoo_customization_sunra` no tiene `.swarm.conf`, asi que rige el default
  del repo (no se escriben tests salvo pedido). Los candidatos naturales, si se piden, son
  `_apply_to_price` (signo y redondeo) y `_get_payment_price_amount` (bases con y sin impuestos).
