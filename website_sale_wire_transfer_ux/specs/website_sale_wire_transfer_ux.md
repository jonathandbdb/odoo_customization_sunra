# Spec de modulo: website_sale_wire_transfer_ux

| Campo | Valor |
|-------|-------|
| **Modulo** | `website_sale_wire_transfer_ux` |
| **Version** | `1.0.0` (== `version` del `__manifest__.py`, formato `x.x.x`) |
| **Serie Odoo** | `19` (informativa) |
| **Estado** | `implemented` (validado end-to-end en la base local; @reviewer paso sin criticos y sus 7 warnings estan resueltos en T11 — falta re-pasada sobre ese endurecimiento) |
| **Actualizado** | `2026-09-02` |

## Objetivo

Cerrar las dos cosas que le faltan a la pagina de confirmacion del eCommerce cuando el cliente elige
**Transferencia bancaria**, mas los datos bancarios en el mail:

1. **Boton "Copiar CBU"** en la confirmacion, con el CBU tomado del dato estructurado de la compania.
2. **Link "Cambiar medio de pago"**, que reabre el paso de pago del checkout con todos los medios.
3. **Datos de la transferencia en el mail de orden pendiente** (mensaje pendiente + CBU +
   Comunicacion), que hoy no los lleva.

Motivo: pedido de la cliente (Lucila, 02/09/2026). En su otra tienda (Tiendanube) las dos cosas son
nativas. Ella ya habia insertado un boton "COPIAR CBU" dentro del campo **Mensaje pendiente** del
proveedor y no hacia nada: ese campo es HTML **sanitizado** y Odoo le borra los `<button>` (con su
contenido) y todo `onclick`/`<script>`; solo sobrevive el `<a class="btn">` decorativo que inserta el
editor. Un boton funcional **no puede vivir en ese campo**: tiene que venir del template.

## Decisiones vigentes

| # | Decision | Valor vigente |
|---|----------|---------------|
| D1 | ¿De donde sale el CBU que copia el boton? | De la **cuenta bancaria de la compania** (`res.partner.bank` con `acc_type = 'cbu'`), no del texto libre del mensaje pendiente. `l10n_ar` agrega ese tipo y lo detecta solo validando el numero con `stdnum.ar.cbu` (`/home/leandro/projects/nexit/19.0/odoo/addons/l10n_ar/models/res_partner_bank.py:21-27`). Un boton que copia un numero parseado de HTML libre puede copiar un CBU viejo: es plata a la cuenta equivocada. |
| D2 | ¿Se agrega un campo `cbu` propio? | **No.** Odoo AR ya tiene donde guardarlo (D1) y ademas ese dato alimenta el QR bancario del core. Cero campos nuevos. |
| D3 | ¿Donde se inyecta el boton? | Herencia de **`website_sale.payment_confirmation_status`** (`/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/templates.xml:4175`), con `xpath` sobre `//div[@id='order_reference']`, o sea dentro del bloque `tx_sudo.provider_code == 'custom'` y al lado de la Comunicacion. Esa pagina **no** pasa por `payment.state_header` (ese es el del portal y `/payment/status`): imprime `provider.pending_msg` directo en `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/templates.xml:4206`. |
| D4 | ¿Se muestra el CBU tambien como texto? | **Si**, al lado del boton. Es lo que evita el drift silencioso: si el mensaje pendiente dijera otro numero, se ve en pantalla. La configuracion recomendada es quitar la linea del CBU del mensaje (queda en el README). |
| D5 | ¿Solo transferencia? | **Si**, en los tres lugares: la tira, el link y el bloque del mail exigen `custom_mode == 'wire_transfer'` y `tx.state == 'pending'`. `provider_code == 'custom'` tambien cubre "pago en tienda" y "contra reembolso", donde un CBU no aplica. |
| D6 | ¿Como se cambia el medio de pago? | Con una **ruta propia** que reabre el checkout (`/shop/wire-transfer/change-payment-method`). El camino del core seria el portal (`/my/orders/<id>` → "Pagar ahora"), pero depende de `require_payment = company.portal_confirmation_pay` (`/home/leandro/projects/nexit/19.0/odoo/addons/sale/models/sale_order.py:356-359`) y en la base **las 4 companias lo tienen en falso**; prenderlo agregaria "Pagar ahora" a **todos** los presupuestos (cambio de negocio, no de este modulo). Ademas deja al cliente en el portal, no en la tienda. |
| D7 | ¿Que hace exactamente esa ruta? | Las **tres** cosas necesarias: cancela la transaccion pendiente, devuelve el pedido a `draft` (`action_draft`, `/home/leandro/projects/nexit/19.0/odoo/addons/sale/models/sale_order.py:1059`) y vuelve a apuntar `sale_order_id` en la sesion. Las tres, porque `Website._get_and_cache_current_cart()` (`/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/models/website.py:803-810`) descarta el carrito si el pedido no esta en `draft` **o** si su ultima transaccion sigue en `pending`, y `_check_cart` exige `draft` (`/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/controllers/main.py:1749-1752`). |
| D8 | ¿Que pedido alcanza la ruta? | Solo el de la **propia sesion** (`sale_last_order_id`), del mismo `website_id`, en `draft`/`sent` y sin pago `authorized`/`done`. Sin `access_token` en la URL ni ids arbitrarios. |
| D9 | ¿Se cancela la transaccion pendiente? | **Si** (`_set_canceled`, permitido desde `pending` — `/home/leandro/projects/nexit/19.0/odoo/addons/payment/models/payment_transaction.py:967-979`). Si no, queda una transferencia fantasma en `pending` y el propio core rechaza el carrito (D7). |
| D10 | ¿Como llegan los datos bancarios al mail? | Con un **`post_init_hook`** que inserta el bloque en la plantilla del core `sale.mail_template_sale_payment_executed`, y un `uninstall_hook` que lo quita. Los `mail.template` **no son heredables**; copiar la plantilla al modulo obligaria a mantener todo el cuerpo y perder su traduccion, y el paso manual habria que repetirlo (y olvidarse) en las tres bases. La plantilla del core es `noupdate="1"` (`/home/leandro/projects/nexit/19.0/odoo/addons/sale/data/mail_template_data.xml:3`), asi que la edicion sobrevive a los upgrades. Lo que se inserta es **una sola linea** (`<t t-out="transaction_sudo._get_wire_transfer_mail_block()"/>`): el contenido lo arma Python, asi la linea no depende del idioma y la superficie a insertar/quitar es minima. |
| D11 | ¿Cual es la plantilla del mail de orden pendiente? | **`sale.mail_template_sale_payment_executed`** ("Sales: Payment Done", `/home/leandro/projects/nexit/19.0/odoo/addons/sale/data/mail_template_data.xml:344`), NO `mail_template_sale_confirmation`. Con la transaccion en `pending` el core manda esa (`/home/leandro/projects/nexit/19.0/odoo/addons/sale/models/payment_transaction.py:72`, `_send_payment_succeeded_for_order_mail`) y el pedido queda en `sent`. Verificado en la base: el mensaje "Miluan SRL Orden pendiente (Ref S00057)" sale de ahi. |
| D12 | ¿Y si alguien edito el cuerpo de esa plantilla? | El hook **no adivina**: si el ancla (`</t>\n        <br/><br/>`, unica y sin texto traducible) no aparece exactamente una vez, deja un `WARNING` y no toca nada. El mail sigue saliendo, sin los datos. Al desinstalar, el bloque se quita **por marcador** (regex sobre el nodo con `class="o_swt_mail_transfer_data"`, no por igualdad de string) y con dos chequeos: que no queden restos (`_get_wire_transfer_` en el cuerpo) y que el ancla vuelva a estar (si no, `WARNING` para restaurar la plantilla a mano). |
| D16 | ¿Se toca solo el idioma fuente? | **No**: se recorren **todos los idiomas activos** (`res.lang` activos + `en_US`). `body_html` es traducible y Odoo distribuye los cuerpos traducidos en los `.po` de `sale`, asi que escribir solo el fuente dejaria a cada idioma ya traducido mandando el mail **sin** los datos bancarios, en silencio. Un idioma que se active despues de instalar no queda cubierto (el hook corre una vez): esta anotado en Edge cases. |
| D17 | ¿Se depende de `l10n_ar` en el manifest? | **No.** Es una localizacion: ponerla en `depends` la instalaria (plan de cuentas incluido) en cualquier base que instale este modulo. En su lugar, el requisito esta en la `description` del manifest y el `post_init_hook` deja un **`WARNING`** en el log si ninguna compania con proveedor de transferencia tiene cuenta con CBU — el modo de falla pasa de silencioso a visible justo cuando el admin puede arreglarlo. |
| D18 | ¿Se valida el partner en la ruta? | **Si**, ademas de la sesion: `authenticate()` no limpia el diccionario de sesion (solo `logout()`), asi que en un navegador compartido el `sale_last_order_id` puede ser de otra persona. Si hay usuario logueado, el pedido tiene que ser suyo. |
| D13 | ¿Como se copia al portapapeles? | `navigator.clipboard.writeText` con fallback a `textarea` + `execCommand('copy')`. La Clipboard API solo existe en contextos seguros: PROD/STG son https y `localhost` cuenta como seguro, pero el fallback cubre un http eventual. |
| D14 | Patron del JS | **`Interaction`** de v19 registrada en `public.interactions` (patron de `/home/leandro/projects/nexit/19.0/odoo/addons/web/static/src/public/show_password.js:1-23` y del vecino `website_sale_installation_appointment`). `publicWidget` es legacy y no se usa en codigo nuevo. |
| D15 | ¿GET o POST en la ruta de cambio de medio? | **POST con token CSRF** (`methods=["POST"]`), aunque en pantalla siga siendo un link (`<form>` + `<button class="btn btn-link p-0">`). Por GET, Odoo no valida CSRF (solo lo hace en metodos no seguros) y un `<img src=...>` en cualquier sitio de terceros alcanzaria para cancelarle la transferencia al visitante y devolverle el pedido a `draft`; ademas queda expuesto al prefetch del navegador. Verificado: `GET` responde **405** y un `POST` sin token, **400**. |

## Alcance

### Incluye
- Tira `CBU: <numero>` + boton **Copiar CBU** en `/shop/confirmation`, solo para transferencia
  pendiente, con feedback "¡Copiado!" temporal.
- Link **Cambiar medio de pago** y la ruta que reabre el paso de pago del checkout.
- Bloque con mensaje pendiente + CBU + Comunicacion en el mail de orden pendiente (via hooks).
- Traduccion `es_AR` de todas las cadenas visibles.
- Documentacion (`README.md` + `static/description/index.html`) y fila en el README raiz del repo.

### NO incluye
- **Campo propio de CBU o de alias** (D1, D2). Tampoco boton "Copiar alias": la localizacion AR no
  tiene campo de alias y la cliente pidio el CBU.
- **Activar el pago online en presupuestos** (`portal_confirmation_pay`) ni tocar el flujo del portal
  (D6).
- **Cambiar el circuito de acreditacion de la transferencia** ni la reserva de stock.
- **Editar el mensaje pendiente por codigo**: es configuracion del cliente (se recomienda quitar la
  linea del CBU, no se fuerza).
- Modificar core/enterprise: todo es `_inherit`, herencia de template y hooks sobre datos.

## Modelos

### Extendidos

| Modelo | Que se agrega |
|--------|--------------|
| `payment.provider` | `_get_wire_transfer_cbu_account()` |
| `payment.transaction` | `_get_wire_transfer_mail_block()` |

Sin modelos nuevos y sin campos nuevos (D2).

## Campos

Ninguno: no se agrega ningun campo (D2). El CBU vive en el `acc_number` de la cuenta bancaria
de la compania, con `acc_type = 'cbu'`.

## Metodos

### `PaymentProvider._get_wire_transfer_cbu_account(self)`
Devuelve la primera `res.partner.bank` con `acc_type == 'cbu'` del partner de la compania del
proveedor, o un recordset vacio si el proveedor no es transferencia o no hay cuenta cargada. Lee los
`bank_ids` en `sudo()` (el cliente del sitio no tiene acceso). Es el unico lugar que resuelve el CBU:
lo usan el template y el bloque del mail.

### `PaymentTransaction._get_wire_transfer_mail_block(self)`
Arma el bloque que va en el mail (mensaje pendiente + CBU + Comunicacion) y devuelve `Markup`,
o vacio si la transaccion no es una transferencia pendiente. Las etiquetas se traducen con `_()`
en el idioma del destinatario (el que la plantilla pone en el contexto al renderizar), que es lo
que permite insertar una sola linea igual para todos los idiomas (D16).
**No usa `ensure_one()` a proposito**: `ai` (Enterprise) valida los `mail.template` al guardarlos
**renderizandolos** (`/home/leandro/projects/nexit/19.0/enterprise/ai/models/mail_template.py:14`),
y en esa pasada la transaccion viene vacia. Un metodo llamado desde el cuerpo de un mail no puede
levantar excepciones: con `ensure_one()`, el `write` del hook fallaba con `ValidationError` y el
parche no se aplicaba (encontrado en vivo).

### `WebsiteSaleWireTransferUx.shop_wire_transfer_change_payment_method(self, **kwargs)`
Ruta `/shop/wire-transfer/change-payment-method` (`type='http'`, `auth='public'`, `POST`,
`website=True`, `sitemap=False`). Cancela la transaccion pendiente, `action_draft()` del pedido,
restaura `sale_order_id` en la sesion, limpia `sale_transaction_id` y redirige a `/shop/payment`.

### `WebsiteSaleWireTransferUx._get_reopenable_order(self)`
Guardas de D8. Devuelve recordset vacio si el pedido no es reabrible (y la ruta manda a `/shop`).

### `post_init_hook(env)` / `uninstall_hook(env)` / `_mail_template_langs(env)` / `_check_cbu_configuration(env)`
Insertan/quitan el bloque del mail (D10, D12), por idioma. Trampa registrada: el valor de un campo
`Html` vuelve como `Markup` y **`Markup.replace()` escapa sus argumentos**, asi que el reemplazo se
hace siempre sobre `str(...)` — sin eso el parche no encuentra el ancla y **se pierde en silencio**
(paso en la primera version).

## Assets y JS

`web.assets_frontend` → `static/src/js/wire_transfer_confirmation.js`.

`WireTransferConfirmation extends Interaction`, `selector = ".o_swt_transfer_data"`, con
`dynamicContent` sobre `.o_swt_copy`: `t-on-click` para copiar y `t-out` para el label. El label
vuelve a su valor original con `Interaction.INITIAL_VALUE` (`/home/leandro/projects/nexit/19.0/odoo/addons/web/static/src/public/colibri.js:172-175`)
y `waitForTimeout(..., 2000)` (`/home/leandro/projects/nexit/19.0/odoo/addons/web/static/src/public/interaction.js:253`). Sin SCSS propio: alcanzan
las clases de Bootstrap.

## Vistas

| XML ID | Hereda | Que agrega |
|--------|--------|-----------|
| `website_sale_wire_transfer_ux.payment_confirmation_status` | `website_sale.payment_confirmation_status` | Tira del CBU con el boton y link de cambio de medio de pago |

## Seguridad

Sin modelos nuevos → sin ACL. El acceso del cliente publico a la cuenta bancaria se resuelve con
`sudo()` acotado a la lectura del CBU (D1); la ruta publica no acepta ids externos (D8).

## Reglas de negocio

- La tira solo se dibuja con `tx.state == 'pending'`, `provider_code == 'custom'`,
  `custom_mode == 'wire_transfer'` y cuenta con CBU cargada.
- El bloque del mail solo se renderiza con transaccion `pending` de proveedor `custom`.
- Reabrir el checkout **cancela** el pago pendiente: el cliente que vuelve a elegir transferencia
  genera una transaccion nueva (y una Comunicacion nueva si cambia el pedido).
- El link solo se dibuja mientras el pedido siga siendo reabrible (`draft`/`sent`): si un
  administrativo lo confirmo a mano con la transferencia acreditada, el link desaparece en vez de
  llevar a la tienda sin explicacion.

## Edge cases

| Caso | Comportamiento |
|------|----------------|
| Sin cuenta con `acc_type = 'cbu'` | No se dibuja la tira ni la linea del CBU en el mail; el resto sigue igual |
| Navegador sin Clipboard API (http) | Fallback `textarea` + `execCommand`; si tampoco copia, el label avisa "Presioná Ctrl+C para copiar" |
| Sesion vencida / otro navegador | La ruta no encuentra `sale_last_order_id` y redirige a `/shop` (no expone pedidos ajenos) |
| Pedido ya pagado o confirmado | La ruta redirige a `/shop` sin tocar nada (D8) |
| Plantilla de correo editada a mano | El hook no toca nada y loguea un `WARNING` (D12) |
| Modulo desinstalado | `uninstall_hook` quita el bloque del mail: sin eso el mail llamaria a un metodo inexistente y no se renderizaria |
| Pedido ya confirmado a mano | El link no se dibuja (la condicion mira `order.state`) |
| Idioma activado despues de instalar | Su cuerpo de la plantilla no tiene el bloque (el hook corre una sola vez): reinstalar el modulo o pegar la linea a mano |
| `l10n_ar` no instalado | No hay tipo de cuenta `cbu` → no hay CBU que copiar; el `post_init_hook` lo avisa con un `WARNING` (D17) |
| Navegador comparte sesion entre dos personas | Si hay usuario logueado y el pedido de la sesion no es suyo, la ruta no lo toca (D18) |

## Criterios de aceptacion

| # | Criterio | Estado |
|---|----------|--------|
| **CA01** | En `/shop/confirmation` con transferencia pendiente aparece `CBU: <numero>` y el boton **Copiar CBU** | OK |
| **CA02** | El boton copia el CBU **exacto** de la cuenta con `acc_type = 'cbu'` (verificado pegando el valor) | OK |
| **CA03** | El label pasa a "¡Copiado!" y vuelve a "Copiar CBU" a los 2 s | OK |
| **CA04** | Sin cuenta con CBU cargada, la pagina se dibuja igual, sin la tira | OK |
| **CA05** | El link **Cambiar medio de pago** deja el checkout en `/shop/payment` con los medios disponibles | OK |
| **CA06** | Tras ese link, el pedido queda en `draft` y la transaccion de transferencia en `cancel` con su motivo | OK |
| **CA07** | Desde el checkout reabierto se puede pagar y el pedido vuelve a `sent` con su transaccion `pending` | OK |
| **CA08** | La ruta no hace nada (redirige a `/shop`) si el pedido no es de la sesion, es de otro sitio o ya se cobro | OK |
| **CA09** | El mail de orden pendiente llega con mensaje pendiente + CBU + Comunicacion | OK |
| **CA10** | `post_init_hook` parchea la plantilla en **todos los idiomas activos**; `uninstall_hook` la deja identica al original (2112/2111 caracteres y ancla intacta, ida y vuelta) | OK |
| **CA11** | Las cadenas visibles salen en castellano (boton, feedback, link, etiquetas del mail) | OK |
| **CA12** | La tira no aparece con "pago en tienda" ni "contra reembolso" | OK |
| **CA13** | La ruta rechaza `GET` (405) y un `POST` sin token CSRF (400) | OK |
| **CA14** | El link no se dibuja si el pedido ya no es reabrible | OK (por codigo; no probado en el navegador) |
| **CA15** | Con usuario logueado, la ruta ignora un pedido de la sesion que no sea del propio partner | Por codigo (no probado en el navegador) |

## Referencias al core

| Que | Donde |
|-----|-------|
| `pending_msg` (Html sanitizado, sin `sanitize=False`) | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/models/payment_provider.py:140-145` |
| Sanitizer: mata `<button>`, borra `on*` y `data-*` genericos | `/home/leandro/projects/nexit/19.0/odoo/odoo/tools/mail.py:68-93` |
| Template de la confirmacion (imprime `pending_msg`) | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/templates.xml:4175`, `:4206`, bloque `custom` `:4226-4237` |
| Controller `/shop/confirmation` (usa `sale_last_order_id`) | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/controllers/main.py:1686-1701` |
| `sale_reset()` antes de la confirmacion | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/controllers/main.py:1679` |
| Carrito de la sesion: descarta si no esta en `draft` o si la tx sigue `pending` | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/models/website.py:792-812` (clave `CART_SESSION_CACHE_KEY`, `:24`) |
| `_check_cart` exige `draft` | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/controllers/main.py:1749-1752` |
| `action_draft()` (permite `sent` → `draft`) | `/home/leandro/projects/nexit/19.0/odoo/addons/sale/models/sale_order.py:1059-1066` |
| `_set_canceled` (permitido desde `pending`) | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/models/payment_transaction.py:967-979` |
| Pendiente: la SO queda en `sent` y se manda el mail "Payment Done" | `/home/leandro/projects/nexit/19.0/odoo/addons/sale/models/payment_transaction.py:40-72` |
| Plantilla del mail parcheada (`noupdate="1"`) | `/home/leandro/projects/nexit/19.0/odoo/addons/sale/data/mail_template_data.xml:3`, `:344-372` |
| `mail.template` renderiza sin restricciones de expresion | `/home/leandro/projects/nexit/19.0/odoo/addons/mail/models/mail_template.py:24` (`_unrestricted_rendering`) |
| `acc_type = 'cbu'` autodetectado (AR) | `/home/leandro/projects/nexit/19.0/odoo/addons/l10n_ar/models/res_partner_bank.py:21-27` |
| `Interaction` (base, `waitForTimeout`, `dynamicContent`) | `/home/leandro/projects/nexit/19.0/odoo/addons/web/static/src/public/interaction.js:19-52`, `:253` |
| `INITIAL_VALUE` en `t-out` | `/home/leandro/projects/nexit/19.0/odoo/addons/web/static/src/public/colibri.js:172-175` |
| Ejemplo de interaction simple con click | `/home/leandro/projects/nexit/19.0/odoo/addons/web/static/src/public/show_password.js:1-23` |

## Documentacion afectada

- `README.md` del modulo (nuevo).
- `static/description/index.html` (nuevo).
- Fila en el `README.md` raiz de `odoo_customization_sunra`.
- `Nokey_Transferencia_Bancaria_Configuracion.pdf` (guia del cliente): su §6 dice que el mail no lleva
  los datos bancarios y que el boton no se puede hacer desde el campo — con este modulo eso cambia.
  Pendiente de regenerar (fuera del repo).

## Plan del cambio en curso

| Tarea | Descripcion | Depende de | Archivos | CA |
|-------|-------------|-----------|----------|-----|
| **T01** | Esqueleto del modulo y manifest | — | `__init__.py`, `__manifest__.py` | — |
| **T02** | `_get_wire_transfer_cbu_account()` | T01 | `models/payment_provider.py` | CA02, CA04 |
| **T03** | Herencia del template de confirmacion (tira + link) | T02 | `views/website_sale_templates.xml` | CA01, CA04, CA12 |
| **T04** | Interaction de copiado con fallback y feedback | T03 | `static/src/js/wire_transfer_confirmation.js` | CA02, CA03 |
| **T05** | Ruta que reabre el paso de pago, con sus guardas | T01 | `controllers/website_sale_wire_transfer_ux.py` | CA05, CA06, CA07, CA08 |
| **T06** | Hooks del mail de orden pendiente | T02 | `__init__.py` | CA09, CA10 |
| **T07** | Traduccion `es_AR` | T03, T04, T05, T06 | `i18n/es_AR.po` | CA11 |
| **T08** | Documentacion del modulo y fila en el README del repo | T07 | `README.md`, `static/description/index.html` | — |
| **T09** | Validacion manual end-to-end en la base local | T08 | — | CA01..CA12 |
| **T10** | Pasada de @reviewer | T09 | — | — |
| **T11** | Endurecimiento post-review: POST+CSRF y guarda de partner en la ruta, link condicionado al estado del pedido, bloque del mail de una linea armado en Python para todos los idiomas activos, quite por marcador, `WARNING` de configuracion, timer del JS y `aria-live` | T10 | `controllers/website_sale_wire_transfer_ux.py`, `views/website_sale_templates.xml`, `models/payment_transaction.py`, `__init__.py`, `static/src/js/wire_transfer_confirmation.js`, `i18n/es_AR.po` | CA10, CA13, CA14, CA15 |
| **T12** | Re-pasada de @reviewer sobre T11 | T11 | — | — |

> T01..T11 cerradas. T12 pendiente.

## Notas de implementacion

- **Minimal footprint**: cero modelos y cero campos nuevos. El CBU ya tenia lugar en Odoo AR (D1), el
  cambio de medio de pago reusa el propio paso de pago del core en vez de reimplementar un formulario,
  y el mail reusa la plantilla existente en vez de clonarla.
- **Trampa encontrada en vivo**: `Markup.replace()` escapa sus argumentos, asi que el primer parche
  del mail no reemplazaba nada y **no fallaba**: solo no hacia efecto. Cualquier edicion de un campo
  `Html` desde codigo va sobre `str(...)`.
- **Por que el boton no puede ir en el mensaje pendiente**: no es preferencia de diseño, es el
  sanitizer del campo (D3 y Referencias). Vale explicarselo a la cliente, que ya intento esa via.
- **Dos trampas mas, encontradas en vivo y no leyendo codigo**: (1) `ai` (Enterprise) valida los
  `mail.template` **renderizandolos** al guardar, con la transaccion vacia → un `ensure_one()` en el
  metodo del bloque hacia fallar el `write` con `ValidationError` y el parche no se aplicaba (el log
  del install mostraba el traceback entre warnings, facil de pasar por alto). (2) El regex que quita
  el bloque llevaba `\s*` y se comia la indentacion de la linea siguiente: el bloque se iba pero el
  **ancla quedaba roto**, o sea que el modulo ya no se podia reinstalar. Las dos se cazan comparando
  el largo del cuerpo antes y despues, ida y vuelta.
- **Tests automaticos**: `odoo_customization_sunra` no tiene `.swarm.conf` → rige el default del repo
  (no se escriben salvo pedido). Los candidatos naturales, si se piden, son
  `_get_wire_transfer_cbu_account()` (con y sin cuenta CBU, y con otros `custom_mode`) y las guardas
  de `_get_reopenable_order()`.
