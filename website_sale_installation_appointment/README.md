# website_sale_installation_appointment

Vender un **envío con instalación incluida** desde el eCommerce y que esa venta quede **agendada como
Cita** (app Citas), con las **fotos del lugar** y los datos que cargó el cliente, y con la **tarea de
Field Service** del instalador.

- **Versión**: 1.12.1
- **Licencia**: LGPL-3
- **Depende de**: `website_sale`, `delivery`, `website_appointment_sale`, `sale_project`

## Para qué sirve

El negocio vende productos que pueden entregarse de dos formas:

| Método de envío | Costo | Qué pide en el checkout |
|---|---|---|
| Envío normal | precio del carrier | nada extra |
| Envío **con instalación** | precio del carrier (distinto) | día y hora + fotos del lugar |

Cuando el cliente elige el método con instalación, el checkout agrega un paso **Instalación** donde
agenda día y hora sobre la **disponibilidad real de la cuadrilla** y sube las **fotos del lugar**. Al
pagarse el pedido, la reserva se convierte en **Cita** y (si el producto de la cita genera tarea) en
la **tarea de Field Service** del instalador, con la fecha, la dirección de entrega, las respuestas
del formulario de la cita y las fotos en el chatter.

Si elige el envío normal, el paso **no aparece**: no molesta al flujo de compra habitual.

Este paso **reemplaza la guía de instalaciones que antes se pedía por un formulario externo
(JotForm)**: el checklist previo, la guía de fotos y las imágenes de referencia para medir la puerta
que estaban en ese formulario ahora viven en `/shop/installation` (ver "Contenido del paso
Instalación" más abajo).

## Cómo funciona (qué es nativo y qué agrega el módulo)

Casi todo el mecanismo es nativo de Odoo Enterprise; el módulo sólo lo engancha al método de envío:

1. **Nativo** — `appointment_account_payment` crea un `calendar.booking` (reserva pendiente) cuando el
   tipo de cita tiene paso de pago y producto.
2. **Nativo** — `website_appointment_sale` agrega esa reserva al carrito como línea de pedido.
3. **Nativo** — al confirmarse/pagarse el pedido, `sale.order._action_confirm()` convierte la reserva
   en `calendar.event` (con revalidación de disponibilidad anti doble-booking, mails y recordatorios).
4. **Nativo** — `sale_project` genera la tarea y `website_appointment_sale_project` le propaga fecha,
   duración, cliente, recursos como etiquetas y las respuestas del formulario en la descripción.
5. **Este módulo** — vincula el **método de envío** con el tipo de cita, agrega el **paso de checkout
   condicional**, recibe las **fotos**, **bloquea el pago** si falta agendar o faltan fotos, copia
   las fotos a la **Cita** y a la **tarea**, e **invita al cliente al portal** (ver más abajo).

## Contenido del paso Instalación

El paso `/shop/installation` se reorganizó (v1.10.0) en **3 bloques tipo acordeón que se habilitan
de a uno** (Bootstrap `collapse`, sin JS nuevo): los tres títulos se ven **desde el inicio**, el
completado muestra tilde + resumen, el pendiente muestra su número y el bloqueado muestra candado +
la razón ("Completá el paso N primero"). **El bloque bloqueado no renderiza su cuerpo**: no hay
controles deshabilitados que igual se puedan postear a mano. El estado de cada bloque lo calcula
**el servidor** (`sale.order._get_installation_block_states()`), nunca la plantilla.

1. **Paso 1 · Dirección de instalación** — es la **dirección de entrega del pedido**
   (`partner_shipping_id`, la misma que ya pide `/shop/address` y la misma que usa Field Service).
   Muestra el resumen (nombre + dirección formateada) con un link **Editar dirección** que abre el
   paso de dirección del core y **vuelve** a este paso al guardar/descartar, y un formulario propio
   con dos datos que el core no tiene: **entre calles** (`res.partner.between_streets`, opcional) e
   **indicaciones para el instalador** (`sale.order.installation_notes`). El botón **Confirmar
   dirección** cierra el bloque. Si el visitante todavía **no cargó dirección** (carrito anónimo o
   sin `partner_shipping_id`), el bloque muestra un aviso para cargarla primero **en vez de** el
   resumen y el formulario — nunca se escribe sobre el contacto público compartido de la base.
   - **Se cae si se edita la dirección después de confirmar** (elegir otro contacto de envío o
     editar el mismo): el Paso 2 se bloquea de nuevo. Las indicaciones ya cargadas no se pierden.
2. **Paso 2 · Turno y fotos** — bloqueado hasta confirmar el Paso 1. Adentro: el checklist
   `message_intro` del tipo de cita **si está cargado** (si no, no se pinta ningún checklist por
   defecto — los avisos genéricos ahora están repartidos por bloque), la duración estimada (2 a 4
   horas), el turno (agendar/cambiar, delega en la página nativa de Citas) y la guía de fotos.
3. **Paso 3 · (rótulo del paso siguiente del core, normalmente "Pago")** — bloqueado mientras falte
   turno, fotos o la confirmación de la dirección (los mismos mensajes que antes estaban arriba
   ahora se leen acá, en el bloque que los resuelve). Habilitado, es un link directo al paso
   siguiente real del checkout (`next_website_checkout_step_href`): el candado es **presentacional**,
   `/shop/payment` sigue validando todo del lado del servidor.

Debajo del acordeón, un renglón corto con la garantía (1 año) y las pilas (incluidas o a cargo del
cliente, según el método de envío — una sola línea con las dos versiones mutuamente excluyentes) y
el link **Volver** al paso anterior.

### Guía de fotos

La consigna sale del campo `installation_photos_message` del tipo de cita (ver *Textos
configurables*; vacío = texto por defecto del módulo: **3 fotos** — frente con la manija, canto,
marco), junto al input de subida, **con un ejemplo visual de cada toma** (template
`installation_photo_examples`): **3 tomas "así sí"** (con tilde) y **3 ejemplos de "así no"** (con
cruz y su motivo: borrosa/oscura, cortada, tapada por una mano).

- Las fotos **se suben apenas se eligen** (`static/src/js/installation_photos.js`) y el paso
  muestra una barra de progreso "N de `installation_min_photos`". Antes había que elegirlas **y
  además** apretar el botón: si el cliente iba directo al pago, el paso lo rebotaba pidiendo fotos
  que él veía seleccionadas en pantalla. Sin JS el botón *Subir fotos* sigue funcionando igual.
- Si un archivo se rechaza se avisa **con el nombre del archivo** (caso típico: fotos HEIC de
  iPhone, que no se pueden leer como imagen — hay que mandarlas en JPG).

### Imágenes

| Archivo | Para qué |
|---|---|
| `static/src/img/installation_measure_a_door_thickness.jpg` | Medida A) Ancho del canto (espesor) de la puerta |
| `static/src/img/installation_measure_b_lock_length.jpg` | Medida B) Largo de la cerradura en la puerta |
| `static/src/img/photo_ok_front.jpg` | Guía de fotos, "así sí": frente de la puerta con la manija |
| `static/src/img/photo_ok_edge.jpg` | Guía de fotos, "así sí": canto/espesor de la puerta |
| `static/src/img/photo_ok_frame.jpg` | Guía de fotos, "así sí": marco de la puerta |
| `static/src/img/photo_bad_blurry.jpg` | Guía de fotos, "así no": borrosa u oscura |
| `static/src/img/photo_bad_cropped.jpg` | Guía de fotos, "así no": cortada, falta parte de la puerta |
| `static/src/img/photo_bad_obstructed.jpg` | Guía de fotos, "así no": tapada por una mano |

> **Baja (v1.10.0)**: `installation_example_lock.jpg` e `installation_example_door_edge.jpg` (las dos
> fotos de ejemplo viejas, apaisadas y sin ejemplos de "así no") se dieron de baja junto con sus
> `msgid` de `alt`/pie en `i18n/es_419.po`. Las 6 fotos nuevas son **verticales (~3:4)** y salen de
> tomas reales entregadas por el cliente (convertidas a JPEG, calidad ~82, ancho máx. 600 px).

Se sirven directo desde `static/` (URL `/website_sale_installation_appointment/static/src/img/...`),
sin bundle de assets: son `<img>` del template, no JS/CSS.

### Guía de medidas (dónde aparece)

Los diagramas A/B viven en el template `installation_measure_guide` y se renderizan **dentro del
bucle de preguntas del formulario del turno, justo antes de la pregunta marcada** con el campo
`installation_measure_guide` de `appointment.question` (casilla *Mostrar la guía de medidas*).

Esto cubre **los dos caminos con un solo lugar**: la pregunta del espesor es **reutilizable** y la
comparten el tipo de cita del checkout y el del link que comparte Nokey, así que marcarla una vez
alcanza. Antes los diagramas iban sueltos —arriba de todas las preguntas en el formulario, y en una
tarjeta del paso de checkout, que es otra página—: el cliente leía el diagrama lejos de donde tenía
que escribir la medida.

> ⚠️ **Config obligatoria por base**: si nadie marca *Mostrar la guía de medidas* en la pregunta del
> espesor, los diagramas no se muestran en ningún lado. El campo es del cliente (las preguntas las
> crea el funcional), por eso el módulo no puede traerlo marcado de fábrica.

Los **ejemplos de las fotos a subir** viven en el template `installation_photo_examples` (definido en
`views/website_sale_installation_templates.xml`) y se llaman con `t-call` desde los dos caminos, justo
arriba del input de archivos: uno solo para mantener, mismo mensaje compre por donde compre.

## Textos configurables

Los dos textos que el funcional cambia seguido **no viven en las plantillas**: viven en campos del
**tipo de cita**, traducibles, y se editan desde *Citas → Tipos de cita → pestaña Comunicación* (o en
línea sobre la propia página, con el editor del sitio).

| Texto | Campo | Dónde se ve |
|---|---|---|
| Checklist "antes de agendar" (condiciones extra que el funcional quiera agregar) | `message_intro` (**nativo**) | **Dentro del Paso 2** del checkout **y** arriba del calendario en la página del link |
| Consigna de las fotos del lugar | `installation_photos_message` | Arriba del input de fotos, en el checkout **y** en el formulario de la cita |

Vacío el `message_intro` → **no se pinta ningún checklist por defecto** (v1.10.0): los avisos
genéricos (duración, condición de pago, garantía, pilas) ahora están **repartidos por bloque** del
acordeón, no todos juntos en un checklist. `installation_photos_message` sí conserva su texto por
defecto propio (3 fotos: frente con la manija, canto, marco).

> **No se repite en la página del turno cuando se viene del checkout**: si el visitante entra al
> formulario de la cita apretando *Agendar la instalación* desde el Paso 2, el bloque nativo de
> `message_intro` al pie de esa página **no se muestra** (ya lo leyó arriba). Por el **link
> compartido** (sin carrito) se sigue mostrando arriba del calendario, como siempre.

> ⚠️ **Por qué en campos y no editando la plantilla desde el editor web.** Editar una plantilla desde
> el editor crea una **copia por sitio (COW)**: esa copia queda congelada y **nunca más recibe las
> actualizaciones del módulo**. Ya pasó en producción — se editó `installation_photo_examples` desde
> el editor y la guía de fotos quedó vacía **en los dos flujos** durante una semana, sin que ningún
> deploy la arreglara. Un campo se guarda en el registro: sobrevive upgrades, es traducible y lo leen
> los dos caminos.

> El checklist es **por tipo de cita** a propósito: el tipo del eCommerce cobra online y el del link
> se cobra el día del turno. Son condiciones distintas y tienen que poder decirse distinto.

Para bloques libres (banners, promos) están las zonas de snippets que ya trae cada página: el
`oe_structure` del paso del checkout y el de la página de la cita.

## Qué agrega

### Campos

| Modelo | Campo | Para qué |
|---|---|---|
| `delivery.carrier` | `installation_appointment_type_id` | Tipo de cita a agendar. Si está vacío, el método de envío es normal. |
| `delivery.carrier` | `installation_min_photos` | Fotos mínimas del lugar (0 = opcionales). Default 1. |
| `delivery.carrier` | `includes_free_batteries` | Si está tildado, agrega **sin cargo** las pilas configuradas en los productos del carrito (ver *Pilas incluidas sin costo*). |
| `product.template` | `free_battery_product_id` | Producto de pila que este producto necesita (se agrega gratis solo si el método de envío tiene `includes_free_batteries`). |
| `product.template` | `free_battery_qty` | Cantidad de pilas, **en la UoM del producto de pila elegido** (ver *Pilas incluidas sin costo*). |
| `sale.order.line` | `is_free_battery_line` | Flag técnico (no va en vistas) que marca la línea de pilas gratis. |
| `sale.order` | `installation_appointment_type_id` | Related del carrier elegido. |
| `sale.order` | `installation_required` | Si el pedido exige agendar instalación. |
| `sale.order` | `installation_booking_id` | Reserva pendiente (antes de confirmar). |
| `sale.order` | `installation_event_id` | Cita creada (después de confirmar). |
| `sale.order` | `installation_photo_ids` | Fotos del lugar que subió el cliente. |
| `sale.order` | `installation_photo_count` | Cantidad de fotos (para el gate). |
| `res.partner` | **`between_streets`** *(v1.10.0)* | "Entre calles" del domicilio (Char, opcional). Se edita en el Paso 1 del checkout y en la ficha del contacto (backend). |
| `sale.order` | **`installation_notes`** *(v1.10.0)* | Indicaciones para el instalador de **esta** venta (Text, `copy=False`). Se editan en el Paso 1 y se propagan a la descripción de la tarea de FSM. |
| `sale.order` | **`installation_address_confirmed`** *(v1.10.0)* | Lo marca el botón *Confirmar dirección* del Paso 1 (Boolean, `copy=False`, default `False`). Se resetea si se edita la dirección de envío después. |
| `appointment.type` | `installation_fsm_project_id` | Proyecto de Field Service donde crear la tarea cuando la cita se agenda **sin** pasar por el eCommerce (link compartido). Vacío = la tarea la genera el pedido. |
| `appointment.type` | `installation_request_photos` | Pedir fotos del lugar en el formulario de la cita. |
| `appointment.type` | `installation_min_photos` | Fotos necesarias para reservar (0 = opcionales pero visibles). |
| `appointment.type` | `installation_photos_message` | Consigna de las fotos del lugar (Html, traducible). Vacío = texto por defecto del módulo. |
| `appointment.question` | `answer_format` | Formato esperado de la respuesta: texto libre, número entero, número, teléfono o documento (DNI/CUIT). |
| `calendar.event` | `installation_task_id` | Tarea de Field Service generada por una cita agendada fuera del eCommerce. |

### Rutas

| Ruta | Qué hace |
|---|---|
| `GET /shop/installation` | Paso de checkout: estado de los 3 bloques + subida de fotos. |
| `POST /shop/installation/submit` | Una sola ruta para las 3 acciones del paso: confirmar la dirección (`confirm_installation_address`), quitar una foto (`remove_photo_id`) o subir fotos (input `installation_photos`, siempre con `stay_on_step`). |
| `POST /shop/installation/photo/<id>/remove` | Quita una foto del pedido en curso. |

### Puntos de extensión usados

- `sale.order._get_installation_block_states()` *(v1.10.0)* — único lugar que decide qué bloque del
  acordeón está hecho, cuál está abierto y cuál bloqueado; la plantilla solo pinta.
- `ResPartner.write()` y `SaleOrder.write()` *(v1.10.0)* — resetean `installation_address_confirmed`
  si se edita el domicilio del contacto de envío o si se elige otro contacto de envío.
- `AppointmentType._is_installation_checkout_source()` *(v1.10.0)* — evita repetir el checklist
  (`message_intro`) en la página del turno cuando el visitante viene del Paso 2 del checkout.
- `website._get_allowed_steps_domain()` — saca el paso del checkout cuando el envío no lleva
  instalación (así el core calcula solo el paso siguiente/anterior y el wizard no lo dibuja).
- `sale.order._check_cart_is_ready_to_be_paid()` y `WebsiteSale._get_shop_payment_errors()` — gate de
  pago: sin cita o sin las fotos mínimas no se puede pagar.
- `WebsiteSale.shop_payment()` — si la instalación está incompleta, redirige al paso en vez de
  mostrar el error. Hace falta porque el link "siguiente paso" del paso de envío se renderiza **antes**
  de que el cliente elija el método, así que apunta al pago incluso cuando el envío exige instalación.
- `sale.order._action_confirm()` — copia las fotos a la Cita y a la tarea, e invita al cliente al
  portal (después de `super()`, que es donde el core crea la Cita y la tarea).
- `sale.order.line._timesheet_create_task_prepare_values()` — título estable para la tarea del
  instalador (`<pedido> - <tipo de cita>`). Sin esto, cuando el producto de la cita se llama igual
  que el tipo de cita, `sale_project` descarta esa línea y la tarea queda titulada con la fecha.
- `WebsiteAppointmentSale._redirect_to_payment()` — al volver de agendar, vuelve al paso Instalación
  (el nativo vuelve al paso de dirección) y descarta la reserva anterior si el cliente reagenda.
- `calendar.event._notify_by_email_prepare_rendering_context()` — compañía correcta (logo/colores)
  en el correo de **recordatorio** de la cita, en una base con más de una compañía (ver *Marca del
  correo de la cita* más abajo).

### Validaciones

- El tipo de cita asociado a un método de envío **debe** tener paso de pago y producto de reserva, y
  ese producto debe generar tarea o tener precio; si no, la reserva nunca se ataría al pedido. Se
  frena con `ValidationError` al guardar el método de envío.
- El endpoint público de fotos acepta **sólo imágenes** (se valida el mimetype real del contenido, no
  el que declara el navegador), hasta **10 MB** por archivo y **10 fotos** por pedido.

## Invitación automática al portal

Al confirmarse un pedido con instalación (`_action_confirm()`), el módulo intenta darle acceso al
**portal** al cliente del pedido, reusando el mecanismo nativo de invitación (`portal.wizard`), el
mismo que usa el botón *Otorgar acceso al portal* de un contacto. Es **incondicional**: no hay
forma de desactivarla para un pedido puntual (aplica a todo pedido con instalación).

- **Cuándo se dispara**: solo en pedidos donde `installation_required` es verdadero (el método de
  envío elegido exige instalación). Los pedidos con envío normal no la disparan.
- **Idempotencia**: si el partner ya tiene un usuario activo (portal o interno), no hace nada. Si
  el partner tiene un usuario **archivado**, tampoco hace nada (no lo reactiva en automático) y
  deja una nota en el chatter del pedido.
- **Sin email**: si el partner no tiene email cargado, no se puede invitar; se deja una nota en el
  chatter del pedido.
- **Qué manda**: el mail nativo de invitación al portal (plantilla `auth_signup.portal_set_password_email`),
  con el link de *sign up* para que el cliente elija su contraseña.
- **Fallos**: cualquier error (ej. el email ya está en uso por otro usuario) queda aislado con
  `savepoint` y **nunca** rompe la confirmación del pedido; queda logueado y anotado en el chatter.

**Gotcha**: sin un **servidor de correo saliente** configurado (Configuración → Técnico → Correo →
Servidores de correo saliente), el mail de invitación no sale (queda en la cola o falla en silencio
según la configuración de Odoo); la invitación en sí se sigue disparando (el usuario portal queda
creado), pero el cliente no recibe el link de *sign up*.

## Marca del correo de la cita (recordatorio)

En una base con **más de una compañía** (ej. Miluan SRL / Nokey y YG S.A. / Sunra), la confirmación
Y el recordatorio de la cita se mandan por el **mismo camino** (`_notify_attendees()` sobre la
Cita). La diferencia es **cuándo** corre cada uno: la confirmación corre dentro del **request web**
del checkout (la compañía activa ya es la del sitio/cliente) y sale bien; el recordatorio lo dispara
el **cron** nativo de alarmas, cuya compañía activa es la del usuario técnico que lo corre. El hook
que pinta el logo/colores del correo arma la compañía leyendo un campo `company_id` del registro —y
`calendar.event` no tiene ese campo—, así que sin este fix el recordatorio salía con el logo/colores
de la compañía del **usuario del cron**, no la del cliente.

Dos overrides en `calendar.event` resuelven esto, ambos en el mismo orden — (1) la compañía del
**pedido de venta** que originó la cita (el más antiguo entre los no cancelados: duplicar un pedido
copia el vínculo con la cita); (2) si no hay pedido (agendada por el link compartido), la del
**organizador**; (3) si tampoco, la de quien **creó** la cita; (4) si tampoco, el comportamiento
nativo—: `_mail_get_companies()` (afecta a quién responde el reply-to del correo, útil porque cada
compañía tiene su propio dominio de alias) y `_notify_by_email_prepare_rendering_context()` (el que
realmente pinta el logo/colores del layout).

## Pilas incluidas sin costo

Cuando un método de envío incluye las pilas (instalación con cuadrilla propia, por ejemplo), el
pedido agrega automáticamente una línea con las pilas que necesita cada producto, **a $0**: el costo
ya está integrado en el servicio de instalación.

- **Configuración por producto** — en la ficha del producto (pestaña *Ventas*, grupo *Venta cruzada*):
  `free_battery_product_id` (qué pila necesita) y `free_battery_qty` (cuántas). La UoM se muestra al
  lado del número: la pila real se vende en "Paquete de 4", así que `1` significa **un paquete (4
  pilas)**, no una pila suelta.
- **Opt-in por método de envío** — independiente de que el envío lleve o no instalación: `includes
  Free Batteries` en la ficha del método de envío. Así el día de mañana otro envío puede incluir
  pilas sin necesidad de agendar cita.
- **Agregación por producto de pila** — dos productos distintos que usan la misma pila generan
  **una sola línea**, con la suma de ambos.
- **Sincronización idempotente** — la línea se crea/ajusta/borra automáticamente al armar el carrito
  en el sitio, al cambiar el método de envío, al armar el pedido en el backend (con o sin el botón
  *Add shipping*) y al confirmar (red de seguridad final). Correr la sincronización dos veces seguidas
  no cambia nada.
- **Visible pero no editable** — la línea se ve en el carrito (constancia de qué pilas se entregan)
  pero no tiene selector de cantidad ni botón *Eliminar*; si el cliente la manipula por el endpoint
  público del carrito, se re-sincroniza en el mismo request.
- **Aparece en la factura, a $0**: es la constancia de que las pilas fueron entregadas.
- **Renglón del pie del acordeón (v1.10.0)** — una sola línea con `t-if`/`t-else` sobre
  `includes_free_batteries`: si el método de envío incluye las pilas, se lee que van incluidas sin
  cargo; si no, se lee que hay que tenerlas el día de la instalación. Las dos versiones son
  mutuamente excluyentes por construcción (nunca conviven).

## Configuración (registros a crear)

1. **Producto de la cita** — tipo *Servicio*, `service_tracking = Crear tarea en proyecto existente`
   apuntando al proyecto de **Field Service**. El precio puede ser 0 (el costo va en el método de
   envío) o el costo de la instalación.
2. **Tipo de cita** (Citas → Configuración) — con **paso de pago** activado y el producto anterior;
   agendado **por recursos** (la cuadrilla como `appointment.resource` con su capacidad), franjas
   horarias reales, zona horaria, y publicado en el website.
   - Las **preguntas** del tipo de cita (`appointment.question`) se cargan acá: las respuestas viajan
     solas a la Cita y a la descripción de la tarea de FSM (vía `website_appointment_sale_project`,
     nativo). Preguntas a crear (textos exactos, en español, adaptados del JotForm reemplazado):

     | Pregunta | Tipo | Formato | Obligatoria | Opciones |
     |---|---|---|---|---|
     | Teléfono de contacto | Teléfono | Teléfono | Sí | — |
     | Material de la puerta | Desplegable | Texto libre | Sí | Chapa/Metal · Madera · Aluminio/PVC · Vidrio/Blindada · No estoy seguro |
     | A) ¿Qué tan gruesa es la puerta? (ancho del canto, en cm) | Texto corto | **Número** | Sí | — |
     | B) Largo de la cerradura en la puerta (en cm) | Texto corto | **Número** | Sí | — |
     | ¿Contás con lugar para estacionar? | Desplegable | Texto libre | No | Sí, cochera propia / entrada · Sí, estacionamiento medido / garage cerca · No, es zona de estacionamiento libre · No hay lugar cerca |
     | Observaciones para el instalador | Texto largo | Texto libre | No | — |

     **No** se piden acá la dirección ni el DNI/CUIT: los toma el checkout (dirección estructurada
     que después guía al instalador, y *Número de Identificación*, que la localización argentina ya
     valida con dígito verificador). Preguntarlos dos veces era lo que confundía y duplicaba datos.

     El **orden** se cambia arrastrando las preguntas en la pestaña *Preguntas* del tipo de cita
     (columna de tirador). Ojo: `sequence` es **global** de la pregunta, así que reordenar afecta a
     todos los tipos de cita que la reutilicen.

     El **Formato de la respuesta** (campo propio de este módulo) es lo que evita que el cliente
     escriba cualquier cosa: emite `type`/`inputmode`/`pattern` reales en el input (el nativo emite
     `type="phone"` y `type="char"`, que **no existen en HTML** y el navegador trata como texto
     libre) y revalida en el servidor por las dudas.

     Las dos preguntas de medida (A y B) corresponden a los diagramas del paso "Medí tu puerta antes
     de agendar": el cliente ya vio cómo medir antes de llegar a este paso.
3. **Etiqueta de producto** (ej. *Requiere instalación*) en los productos instalables.
   Desmarcar **Visible para los clientes** (`product.tag.visible_to_customers`): la etiqueta es
   un marcador interno para el método de envío y, si se publica, aparece en la ficha del
   producto y confunde al comprador. Ocultarla **no** afecta a *Debe tener etiquetas*.
4. **Método de envío "Envío con instalación"** — `Precio fijo` con su costo, publicado en el website,
   con la etiqueta anterior en *Debe tener etiquetas* (así el método aparece sólo si el carrito lleva
   un producto instalable), zona de cobertura por país/provincia/CP si la cuadrilla no llega a todos
   lados, y **Tipo de cita de instalación** = el del punto 2.
5. **Método de envío "Envío normal"** — el de siempre, sin tipo de cita.
6. **Proveedor de pago habilitado** — el pedido se confirma al pagarse; sin proveedor habilitado el
   checkout no llega a confirmar y la Cita no se crea.
7. **Nombre del tipo de cita** — es el texto que se ve en la línea del pedido (el nativo arma la
   descripción con el nombre del tipo + el horario). Conviene que se lea como el turno y no como un
   segundo cargo, ej. *Turno de instalación a domicilio*; el módulo además le agrega
   "Incluido en el método de envío … — sin cargo adicional".
8. **Pilas incluidas sin costo** (opcional) — en cada producto que las necesite: `free_battery_product_id`
   + `free_battery_qty` (en la UoM del producto de pila); y en el método de envío que las incluye:
   `Includes Free Batteries`. Dos requisitos de configuración:
   - **`invoice_policy = 'order'`** en el producto de pila: con `'delivery'` y stock 0 la línea no
     llegaría a facturarse, perdiendo la constancia de entrega.
   - **Aprovisionar stock** si la pila es storable: con stock 0 el picking la muestra como no
     disponible, y mientras esté agotada se **apaga el mail de carrito abandonado** de ese carrito.
   - Si el `message_intro` del tipo de cita menciona "vas a necesitar pilas", **sacar ese punto**
     cuando el método de envío las incluye (si no, el cliente lee dos mensajes contradictorios).

### Agenda compartida sin cobrar online (el cliente paga por fuera)

Cuando Nokey coordina la instalación por teléfono/WhatsApp y el pago se arregla aparte, el cliente
solo tiene que elegir día y hora. Eso **no** se hace con el tipo de cita del eCommerce (tiene paso de
pago y termina en el checkout): se configura un **segundo tipo de cita**.

1. **Tipo de cita** ej. *Instalación coordinada por Nokey*: **sin** paso de pago, **no publicado**,
   con el **mismo recurso** (la cuadrilla) que el tipo del eCommerce — así **comparten
   disponibilidad**: el nativo busca las reservas **por recurso**, no por tipo, y no se pueden
   superponer dos instalaciones. Copiarle también las franjas horarias, la duración y el
   *Total de reservas* (citas simultáneas) del tipo web: si no coinciden, una agenda muestra
   horarios que la otra ya considera ocupados.
2. **Proyecto de Field Service** en el campo homónimo: sin venta no hay quien genere la tarea del
   instalador, la crea este módulo con la fecha, el cliente, la dirección y las respuestas. La tarea
   nace **sin asignar** (por recursos Odoo no sabe qué persona va) y se sincroniza si la cita se
   reprograma o se cancela.
3. **Preguntas**: las mismas técnicas del tipo web. Las preguntas se reutilizan entre tipos, no hay
   que duplicarlas — pero la de *Notas aclaratorias* conviene dejarla **solo acá**: en el checkout
   duplica el campo "Indicaciones para el instalador" del Paso 1.
4. **Dirección de la instalación**: activar **_Pedir la dirección de instalación_**. Acá no hay
   checkout que la aporte, así que sin esto la tarea del instalador sale **sin lugar al que ir**. El
   formulario pide calle y número y localidad (obligatorias), piso/depto, código postal y **entre
   calles**; los datos se guardan en el contacto que reserva (solo los campos que estén vacíos, para
   no pisar una dirección ya cargada por el backoffice) y el "entre calles" además se escribe en el
   cuerpo de la tarea.
5. **Fotos del lugar**: activar *Pedir fotos del lugar*. El mínimo puede quedar en 0 (se muestran
   pero no bloquean) — bloquear una reserva por una subida desde el celular es arriesgado.
   ⚠️ En el tipo de cita **del eCommerce** esta opción no hace falta: ese camino ya pide las fotos en
   el Paso 2 del checkout, y el módulo esconde la carga en el formulario de la cita para no pedirlas
   dos veces (aunque la opción quede activada).
6. **Orden del formulario**: el formulario de este camino se muestra en **cuatro secciones
   numeradas** (Tus datos · Sobre tu puerta · Dirección de instalación · Fotos del lugar), con la
   etiqueta arriba del campo. El **orden de las preguntas** dentro de la sección 2 lo maneja el
   funcional desde el backend, arrastrando con el tirador de la lista de preguntas del tipo de
   cita. ⚠️ Esa secuencia es **global**: las preguntas se reutilizan entre tipos de cita, así que
   reordenar acá reordena en todos los tipos que usen la misma pregunta.
7. **Link para compartir**: abrir el tipo de cita y apretar **Compartir** (arriba a la izquierda).
   Odoo abre *Crear un enlace para compartir* con la URL ya armada (ej. `/book/instalacion`) y el
   botón *Copiar enlace y cerrar*. Ese es el link que se manda al cliente por WhatsApp o mail; **no**
   requiere que se registre y **es siempre el mismo** (queda guardado en el smart button *Enlaces
   compartidos* del tipo de cita, modelo `appointment.invite`).

Este camino **no genera pedido de venta**: si además hay que facturar, el pedido lo arma Nokey en el
backoffice.

## Flujo del cliente

1. Agrega el producto al carrito.
2. Dirección + **método de envío**: elige *Envío con instalación* (ve el costo).
3. Paso **Instalación**, en 3 bloques:
   - **Paso 1**: revisa la dirección de entrega, agrega "entre calles" e indicaciones para el
     instalador (opcional) y aprieta *Confirmar dirección* → se habilita el Paso 2.
   - **Paso 2**: *Agendar la instalación* → elige día y hora en la página de la cita y responde
     **solo lo que el checkout no le preguntó** (las medidas, con la ayuda de los diagramas): el
     nombre y el correo viajan ocultos y se muestran como *"Reservás como …"*, y **las fotos no se
     piden ahí** → vuelve al paso → sube las fotos del lugar (según la guía visual) → cuando agendó
     y subió las mínimas, se habilita el Paso 3.
   - **Paso 3**: link directo al pago.
4. Paga. Al confirmarse el pedido: se crea la **Cita**, la **tarea de Field Service** (con "entre
   calles" e indicaciones en la descripción) y las fotos quedan en el chatter de las dos.

## Gotchas

- **Nombre de la empresa fuera del checkout**: la vista `website_sale.address_form_fields` se hereda
  para sacar `#company_name_div`. **No** alcanza con desactivar la vista opcional
  `website_sale.address_b2b`: ese switch apaga todo el bloque b2b y `l10n_ar` cuelga ahí adentro la
  *Responsabilidad de ARCA*, que sí se necesita. El formulario de *Mi cuenta* del portal queda
  intacto (se hereda la variante `primary` del checkout).
- **Invitado que cambia el mail en la cita**: el formulario llega prellenado con el contacto del
  checkout (`_get_customer_partner` cae al partner del carrito), pero si el cliente **edita** el mail
  o el teléfono ahí, el nativo crea un contacto nuevo. No se puede impedir sin bloquear los campos.
- **DNI / CUIT**: los valida la localización argentina en el checkout (largo, solo números, dígito
  verificador y prefijo de CUIT). Este módulo no duplica esa validación: solo la reusa en las
  preguntas de cita que se configuren con formato *Documento*.
- **El `sequence` de las preguntas es global**: se comparten entre tipos de cita.

- **La confirmación de la dirección (Paso 1) se cae si se edita la dirección después**: elegir otro
  contacto de envío **o** editar el mismo contacto (calle, ciudad, entre calles, etc.) resetea
  `installation_address_confirmed` y el Paso 2 vuelve a bloquearse. Es conservador a propósito.
- **`between_streets` es del *contacto*, `installation_notes` es del *pedido***: dos carritos abiertos
  a la misma dirección comparten "entre calles" (es el domicilio) pero cada uno tiene sus propias
  indicaciones para el instalador (son de *esa* venta).
- **Sin JavaScript el acordeón no colapsa/despliega**, pero los encabezados de los 3 bloques y el
  cuerpo del bloque abierto se renderizan igual (el estado sale del servidor) y las fotos se suben
  con el botón *Subir fotos*. Nadie queda sin poder terminar la compra.
- **El candado del Paso 3 es presentacional, no seguridad**: `/shop/installation/submit` y
  `/shop/payment` siguen validando todo del lado del servidor.

- **Sin proveedor de pago habilitado no hay Cita**: la reserva se convierte en Cita al confirmarse el
  pedido. Un pedido que queda en presupuesto conserva la reserva pendiente (`calendar.booking`), que
  el garbage collector nativo limpia a los 2-6 meses.
- **Cancelar el pedido archiva la Cita** (comportamiento nativo de `website_appointment_sale`).
- **Reagendar** desde el paso reemplaza la reserva anterior: queda una sola línea de instalación.
- Si el cliente cambia el método de envío a uno normal después de agendar, la línea de la reserva
  queda en el carrito hasta que la quite; el paso deja de mostrarse porque el envío ya no exige cita.
- `free_over` (envío gratis a partir de un monto) no tiene sentido en el método con instalación.
- Las **preguntas del tipo de cita** (tabla en "Configuración" arriba) viven en la base de datos, no
  en este módulo: si se editan los textos/opciones en el tipo de cita, hay que actualizar esa tabla
  a mano (drift entre la config real y esta doc).

- **`free_battery_qty` va en la UoM del producto de pila**: si la pila real se vende en "Paquete de
  4", `1` significa un paquete (4 pilas). Leerlo como "cantidad de pilas" duplica o cuadriplica lo
  que se despacha — el `help` del campo y la UoM visible al lado del número lo aclaran.
- **Publicar el producto de pila no lo vuelve editable en el carrito**: la línea gratis sigue sin
  selector de cantidad ni botón Eliminar, esté o no publicado el producto (no hace falta publicarlo:
  la línea se crea del lado del servidor).
- **La línea gratis nunca bloquea el pago por stock**, aunque la pila sea storable, tenga stock 0 y
  no permita venta sin stock: es un producto que el cliente no eligió y no puede quitar, así que
  bloquear el checkout por eso dejaría un carrito sin salida.
- **No repetir el pedido de pilas en `message_intro`**: si el checklist del tipo de cita menciona
  "vas a necesitar pilas" y el método de envío las incluye, el cliente lee dos cosas contradictorias
  (el checklist pidiéndolas y el aviso diciendo que van incluidas).

## Validación manual

1. Carrito con un producto etiquetado como instalable → el método *Envío con instalación* aparece.
2. Elegirlo → el paso *Instalación* aparece con los **3 bloques visibles desde el inicio**: Paso 1
   abierto (número 1), Paso 2 y 3 con candado.
3. Intentar ir directo a `/shop/payment` → redirige al paso (no muestra un error suelto en el pago).
4. En el Paso 1: cargar "entre calles" e indicaciones, *Confirmar dirección* → el bloque queda con
   tilde + resumen, y el Paso 2 se habilita. Recargar la página → el estado se mantiene.
5. Editar la dirección de envío (`/shop/address`, o elegir otro contacto) → el Paso 1 vuelve a
   pendiente y el Paso 2 se bloquea de nuevo; las indicaciones cargadas no se pierden.
6. En el Paso 2: agendar día y hora → volver al paso con el día y hora visibles; subir fotos según la
   guía (3 "así sí" / 3 "así no") → la barra de progreso avanza.
7. Intentar pagar sin fotos (con `installation_min_photos = 1`) → el Paso 3 sigue con candado y lista
   lo que falta.
8. Con todo completo, el Paso 3 es un link habilitado → pagar.
9. Verificar: Cita creada con las respuestas y las fotos; tarea de FSM con fecha, dirección, "entre
   calles" e indicaciones en la descripción, y las fotos en los dos chatters.
10. Repetir con el *Envío normal* → el paso *Instalación* no aparece en ningún momento.
11. Entrar a la página del turno **desde el checkout** → el checklist (`message_intro`) no se repite
    al pie. Entrar por el **link compartido** → se sigue viendo arriba del calendario.
12. Con un cliente sin usuario de portal: verificar que quede creado tras confirmar (Ajustes →
    Usuarios y Compañías → Usuarios) y que llegue el mail de invitación (requiere servidor de correo
    saliente configurado). Repetir con un cliente que ya tiene usuario portal/interno → no debe
    mandar mail ni crear un usuario nuevo.

### Pilas incluidas sin costo

13. Configurar `free_battery_product_id` + `free_battery_qty` en la cerradura, y `Includes Free
    Batteries` en el método de envío → agregar la cerradura al carrito y elegir ese método → aparece
    la línea de pilas a **$0**, con la cantidad correcta (`free_battery_qty × cantidad de cerraduras`).
14. Cambiar la cantidad de cerraduras → la línea de pilas se ajusta (no se duplica).
15. Cambiar a un método de envío **sin** el flag → la línea desaparece; volver al que lo tiene → reaparece.
16. En el carrito: la línea gratis se ve pero sin selector de cantidad ni botón Eliminar.
17. En el renglón corto al pie del acordeón: con el flag activo se lee que las pilas **van
    incluidas**; sin el flag, se lee que hay que tenerlas el día de la instalación — nunca las dos
    (es una sola línea con `t-if`/`t-else`, v1.10.0).
18. Agregar la misma pila como producto suelto → se agrega una segunda línea, **pagada**.
19. Pagar y revisar la **factura**: la línea de pilas aparece a $0.
20. Duplicar el pedido (Acciones → Duplicar) → el duplicado trae **una** línea de pilas a $0.

### Marca del correo de la cita

21. En una base con más de una compañía, confirmar un pedido con instalación de una compañía desde
    un usuario cuya compañía por defecto sea la **otra** → correr el cron de alarmas (Ajustes →
    Técnico → Automatización → Acciones Planificadas → *ir_cron_scheduler_alarm* → *Ejecutar
    Manualmente*) o esperar la ventana del recordatorio → el correo de recordatorio sale con el
    logo/colores de la compañía **del pedido**, no la del usuario del cron. El de confirmación no
    cambia (ya salía bien).
