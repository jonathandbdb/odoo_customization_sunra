# website_sale_delivery_price_label

Reemplaza el precio (o el **"Gratis"** que muestra el core cuando la tarifa es 0) del badge de un
**método de envío** en el checkout del eCommerce por un **texto configurable** (ej. "A convenir").

| | |
|---|---|
| **Versión** | 1.0.0 |
| **Depende de** | `website_sale` |
| **Repos/entornos** | `odoo_customization_sunra`, rama `develop_19.0` |

## Para qué sirve

Nokey tiene un método de envío ("Envío con Instalación") con tarifa **$ 0** en Odoo, porque la
instalación se cotiza aparte según zona y se cobra por fuera del pedido. El core, ante una tarifa
0, muestra **"Gratis"** en el badge del selector de métodos de envío del checkout — un mensaje que
contradice al renglón siguiente, que explica que la instalación se cotiza y se abona aparte.

El módulo permite cargar, por método de envío, un texto que reemplaza a ese badge. Con
"A convenir" cargado en "Envío con Instalación", el checkout deja de decir "Gratis" y dice
"A convenir".

## Qué hace

- Cada `delivery.carrier` gana el campo **"Website price label"** (`website_price_label`, `Char`,
  traducible).
- Si el campo está cargado, ese texto se muestra en el badge de precio del selector de método de
  envío de `/shop/checkout`, en lugar del precio calculado o de "Gratis"/"Free".
- Si el campo está **vacío**, el comportamiento es **idéntico al core**: no cambia nada.
- El texto se muestra **desde el primer render** (sin parpadeo) y se sostiene tras elegir el método,
  cambiar a otro y volver.

## Configuración

**Inventario → Configuración → Métodos de envío → abrir el método → pestaña con la descripción
para el sitio web → campo "Website price label"** (placeholder `Ej: A convenir`). El campo es
traducible por idioma del sitio, igual que el resto de esa pestaña.

## Cómo funciona

### Vista heredada del carrier

`views/delivery_carrier_views.xml` hereda `delivery.view_delivery_carrier_form`
(`delivery_carrier_view_form`) y agrega `website_price_label` justo después de
`website_description`, que es el campo que `website_sale` ya agrega en esa misma pestaña.

### Template del checkout

`views/website_sale_templates.xml` hereda `website_sale.delivery_method`
(`odoo/addons/website_sale/views/delivery_form_templates.xml`, template `delivery_method`) y
reemplaza (`position="replace"`) el `<span name="price">` del badge:

- **Con etiqueta** (`dm.website_price_label`): un badge propio, con las **mismas clases y el mismo
  `name="price"`** que el core (`o_wsale_delivery_price_badge text-muted fw-bold text-end`) —
  necesario porque `_getDeliveryPriceBadge` y el CSS del core lo buscan por ese `name`. Expone el
  texto también en `data-price-label`, para que el JS lo pueda recuperar tras el RPC.
- **Sin etiqueta**: `$0`, que en la herencia de vistas de Odoo (dentro de un `position="replace"`)
  es la referencia al **nodo original reemplazado** — o sea, reconstruye el badge del core tal cual
  (con su `<small>Select to compute delivery rate</small>`), sin reescribirlo a mano. Comportamiento
  100 % idéntico al core.

### Parche JS

`static/src/js/delivery_price_label.js` (bundle `web.assets_frontend`) parchea con `patch()` el
método `_updateAmountBadge` de la interacción `Checkout`
(`website_sale/static/src/interactions/checkout.js:331`, el método que escribe "Free" en
`checkout.js:339` cuando `rateData.is_free_delivery`). El motivo: al elegir un método de envío, el
checkout llama a `/shop/get_delivery_rate` y **reescribe el badge con el precio/"Free" que devuelve
el servidor**, pisando cualquier contenido server-side previo.

El parche llama a `super()` primero (deja que el core escriba lo que le corresponda) y, si
`rateData.success` y el badge tiene `data-price-label`, vuelve a escribir la etiqueta encima. Sin
etiqueta o con error de tarifa, no toca nada — el comportamiento queda idéntico al de `super()`.

## Gotcha: copias por sitio (COW) del template

El locator del `xpath` en `views/website_sale_templates.xml` apunta **solo** al
`<span name="price">`, nunca a su contenido (el `<small>` interno). Motivo: el sitio puede tener una
**copia por sitio (COW)** del template `delivery_method`, editada alguna vez desde el editor web —
en Nokey esa copia ya no conserva el `<small>` del core: el badge quedó congelado como texto fijo
"Gratis" en `es_AR`. Anclar el `xpath` en el `<small>` rompía el checkout con un **500** aunque el
`-i` del módulo pasara sin error (la vista base validaba bien; la copia COW, no). Si se toca este
template a futuro, mantener el locator sobre el `span`, no sobre su interior.

## Traducciones

`i18n/es_AR.po` traduce el label del campo ("Etiqueta de precio en la web"), su ayuda y el
placeholder del formulario ("Ej: A convenir"). El texto que carga cada usuario en
`website_price_label` es un dato, no una traducción del módulo: se traduce por idioma del sitio
desde el propio campo (es `translate=True`).

## Qué NO incluye

- No cambia el **importe** del envío ni ningún cálculo de tarifa: el pedido se sigue facturando con
  la tarifa real del método (en el caso de uso, $ 0).
- No toca el **resumen del pedido** (`/shop/cart`, `/shop/payment`) ni el total: solo el badge del
  selector de métodos de envío del checkout.
- Sin modelos nuevos → sin ACL nuevas.
- Sin tests: el repo (`odoo_customization_sunra`) no declara `.swarm.conf` con `TESTS`/`E2E`
  requeridos.

## Validación manual

1. Configurar "Website price label" en un método de envío (ej. "A convenir").
2. Ir a `/shop/checkout` con al menos dos métodos de envío, uno con etiqueta y otro sin ella.
3. El método con etiqueta debe mostrar el texto configurado **desde el primer render** (sin
   parpadeo ni "Gratis" momentáneo).
4. Elegir ese método: el texto se mantiene (no lo pisa el precio que devuelve
   `/shop/get_delivery_rate`).
5. Elegir otro método y volver al que tiene etiqueta: el texto se mantiene.
6. El o los métodos **sin** etiqueta deben comportarse igual que antes de instalar el módulo
   (precio calculado o "Gratis"/"Free" según corresponda).
7. Vaciar el campo del método: el badge vuelve a mostrar el comportamiento del core.
