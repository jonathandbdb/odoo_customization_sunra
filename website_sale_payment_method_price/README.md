# website_sale_payment_method_price

Descuento (o recargo) por **medio de pago** en el eCommerce: se muestra como un segundo precio
debajo del precio de lista y se aplica de verdad al pedido en el checkout.

| | |
|---|---|
| **Versión** | 1.0.2 |
| **Depende de** | `website_sale` |
| **Repos/entornos** | `odoo_customization_sunra`, rama `develop_19.0` |
| **Spec SDD** | `specs/website_sale_payment_method_price.md` |

## Para qué sirve

Nokey vende hoy en Tiendanube, donde cada producto muestra el precio de lista y debajo un segundo
precio con la etiqueta *"con TRANSFERENCIA"* (15 % menos). Odoo no tiene nada equivalente: los
recargos por medio de pago existieron en `payment.provider` hasta la v15 y fueron eliminados, y el
precio del carrito se calcula **antes** de que el cliente elija cómo pagar.

Este módulo cubre las dos puntas: la vidriera (el segundo precio) y el cobro (el descuento real en
el pedido).

## Configuración

**Ajustes → Medios de pago → abrir un medio → pestaña *Website*.** Una línea por sitio:

| Campo | Qué hace |
|-------|----------|
| **Sitio web** | Sitio al que aplica la línea. Un mismo medio puede tener reglas distintas por sitio |
| **Tipo** | `Descuento` baja el precio, `Recargo` lo sube |
| **Porcentaje** | 0 a 100. Una línea en 0 no tiene efecto |
| **Aplica a** | `Productos`, `Envíos` o `Productos y envíos`. Solo afecta al checkout: la vidriera muestra siempre el precio del producto |
| **Redondeo del precio** | Deja el precio como múltiplo de este valor, **después** del porcentaje. En 0 no redondea. Misma semántica que `price_round` de las listas de precios |
| **Mostrar el precio en el sitio web** | Si se dibuja el segundo precio. Un medio puede aplicar el descuento sin publicarlo |

La pestaña solo aparece en los medios **primarios** (Transferencia, Tarjeta, Mercado Pago Wallet…),
porque la acción del core filtra `is_primary = True`.

### Ejemplo (configuración real de Nokey)

Medio *Transferencia bancaria* → sitio *Nokey* → Descuento, 15,00, Productos, redondeo 0, Mostrar sí.
Con un producto a $ 157.300,00 la ficha muestra `$ 133.705,00 con Transferencia bancaria` y el
checkout cobra $ 133.705,00.

## Cómo funciona

### La vidriera

El segundo precio se calcula sobre el precio **ya mostrado** (después de impuestos, según
`show_line_subtotals_tax_selection` del sitio), así los dos números son comparables. Aparece en:

- la grilla del shop (`_get_sales_prices`);
- la ficha del producto (`_get_additionnal_combination_info`), y se **repinta por JS** al cambiar de
  variante, porque ese precio se recalcula por jsonrpc y no re-renderiza el HTML;
- el total del carrito y del checkout, como una fila por medio de pago debajo del Total.

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

## Validación manual

1. Configurar la regla y abrir `/shop`: cada tarjeta muestra el precio y debajo el del medio de pago.
2. Abrir una ficha y **cambiar de variante**: el segundo precio se actualiza.
3. `/shop/cart`: el total muestra la fila del medio de pago debajo del Total.
4. `/shop/payment`: elegir el medio con descuento → aparece la línea *Descuento* con su IVA y el
   Total baja al precio mostrado en la vidriera. Cambiar de medio → el descuento se cae.
5. Cambiar cantidades en el carrito con el descuento aplicado y volver al pago: el descuento se
   recalcula sobre el nuevo total.
