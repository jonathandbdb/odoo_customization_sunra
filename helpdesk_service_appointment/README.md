# helpdesk_service_appointment

Pedir **service/reparación de una cerradura ya instalada** desde el portal, en autoservicio,
reemplazando al JotForm "Agendar service con Nokey": el cliente elige su cerradura, describe la
falla y agenda la visita sobre la disponibilidad real del técnico. El pedido queda como **ticket de
Helpdesk** y la cita agendada genera la **tarea de Field Service** con fecha, dirección, fotos y el
estado de garantía (informativo).

- **Versión**: 1.0.0
- **Licencia**: LGPL-3
- **Depende de**: `helpdesk_fsm`, `helpdesk_stock`, `website_appointment`, `sk_customer_product_warranty`

## Para qué sirve

Sunra vende cerraduras con instalación, y después de la venta los clientes necesitan pedir service
(la cerradura no abre, la batería se agota, etc.). Antes ese pedido se hacía por un JotForm externo
que no validaba nada contra los datos reales del cliente ni contra la agenda del técnico. Este
módulo mueve ese formulario al portal de Odoo: el cliente **ya está identificado** (usuario portal
de su compra/instalación), elige entre **sus** cerraduras entregadas, y agenda sobre la
**disponibilidad real** del técnico usando la app nativa de Citas.

El service se agenda **siempre gratis**: no hay paso de pago ni `sale.order`. La garantía es
puramente **informativa** (badge en el portal + bloque en la tarea del técnico); si el service
termina siendo pago, se presupuesta después de la visita, fuera de este módulo.

## Cómo funciona (qué es nativo y qué agrega el módulo)

1. **Nativo (Helpdesk + FSM)** — un `helpdesk.ticket` en un team con `use_fsm=True` puede generar una
   tarea de Field Service vía el wizard `helpdesk.create.fsm.task`.
2. **Nativo (Citas/`appointment`)** — un `appointment.type` no publicado, accesible solo por el link
   de un `appointment.invite` (`redirect_url`), ofrece horarios reales sobre la disponibilidad del
   staff asignado.
3. **Este módulo** — agrega el formulario de portal (`/my/service/new`) que crea el ticket, arma la
   URL de agendado correcta y la manda al cliente; engancha el `create()`/`write()` de
   `calendar.event` para que la cita agendada genere/actualice/cancele la tarea FSM del ticket; y
   calcula el estado de garantía **sin números de serie**, a partir de las entregas históricas del
   cliente y de la configuración de `sk_customer_product_warranty`.

No se crean modelos ni tablas nuevas: todo es `_inherit` sobre `product.product`, `helpdesk.ticket`,
`calendar.event`, `project.task` y el wizard `helpdesk.create.fsm.task`, más dos overrides de
controllers de Citas.

## Qué agrega

### Modelos extendidos

| Modelo | `_inherit` | Qué se agrega |
|--------|-----------|----------------|
| `product.product` | `product.product` | `_get_service_warranty()` (garantía efectiva desde entregas, sin series) y `_get_partner_service_products()` (productos entregados a un partner, con primera/última entrega). Sin campos nuevos. |
| `helpdesk.ticket` | `helpdesk.ticket` | Dirección de la visita, cita vigente y snapshot de garantía (campos abajo); helpers de URL de agendado y de fotos. |
| `calendar.event` | `calendar.event` | Campo `service_ticket_id`; overrides de `create` (genera la tarea FSM) y `write` (cancelación / reposición / sync de fechas). |
| `project.task` | `project.task` | Dos campos `related` readonly para mostrar la garantía en el form de la tarea FSM. Sin lógica. |
| `helpdesk.create.fsm.task` (wizard) | `helpdesk.create.fsm.task` | Override de `_generate_task_values()`: dirección de la visita + bloque de garantía en la descripción de la tarea. |

### Campos

| Modelo | Campo | Tipo | Notas |
|--------|-------|------|-------|
| `helpdesk.ticket` | `service_visit_address_id` | Many2one (`res.partner`) | Dirección donde va el técnico; debe pertenecer al commercial partner del ticket. Es el `partner_id` de la tarea FSM. |
| `helpdesk.ticket` | `service_event_ids` | One2many (`calendar.event`) | Solo eventos **activos** (los cancelados quedan archivados fuera). |
| `helpdesk.ticket` | `service_event_id` | Many2one compute | Última cita activa; gate del "no se puede agendar dos veces". |
| `helpdesk.ticket` | `warranty_status` | Selection (`valid`/`expired`/`unknown`) compute stored | Snapshot congelado al crear el ticket. Puramente informativo, nunca bloquea el flujo. |
| `helpdesk.ticket` | `warranty_expiry_date` | Date compute stored | Vencimiento calculado (vacío si `unknown`). |
| `helpdesk.ticket` | `warranty_delivery_date` | Date compute stored | Entrega usada como base del cálculo (primera o última, según config). |
| `calendar.event` | `service_ticket_id` | Many2one (`helpdesk.ticket`) | Vínculo cita ↔ ticket. `ondelete='set null'`. |
| `project.task` | `service_warranty_status` / `service_warranty_expiry_date` | Selection / Date related readonly | Solo display en el form de la tarea FSM. |

> `product_id` y `lot_id` del ticket **no** los agrega este módulo: ya los aporta `helpdesk_stock`
> (`product_id` restringido por `groups="stock.group_stock_user"` — ver Seguridad).

### Rutas

| Ruta | Método | Qué hace |
|------|--------|----------|
| `/my/service/new` | GET | Renderiza el formulario de portal (paso 1). |
| `/my/service/new` | POST | Valida, crea el ticket y redirige (303) a la página nativa de Citas para agendar (paso 2). |

### Puntos de extensión usados

- `AppointmentController._get_extra_calendar_event_params()` — recibe `service_ticket_id` del
  submit de Citas y lo materializa en el `calendar.event` (con anti-IDOR y anti-doble-agendado).
- `AppointmentCalendarController.appointment_cancel()` — reinyecta `service_ticket_id` en la URL de
  vuelta tras cancelar, para que un reagendado del cliente no genere una cita huérfana.
- `calendar.event.create()` / `write()` — generan/cancelan/sincronizan la tarea FSM del ticket.
- `helpdesk.create.fsm.task._generate_task_values()` — dirección de visita + bloque de garantía.
- `CustomerPortal._ticket_get_page_view_values()` (de `helpdesk`) — inyecta la URL/estado de la cita
  en el detalle del ticket (`/my/ticket/<id>`).

### Validaciones

- El `product_id` elegido debe estar entre las cerraduras **entregadas** al commercial partner del
  usuario (anti-IDOR); la `visit_address_id` debe pertenecer a ese mismo commercial partner.
- El tipo de problema es obligatorio y debe ser uno de los 7 `helpdesk.tag` semilla.
- Fotos: opcionales, hasta **10** por ticket, hasta **10 MB** cada una, validando el **mimetype real
  del contenido** (no la extensión declarada por el navegador).

## Cálculo de garantía sin números de serie

Sunra no usa tracking por número de serie, así que `stock.lot.warranty_expiry_date` (de
`sk_customer_product_warranty`) siempre está vacío. La garantía se calcula en cambio desde las
**entregas** del cliente:

1. `_get_partner_service_products()` agrupa las entregas `done`/`outgoing` (sin reemplazos) del
   commercial partner por producto, con la primera y la última fecha de entrega.
2. `_get_service_warranty()` resuelve la duración/unidad/tipo de inicio configurados
   (variante → plantilla → categoría, vía `sk_customer_product_warranty`) y calcula el vencimiento
   con el mismo mapeo de unidades que ese módulo.
3. Si el tipo de inicio es "Fabricación" (`manufacture`) y no hay lote con fecha, el resultado es
   **`unknown`** a propósito: sin serie no se conoce la fecha real de fabricación, y usar la entrega
   como proxy informaría *más* garantía de la real. Se prefiere no informar antes que informar mal.
4. Si algún día se activa `lot_id` con `warranty_expiry_date`, esa fecha **prioriza** sobre el
   cálculo por entregas.

El resultado se **congela** en el ticket al crearlo (`warranty_status`, `warranty_expiry_date`,
`warranty_delivery_date` son compute `store=True`): reconfigurar la garantía del producto después no
reescribe tickets viejos.

## Seguridad

**Sin ACLs ni record rules nuevas** — es una decisión explícita, no un olvido: el módulo no define
modelos nuevos, todo se agrega por `_inherit` sobre modelos que ya traen sus ACLs
(`helpdesk`, `helpdesk_stock`, `helpdesk_fsm`, `appointment`, `project`, `stock`).

- El acceso del cliente a **su** ticket lo resuelve la record rule nativa de Helpdesk
  (`helpdesk_portal_ticket_rule`), que exige `team_privacy_visibility = 'portal'` (por eso la
  semilla del team "Service" lo fija explícitamente) y que el partner sea *follower* del ticket (lo
  hace el `create` nativo al recibir `partner_id`).
- No se crean grupos nuevos. Los usuarios internos que atienden Service son usuarios de Helpdesk
  normales, pero necesitan el grupo **`stock.group_stock_user`** (Inventario) para ver el campo
  **Producto** del ticket, que `helpdesk_stock` restringe con ese grupo — ver *Configuración* abajo.
- Mono-compañía: no se agregan campos ni reglas por compañía.

**Sudos usados** (todos de lectura/escritura acotada, ver la spec para el detalle completo): lectura
agregada de entregas para armar la lista de cerraduras del cliente, creación del ticket desde el
portal (mismo criterio que el formulario nativo de `website_helpdesk`, con re-validación anti-IDOR
antes de crear), manejo de adjuntos de fotos, lectura del `appointment.invite` semilla para construir
la URL de agendado, y las escrituras del wizard FSM / `project.task` al generar o sincronizar la
tarea (el cliente portal no tiene permisos sobre `project.task`).

## Vistas

**Backoffice**: grupo "Service" en el form del ticket (dirección de visita, cita vigente readonly,
garantía con badge y decoración por estado); columna opcional de garantía en la lista de tickets;
garantía readonly en el form de la tarea FSM.

**Portal**: formulario `/my/service/new` (datos de contacto, dirección + aclaraciones, cerraduras
con badge de garantía y fallback de texto libre, tipo de problema, descripción, fotos); botón
"New Service Request" en `/my/tickets`; bloque **Service** en el detalle del ticket
(`/my/ticket/<id>`) con producto, garantía y la cita (link a gestionar/cancelar, o botón
"Schedule visit" si no hay cita activa).

## Datos semilla (`noupdate="1"`)

| Registro | Qué es |
|----------|--------|
| Team **Service** (`helpdesk.team`) | `use_fsm=True`, `privacy_visibility='portal'` explícito, etapas nativas (sin etapas propias). |
| Tipo de cita **Service Visit** (`appointment.type`) | 2 horas, agendado por usuarios, **despublicado** (`is_published=False`), y con `staff_user_ids` **vacío a propósito** (ver Configuración). |
| Invite (`appointment.invite`, `short_code='service'`) | Habilita el tipo despublicado vía su `access_token`/`redirect_url`, sin exponerlo en `/appointment` público. |
| 7 `helpdesk.tag` | Los tipos de problema del JotForm original (batería, no abre, no cierra, conectividad, etc.), con nombres calificados ("Lock …") para no chocar con tags existentes. |

## Configuración (obligatoria antes de usar el módulo)

El módulo se instala **inerte a propósito**: sin esta configuración, el formulario de portal existe
pero **no ofrece horarios** para agendar. Es el estado seguro (mejor "no agendable" que "agendable
con el técnico equivocado"). Pasos:

1. **Asignar staff (técnicos) al tipo de cita "Service Visit"** — Citas → Configuración → Tipos de
   cita → *Service Visit* → agregar los usuarios técnicos en **Usuarios**. La semilla lo deja
   **vacío a propósito**: sin staff asignado, la página de agendado no muestra ningún horario
   disponible (inerte).
2. **Ajustar los slots (franjas horarias)** — Odoo auto-crea slots por defecto **Lunes a Viernes,
   9-12 y 14-17** en cuanto el tipo de cita se crea sin franjas propias (no se pueden "no
   semillar"). Revisar/editar esas franjas en la pestaña **Disponibilidad** del tipo de cita según
   el horario real del equipo técnico.
3. **Configurar el proyecto de Field Service del team** — Helpdesk → Configuración → Equipos →
   *Service* → pestaña **Field Service** → **Proyecto**: sin este `fsm_project_id`, la cita se
   agenda igual pero **no se genera** la tarea del técnico (queda una nota en el chatter del
   ticket).
4. **Configurar garantías de las cerraduras** — en la ficha del producto (o su categoría), pestaña
   *Información general* → grupo **Warranty Information**: activar `warranty_tracking` y configurar
   duración/unidad/tipo de inicio (módulo `sk_customer_product_warranty`). Sin esto, el badge de
   garantía siempre muestra "Sin datos de garantía" (`unknown`), lo cual **no bloquea** el pedido
   pero deja sin informar al cliente/técnico.
   - Ese grupo era **invisible para productos sin tracking por serie** (condición del módulo de
     garantías); este módulo lo hace visible vía `views/product_views.xml` (v1.0.1), porque acá la
     garantía se calcula desde las entregas, sin series.
   - **Gotcha de variantes existentes**: la propagación de `warranty_tracking` desde la plantilla a
     sus variantes (`_prepare_variant_values`) solo aplica a variantes **nuevas**. Si las cerraduras
     ya tenían variantes creadas **antes** de activar la garantía en la plantilla, hay que revisar
     manualmente cada variante existente y activar `warranty_tracking` en ella (no alcanza con
     tocar solo la plantilla o la categoría).
5. **Dar el grupo `stock.group_stock_user` a los agentes de Helpdesk que atienden Service** —
   Ajustes → Usuarios y Compañías → Usuarios → pestaña *Otros* → agregar el grupo de **Inventario /
   Usuario**. Sin este grupo no ven el campo **Producto** del ticket (lo restringe `helpdesk_stock`),
   y por lo tanto tampoco ven qué cerradura reportó el cliente.
6. **Procedimiento telefónico** (pedidos que no entran por el portal): compartir la URL
   `/my/service/new` con el cliente. Si el cliente **no tiene** usuario portal, invitarlo desde su
   ficha de contacto con la acción nativa **"Grant portal access"**. También puede llegar con
   usuario portal ya creado si compró con instalación: el módulo hermano
   `website_sale_installation_appointment` (v1.1.0) lo auto-invita al confirmarse esa venta.

## Flujo del cliente

1. Entra a `/my/service/new` (logueado, o recibe el link por teléfono e inicia sesión).
2. Ve un resumen de sus datos de contacto (con link a `/my/account` para corregirlos), elige la
   **dirección de la visita** entre las suyas + aclaraciones libres (piso/depto/indicaciones).
3. Elige su cerradura entre las **entregadas** (con badge "En garantía" / "Fuera de garantía" / "Sin
   datos de garantía"), o usa el fallback "No está en la lista / No lo sé" con modelo declarado a
   mano y antigüedad aproximada.
4. Elige el **tipo de problema** (7 opciones), describe la falla y sube fotos opcionales (hasta 10,
   10 MB c/u).
5. Al enviar, el ticket de Helpdesk se crea y el cliente es redirigido a la **página nativa de
   Citas** para elegir día y hora reales sobre la disponibilidad del técnico.
6. Al confirmar la cita se crea automáticamente la **tarea de Field Service**, con las fechas de la
   cita, la dirección de visita, el bloque de garantía y las fotos en su chatter.
7. En `/my/tickets` / `/my/ticket/<id>` el cliente ve el estado: producto, garantía y la cita, con
   link para gestionar/cancelar, o el botón "Schedule visit" si no hay cita activa.
8. Si cancela la cita, la tarea FSM abierta se cancela y el portal vuelve a ofrecer "Schedule
   visit" para reagendar (se crea una tarea nueva, conservando el vínculo con el mismo ticket).

## Gotchas

- **Garantía informativa, sin números de serie**: es una aproximación desde las entregas del
  cliente. Nunca bloquea el agendado ni genera un paso de pago — el service siempre es gratis en
  este módulo; el presupuesto (si aplica) se hace después de la visita, fuera del sistema.
- **Sincronización de una sola vía**: mover fechas de la **cita** sincroniza la tarea FSM; mover la
  **tarea** (ej. en el Gantt de FSM) **no** reagenda la cita del cliente. Si el técnico necesita
  cambiar la fecha, hay que hacerlo desde el evento de Calendario/Citas.
- **Ventana `min_cancellation_hours`** (1 hora por defecto en el tipo de cita): dentro de esa
  ventana el portal **no deja cancelar** la cita. Para reprogramar una visita sobre la hora hay que
  hacerlo desde el backoffice (mover la cita/tarea directamente).
- **Reagendar = cancelar + volver a reservar**: la página nativa de Citas no ofrece "mover" un
  turno ya confirmado; el cliente cancela y agenda de nuevo (el vínculo con el ticket se conserva).
- **Invitaciones por mail**: para que el cliente reciba el mail de invitación al portal (flujo
  telefónico o del módulo hermano) hace falta un **servidor de correo saliente** configurado
  (Ajustes → Técnico → Correo).
- **La URL de agendado nunca se arma a mano**: siempre sale de `_get_service_appointment_url()`
  (basada en `invite.redirect_url`). Armarla como `/appointment/<id>?invite_token=...` responde
  **403 Forbidden** en cuanto hay 2+ tipos de cita activos (ya pasa: convive con el tipo de
  instalación del módulo hermano).
- **Un ticket con cita activa no puede agendar otra**: si se manipula el parámetro o se reintenta,
  la nueva cita se crea igual pero **sin** vincularse al ticket ni generar tarea.

## Validación manual

1. Como usuario portal con entregas registradas: abrir `/my/service/new`, verificar que aparezcan
   sus cerraduras entregadas con el badge de garantía correcto.
2. Elegir una cerradura, un tipo de problema, describir la falla, subir una foto → enviar → debe
   redirigir a la página de Citas **sin error 403** (probar con al menos 2 tipos de cita activos en
   la base, ej. junto con el de instalación).
3. Agendar un turno (requiere que el tipo "Service Visit" ya tenga staff asignado, paso 1 de
   *Configuración*) → verificar en el backoffice: ticket con `service_visit_address_id`, tarea FSM
   creada con las fechas de la cita, bloque de garantía en su descripción y la foto en su chatter.
4. Repetir el formulario con "No está en la lista / No lo sé" → el ticket debe crearse **sin**
   `product_id`, con el modelo/antigüedad en la descripción y garantía "Sin datos".
5. Cancelar la cita desde `/calendar/view/<token>` (fuera de la ventana de 1 hora) → la tarea FSM
   pasa a cancelada y el portal vuelve a ofrecer "Schedule visit"; reservar de nuevo debe generar
   una tarea nueva conservando el ticket.
6. Intentar manipular `product_id`/`visit_address_id` con valores de otro partner (vía POST directo)
   → debe rechazarse sin crear el ticket.
7. Sin asignar staff al tipo de cita: verificar que la página de agendado no ofrezca ningún horario
   (estado inerte esperado tras la instalación).

## Dependencias

- `helpdesk_fsm` (Enterprise) — vehículo del reclamo (`helpdesk.ticket` + wizard de generación de
  tarea FSM).
- `helpdesk_stock` (Enterprise) — `product_id` (con `groups="stock.group_stock_user"`) y `lot_id`
  (sin esa restricción) del ticket.
- `website_appointment` (Enterprise) — la app de Citas (`appointment.type`, `appointment.invite`,
  `calendar.event`).
- `sk_customer_product_warranty` (propio, este repo) — configuración de garantía por
  categoría/plantilla/variante que este módulo consulta (no duplica).

## Mapa de archivos

```
helpdesk_service_appointment/
    controllers/
        helpdesk_service_appointment.py    # /my/service/new (GET/POST) + hook portal del ticket
        appointment.py                     # overrides de Citas (params extra + cancelación)
    models/
        product_product.py                 # _get_service_warranty, _get_partner_service_products
        helpdesk_ticket.py                  # campos, snapshot de garantía, URL de agendado, fotos
        calendar_event.py                   # service_ticket_id, create/write (genera/sincroniza FSM)
        project_task.py                     # related readonly de garantía
    wizard/
        helpdesk_create_fsm_task.py         # override _generate_task_values (dirección + garantía)
    views/
        helpdesk_ticket_views.xml           # bloque Service en el form/list del ticket
        project_task_views.xml              # garantía readonly en la tarea FSM
        helpdesk_service_appointment_templates.xml   # formulario de portal + inherits de helpdesk
    data/
        helpdesk_service_appointment_data.xml   # team, tipo de cita, invite, 7 tags (noupdate)
    i18n/
        es_419.po
    specs/
        helpdesk_service_appointment.md     # spec SDD — fuente de verdad técnica del módulo
```

## Comandos (Docker, entorno Nokey)

```bash
# Instalar el módulo
docker exec nokey-odoo-1 odoo -d nokey -i helpdesk_service_appointment --stop-after-init

# Actualizar tras un cambio
docker exec nokey-odoo-1 odoo -d nokey -u helpdesk_service_appointment --stop-after-init
```

O con el wrapper del enjambre: `.claude/scripts/odoo_runtime.sh install nokey helpdesk_service_appointment`
/ `.claude/scripts/odoo_runtime.sh upgrade nokey helpdesk_service_appointment`.

## Notas de mantenimiento

- El módulo es **SDD**: `specs/helpdesk_service_appointment.md` es la fuente de verdad técnica
  (decisiones, campos, métodos, reglas de negocio, edge cases y anclajes al core). Cualquier cambio,
  por chico que sea, debería reflejarse ahí y mantener el `version` del manifest sincronizado con la
  `Version` de la spec.
- El snapshot de garantía del ticket es **stored**: si se cambia la configuración de garantía de un
  producto, los tickets ya creados **no** se actualizan solos (hay que recomputar a mano si hace
  falta corregir un ticket viejo).
- El anti-doble-agendado es **por ticket**, no por partner: un mismo cliente puede tener varios
  tickets de service abiertos con cita cada uno.
- No hay límite de tickets de service abiertos por cliente.

## Licencia y autoría

LGPL-3 · Sunra · https://github.com/sunraargsh
