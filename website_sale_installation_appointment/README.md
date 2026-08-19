# website_sale_installation_appointment

Vender un **envío con instalación incluida** desde el eCommerce y que esa venta quede **agendada como
Cita** (app Citas), con las **fotos del lugar** y los datos que cargó el cliente, y con la **tarea de
Field Service** del instalador.

- **Versión**: 1.2.0
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

El paso `/shop/installation` es una adaptación del **JotForm** de instalaciones que Nokey usaba
antes de este módulo (el formulario externo queda reemplazado por este flujo). Contenido, de arriba
hacia abajo:

0. **Encabezado** — "Preparemos tu instalación / Necesitamos estos tres datos antes de confirmar
   el turno", y debajo los tres pedidos **numerados y cada uno en su propia tarjeta** (antes el de
   las fotos quedaba suelto y se leía distinto de los otros dos).
1. **Checklist previo** ("Antes de agendar") — puntos adaptados del JotForm: pilas AA/AAA
   necesarias el día de la instalación, dirección completa, duración estimada (2 a 4 horas) y
   garantía de 1 año por fallas de fábrica.
   - **Adaptación deliberada**: el JotForm original incluía una condición de **pago en efectivo o
     transferencia el día del turno**. Acá **no aplica y no se muestra**: el pago de este flujo es
     **online, en el checkout**, antes de que la instalación quede agendada como Cita.
> El paso pide **dos** cosas, no tres. La tarjeta *"Medí tu puerta antes de agendar"* se eliminó:
> al mudar los diagramas junto a la pregunta quedaba como un recordatorio suelto sin imágenes. Las
> medidas se preguntan como `appointment.question` al agendar y su guía aparece ahí (ver *Guía de
> medidas* abajo).
2. **Día y hora** (existente) — se delega en la página nativa de Citas.
3. **Guía de fotos** — texto adaptado del JotForm sobre qué fotos subir (puerta desde afuera, desde
   adentro, y el canto/borde donde entra la cerradura), junto al input de subida, **con un ejemplo
   visual de cada toma** (template `installation_photo_examples`): antes solo estaba el párrafo y el
   cliente subía cualquier cosa. La toma "desde adentro" todavía no tiene foto propia: se muestra
   como recuadro con ícono hasta que Nokey la provea.
   - Las fotos **se suben apenas se eligen** (`static/src/js/installation_photos.js`) y el paso
     muestra "Subidas hasta ahora: X de Y". Antes había que elegirlas **y además** apretar
     *Continuar*: si el cliente iba directo al pago, el paso lo rebotaba pidiendo fotos que él veía
     seleccionadas en pantalla. Sin JS el botón *Continuar* sigue funcionando igual.
   - Si un archivo se rechaza se avisa **con el nombre del archivo** (caso típico: fotos HEIC de
     iPhone, que no se pueden leer como imagen — hay que mandarlas en JPG).

### Imágenes

| Archivo | Para qué |
|---|---|
| `static/src/img/installation_measure_a_door_thickness.jpg` | Medida A) Ancho del canto (espesor) de la puerta |
| `static/src/img/installation_measure_b_lock_length.jpg` | Medida B) Largo de la cerradura en la puerta |
| `static/src/img/installation_example_lock.jpg` | Ejemplo de foto: la puerta desde afuera (manija y cilindro) |
| `static/src/img/installation_example_door_edge.jpg` | Ejemplo de foto: el canto, con la puerta abierta |

Las dos de **ejemplo** salen de las mismas tomas reales que las de medidas, recortadas y con las
marcas rojas A/B quitadas: esas marcan *qué medir*, no *qué fotografiar*, y mezclarlas confundía.

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

## Qué agrega

### Campos

| Modelo | Campo | Para qué |
|---|---|---|
| `delivery.carrier` | `installation_appointment_type_id` | Tipo de cita a agendar. Si está vacío, el método de envío es normal. |
| `delivery.carrier` | `installation_min_photos` | Fotos mínimas del lugar (0 = opcionales). Default 1. |
| `sale.order` | `installation_appointment_type_id` | Related del carrier elegido. |
| `sale.order` | `installation_required` | Si el pedido exige agendar instalación. |
| `sale.order` | `installation_booking_id` | Reserva pendiente (antes de confirmar). |
| `sale.order` | `installation_event_id` | Cita creada (después de confirmar). |
| `sale.order` | `installation_photo_ids` | Fotos del lugar que subió el cliente. |
| `sale.order` | `installation_photo_count` | Cantidad de fotos (para el gate). |
| `appointment.type` | `installation_fsm_project_id` | Proyecto de Field Service donde crear la tarea cuando la cita se agenda **sin** pasar por el eCommerce (link compartido). Vacío = la tarea la genera el pedido. |
| `appointment.type` | `installation_request_photos` | Pedir fotos del lugar en el formulario de la cita. |
| `appointment.type` | `installation_min_photos` | Fotos necesarias para reservar (0 = opcionales pero visibles). |
| `appointment.question` | `answer_format` | Formato esperado de la respuesta: texto libre, número entero, número, teléfono o documento (DNI/CUIT). |
| `calendar.event` | `installation_task_id` | Tarea de Field Service generada por una cita agendada fuera del eCommerce. |

### Rutas

| Ruta | Qué hace |
|---|---|
| `GET /shop/installation` | Paso de checkout: estado de la cita + subida de fotos. |
| `POST /shop/installation/submit` | Guarda las fotos y avanza al paso siguiente. |
| `POST /shop/installation/photo/<id>/remove` | Quita una foto del pedido en curso. |

### Puntos de extensión usados

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
3. **Preguntas**: las mismas técnicas del tipo web **más la dirección de la instalación** (acá no hay
   checkout que la aporte). Las preguntas se reutilizan entre tipos, no hay que duplicarlas.
4. **Fotos del lugar**: activar *Pedir fotos del lugar*. El mínimo puede quedar en 0 (se muestran
   pero no bloquean) — bloquear una reserva por una subida desde el celular es arriesgado.
5. **Link para compartir**: abrir el tipo de cita y apretar **Compartir** (arriba a la izquierda).
   Odoo abre *Crear un enlace para compartir* con la URL ya armada (ej. `/book/instalacion`) y el
   botón *Copiar enlace y cerrar*. Ese es el link que se manda al cliente por WhatsApp o mail; **no**
   requiere que se registre y **es siempre el mismo** (queda guardado en el smart button *Enlaces
   compartidos* del tipo de cita, modelo `appointment.invite`).

Este camino **no genera pedido de venta**: si además hay que facturar, el pedido lo arma Nokey en el
backoffice.

## Flujo del cliente

1. Agrega el producto al carrito.
2. Dirección + **método de envío**: elige *Envío con instalación* (ve el costo).
3. Paso **Instalación**: lee el checklist previo y mide la puerta con la ayuda de los diagramas →
   *Agendar la instalación* → elige día y hora en la página de la cita y responde las preguntas
   (incluidas las medidas) → vuelve al paso → sube las fotos del lugar (según la guía) → *Continuar*.
4. Paga. Al confirmarse el pedido: se crea la **Cita**, la **tarea de Field Service** y las fotos
   quedan en el chatter de las dos.

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

## Validación manual

1. Carrito con un producto etiquetado como instalable → el método *Envío con instalación* aparece.
2. Elegirlo → el paso *Instalación* aparece en el wizard del checkout, con el checklist previo, el
   bloque de medidas (dos imágenes lado a lado, responsive) y la guía de fotos visibles.
3. Intentar ir directo a `/shop/payment` → error explicando que falta agendar.
4. Agendar → volver al paso con el día y hora visibles.
5. Intentar pagar sin fotos (con `installation_min_photos = 1`) → error de fotos faltantes.
6. Subir una foto → *Continuar* → pagar.
7. Verificar: Cita creada con las respuestas y las fotos, tarea de FSM con fecha, dirección y fotos.
8. Repetir con el *Envío normal* → el paso *Instalación* no aparece en ningún momento.
9. Con un cliente sin usuario de portal: verificar que quede creado tras confirmar (Ajustes →
   Usuarios y Compañías → Usuarios) y que llegue el mail de invitación (requiere servidor de correo
   saliente configurado). Repetir con un cliente que ya tiene usuario portal/interno → no debe
   mandar mail ni crear un usuario nuevo.
