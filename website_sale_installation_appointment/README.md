# website_sale_installation_appointment

Vender un **envío con instalación incluida** desde el eCommerce y que esa venta quede **agendada como
Cita** (app Citas), con las **fotos del lugar** y los datos que cargó el cliente, y con la **tarea de
Field Service** del instalador.

- **Versión**: 1.0.2
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
   condicional**, recibe las **fotos**, **bloquea el pago** si falta agendar o faltan fotos, y copia
   las fotos a la **Cita** y a la **tarea**.

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
- `sale.order._action_confirm()` — copia las fotos a la Cita y a la tarea (después de `super()`, que
  es donde el core crea ambas).
- `WebsiteAppointmentSale._redirect_to_payment()` — al volver de agendar, vuelve al paso Instalación
  (el nativo vuelve al paso de dirección) y descarta la reserva anterior si el cliente reagenda.

### Validaciones

- El tipo de cita asociado a un método de envío **debe** tener paso de pago y producto de reserva, y
  ese producto debe generar tarea o tener precio; si no, la reserva nunca se ataría al pedido. Se
  frena con `ValidationError` al guardar el método de envío.
- El endpoint público de fotos acepta **sólo imágenes** (se valida el mimetype real del contenido, no
  el que declara el navegador), hasta **10 MB** por archivo y **10 fotos** por pedido.

## Configuración (registros a crear)

1. **Producto de la cita** — tipo *Servicio*, `service_tracking = Crear tarea en proyecto existente`
   apuntando al proyecto de **Field Service**. El precio puede ser 0 (el costo va en el método de
   envío) o el costo de la instalación.
2. **Tipo de cita** (Citas → Configuración) — con **paso de pago** activado y el producto anterior;
   agendado **por recursos** (la cuadrilla como `appointment.resource` con su capacidad), franjas
   horarias reales, zona horaria, y publicado en el website.
   - Las **preguntas** del tipo de cita (piso/depto, ascensor, contacto en obra, observaciones) se
     cargan acá: las respuestas viajan solas a la Cita y a la descripción de la tarea de FSM.
3. **Etiqueta de producto** (ej. *Requiere instalación*) en los productos instalables.
4. **Método de envío "Envío con instalación"** — `Precio fijo` con su costo, publicado en el website,
   con la etiqueta anterior en *Debe tener etiquetas* (así el método aparece sólo si el carrito lleva
   un producto instalable), zona de cobertura por país/provincia/CP si la cuadrilla no llega a todos
   lados, y **Tipo de cita de instalación** = el del punto 2.
5. **Método de envío "Envío normal"** — el de siempre, sin tipo de cita.
6. **Proveedor de pago habilitado** — el pedido se confirma al pagarse; sin proveedor habilitado el
   checkout no llega a confirmar y la Cita no se crea.

## Flujo del cliente

1. Agrega el producto al carrito.
2. Dirección + **método de envío**: elige *Envío con instalación* (ve el costo).
3. Paso **Instalación**: *Agendar la instalación* → elige día y hora en la página de la cita y
   responde las preguntas → vuelve al paso → sube las fotos del lugar → *Continuar*.
4. Paga. Al confirmarse el pedido: se crea la **Cita**, la **tarea de Field Service** y las fotos
   quedan en el chatter de las dos.

## Gotchas

- **Sin proveedor de pago habilitado no hay Cita**: la reserva se convierte en Cita al confirmarse el
  pedido. Un pedido que queda en presupuesto conserva la reserva pendiente (`calendar.booking`), que
  el garbage collector nativo limpia a los 2-6 meses.
- **Cancelar el pedido archiva la Cita** (comportamiento nativo de `website_appointment_sale`).
- **Reagendar** desde el paso reemplaza la reserva anterior: queda una sola línea de instalación.
- Si el cliente cambia el método de envío a uno normal después de agendar, la línea de la reserva
  queda en el carrito hasta que la quite; el paso deja de mostrarse porque el envío ya no exige cita.
- `free_over` (envío gratis a partir de un monto) no tiene sentido en el método con instalación.

## Validación manual

1. Carrito con un producto etiquetado como instalable → el método *Envío con instalación* aparece.
2. Elegirlo → el paso *Instalación* aparece en el wizard del checkout.
3. Intentar ir directo a `/shop/payment` → error explicando que falta agendar.
4. Agendar → volver al paso con el día y hora visibles.
5. Intentar pagar sin fotos (con `installation_min_photos = 1`) → error de fotos faltantes.
6. Subir una foto → *Continuar* → pagar.
7. Verificar: Cita creada con las respuestas y las fotos, tarea de FSM con fecha, dirección y fotos.
8. Repetir con el *Envío normal* → el paso *Instalación* no aparece en ningún momento.
