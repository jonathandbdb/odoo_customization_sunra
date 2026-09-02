# website_sale_wire_transfer_ux

Botón **Copiar CBU** y link **Cambiar medio de pago** en la página de confirmación del eCommerce, y
los datos de la transferencia en el mail de orden pendiente.

| | |
|---|---|
| **Versión** | 1.0.0 |
| **Depende de** | `website_sale`, `payment_custom` (y **requiere `l10n_ar` instalado**, ver *Configuración*) |
| **Repos/entornos** | `odoo_customization_sunra`, rama `develop_19.0` |
| **Spec SDD** | `specs/website_sale_wire_transfer_ux.md` |

## Para qué sirve

Cuando el cliente elige **Transferencia bancaria** en la tienda, Odoo lo deja en la página *"Gracias
por su orden"* con el contenido del campo **Mensaje pendiente** del proveedor de pago (los datos
bancarios cargados a mano) y la **Comunicación** (el número de pedido que sirve de referencia). Le
faltan dos cosas que sí tienen otras tiendas:

1. **Un botón para copiar el CBU.** Un botón pegado dentro del propio campo "Mensaje pendiente" no
   puede funcionar: ese campo es HTML **sanitizado** y Odoo le borra los `<button>` (con su
   contenido) y cualquier `onclick`/`<script>` — solo sobrevive un `<a class="btn">` decorativo, sin
   comportamiento. El botón tiene que venir del template, y de ahí este módulo.
2. **Poder cambiar de medio de pago.** El core no tiene vuelta atrás: al elegir transferencia el
   pedido queda en presupuesto enviado y la sesión pierde el carrito, así que el cliente que se
   arrepiente no puede volver a elegir (por ejemplo) Mercado Pago sin escribirle a la empresa.

Además, el mail que recibe el cliente (*"<Empresa> Orden pendiente (Ref S000xx)"*) **no llevaba los
datos bancarios**: si cerraba la pestaña, perdía el CBU.

## Qué agrega

### En la página de confirmación (`/shop/confirmation`)

Solo cuando el pago quedó **pendiente** con el proveedor de **transferencia bancaria**:

- **`CBU: <número>` + botón `Copiar CBU`** — copia el CBU al portapapeles y confirma con un
  *"¡Copiado!"* que vuelve a su texto original a los 2 segundos.
- **Link `Cambiar medio de pago`** — reabre el paso de pago del checkout con todos los medios
  disponibles.

El número **sale de la cuenta bancaria de la compañía** (`res.partner.bank` con `acc_type = 'cbu'`),
no del texto del mensaje: es la única fuente de verdad, así el botón no puede copiar un CBU
desactualizado. Si no hay cuenta con CBU cargada, la tira no se dibuja (no rompe nada).

### En el mail de orden pendiente

Un `post_init_hook` inserta en la plantilla del core `sale.mail_template_sale_payment_executed`
(*"Sales: Payment Done"*, la que se manda cuando el pago queda pendiente) **una línea** que llama a
`payment.transaction._get_wire_transfer_mail_block()`; ese método arma el **mensaje pendiente**, el
**CBU** y la **Comunicación**, con las etiquetas en el idioma del destinatario. La línea se inserta en
**todos los idiomas activos** (el cuerpo del mail es traducible: cada idioma guarda el suyo). La
plantilla del core es `noupdate="1"`, así que la edición sobrevive a los upgrades; el
`uninstall_hook` la deja como estaba.

> Si alguien editó a mano el cuerpo de esa plantilla y el punto de inserción ya no se puede ubicar, el
> hook **no toca nada** y deja un `WARNING` en el log (el mail sigue saliendo, sin los datos
> bancarios). En ese caso, pegar a mano en *Ajustes → Técnico → Plantillas de correo*, justo antes de
> los saludos finales:
> ```xml
> <t t-out="transaction_sudo._get_wire_transfer_mail_block()" class="o_swt_mail_transfer_data"/>
> ```
> Un idioma que se active **después** de instalar el módulo tampoco lo tiene (el hook corre una sola
> vez): reinstalar el módulo o pegar esa línea en el cuerpo de ese idioma.

## Configuración

> ⚠️ **Requiere `l10n_ar` instalado**: de ahí sale el tipo de cuenta `cbu`. No está en `depends` a
> propósito (es una localización: ponerla como dependencia la instalaría, plan de cuentas incluido, en
> cualquier base donde se instale este módulo). Si al instalar no hay ninguna cuenta con CBU, el
> módulo deja un `WARNING` en el log.

**Contabilidad → Configuración → Cuentas bancarias** (o la pestaña *Cuentas bancarias* del contacto
de la compañía): cargar la cuenta con el **CBU de 22 dígitos** en *Número de cuenta*. La localización
argentina (`l10n_ar`) detecta sola que es un CBU y deja `Tipo de cuenta = CBU`; de ese tipo depende
que el botón aparezca. La cuenta con el número de cuenta común (ej. `055-4876293-2`) se puede
conservar: el módulo busca la que tiene tipo CBU.

Y en el **Mensaje pendiente** del proveedor de transferencia (*Sitio web → Configuración → Proveedores
de pago → Transferencia bancaria → pestaña Mensajes*): conviene **quitar la línea del CBU**, porque
ahora la pinta el módulo con su botón. El resto (banco, titular, CUIT, alias, cuenta, instrucciones)
queda como está.

## Cómo funciona por dentro

| Pieza | Archivo | Qué hace |
|-------|---------|----------|
| Template | `views/website_sale_templates.xml` | Hereda `website_sale.payment_confirmation_status` y agrega la tira del CBU y el link, después de la Comunicación |
| CBU | `models/payment_provider.py` | `_get_wire_transfer_cbu_account()` devuelve la cuenta con `acc_type = 'cbu'` de la compañía del proveedor |
| Copiado | `static/src/js/wire_transfer_confirmation.js` | `Interaction` de v19 (`public.interactions`) con la Clipboard API y fallback a `textarea` + `execCommand` para contextos no seguros |
| Cambio de medio | `controllers/website_sale_wire_transfer_ux.py` | Ruta `/shop/wire-transfer/change-payment-method` (POST con token CSRF) |
| Bloque del mail | `models/payment_transaction.py` | `_get_wire_transfer_mail_block()` arma el HTML con las etiquetas traducidas |
| Mail | `__init__.py` | `post_init_hook` / `uninstall_hook` sobre `sale.mail_template_sale_payment_executed` |

### La ruta de cambio de medio de pago

`/shop/wire-transfer/change-payment-method` deshace las tres cosas que dejan el checkout cerrado:

1. **Cancela la transacción pendiente** (`_set_canceled`), para no dejar una transferencia fantasma.
2. **Devuelve el pedido a presupuesto** (`action_draft`), porque `_check_cart` del core rechaza todo
   lo que no esté en `draft`.
3. **Vuelve a apuntar el carrito de la sesión** (`sale_order_id`), que `sale_reset()` había borrado.

Los tres pasos son necesarios: `Website._get_and_cache_current_cart()` descarta el carrito si el
pedido no está en `draft` **o** si su última transacción sigue en `pending`.

El único pedido alcanzable es el de la propia sesión (`sale_last_order_id`), del mismo sitio web, en
`draft`/`sent`, sin pago hecho (`authorized`/`done`) y —si hay usuario logueado— del propio partner
(`authenticate()` no limpia la sesión, así que en un navegador compartido el pedido de la sesión puede
ser de otra persona). Nunca un pedido arbitrario por id.

Es **POST con token CSRF** aunque en pantalla sea un link: por GET, Odoo no valida CSRF y un
`<img src="…">` en cualquier sitio ajeno alcanzaría para cancelarle la transferencia al visitante.

## Probado

Compra completa en local (base `nokey`, sitio `miluan.odoo.com`): confirmación con la tira del CBU en
español, copiado verificado pegando el valor en un input (coincide con el CBU de la cuenta), label que
vuelve a los 2 s, *Cambiar medio de pago* → `/shop/payment` con el pedido en `draft` y la transacción
en `cancel`, y nuevo pago que vuelve a dejar el pedido en `sent` con su transacción `pending`. Mail de
orden pendiente disparado por el mismo camino del core (`_send_payment_succeeded_for_order_mail`):
sale con el mensaje, el CBU y la Comunicación. `post_init_hook` y `uninstall_hook` probados en los dos
idiomas activos (`en_US`, `es_AR`), ida y vuelta, con el cuerpo volviendo carácter por carácter al del
core. Y la ruta rechaza `GET` (405) y `POST` sin token (400).
