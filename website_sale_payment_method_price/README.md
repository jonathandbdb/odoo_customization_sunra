# website_sale_payment_method_price

Descuento (o recargo) por **medio de pago** en el eCommerce: se publica en un **recuadro propio**
(un precio por renglón con su pill, el precio del medio como protagonista y la línea "Ahorrás $X" en verde) y se
aplica de verdad al pedido en el checkout.

| | |
|---|---|
| **Versión** | 1.3.1 |
| **Depende de** | `website_sale` |
| **Repos/entornos** | `odoo_customization_sunra`, rama `develop_19.0` |
| **Spec SDD** | `specs/website_sale_payment_method_price.md` |

## Para qué sirve

Nokey vende hoy en Tiendanube, donde cada producto muestra el precio de lista tachado, un pill con
el porcentaje y el precio con transferencia como protagonista. Odoo no tiene nada equivalente: los
recargos por medio de pago existieron en `payment.provider` hasta la v15 y fueron eliminados, y el
precio del carrito se calcula **antes** de que el cliente elija cómo pagar.

Este módulo cubre las dos puntas: la vidriera (el recuadro de precio) y el cobro (el descuento real
en el pedido).

## Configuración

**Ajustes → Medios de pago → abrir un medio → pestaña *Website*.** Una línea por sitio:

| Campo | Qué hace |
|-------|----------|
| **Sitio web** | Sitio al que aplica la línea. Un mismo medio puede tener reglas distintas por sitio |
| **Tipo** | `Descuento` baja el precio, `Recargo` lo sube |
| **Porcentaje** | 0 a 100. Una línea en 0 no tiene efecto |
| **Aplica a** | `Productos`, `Envíos` o `Productos y envíos`. Solo afecta al checkout: la vidriera muestra siempre el precio del producto |
| **Redondeo del precio** | Deja el precio como múltiplo de este valor, **después** del porcentaje. En 0 no redondea. Misma semántica que `price_round` de las listas de precios |
| **Mostrar el precio en el sitio web** | Si se dibuja el recuadro de precio. Un medio puede aplicar el descuento sin publicarlo |

La pestaña solo aparece en los medios **primarios** (Transferencia, Tarjeta, Mercado Pago Wallet…),
porque la acción del core filtra `is_primary = True`.

### Ejemplo (configuración real de Nokey)

Medio *Transferencia bancaria* → sitio *Nokey* → Descuento, 15,00, Productos, redondeo 0, Mostrar sí.
Con un producto a $ 157.300,00 la ficha muestra el recuadro con `$ 157.300,00` tachado, el pill
`-15% OFF` y `$ 133.705,00` protagonista con la etiqueta *pagando con* **Transferencia bancaria**; el
checkout cobra $ 133.705,00.

## Cómo funciona

### La vidriera: el recuadro de precio

Desde 1.3.0 el bloque de precio es un **recuadro propio** (segunda maqueta, la que eligió el
cliente), con **un precio por renglón** y el pill que lo explica al lado:

1. Dentro del recuadro, el precio de **referencia** tachado con un **pill neutro** (`-22%`): es el
   precio que el core ya publica cuando hay uno (el de lista, si la lista de precios aplica un
   descuento visible, o el **Precio comparativo** de la ficha del producto). Si no hay ninguno,
   este renglón **no se dibuja**.
2. El precio **actual** del core tachado, con el **pill de marca** (`#A3EA24`) del medio de pago
   (`-15% OFF`), solo si la regla es un descuento; con recargo no hay pill ni tachado.
3. El precio del medio de pago, **protagonista**.
4. **`Ahorrás $X`** en verde: la diferencia contra el precio de referencia (o contra el actual, si
   no hay referencia).
5. La etiqueta *pagando con* **`<medio>`**.
6. Un **slot vacío** (`div[@name='wspmp_installments']`) para que el módulo puente
   `website_sale_installment_plans_ux` publique ahí la línea de cuotas de ADHOC, si está instalado.
7. **Debajo del recuadro** (desde 1.3.1), el precio sin impuestos nacionales de
   `l10n_ar_website_sale` (si el sitio es AR), en cuerpo chico y gris: es un dato para ARCA, no un
   argumento de venta. El nodo **no se toca, no se mueve por herencia y no se elimina** — se
   reordena por CSS.

Los importes **no se duplican ni se recalculan**: son los mismos nodos que renderiza el core
(`oe_price` / `oe_default_price` en la ficha, `price_reduce` / `base_price` en la grilla), que la
herencia **envuelve** en su renglón para poder ponerles el pill al lado, y tacha por CSS.

> **Para que se vea el primer renglón hace falta un dato, no código**: hoy ningún producto de Nokey
> tiene *Precio comparativo* cargado ni un descuento porcentual visible en la lista de precios, así
> que el recuadro arranca en el punto 3. Cargando *Precio comparativo* en la ficha del producto
> aparece el renglón tachado de arriba con su `-XX%`, y `Ahorrás` pasa a contarse contra ese número.

El recuadro entero es `div[@name='wspmp_box']`: **el contrato de cualquier integración es el
atributo `name`, no la clase** — las clases (`o_wspmp_box_active`, `o_wspmp_discounted`) son
dinámicas (`t-attf-class`) para togglear la decoración según haya o no reglas visibles, y
`hasclass()` no las ve.

Se calcula sobre el precio **ya mostrado** (después de impuestos, según
`show_line_subtotals_tax_selection` del sitio), así los números son comparables. Aparece en:

- la grilla del shop (`_get_sales_prices`);
- la ficha del producto (`_get_additionnal_combination_info`), y se **repinta por JS** al cambiar de
  variante, porque ese precio se recalcula por jsonrpc y no re-renderiza el HTML;
- el total del carrito y del checkout, como una fila por medio de pago debajo del Total, con su
  propia etiqueta y su propio pill (sin recuadro ni slot de cuotas).

### El checkout

1. Al entrar al paso de pago, si el core deja un medio **preseleccionado** (lo hace cuando hay uno
   solo), el servidor ya aplica el ajuste antes de renderizar: no hay recarga extra.
2. Si hay varios medios, al elegir uno el navegador llama a `/shop/payment/method_price`, se aplica
   el ajuste y se recarga el paso de pago (el importe vive en el `dataset` del formulario, así que un
   refresh parcial dejaría un número viejo). La selección se conserva vía el parámetro `wspmp_pm`.
3. El ajuste se materializa **reusando el descuento global del core** (`sale.order.discount` con
   importe fijo), que reparte el importe por combinación de impuestos. Queda como una línea
   *"Descuento - <medio>"* con su IVA.
4. Si el cliente cambia de medio, el ajuste se cae. Si modifica el carrito, se recalcula.
5. Al crear la transacción se revalida que el ajuste corresponda al medio con el que se paga: si no,
   se corrige y el chequeo de importe del core pide refrescar. Nunca se cobra un importe distinto al
   mostrado.

## Qué agrega

### Modelo nuevo

`payment.method.website.price` — una línea por (medio de pago, sitio). Único por ese par.
Método central: `_apply_to_price(price)` (porcentaje y después redondeo, mismo orden que el core).

### Campos en modelos existentes

| Modelo | Campo | Para qué |
|--------|-------|----------|
| `payment.method` | `website_price_ids` | Las líneas de la pestaña Website |
| `sale.order` | `payment_price_rule_id` | Regla aplicada en el pedido (permite validar y revertir) |
| `sale.order.line` | `is_payment_method_discount` | Marca las líneas del módulo, para borrarlas sin adivinar por producto |

### Rutas

- `POST /shop/payment/method_price` — aplica o quita el ajuste sobre el carrito de la sesión.

## Convivencia con cupones y promociones

El ajuste **se suma** a los descuentos de cupones/promociones (decisión comercial de la cliente): un pedido con cupón y pago
por transferencia muestra **dos** renglones de descuento, uno por mecanismo.

Desde 1.1.0, los renglones de descuento que quedan **sin impuestos** (el residual que deja el reparto por grupo de impuesto)
no cuentan como base descontable. Sin eso, el residual de un descuento hacía que el otro se partiera en dos, y viceversa: los
dos descuentos quedaban en cuatro renglones que no se consolidaban solos. Si el pedido tiene una porción sin IVA **real** (un
producto sin impuestos), el descuento sí se parte por grupo: es lo correcto, no se puede revertir un IVA que no existe.

## Gotchas

- **La regla se busca por el medio primario, no por el de la transacción.** En el checkout el radio
  es siempre el primario (`card`), pero el proveedor **reescribe** `payment_method_id` con la marca
  real (`visa`, `argencard`) al procesar el feedback. Buscar por el método tal cual llega haría que
  un descuento configurado en `card` no se encuentre. Se usa `primary_payment_method_id`.
- **El JS se cuelga de la interacción, no del mixin.** `website_sale` copia `VariantMixin` al
  prototipo con `Object.assign` (`website_sale/interactions/website_sale.js:651`): un `patch()` sobre
  el mixin llega tarde y no tiene efecto. Hay que parchear `WebsiteSale.prototype`.
- **El servidor no le pisa la elección al cliente.** El sync del medio preseleccionado solo actúa si
  el pedido todavía no tiene regla; si no, cada recarga pelearía contra lo que el cliente eligió.
- **Un medio no disponible no muestra precio.** Se descartan las reglas de medios archivados o cuyo
  proveedor está deshabilitado, sin publicar, de otra compañía o restringido a otro sitio: mostrar
  el precio de un medio que el cliente no puede elegir sería mentirle.
- **Mercado Pago dinero en cuenta hay que habilitarlo a mano.** El módulo de MP activa por defecto
  solo tarjetas (`payment_mercado_pago/const.py`); `mercado_pago_wallet` existe en el catálogo pero
  nace inactivo. Verificar en staging que el checkout de MP lo ofrezca antes de prometerlo.
- **Impuestos mixtos.** El redondeo es por precio unitario y el ajuste se entrega al core como
  importe con impuestos, que lo reparte por grupo de impuesto: el total cierra exacto. Con 21 % y
  10,5 % en el mismo carrito puede haber diferencias de centavos en el reparto entre grupos.
- **`aria-label` no sirve como locator de herencia.** Es un atributo traducible
  (`TRANSLATED_ATTRS`, `odoo/tools/translate.py`) y la validación de vistas de Odoo 19 rechaza
  `View inheritance may not use attribute 'aria-label' as a selector` con `ParseError`
  (`ir_ui_view.py:412`), abortando la carga. El precio de la grilla (`span[@aria-label='Sale
  price']`) no tiene `name`, pero sí clase propia (`fw-bold`, además de `mb-0`): el `move` usa
  `//div[hasclass('product_price')]//span[hasclass('fw-bold')]`, único dentro del bloque de precio.
- **El recuadro se localiza siempre por `name`, nunca por clase.** `div[@name='wspmp_box']` y
  `div[@name='wspmp_installments']` son el contrato para cualquier integración (el módulo puente de
  cuotas incluido): el recuadro lleva clases condicionales por `t-attf-class`
  (`o_wspmp_box_active`, `o_wspmp_discounted`) y `hasclass()` solo lee el atributo estático `class`,
  con lo que un xpath por clase no matchearía y abortaría la combinación de la vista.
- **Los pills viven siempre en el DOM (en la ficha).** Para que el JS de variantes solo tenga que
  togglear clases y texto (nunca crear/destruir nodos dentro del recuadro), los tres `span` de pill
  de la ficha —`.o_wspmp_badge_pm` y los dos `.o_wspmp_badge_ref`, uno por cada precio tachado
  posible— se renderizan siempre, ocultos con `d-none` cuando no hay nada que mostrar. En la
  **grilla** el pill de referencia va con `t-if`: esa superficie no se repinta por JS.

## Validación manual

1. Configurar la regla y abrir `/shop`: cada tarjeta muestra el recuadro con el precio actual
   tachado, el pill `-15% OFF`, el precio del medio en grande y `Ahorrás $X` en verde.
2. Cargar **Precio comparativo** en la ficha de un producto: aparece un renglón más arriba, con ese
   importe tachado y un pill neutro (`-22%`), y el `Ahorrás` pasa a contarse contra ese número.
   Sacarlo: el renglón desaparece sin dejar hueco ni pill suelto.
3. Abrir una ficha y **cambiar de variante**: el recuadro se repinta (precio, ahorro, los dos pills
   y la decoración).
4. `/shop/cart`: el total muestra la fila del medio de pago debajo del Total, con su propio pill.
5. `/shop/payment`: elegir el medio con descuento → aparece la línea *Descuento* con su IVA y el
   Total baja al precio mostrado en la vidriera. Cambiar de medio → el descuento se cae.
6. Cambiar cantidades en el carrito con el descuento aplicado y volver al pago: el descuento se
   recalcula sobre el nuevo total.
7. Poner la regla en `Recargo` (surcharge): el recuadro muestra precio y etiqueta, pero **sin**
   pill, **sin** tachado y **sin** `Ahorrás` (CA23).
8. Con el módulo puente `website_sale_installment_plans_ux` instalado, verificar que la línea de
   cuotas queda **dentro** del recuadro, debajo del precio del medio de pago.
9. A 360 px de ancho, la etiqueta y el pill no se cortan ni desbordan el recuadro; en la grilla a
   390 px (2 columnas) el precio tachado y su pill entran en el **mismo** renglón.
