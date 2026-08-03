# Spec de modulo: helpdesk_service_appointment

| Campo | Valor |
|-------|-------|
| **Modulo** | `helpdesk_service_appointment` |
| **Version** | `1.0.2` (== `version` del `__manifest__.py`, formato `x.x.x`) |
| **Serie Odoo** | `19` (informativa — serie de `ODOO_VERSION`, no es la version de la spec) |
| **Estado** | `verified` |
| **Actualizado** | `2026-08-03` |

## Objetivo

Permitir que un cliente de Sunra pida **service/reparacion de una cerradura ya instalada** desde el
portal, en autoservicio y sin pasar por el eCommerce: llena un formulario (que reemplaza al JotForm
"Agendar service con Nokey"), selecciona su cerradura entre las que le entregaron, describe la falla,
sube fotos opcionales y **agenda la visita** sobre la disponibilidad real del tecnico. El pedido queda
como **ticket de Helpdesk** y la cita agendada genera la **tarea de Field Service** con la fecha, la
direccion de la visita, las fotos y el **estado de garantia** (informativo) calculado desde las
entregas del cliente.

El modulo **no crea modelos ni tablas nuevas**: extiende `product.product`, `helpdesk.ticket`,
`calendar.event`, `project.task` y el wizard `helpdesk.create.fsm.task`, agrega dos rutas de portal
(`/my/service/new` GET/POST), dos overrides de controllers de Citas (el hook de submit y la
cancelacion), templates de portal, vistas de backoffice y datos semilla (team Service, tipo de cita,
invite y tags de problema).

## Decisiones vigentes

> Decisiones de diseño que rigen HOY (fuente: planning aprobado por el usuario el 2026-07-29). Lo
> marcado `[ASUNCION]` se asumio con criterio conservador (sin respuesta explicita) y queda auditable.

| # | Decision | Valor vigente |
|---|----------|---------------|
| D1 | Vehiculo del reclamo | **Helpdesk + FSM**: el reclamo es un `helpdesk.ticket` (team "Service", `use_fsm=True`) y la visita es una tarea FSM generada via `helpdesk_fsm`. Se descarto `repair` (core): orientado a taller, sin portal; el service es on-site. |
| D2 | Cobro fuera de garantia | **Presupuesto post-visita**. Se agenda **siempre gratis**, sin paso de pago ni `sale.order`. La garantia es **informativa** (badge en el portal + bloque en la tarea FSM); nunca bloquea el agendado. |
| D3 | Identificacion del producto | Cliente **registrado** (usuario portal) que elige su cerradura entre **sus productos entregados**. **Sin numeros de serie hoy** (Sunra no usa tracking por serie); el diseño queda compatible con `lot_id` a futuro. |
| D4 | Origen del usuario portal | El partner ya tiene usuario portal porque tuvo una instalacion. La **auto-invitacion** al confirmarse la venta con instalacion vive en el modulo hermano `website_sale_installation_appointment` (ver NO incluye). |
| D5 | Pedidos por telefono | El backoffice comparte el **link al formulario** (`/my/service/new`). Si el partner no tiene usuario portal, se lo invita con el wizard nativo (`portal.wizard`) — procedimiento funcional, no codigo de este modulo. |
| D6 | Datos de contacto en el formulario | **No se piden**: se muestran como resumen del usuario logueado (nombre, telefono, email) con link a `/my/account` para corregirlos. |
| D7 | Direccion de la visita | Select entre las **direcciones existentes** del commercial partner — **filtradas por `type in ('invoice','delivery','other')`** (fix post-review, m1: sin el filtro, `child_ids` trae tambien contactos-persona `type='contact'`, ej. empleados de la empresa, que no son direcciones fisicas utilizables) — (default: la principal, o la de entrega si existe) + campo libre "Aclaraciones" (piso/depto/indicaciones). El partner elegido se guarda en `helpdesk.ticket.service_visit_address_id` y es el `partner_id` de la tarea FSM (guia la ruta del tecnico). |
| D8 | Producto no identificable | Fallback **"No esta en la lista / No lo se"**: texto libre del modelo + select de antiguedad de instalacion (`<6m` / `6m-1a` / `>1a`, proxy del JotForm). El ticket queda **sin** `product_id` y con `warranty_status = unknown`; el agendado no cambia. |
| D9 | Producto "Todavia no la elegi" (pre-venta) | **Fuera de alcance**: es venta/instalacion, la cubre el flujo existente de eCommerce (`website_sale_installation_appointment`). |
| D10 | Tipo de problema | Select **obligatorio** con los 7 del JotForm, materializados como `helpdesk.tag` semilla; se asigna al `tag_ids` del ticket. |
| D11 | Fotos de la falla | **Opcionales** (mejora sobre el JotForm), con el patron endurecido ya usado en el checkout de instalacion: `guess_mimetype` del **contenido real**, maximo **10 fotos** y **10 MB** por archivo. Se crean como adjuntos **pendientes** (`res_model='mail.compose.message'`, `res_id=0`) y el `message_post` del ticket los **reasigna** al ticket: `mail.thread._process_attachments_for_post` descarta los `attachment_ids` de un usuario **portal** que no sean pendientes suyos, asi que crearlos ya apuntando al ticket haria que las fotos se pierdan silenciosamente. |
| D12 | Fecha y hora | Paso 2 = **pagina nativa de Citas** (disponibilidad y capacidad reales del tecnico). Mejora sobre el JotForm, que no validaba agenda. |
| D13 | Como se vinculan cita y ticket | Query param custom `service_ticket_id` que viaja del redirect hasta el submit de Citas y se materializa via override de `_get_extra_calendar_event_params` en `calendar.event.service_ticket_id`. La URL de agendado se arma con **`invite.redirect_url`** (campo nativo computado) + `&service_ticket_id=<id>`: armarla a mano como `/appointment/<id>?invite_token=...` da **403 Forbidden** en cuanto hay 2+ tipos de cita activos (garantizado: existe el de instalacion), porque `_fetch_and_check_private_appointment_types` levanta **todos** los tipos activos y `appointment.invite._check_appointments_params` exige match exacto con los tipos del invite. `redirect_url` ya emite `invite_token` **y** `filter_appointment_type_ids`. |
| D14 | Quien crea la tarea FSM | El **`create` de `calendar.event`** (capa modelo): si viene `service_ticket_id`, instancia el wizard nativo `helpdesk.create.fsm.task` (sudo) y llama `action_generate_task()`. Una cita de Citas no genera tarea FSM por si sola (eso lo hace `sale_project` tras una venta pagada), y el service se agenda gratis. |
| D15 | Robustez del vinculo | `[ASUNCION]` La generacion de la tarea FSM corre en un **savepoint + try**: si falla (team sin `fsm_project_id`, permisos, datos raros) **no rompe la creacion de la cita** del cliente; deja nota en el chatter del ticket. Criterio conservador: el cliente nunca ve un error al agendar. |
| D16 | Doble agendado | **Rechazado**: si el ticket ya tiene un evento activo, el param `service_ticket_id` se ignora (la cita se crea sin tarea ni vinculo). El portal solo ofrece "Schedule visit" cuando no hay evento activo **y** la etapa del ticket no esta plegada/cerrada (`not ticket.stage_id.fold`, fix post-review m8: un ticket cerrado no deberia poder generar una cita/tarea nueva). |
| D17 | Cancelacion desde el portal | Cancelar la cita en `/calendar/view/<token>` archiva el evento (`active=False`, via `action_cancel_meeting`). Eso pasa las tareas FSM **abiertas** del ticket a `1_canceled` + mensaje en el ticket, y el portal vuelve a ofrecer "Schedule visit". |
| D18 | Reagendado | Dos caminos distintos: (a) **interno** — mover `start`/`stop` del evento **sincroniza** `planned_date_begin`/`date_deadline` de la tarea FSM abierta, y desarchivar el evento **repone** la ultima tarea cancelada; (b) **cliente** — el portal de Citas no ofrece "mover": reagendar es **cancelar + volver a reservar** (el evento viejo queda archivado, y el guard anti-doble-agendado lo permite porque el o2m solo ve eventos activos). Para que ese segundo agendado no quede huerfano, ver D34. |
| D19 | Sentido de la sincronizacion | **Una sola via**: evento → tarea. Mover la tarea en el Gantt/FSM **no** modifica la cita (documentado; evitar loops de escritura). |
| D20 | Calculo de garantia (sin series) | La config vive en categoria/plantilla/variante (`sk_customer_product_warranty`); `stock.lot.warranty_expiry_date` hoy **nunca** se llena (solo lo escribe `_action_done` si `tracking == 'serial'`). Por eso la garantia se calcula desde las **entregas** del partner + `_get_warranty_info()`: `first_sale` → primera entrega, `last_sale` → ultima entrega. |
| D21 | `warranty_start_type = manufacture` sin lote | `[ASUNCION]` → **`unknown`**. Sin numero de serie no conocemos la fecha de fabricacion, y usar la entrega como proxy **inventaria** una garantia (la fecha de fabricacion es anterior a la entrega: informariamos mas garantia de la real). Se prefiere ser honestos: badge "Sin datos de garantia" y que el tecnico/backoffice resuelva. |
| D22 | Prioridad del lote | `[ASUNCION]` Si en el futuro hay `lot_id` con `warranty_expiry_date`, esa fecha **gana** sobre el calculo por entregas (el lote es el dato mas especifico, y es el que ya escribe `sk_customer_product_warranty`). |
| D23 | Producto mal configurado | `[ASUNCION]` `warranty_tracking` apagado o sin duracion → `warranty_status = unknown` y badge "Sin datos de garantia". **No se filtra** al producto de la lista: el cliente igual puede pedir service (criterio conservador: nunca bloquear el pedido por un dato de configuracion). |
| D24 | Snapshot en el ticket | `warranty_status` / `warranty_expiry_date` / `warranty_delivery_date` son **compute stored** en `helpdesk.ticket` (depends `partner_id`, `product_id`, `lot_id`), con lectura interna en `sudo()`. Se congelan al crear el ticket y no cambian si despues se reconfigura la garantia del producto. |
| D25 | Lista de "sus cerraduras" | `_read_group` (sudo) sobre `stock.move.line` — `state=done`, `picking_code=outgoing`, `picking_id.partner_id child_of` commercial partner, `picking_id.is_replacement = False` — agrupado por `product_id` con `date:min`/`date:max`. **Diferencia deliberada** con el nativo `_compute_suitable_product_ids` de `helpdesk_stock`: ese incluye tambien productos de **ventas confirmadas sin entregar**, que aca no sirven porque la garantia necesita una **fecha de entrega**. Se excluyen los pickings de reemplazo (igual que el nativo). Multiples unidades del mismo producto = **una fila** (dedupe). |
| D26 | Seguridad del create desde portal | El ticket se crea en **sudo** (mismo criterio que el form nativo de `website_helpdesk`), pero **re-validando** que el `product_id` este entre las entregas del partner y que la direccion elegida pertenezca a su commercial partner (anti-IDOR). |
| D27 | Modelos y ACLs | **Sin modelos nuevos** → sin `security/`: no hay `ir.model.access.csv` ni `ir.rule` propios. El portal lee su ticket por la **record rule nativa de helpdesk** (`helpdesk_portal_ticket_rule`), que exige dos cosas: `team_privacy_visibility = 'portal'` (de ahi que la semilla del team lo fije **explicitamente**) y que el partner sea **follower** del ticket (lo hace el `create` nativo de `helpdesk.ticket` al recibir `partner_id`). |
| D28 | Datos semilla | `noupdate="1"`: team "Service" (`use_fsm=True`, `privacy_visibility='portal'` explicito, etapas nativas), tipo de cita "Service Visit" (2 h, `schedule_based_on='users'`, **`is_published=False`**, `staff_user_ids` **vaciado explicitamente** con `eval="[(6, 0, [])]"` para que no quede el usuario que instala), `appointment.invite` con `short_code='service'` (su `access_token` + `redirect_url` habilitan el tipo sin publicarlo) y los 7 `helpdesk.tag`. El codigo los referencia por `env.ref()` con error claro si faltan. |
| D29 | Horarios, staff y `fsm_project_id` | **Configuracion funcional** (documentada en el README), no semilla. Comportamiento real a documentar: el `_compute_category` del core **auto-crea slots por defecto** (L-V 9-12 y 14-17) si el tipo nace sin `slot_ids` — no se pueden "no semillar", solo ajustar despues. Con `staff_user_ids` vacio (D28) el tipo **no ofrece horarios**: queda inerte (no agendable) hasta que el funcional asigne tecnicos, que es el estado seguro deseado. El `fsm_project_id` del team tambien lo confirma/ajusta el funcional. |
| D30 | Multi-compania | `[ASUNCION]` **Mono-compania**: no se agregan campos ni reglas de compania; se usa la compania del ticket/team. |
| D31 | Idioma | UI en **ingles** con `_()`, traduccion en `i18n/es_419.po` (mismo criterio que `website_sale_installation_appointment`). |
| D32 | Limite de tickets abiertos | `[ASUNCION]` **Sin limite**: un partner puede tener varios tickets de service abiertos. El anti-doble-agendado es por **ticket** (D16), no por partner. |
| D33 | Alcance del override del wizard FSM | El `partner_id` = `service_visit_address_id` se aplica **solo** cuando el wizard corre desde nuestro flujo, marcado con la clave de contexto `hsa_from_appointment=True` que pasa `calendar.event.create`. El camino **manual** del backoffice (agente que abre "Create a Field Service task" y elige un cliente) queda **intacto**: pisarle la eleccion seria un efecto lateral inesperado. El **bloque de garantia** en la descripcion, en cambio, se agrega **siempre** (es informacion, no una decision del agente). |
| D34 | Reagendado del cliente tras cancelar | El controller nativo de cancelacion redirige a `invite.redirect_url + '&state=cancel'`, **sin** `service_ticket_id` → si el cliente reserva de nuevo desde ahi, la cita nace **huerfana** (sin ticket ni tarea). Se agrega un override chico de `appointment_cancel`: si el evento cancelado tenia `service_ticket_id`, se **reinyecta** ese param en la URL de redireccion, de forma que el rebooking conserve el vinculo. |
| D35 | Asignado de la tarea FSM (varios tecnicos) | La tarea se asigna al **tecnico de la cita** = organizador del evento (`calendar.event.user_id`), **solo** si el tipo de cita agenda `schedule_based_on='users'`; en las citas por **recursos** el nativo pone ahi el `create_uid` del tipo de cita (`appointment.type._prepare_calendar_event_values`), que no es quien va a la visita, asi que la tarea queda **sin asignar** y el despacho lo resuelve el backoffice. Se escribe **explicitamente** (no se confia en el default) porque el `create` de `project.task` deja como asignado al **uid actual**, que en este flujo es el **cliente portal** que agendo (`sudo()` no cambia el uid) — un `share=True` como asignado ademas viola el `domain` del campo. Limitacion aceptada: cambiar el organizador del evento **despues** no re-asigna la tarea (mismo criterio que "mover la tarea no sincroniza la cita", D18). |

## Alcance

### Incluye

- Formulario de portal `/my/service/new` (GET/POST, `auth='user'`, `website=True`) con: resumen de
  contacto, selector de direccion de visita + aclaraciones, lista de cerraduras entregadas con badge
  de garantia, fallback de texto libre + antiguedad, select obligatorio de problema (tags), textarea
  de descripcion y upload opcional de fotos endurecido.
- Creacion del ticket (sudo, con re-validacion anti-IDOR) en el team Service, con tag, descripcion,
  `product_id`, `service_visit_address_id` y fotos en el chatter; redirect 303 a la pagina de Citas
  usando **`invite.redirect_url`** (que ya trae `invite_token` + `filter_appointment_type_ids`) mas
  `&service_ticket_id=<id>`.
- Override de `_get_extra_calendar_event_params` que valida el `service_ticket_id` y lo materializa en
  el `calendar.event`.
- Override de `appointment_cancel` que **reinyecta** `service_ticket_id` en la URL de vuelta, para que
  el reagendado del cliente tras cancelar no genere una cita huerfana (D34).
- Generacion de la **tarea FSM** en el `create` de `calendar.event` (wizard nativo `helpdesk.create.fsm.task`),
  con fechas de la cita, direccion de visita, bloque de garantia en la descripcion y copia de las fotos.
- Reagendado / cancelacion: sync de fechas evento → tarea, cancelacion de tareas abiertas al archivar
  el evento y reposicion al desarchivarlo.
- Calculo informativo de garantia sin series: `product.product._get_service_warranty()` +
  snapshot stored en el ticket (`warranty_status` / `warranty_expiry_date` / `warranty_delivery_date`).
- Portal del ticket: bloque Service (producto, garantia, cita con link `/calendar/view/<token>` o boton
  "Schedule visit") y boton "New Service Request" en `/my/tickets`.
- Vistas de backoffice: bloque Service en el form del ticket (con decoraciones por garantia) y garantia
  readonly en el form de la tarea FSM.
- Datos semilla `noupdate` (team, tipo de cita despublicado, invite, 7 tags de problema).
- Documentacion (`README.md` + `static/description/index.html`), fila en el README raiz del repo e
  `i18n/es_419.po`.

### NO incluye

- **Auto-invitacion al portal** tras la venta con instalacion: es un **desarrollo hermano** en
  `website_sale_installation_appointment` (v1.0.3 → 1.1.0), porque depende de
  `_is_installation_required()` de ese modulo. No se crea modulo pegamento ni se toca aca.
- **Cobro / presupuesto** del service fuera de garantia: no hay `sale.order`, ni paso de pago, ni
  generacion automatica de presupuesto. Se presupuesta despues de la visita (D2).
- **Numeros de serie / tracking por lote**: no se activa tracking ni se pide serie al cliente. El
  codigo prioriza `lot_id` si algun dia existe (D22), pero no lo crea ni lo exige.
- **Pre-venta** ("Todavia no la elegi la cerradura"): flujo de venta/instalacion existente (D9).
- **Modelos nuevos, ACLs y record rules propias** (D27).
- **Sincronizacion tarea → cita** (mover la tarea no reagenda la cita, D19).
- **Alta de usuarios portal desde este modulo** (se usa el wizard nativo, D5).
- **Horarios/staff del tipo de cita, `fsm_project_id` y `warranty_tracking` de los productos**:
  configuracion funcional documentada, no semilla (D29).
- **Multi-compania** y reglas por compania (D30).
- **Encuestas de satisfaccion, SLA, portal de seguimiento propio**: se usa lo nativo de helpdesk.
- Modificar core/enterprise: todo por `_inherit` / herencia de controller / `t-inherit`.

## Modelos

### Nuevos

No aplica. El modulo no define modelos nuevos (no crea tablas ni `_name`), por diseño (D27).

### Extendidos

| Modelo | _inherit | Que se agrega |
|--------|----------|--------------|
| `product.product` | `product.product` | Helpers de negocio: `_get_service_warranty()` (garantia efectiva desde entregas, sin series) y `_get_partner_service_products()` (productos entregados a un partner con primera/ultima entrega). Sin campos nuevos. |
| `helpdesk.ticket` | `helpdesk.ticket` | Campos `service_visit_address_id`, `service_event_ids`, `service_event_id`, `warranty_status`, `warranty_expiry_date`, `warranty_delivery_date`; computes del snapshot de garantia y del evento vigente; helpers de URL de agendado y de fotos. |
| `calendar.event` | `calendar.event` | Campo `service_ticket_id`; overrides de `create` (genera tarea FSM + fechas + fotos + mensaje) y `write` (cancelacion / reposicion / sync de fechas); helpers privados de servicio. |
| `project.task` | `project.task` | Campos **related readonly** `service_warranty_status` y `service_warranty_expiry_date` (desde `helpdesk_ticket_id`), solo para mostrar la garantia en el form de la tarea FSM. Sin logica. |
| `helpdesk.create.fsm.task` (TransientModel) | `helpdesk.create.fsm.task` | Override de `_generate_task_values()`: `partner_id` = direccion de la visita del ticket y bloque de garantia al inicio de la descripcion. |

## Campos

| Modelo | Campo | Tipo | String | Requerido | Default | Restricciones |
|--------|-------|------|--------|-----------|---------|--------------|
| `helpdesk.ticket` | `service_visit_address_id` | Many2one (`res.partner`) | Visit Address | No | — | Debe pertenecer al commercial partner del ticket (validado en el controller, D26). `ondelete='set null'` (default de m2o no requerido). Usado como `partner_id` de la tarea FSM. |
| `helpdesk.ticket` | `service_event_ids` | One2many (`calendar.event`, `service_ticket_id`) | Service Appointments | No | — | Solo devuelve eventos **activos** (`calendar.event` tiene `active`); los cancelados quedan archivados fuera del o2m. |
| `helpdesk.ticket` | `service_event_id` | Many2one (`calendar.event`) compute | Service Appointment | No | — | `store=False`, `compute='_compute_service_event_id'`, `@api.depends('service_event_ids')`. Ultimo evento activo por `start`. Gate del doble agendado (D16). |
| `helpdesk.ticket` | `warranty_status` | Selection `[('valid','Under Warranty'),('expired','Out of Warranty'),('unknown','Unknown')]` compute | Warranty Status | No | `unknown` (resultado del compute cuando no hay datos) | `store=True`, `compute='_compute_service_warranty'`, `@api.depends('partner_id','product_id','lot_id')`. Solo informativo (D2). |
| `helpdesk.ticket` | `warranty_expiry_date` | Date compute | Warranty Expiry Date | No | — | `store=True`, mismo compute; vacio si `unknown`. |
| `helpdesk.ticket` | `warranty_delivery_date` | Date compute | Delivery Date | No | — | `store=True`, mismo compute; entrega usada como base del calculo (primera o ultima segun `warranty_start_type`). **Precision (m5)**: si gana el lote (D22, `lot.warranty_expiry_date`), este campo queda **vacio** — el vencimiento no vino de una entrega. |
| `calendar.event` | `service_ticket_id` | Many2one (`helpdesk.ticket`) | Service Ticket | No | — | `copy=False`, `index=True`, `ondelete='set null'`. Lo setea el hook del submit de Citas (D13); el backoffice lo ve readonly. |
| `project.task` | `service_warranty_status` | Selection related (`helpdesk_ticket_id.warranty_status`) | Warranty Status | No | — | `readonly=True`, `store=False`. Solo display en el form FSM. |
| `project.task` | `service_warranty_expiry_date` | Date related (`helpdesk_ticket_id.warranty_expiry_date`) | Warranty Expiry Date | No | — | `readonly=True`, `store=False`. Solo display. |

> `product_id` y `lot_id` del ticket **no se declaran aca**: ya los aporta `helpdesk_stock`
> (`product_id` con `groups="stock.group_stock_user"`). Ver la nota de sudo en
> `_compute_service_warranty`.

## Metodos

### `ProductProduct._get_partner_service_products(self, partner)`

- **Modelo**: `product.product` (`_inherit`), metodo `@api.model`.
- **Proposito**: devolver los productos **entregados** al commercial partner (y a sus contactos) con
  la primera y la ultima fecha de entrega, para armar la lista "sus cerraduras" del formulario y para
  re-validar el `product_id` del POST.
- **Decoradores**: `@api.model`.
- **Logica**:
  1. Si no hay `partner` → `return []`.
  2. `commercial = partner.commercial_partner_id or partner`.
  3. `_read_group` **sudo** sobre `stock.move.line` con dominio
     `[('state','=','done'), ('picking_code','=','outgoing'), ('picking_id.partner_id','child_of', commercial.id), ('picking_id.is_replacement','=',False)]`,
     `groupby=['product_id']`, `aggregates=['date:min','date:max']`. **No** es una copia del nativo
     `_compute_suitable_product_ids`: ese suma tambien productos de **ventas confirmadas sin entregar**,
     inutiles aca porque la garantia necesita una fecha de entrega real (D25). `is_replacement` viene de
     `helpdesk_stock` y se excluye igual que en el nativo (un reemplazo no reinicia la garantia).
  4. Normalizar las fechas: los agregados `date:min`/`date:max` son **Datetime en UTC** → convertir con
     `fields.Datetime.context_timestamp(self, dt).date()` para que una entrega de la noche no se lea
     como el dia siguiente/anterior.
  5. Armar una lista de dicts ordenada por nombre de producto:
     `{'product': product_sudo, 'first_delivery': date_min, 'last_delivery': date_max}` (un item por
     producto — dedupe de unidades, D25).
- **Retorna**: `list[dict]` (vacia si el partner no tiene entregas). Los `product` vienen **en sudo**:
  un usuario portal solo lee `product.product` publicados en el eCommerce, y estas cerraduras pueden no
  estarlo → el template los renderiza en sudo (solo `display_name` y la garantia calculada).
- **Errores**: ninguno propio. El `sudo()` es de **solo lectura y agregada** (el portal no lee
  `stock.move.line`).

### `ProductProduct._get_service_warranty(self, first_delivery=None, last_delivery=None, lot=None)`

- **Modelo**: `product.product` (`_inherit`), metodo de instancia (`ensure_one()`).
- **Proposito**: resolver el estado de garantia **efectivo** de una unidad entregada, sin depender de
  numeros de serie (D20).
- **Decoradores**: ninguno.
- **Logica**:
  1. `self.ensure_one()`; resultado base `{'status': 'unknown', 'expiry_date': False, 'delivery_date': False}`.
  2. Si `lot` y `lot.warranty_expiry_date` → `expiry = lot.warranty_expiry_date` y se salta directo al
     paso 9 (status), **sin** pasar por los pasos 3-8 (prioridad al lote, D22). **Precision
     post-review (m5)**: en esta rama `delivery_date` queda `False` — el vencimiento vino del lote,
     no de una entrega, asi que no hay una "fecha de entrega usada" que reportar; el snapshot del
     ticket (`warranty_delivery_date`) tambien queda vacio en ese caso (documentado en Campos).
  3. `duration, unit, start_type, source = self._get_warranty_info()` (cadena
     variante → plantilla → categoria de `sk_customer_product_warranty`).
  4. Si `not duration or duration <= 0 or not unit` → `return` `unknown` (producto sin garantia
     configurada o con `warranty_tracking` apagado, D23).
  5. Si `start_type == 'manufacture'` (y no hubo lote en el paso 2) → `return` `unknown` (D21): sin
     serie no conocemos la fecha de fabricacion y usar la entrega como proxy informaria **mas**
     garantia de la real.
  6. Base del computo: `last_delivery` si `start_type == 'last_sale'`, si no `first_delivery`.
  7. Si no hay base → `return` `unknown`.
  8. `expiry = base + relativedelta(...)` con el **mismo mapeo** que
     `sk_customer_product_warranty/models/stock_move_line.py` (`day`/`week`/`month`/`year`; unidad
     desconocida → `unknown`), sobre fechas ya normalizadas a `Date` (la conversion de UTC a tz del
     usuario la hace `_get_partner_service_products`).
  9. `status = 'valid'` si `expiry >= fields.Date.context_today(self)`, si no `'expired'`.
- **Retorna**: `dict` con `status` (`valid|expired|unknown`), `expiry_date` (Date o `False`) y
  `delivery_date` (Date o `False`, la entrega usada como base).
- **Errores**: ninguno — un producto mal configurado devuelve `unknown`, nunca excepcion (la garantia
  es informativa, D2/D23).

### `HelpdeskTicket._compute_service_event_id(self)`

- **Proposito**: exponer la cita **vigente** del ticket (la ultima activa) para el portal, el
  backoffice y el gate de doble agendado.
- **Decoradores**: `@api.depends('service_event_ids')`.
- **Logica**: por ticket, `ticket.service_event_id = ticket.service_event_ids.sorted('start')[-1:]`
  (los eventos cancelados estan archivados y no entran al One2many).
- **Retorna**: `None` (campo computado, `store=False`).

### `HelpdeskTicket._compute_service_warranty(self)`

- **Proposito**: congelar el snapshot de garantia del ticket al momento de crearlo (D24).
- **Decoradores**: `@api.depends('partner_id', 'product_id', 'lot_id')`; campos `store=True`.
- **Logica**:
  1. `self_sudo = self.sudo()` — **obligatorio**: `product_id`/`suitable_product_ids` de
     `helpdesk_stock` estan restringidos por `groups="stock.group_stock_user"`, y un usuario de
     helpdesk sin ese grupo (o el portal) dispararia `AccessError` al recomputar.
  2. **Batchear por commercial partner**: agrupar los tickets del recordset por
     `partner_id.commercial_partner_id` y llamar `_get_partner_service_products()` **una vez por
     grupo** (no una vez por ticket): el helper hace un `_read_group` sobre `stock.move.line` y en un
     import/recompute masivo un query por ticket seria un N+1 caro. Guardar el resultado en un dict
     `{commercial_id: {product_id: item}}`.
  3. Por ticket: default `warranty_status = 'unknown'`, `warranty_expiry_date = False`,
     `warranty_delivery_date = False`.
  4. Si no hay `product_id` o no hay `partner_id` → queda `unknown` (caso fallback D8).
  5. Buscar el item del producto en el dict del paso 2; si el producto no aparece (comprado por otro
     canal, entrega borrada) → `unknown`.
  6. `info = product._get_service_warranty(first_delivery, last_delivery, lot=ticket_sudo.lot_id or None)`.
  7. Volcar `info` a los tres campos del ticket.
- **Retorna**: `None` (campos computados stored).
- **Errores**: ninguno propio.

### `HelpdeskTicket._get_service_appointment_url(self)`

- **Proposito**: construir la URL de agendado del ticket (paso 2 del flujo y boton
  "Schedule visit" del portal).
- **Decoradores**: ninguno (`ensure_one()`).
- **Logica**:
  1. Resolver por `env.ref()` (con `raise_if_not_found=True`) el invite `appointment_invite_service`
     (D28) en **sudo** (el portal no lee `appointment.invite`); si falta, el error nativo de `env.ref`
     identifica el dato semilla ausente.
  2. Tomar `invite.redirect_url` — campo **nativo computado** que ya emite `invite_token` **y**
     `filter_appointment_type_ids` (y `filter_staff_user_ids` si hubiera staff preseleccionado).
  3. Devolver `f"{invite.redirect_url}&service_ticket_id={self.id}"` (el `redirect_url` ya trae `?`,
     por eso se concatena con `&`).
- **Retorna**: `str`.
- **Errores**: `ValueError` de `env.ref` si falta el invite (dato semilla borrado).
- **Gotcha (critico)**: **no** armar la URL a mano como
  `/appointment/<type_id>?invite_token=<token>`. Sin `filter_appointment_type_ids`,
  `_fetch_and_check_private_appointment_types` levanta **todos** los tipos activos y
  `appointment.invite._check_appointments_params` exige que coincidan exactamente con los del invite →
  **403 Forbidden** en cuanto existe un segundo tipo activo (y existe: el de instalacion del modulo
  hermano). `redirect_url` es la unica forma correcta de compartir un tipo no publicado.

### `HelpdeskTicket._get_service_photo_attachments(self)` / `HelpdeskTicket._post_service_photos(self, target)`

- **Proposito**: recuperar las fotos que el cliente subio al ticket y **copiarlas** al chatter de otro
  registro (la tarea FSM), sin mover los adjuntos originales.
- **Decoradores**: ninguno (`ensure_one()`).
- **Logica**:
  1. `_get_service_photo_attachments()`: `ir.attachment` (sudo) con
     `res_model='helpdesk.ticket'`, `res_id=self.id`, `mimetype` de imagen. Los adjuntos quedan con esos
     valores porque el `message_post` del POST los **reasigno** desde pendientes (D11).
  2. `_post_service_photos(target)`: copiar cada adjunto con
     `copy({'res_model': 'mail.compose.message', 'res_id': 0})` y `target.sudo().message_post(body=..., attachment_ids=[...])`
     (mismo patron que `website_sale_installation_appointment._post_installation_photos`: `message_post`
     reasigna `res_model`/`res_id` al destino, por eso hay que pasarle **copias pendientes** y no los
     adjuntos originales del ticket, que si no se moverian a la tarea).
  3. Sin fotos → no postea nada.
- **Retorna**: recordset de `ir.attachment` / `None`.
- **Errores**: ninguno propio. `sudo()` justificado: la cita la crea el cliente portal, que no escribe
  en `project.task` ni en `ir.attachment`.

### `CalendarEvent.create(self, vals_list)` (override)

- **Proposito**: cerrar el circuito cita → tarea FSM cuando el evento nace con `service_ticket_id`
  (D14).
- **Decoradores**: `@api.model_create_multi` (firma nativa).
- **Logica**:
  1. `events = super().create(vals_list)`.
  2. Por cada evento con `service_ticket_id`: dentro de `with self.env.cr.savepoint()` + `try`
     (D15) llamar `event._service_generate_fsm_task()`.
  3. Si el bloque falla: `_logger.warning(...)` y nota en el chatter del ticket
     ("no se pudo generar la tarea de service"), **sin** propagar la excepcion (el cliente ya agendo).
  4. `return events`.
- **Retorna**: recordset creado.
- **Errores**: no propaga los de la generacion de la tarea (D15); si el `super()` falla, propaga.

### `CalendarEvent._service_generate_fsm_task(self)`

- **Proposito**: crear la tarea FSM del ticket con la fecha de la cita, reusando el wizard nativo.
- **Decoradores**: ninguno (`ensure_one()`).
- **Logica**:
  1. `ticket = self.service_ticket_id.sudo()`; si no hay ticket → salir.
  2. `project = ticket.team_id.fsm_project_id`; si no hay proyecto FSM → nota en el chatter del ticket
     y salir (no se crea tarea, D15/D29).
  3. Crear el wizard **sudo** `helpdesk.create.fsm.task` con **contexto limpio y explicito**:
     `self.env['helpdesk.create.fsm.task'].sudo().with_context(hsa_from_appointment=True, mail_notify_author=False, mail_create_nolog=False, mail_create_nosubscribe=False, skip_contact_description=False)`
     — o directamente reconstruyendo el contexto desde `self.env.context` sin las claves del `create`
     nativo del evento (`mail_notify_author`, `mail_create_nolog`, `mail_create_nosubscribe`,
     `skip_contact_description`, `allowed_company_ids`): si esas claves se heredan, la tarea nace sin
     followers ni log y con el `allowed_company_ids` del staff de la cita, no del ticket. La clave
     `hsa_from_appointment=True` es la que habilita el override del wizard (D33).
     Valores: `{'helpdesk_ticket_id': ticket.id, 'name': ticket.name, 'project_id': project.id, 'partner_id': (ticket.service_visit_address_id or ticket.partner_id).id}`
     — mismos defaults que el `action_generate_fsm_task` nativo, con la direccion de visita
     priorizada (D7).
  4. `task = wizard.action_generate_task()` (reusa `_generate_task_values()` — ya con nuestro override
     de garantia/direccion — y el `message_post_with_source` nativo que linkea la tarea en el ticket).
  5. `task.write({'planned_date_begin': self.start, 'date_deadline': self.stop, 'user_ids': [(6, 0, self._service_task_assignee_ids())]})`
     — **las dos fechas en el MISMO `write`**: `project_enterprise` tiene el constraint SQL
     `_planned_dates_check (planned_date_begin <= date_deadline)`, y escribirlas por separado puede
     violarlo contra el valor viejo del otro campo. (`planned_date_begin` lo aporta
     `project_enterprise`, dependencia transitiva de `industry_fsm`.) El `user_ids` va en el mismo
     `write` y **siempre explicito** (D35): el `create` de `project.task` deja como asignado al uid
     actual, que en este flujo es el **cliente portal**.
  6. `ticket._post_service_photos(task)` (fotos de la falla al chatter de la tarea).
  7. `ticket.message_post(body=self._service_scheduled_message())` — **precision post-review (M4)**:
     `_service_scheduled_message()` formatea la fecha con `odoo.tools.misc.format_datetime` en la
     **tz del partner del ticket** (`ticket.partner_id.tz`, con fallback a `context.get('tz')` y
     luego `'UTC'`) — nunca `fields.Datetime.to_string()` crudo (eso es UTC, desfasado para el
     cliente) — y agrega un link `<a href="/calendar/view/<access_token>">` al evento (`Markup`,
     sin escapar dos veces el link ya construido).
- **Retorna**: la tarea creada (`project.task`) o `None`.
- **Errores**: los deja subir al `try`/savepoint del `create` (D15).

### `CalendarEvent._service_task_assignee_ids(self)`

- **Proposito**: resolver el **tecnico** al que se asigna la tarea FSM (D35).
- **Decoradores**: ninguno (`ensure_one()`).
- **Logica**: si `appointment_type_id.schedule_based_on != 'users'` → `[]` (en las citas por recursos
  el `user_id` del evento es el `create_uid` del tipo de cita, no el tecnico de la visita); si el
  organizador existe y **no** es `share` (portal/publico) → sus ids; si no → `[]`.
- **Retorna**: lista de ids de `res.users` (0 o 1 elemento).

### `CalendarEvent.write(self, vals)` (override)

- **Proposito**: mantener coherente la tarea FSM cuando la cita se reagenda, se cancela o se repone.
- **Decoradores**: ninguno.
- **Logica**:
  1. Capturar el estado previo de los eventos de service (`active` actual, por `event.id`) antes de
     delegar.
  2. `res = super().write(vals)`.
  3. Si `'active' in vals`, **solo para los eventos cuyo `active` PREVIO difiere del nuevo valor**
     (fix post-review, m4: un `write` redundante — ej. `active=True` sobre un evento que ya estaba
     activo — no debe re-disparar cancelar/reponer):
     - `False` (cancelacion portal via `action_cancel_meeting` → `action_archive`), solo si el evento
       **estaba activo**: por evento, `_service_cancel_tasks()` — tareas FSM del ticket **no
       cerradas** pasan a `state = '1_canceled'` y se postea el motivo en el ticket (D17).
     - `True` (unarchive), solo si el evento **estaba inactivo**: `_service_restore_tasks()` —
       reponer la **ultima** tarea cancelada del ticket (volver a estado abierto) y resincronizar
       fechas (D18).
  4. Si cambiaron `start` o `stop` (y el evento sigue activo): `_service_sync_task_dates()` — escribir
     `planned_date_begin`/`date_deadline` en las tareas FSM abiertas del ticket.
  5. `return res`.
- **Retorna**: `True` (firma nativa).
- **Errores**: ninguno propio; las escrituras a la tarea van en `sudo()` (el cliente portal cancela sin
  permisos sobre `project.task`).

### `CalendarEvent._service_cancel_tasks(self)` / `_service_restore_tasks(self)` / `_service_sync_task_dates(self)`

- **Proposito**: los tres helpers privados que usa el `write` (cancelar, reponer, sincronizar fechas).
- **Decoradores**: ninguno.
- **Logica**:
  - `_service_cancel_tasks`: tareas `service_ticket_id.fsm_task_ids` con `state not in ('1_done','1_canceled')`
    → `state = '1_canceled'` (sudo) + mensaje en el ticket.
  - `_service_restore_tasks`: **guard previo (refinamiento post-analyze)** — si el ticket ya tiene
    **otro** evento activo (`ticket.service_event_ids - self`) **o** alguna tarea FSM **abierta**
    (`state not in ('1_done','1_canceled')`), no se repone nada (evita que un rebooking, D18/D34,
    deje el ticket con 2 citas o 2 tareas simultaneas si el evento viejo se desarchiva por error o a
    mano). Superado el guard: la ultima tarea con `state = '1_canceled'` del ticket vuelve a
    `'01_in_progress'` (estado abierto por defecto de `project.task`) + resync de fechas + mensaje.
  - `_service_sync_task_dates`: por tarea abierta, un unico
    `write({'planned_date_begin': event.start, 'date_deadline': event.stop})` (los dos juntos, por el
    constraint `_planned_dates_check`).
- **Retorna**: `None`.
- **Errores**: ninguno propio.

### `HelpdeskCreateFsmTask._generate_task_values(self)` (override)

- **Proposito**: que la tarea FSM nazca con la **direccion de la visita** y con el estado de garantia
  visible para el tecnico.
- **Decoradores**: ninguno (`ensure_one()` heredado del nativo).
- **Logica**:
  1. `values = super()._generate_task_values()`.
  2. `ticket = self.helpdesk_ticket_id.sudo()` — **sudo obligatorio (fix post-review, M1)**: el
     wizard tambien se abre **a mano** desde el ticket por un agente de helpdesk que puede no
     tener `stock.group_stock_user`; sin sudo, leer `ticket.product_id` en el paso 3 revienta con
     `AccessError` y rompe el boton nativo "Create a Field Service task" (CA22). Es lectura
     puramente informativa (mismo criterio que D24). **Solo si**
     `self.env.context.get('hsa_from_appointment')` y
     `ticket.service_visit_address_id` → `values['partner_id'] = ticket.service_visit_address_id.id`
     (D33). Sin esa clave de contexto (wizard abierto **a mano** por un agente desde el ticket) se
     respeta el `partner_id` que eligio el agente.
  3. Si el ticket tiene datos de service (producto o `warranty_status != 'unknown'`): prefijar
     `values['description']` con un bloque HTML — producto, estado de garantia (label del Selection),
     vencimiento y fecha de entrega usada. `description` es un campo **Html**: el bloque se arma con
     `Markup` (`from markupsafe import Markup`) y **escapando** los valores interpolados
     (`markupsafe.escape(product.display_name)`), porque el nombre del producto puede traer `&`, `<`
     o comillas. Este bloque se agrega **siempre** (no depende del contexto).
  4. `return values`.
- **Retorna**: `dict` de valores de `project.task`.
- **Errores**: ninguno propio.

### `CustomerPortal.portal_service_new(self, **kw)` — GET `/my/service/new`

- **Controller**: `controllers/helpdesk_service_appointment.py`, clase que hereda
  `odoo.addons.portal.controllers.portal.CustomerPortal`.
- **Ruta**: `@route('/my/service/new', type='http', auth='user', website=True, methods=['GET'], sitemap=False)`.
- **Proposito**: renderizar el formulario de service (paso 1).
- **Logica**:
  1. `partner = request.env.user.partner_id`.
  2. `_prepare_service_form_values(partner)` arma: datos de contacto, `address_ids`
     (`commercial_partner_id` + sus `child_ids` con `type in ('invoice','delivery','other')`, fix
     post-review m1) con default (`address_get(['delivery'])` o la principal), `products` =
     `_get_partner_service_products(partner)` **con el badge de garantia por producto**
     (`_get_service_warranty` por item) — los productos vienen **en sudo** y el template solo
     muestra su `display_name` (un usuario portal no lee `product.product` no publicado) —,
     `problem_tags` (los 7 semilla, leidos por `env.ref` en sudo), rango de antiguedad para el
     fallback, limites de fotos y, **si el POST rebota** (fix post-review, M3): los `warnings` **y**
     los `form_values` persistidos en sesion (**solo los valores `str` del POST** — en rutas
     `type='http'` Odoo mergea `request.httprequest.files` en los params, y un `FileStorage` en la
     sesion rompe su serializacion JSON, R1; `service_photos` no es re-populable por seguridad del
     navegador), de donde se derivan `selected_address_id`,
     `selected_product_id` y `selected_problem_tag_id` para que el template rehidrate el formulario
     (radios/selects marcados, textareas con el texto tipeado) sin que el cliente pierda lo cargado.
  3. `request.render('helpdesk_service_appointment.portal_service_new', values)`.
- **Retorna**: respuesta HTTP renderizada.
- **Errores**: ninguno (usuario logueado garantizado por `auth='user'`; un usuario sin entregas ve la
  lista vacia y el fallback, CA20).

### `CustomerPortal.portal_service_new_submit(self, **post)` — POST `/my/service/new`

- **Ruta**: `@route('/my/service/new', type='http', auth='user', website=True, methods=['POST'], sitemap=False)`.
- **Proposito**: validar el formulario, crear el ticket y mandar al cliente a agendar.
- **Logica**:
  1. `partner = request.env.user.partner_id`; `commercial = partner.commercial_partner_id or partner`.
  2. **Validaciones** (si alguna falla: warnings **y** `form_values` del POST — **solo claves con
     valor `str`**, nunca los `FileStorage` de `service_photos` (R1) — a sesion (fix post-review,
     M3, para que el template los rehidrate) + `request.redirect('/my/service/new')`):
     - `problem_tag_id` obligatorio y perteneciente a los 7 tags semilla (D10).
     - `product_id` (si vino): debe estar en `_get_partner_service_products(partner)` — **anti-IDOR**
       (D26); si no esta, se rechaza el POST.
     - `visit_address_id` (si vino): debe estar en `commercial | commercial.child_ids` filtrados por
       `type in ('invoice','delivery','other')` (fix post-review, m1) — anti-IDOR.
     - Fallback: si no hay `product_id`, exigir el texto libre del modelo (`product_note`) y aceptar el
       select de antiguedad.
     - `description` obligatoria (no vacia luego de `strip()`) — **precision post-review (m3)**: esta
       validacion ya estaba en el codigo desde la implementacion inicial pero no se habia declarado
       aca; se documenta ahora, no es un cambio de comportamiento.
  3. Crear el ticket en **sudo**:
     `{'name': <resumen con el problema>, 'team_id': env.ref('...helpdesk_team_service').id, 'partner_id': partner.id, 'tag_ids': [Command.link(tag.id)], 'description': <descripcion + aclaraciones de direccion + (fallback: modelo y antiguedad)>, 'product_id': product.id or False, 'service_visit_address_id': address.id}`.
  4. `_save_service_photos(ticket, request.httprequest.files.getlist('service_photos'))` — patron
     endurecido (D11): tamaño, cantidad y `guess_mimetype` del contenido real; los archivos rechazados
     generan warning pero **no** abortan el ticket; los aceptados se crean como `ir.attachment`
     **pendientes** y el `ticket.message_post(attachment_ids=...)` los reasigna al ticket.
  5. `request.redirect(ticket._get_service_appointment_url(), code=303)` — URL derivada de
     `invite.redirect_url` (D13), nunca armada a mano.
- **Retorna**: redirect 303 a la pagina de Citas.
- **Errores**: `ValidationError`/`UserError` no se muestran crudos: las validaciones de negocio vuelven
  al formulario con warnings.

### `CustomerPortal._save_service_photos(self, ticket, uploads)`

- **Proposito**: guardar las fotos de la falla con los limites endurecidos.
- **Logica**: copia adaptada de `_save_installation_photos`: por upload, saltear vacios; cortar si se
  supero `MAX_PHOTOS` (10); rechazar `len(content) > MAX_PHOTO_SIZE` (10 MB); rechazar si
  `guess_mimetype(content)` no es `image/*`; crear `ir.attachment` **sudo** como **pendiente**
  (`res_model='mail.compose.message'`, `res_id=0`, `datas` en base64); al final, un unico
  `ticket.message_post(body=..., attachment_ids=[ids])` que los **reasigna** al ticket.
- **Retorna**: `list[str]` de warnings de los archivos rechazados.
- **Errores**: ninguno propio (todo se degrada a warning).
- **Gotcha (mayor)**: crear los adjuntos ya con `res_model='helpdesk.ticket'` **pierde las fotos en
  silencio**. `mail.thread._process_attachments_for_post` filtra los `attachment_ids` recibidos y, para
  usuarios **no internos** (nuestro caso: portal), se queda **solo** con los que son pendientes
  (`res_model in ('mail.compose.message','mail.scheduled.message')`) y creados por el mismo `uid`
  (`self.env.uid`); el resto se descarta. **Precision post-review (m6, verificado contra el core)**:
  `sudo()` **no** cambia `env.uid` — solo activa el flag `env.su` y salta los chequeos de ACL (docstring
  de `sudo()`: *"The superuser mode does not change the current user"*,
  `/home/leandro/projects/nexit/19.0/odoo/odoo/orm/models.py:L5952-5955`); `create_uid` se asigna
  siempre desde `self.env.uid` en `_add_missing_default_values`
  (`/home/leandro/projects/nexit/19.0/odoo/odoo/orm/models.py:L4799`), sin excepcion para `su=True`.
  Por eso los adjuntos creados con `ir.attachment.sudo().create(...)` **siguen teniendo `create_uid` =
  el usuario portal** (no OdooBot/superuser — eso solo pasaria con `with_user(SUPERUSER_ID)`, que este
  modulo no usa en este flujo), y el `ticket.message_post(...)` que los reasigna corre con ese
  **mismo** `env.uid`: por eso `create_uid == env.uid` se cumple. Lo que hay que respetar es el estado
  **pendiente** (`res_model`/`res_id`), no el usuario.

### `AppointmentController._get_extra_calendar_event_params(self, **kwargs)` (override)

- **Controller**: `controllers/appointment.py`, clase que hereda
  `odoo.addons.appointment.controllers.appointment.AppointmentController` (mismo patron que el
  precedente `appointment_hr_recruitment`).
- **Proposito**: materializar el vinculo cita ↔ ticket en el `create` del `calendar.event` (D13).
- **Logica**:
  1. `res = super()._get_extra_calendar_event_params(**kwargs)`.
  2. `ticket_id = int(kwargs.get('service_ticket_id'))` con guard de conversion; si no vino o no es
     entero → `return res` (no-op).
  3. `ticket_sudo = request.env['helpdesk.ticket'].sudo().browse(ticket_id).exists()`; si no existe →
     `return res`.
  4. **Anti-IDOR**: el commercial partner del ticket debe coincidir con el del usuario logueado, salvo
     que el usuario sea interno (`not request.env.user.share`) → si no, `return res`.
  5. **Anti-doble-agendado** (D16): si `ticket_sudo.service_event_id` → `return res`.
  6. `res['service_ticket_id'] = ticket_sudo.id`; `return res`.
- **Retorna**: `dict` que se mergea en el `create` del `calendar.event`.
- **Errores**: ninguno — un param invalido se **ignora** (la cita se crea sin tarea FSM, inocuo).

### `AppointmentCalendarController.appointment_cancel(self, access_token, partner_id=False, **kwargs)` (override)

- **Controller**: `controllers/appointment.py`, clase que hereda
  `odoo.addons.appointment.controllers.calendar.AppointmentCalendarController`.
- **Proposito**: que el reagendado del cliente **despues de cancelar** conserve el vinculo con su
  ticket (D34). El nativo redirige a `invite.redirect_url + '&state=cancel'`, que **no** lleva
  `service_ticket_id`: si el cliente reserva de nuevo desde esa pagina, la cita nace huerfana.
- **Decoradores**: `@route()` **desnudo** (sin argumentos) — patron nativo para overridear un metodo
  que ya tiene ruta registrada por la clase padre sin redeclarar el path (mismo patron que
  `AppointmentCalendarController.view_meeting` en
  `enterprise/appointment/controllers/calendar.py:L25-26`).
- **Logica**:
  1. Resolver el evento por `access_token` **antes** de delegar (el nativo lo archiva) y guardar
     `ticket_id = event.sudo().service_ticket_id.id`.
  2. `response = super().appointment_cancel(access_token, partner_id=partner_id, **kwargs)`.
  3. Si no habia `ticket_id` → `return response` (no-op para citas que no son de service).
  4. **Guard de tipo/forma antes de tocar la respuesta**: si no es un redirect real —
     `getattr(response, 'status_code', None)` no esta en `[300, 400)` o no tiene `headers`/`Location`
     (ej. `request.not_found()`, un `HTTPException` sin `Location`) — `return response` **intacta**.
  5. Si es un redirect valido y la URL **no** trae ya `service_ticket_id`: parsear el `Location` con
     `urllib.parse.urlsplit`, decodificar la query con `parse_qsl`, agregar `service_ticket_id`,
     re-codificar con `werkzeug.urls.url_encode` y reconstruir la URL con `urlunsplit` — **nunca**
     concatenar `&service_ticket_id=...` a ciegas al string del `Location` (podria haber `#fragment`
     o un query ya presente mal formado). Si el nativo devolvio el redirect de "no se puede cancelar"
     (`state=no_time_left`, ver edge cases) tambien es inocuo enriquecerlo igual.
  6. `return response` con `Location` actualizado (o intacto si el paso 4/5 no aplico).
- **Retorna**: la respuesta del nativo, con el `Location` enriquecido.
- **Errores**: ninguno propio; si algo no matchea (tipo de respuesta, ausencia de `Location`), se
  devuelve la respuesta nativa intacta (degradacion a comportamiento actual: cita huerfana, no error).
- **Nota**: el guard anti-doble-agendado no molesta en este flujo porque el evento cancelado quedo
  **archivado** y `service_event_ids` (One2many) solo ve activos → `service_event_id` vuelve a estar
  vacio y el ticket puede recibir la cita nueva.

## Vistas

### Backoffice

#### `helpdesk_ticket_view_form` (inherit de `helpdesk.helpdesk_ticket_view_form`)
- Grupo **Service** en el sheet, **antes del `<notebook>`** (ancla unica y estable; **no** dentro
  de `page[@name='extra_info']`, que solo se renderiza con `display_extra_info` — en mono-compania
  sin flags de returns/repairs esa pestana no existe y el grupo quedaria invisible):
  `service_visit_address_id`, `service_event_id` (readonly, con link al evento),
  `warranty_status` (widget `badge`), `warranty_expiry_date` (readonly),
  `warranty_delivery_date` (readonly).
- Decoraciones: `warranty_status` en verde (`valid`), rojo (`expired`), gris/muted (`unknown`).
- Campos de garantia `invisible` cuando `warranty_status == 'unknown'` (solo esa condicion: la
  expresion NO debe referenciar `product_id`, campo con `groups` que el postprocess elimina del
  arch para usuarios sin `stock.group_stock_user` y romperia la evaluacion client-side).

#### `helpdesk_tickets_view_tree` (inherit de `helpdesk.helpdesk_tickets_view_tree`)
- Columna `warranty_status` (opcional, `optional="hide"`) para triage rapido.

#### `product_template_form_view_inherit_warranty` / `product_variant_form_view_inherit_warranty` (inherit de las vistas de `sk_customer_product_warranty`, archivo `views/product_views.xml`)
- Relajan los `invisible="tracking != 'serial'"` del grupo **Warranty Information** (y sus campos
  internos) a condiciones por `warranty_tracking`: sin este inherit, la config de plazos de
  garantia es **invisible por UI** para productos sin tracking por serie — que es exactamente el
  caso de Sunra (D21/D25: la garantia se calcula desde entregas, sin series). No se toca el modulo
  vendorizado (politica del repo: overrides en modulo propio).

#### `project_task_view_form` (inherit de `project.view_task_form2`)
- `service_warranty_status` y `service_warranty_expiry_date` readonly en el bloque de datos de la
  tarea, `invisible` si no hay `helpdesk_ticket_id`.

### Portal (templates)

#### `portal_service_new` (template nuevo, extiende `portal.portal_layout`)
- Copy equivalente al JotForm ("Agendar service", "Contanos que esta pasando…").
- Bloque **Tus datos**: nombre, telefono, email del partner + link a `/my/account`.
- Bloque **Direccion de la visita**: `<select>` de direcciones + textarea "Aclaraciones".
- Bloque **Tu cerradura**: radios/select con las cerraduras entregadas y su **badge de garantia**
  (En garantia / Fuera de garantia / Sin datos de garantia); ultima opcion
  "No esta en la lista / No lo se" que despliega el texto libre del modelo + select de antiguedad.
- Bloque **El problema**: select obligatorio (7 tags) + textarea de descripcion.
- Bloque **Fotos** (opcional): `<input type="file" multiple accept="image/*">` con el limite visible
  (hasta 10 fotos, 10 MB cada una).
- Zona de warnings (los del POST rebotado) y boton "Continue to schedule".

#### `portal_helpdesk_ticket` (inherit de `helpdesk.portal_helpdesk_ticket`)
- Boton **"New Service Request"** → `/my/service/new` en la cabecera de `/my/tickets`.

#### `tickets_followup` (inherit de `helpdesk.tickets_followup`)
- Bloque **Service** en el detalle del ticket: producto (o el modelo declarado en texto libre),
  estado de garantia con vencimiento, y la cita: fecha/hora + link a `/calendar/view/<access_token>`
  (gestionar/cancelar) si hay evento activo, o boton **"Schedule visit"** (a
  `_get_service_appointment_url()`) si no hay.

### Datos semilla (`data/helpdesk_service_appointment_data.xml`, `noupdate="1"`)

| XML ID | Modelo | Contenido |
|--------|--------|-----------|
| `helpdesk_team_service` | `helpdesk.team` | Team "Service", `use_fsm=True`, **`privacy_visibility='portal'`** explicito (lo exige la record rule portal de helpdesk — D27; el default del core ya es `portal`, pero se fija para que un cambio de default no rompa el portal), etapas nativas (no se crean etapas propias). |
| `appointment_type_service` | `appointment.type` | "Service Visit", `schedule_based_on='users'`, `appointment_duration=2.0`, `is_published=False`, **`staff_user_ids` vaciado** (`eval="[(6, 0, [])]"`) para neutralizar el `default=lambda self: self.env.user` (si no, el usuario que instala el modulo queda como tecnico). **Los `slot_ids` NO se pueden omitir**: el `_compute_category` del core auto-crea los slots default L-V 9-12 / 14-17 — con staff vacio el tipo igual no ofrece horarios (inerte hasta la config funcional, D29). |
| `appointment_invite_service` | `appointment.invite` | `short_code='service'`, `appointment_type_ids` = el tipo anterior; su `access_token` + `redirect_url` habilitan el tipo sin publicarlo. **Es el dato del que sale la URL de agendado** (D13). |
| `helpdesk_tag_not_opening`, `helpdesk_tag_battery_drain`, `helpdesk_tag_not_closing`, `helpdesk_tag_battery_corrosion`, `helpdesk_tag_connectivity`, `helpdesk_tag_locked_out`, `helpdesk_tag_other` | `helpdesk.tag` | Los 7 tipos de problema del JotForm. `helpdesk.tag` tiene **`UNIQUE(name)`**: los nombres se califican con el dominio para no chocar con tags preexistentes ni con los que cree el equipo — "Lock does not open / unresponsive", "Lock battery drains fast", "Lock does not close properly / jams", "Lock battery corrosion", "Lock App/WiFi connection issue", "Locked in / locked out", "Lock issue - Other". |

## Seguridad

**Sin ACLs ni record rules nuevas** (D27), y esto es una decision explicita, no un olvido:

- El modulo **no define modelos nuevos** → no hay tabla que necesite `ir.model.access.csv`. Todos los
  campos se agregan por `_inherit` sobre modelos que ya traen sus ACLs de `helpdesk`, `helpdesk_stock`,
  `helpdesk_fsm`, `appointment`, `project` y `stock`.
- El acceso del cliente a **su** ticket lo resuelve la **record rule nativa** de helpdesk
  (`helpdesk_portal_ticket_rule`) mas el `_document_check_access` del controller nativo
  (`/my/ticket/<id>`), que ya devuelve el registro en sudo para el template. Esa regla pide
  `team_privacy_visibility = 'portal'` **y** que el partner sea follower: lo primero lo garantiza la
  semilla del team (`privacy_visibility='portal'`), lo segundo el `create` nativo de `helpdesk.ticket`,
  que suscribe al `partner_id` recibido ("make customer follower"). Si alguno de los dos falta, el
  cliente crearia el ticket y despues no podria verlo.
- No se crean grupos: quien atiende service es un usuario de helpdesk. Requisito funcional (README):
  esos usuarios necesitan `stock.group_stock_user` porque el `product_id` del ticket esta restringido
  por ese grupo en `helpdesk_stock`.

**Sudos usados y por que** (todos de alcance acotado):

| Donde | Por que |
|-------|---------|
| `_get_partner_service_products` (`_read_group` sobre `stock.move.line`) | El portal no lee movimientos de stock; se leen **solo agregados** (producto + min/max fecha) del propio commercial partner. |
| Create del ticket en el POST | Mismo criterio que el form nativo de `website_helpdesk`: el portal no crea `helpdesk.ticket`. Se re-validan producto y direccion contra los datos del partner **antes** de crear (anti-IDOR). |
| `_save_service_photos` / `_post_service_photos` (`ir.attachment`) | El cliente no crea adjuntos; ya se validaron tipo real, tamaño y cantidad. Se crean **pendientes** y los reasigna `message_post` (D11), no se elude el filtro de adjuntos de portal. |
| `_get_service_appointment_url` (`appointment.invite`) | El portal no lee `appointment.invite`; se lee **un solo** registro semilla para tomar su `redirect_url`. |
| Wizard FSM y escrituras a `project.task` en `calendar.event` | El evento nace sudo en el controller nativo de Citas; el cliente no tiene permisos sobre `project.task`. |
| `_compute_service_warranty` (`ticket.sudo()`) | `product_id`/`suitable_product_ids` tienen `groups="stock.group_stock_user"`: sin sudo, recomputar el ticket con un usuario sin ese grupo lanzaria `AccessError`. |

**Anti-IDOR**: `service_ticket_id` (ticket de otro partner → se ignora), `product_id` (debe estar en
las entregas del partner), `visit_address_id` (debe pertenecer al commercial partner).
**Fotos**: `guess_mimetype` del contenido real + limites de cantidad/tamaño.

## Reglas de negocio

1. **RB01**: Solo un usuario **logueado** puede pedir service (`auth='user'`); no hay endpoint publico.
2. **RB02**: El **tipo de problema** es obligatorio y debe ser uno de los 7 tags semilla.
3. **RB03**: Si el cliente elige un producto, este debe estar entre los **entregados** a su commercial
   partner; si no, el POST se rechaza (no se crea ticket).
4. **RB04**: Si el cliente no encuentra su producto, el ticket se crea **sin** `product_id`, con el
   modelo en texto libre y la antiguedad declarada en la descripcion, y `warranty_status = unknown`.
5. **RB05**: La direccion de la visita debe pertenecer al commercial partner del usuario y ser de
   `type in ('invoice','delivery','other')` (fix post-review, m1: se excluyen contactos-persona); se
   guarda en `service_visit_address_id` y es el `partner_id` de la tarea FSM.
6. **RB06**: Las fotos son opcionales; se aceptan hasta **10** por ticket, de hasta **10 MB**, y solo
   si el **contenido real** es una imagen. Lo rechazado avisa al cliente sin abortar el pedido. Las
   aceptadas quedan efectivamente adjuntas al ticket (adjuntos pendientes + `message_post`, D11).
7. **RB07**: Tras crear el ticket, el cliente **siempre** va a agendar (redirect 303 a la URL derivada
   de `invite.redirect_url`), sin paso de pago.
8. **RB08**: La garantia es **informativa**: nunca bloquea el agendado ni cambia el flujo (D2).
9. **RB09**: `warranty_status = valid` si la fecha de vencimiento calculada es **hoy o futura**;
   `expired` si es pasada; `unknown` si no hay datos suficientes.
10. **RB10**: Base del calculo: `first_sale` → **primera** entrega; `last_sale` → **ultima** entrega;
    `manufacture` sin lote → **`unknown`** (no se inventa una base, D21). Si existiese un lote con
    `warranty_expiry_date`, esa fecha manda sobre todo lo demas.
11. **RB11**: El snapshot de garantia del ticket se **congela** (compute stored): reconfigurar la
    garantia del producto despues no reescribe tickets viejos (salvo recompute explicito).
12. **RB12**: Un ticket con **evento activo** no puede agendar otra cita: el `service_ticket_id` se
    ignora y la cita queda sin tarea FSM ni vinculo.
13. **RB13**: Un `service_ticket_id` de **otro** partner (o inexistente) se ignora; solo un usuario
    interno puede agendar en nombre de un ticket ajeno.
14. **RB14**: La tarea FSM se crea en el `fsm_project_id` del team del ticket, con
    `planned_date_begin`/`date_deadline` = `start`/`stop` de la cita.
15. **RB15**: Si el team **no** tiene `fsm_project_id`, la cita se crea igual y queda nota en el ticket
    (no se genera tarea). El cliente nunca ve un error al agendar.
16. **RB16**: La descripcion de la tarea FSM incluye el bloque de garantia (estado, vencimiento, fecha
    de entrega) y las fotos del ticket se copian a su chatter.
17. **RB17**: Cancelar la cita desde el portal (archivar el evento) cancela (`1_canceled`) las tareas
    FSM **abiertas** del ticket y habilita volver a agendar.
18. **RB18**: Desarchivar la cita repone la **ultima** tarea cancelada del ticket y resincroniza fechas.
19. **RB19**: Cambiar `start`/`stop` de la cita sincroniza las fechas de las tareas FSM abiertas.
20. **RB20**: Mover/reprogramar la **tarea** no modifica la cita (sincronizacion de una sola via).
21. **RB21**: El tipo de cita de service **no** aparece en `/appointment` publico
    (`is_published=False`); es accesible **solo** por el link del invite semilla, que debe llevar
    `invite_token` **y** `filter_appointment_type_ids` (por eso se usa `invite.redirect_url`; sin el
    filtro, el nativo responde **403**).
22. **RB22**: Si el cliente cancela y vuelve a reservar desde la pagina a la que lo devuelve el nativo,
    la cita nueva **sigue vinculada** al mismo ticket (se reinyecta `service_ticket_id` en el redirect
    de cancelacion) y genera una tarea FSM nueva.
23. **RB23**: El wizard FSM abierto **a mano** desde el ticket conserva el cliente elegido por el
    agente (el override de `partner_id` solo aplica al flujo automatico, D33); el bloque de garantia en
    la descripcion se agrega en ambos casos.

## Edge cases

- **Usuario sin entregas** (comprado por otro canal, o cliente nuevo): la lista sale vacia; el fallback
  de texto libre permite igual crear el ticket y agendar (`warranty_status = unknown`).
- **Varias unidades del mismo producto**: una sola fila (dedupe por producto). Sin series no hay forma
  de distinguir unidades; con `lot_id` futuro la logica ya prioriza el lote.
- **Producto con `warranty_tracking` apagado** o sin duracion (incluido el bug conocido de propagacion
  a variantes existentes de `sk_customer_product_warranty`): badge "Sin datos de garantia",
  `unknown`, flujo intacto.
- **`warranty_start_type = manufacture` sin lote**: `unknown` — no se usa la entrega como proxy porque
  informaria mas garantia de la real (D21, `[ASUNCION]`).
- **Unidad de garantia desconocida** (dato corrupto en la config): `unknown`, sin excepcion.
- **Entrega registrada de noche** (Datetime UTC cerca del limite del dia): la fecha se normaliza a la tz
  del usuario antes de calcular, para no correr un dia el vencimiento.
- **Ticket sin producto** (fallback): sin badge, sin bloque de garantia en la tarea, sin `lot_id`.
- **Doble agendado**: rechazado (RB12); la cita creada queda sin vinculo — inocua, visible en Calendar.
- **`service_ticket_id` manipulado** (otro partner, inexistente, no entero): se ignora silenciosamente.
- **Team sin `fsm_project_id`**: cita creada, tarea no; nota en el chatter del ticket (RB15).
- **URL de agendado sin `filter_appointment_type_ids`**: **403 Forbidden** en cuanto hay 2+ tipos de
  cita activos (siempre, por el tipo de instalacion). Por eso la URL se deriva de `invite.redirect_url`
  y no se arma a mano (D13). Es el edge case que mas facil se cuela si alguien "simplifica" la URL.
- **Tipo de cita recien instalado**: trae los **slots default** del core (L-V 9-12 / 14-17) y
  `staff_user_ids` vacio → la pagina de Citas **no ofrece horarios** hasta que el funcional asigne
  tecnicos (y ajuste los horarios). Estado inerte deseado, documentado en el README (D29).
- **Cancelacion dentro de la ventana `min_cancellation_hours`** (default **1 h** en el tipo de cita): el
  nativo **no** deja cancelar y redirige con `state=no_time_left`. Consecuencia: el ticket sigue con su
  evento activo y el portal **no** ofrece "Schedule visit" — para reprogramar sobre la hora hay que
  llamar al backoffice (que mueve la cita/tarea desde el backend). Se documenta en el README.
- **Reagendado del cliente tras cancelar**: la cita nueva conserva el vinculo al ticket (RB22) y genera
  otra tarea FSM; la tarea de la cita cancelada queda en `1_canceled` (historial).
- **Desarchivo tardio de un evento cancelado ya reemplazado**: si el evento viejo (cancelado tras un
  rebooking, o por error) se desarchiva cuando el ticket **ya** tiene otro evento activo u otra tarea
  FSM abierta, `_service_restore_tasks` **no** repone la tarea vieja (guard, ver metodo): evita que el
  ticket termine con 2 citas o 2 tareas simultaneas.
- **Colision de nombre de tag**: `helpdesk.tag` tiene `UNIQUE(name)`; si el equipo ya creo un tag con el
  mismo nombre, la instalacion fallaria → los nombres semilla estan calificados ("Lock ...") para
  minimizar el riesgo (D28).
- **Fotos**: >10 archivos, archivo >10 MB, PDF renombrado a `.jpg` → rechazados con aviso; el resto se
  guarda y el ticket se crea igual.
- **Datos semilla borrados** (team/tipo/invite/tags): `env.ref` falla con el XML ID en el mensaje →
  error claro en vez de comportamiento silencioso.
- **`calendar.booking` / GC de reservas**: no aplica — sin pago no hay booking, el evento nace directo
  del submit.
- **Multi-compania**: fuera de alcance (D30) — se asume una sola compania.
- **Borrado del ticket**: `service_ticket_id` queda en `False` (`ondelete='set null'`); la cita y la
  tarea sobreviven sin vinculo.

## Criterios de aceptacion

- [ ] **CA01**: Un usuario portal abre `/my/service/new` y ve: resumen de sus datos de contacto con link
  a `/my/account`, selector de direccion de visita (default la principal/entrega) + aclaraciones, lista
  de sus cerraduras entregadas, select obligatorio de problema con los 7 tipos, textarea de descripcion
  y upload opcional de fotos.
- [ ] **CA02**: Producto entregado **en garantia** (config vigente + entrega dentro del plazo) → badge
  "En garantia" y, al crear el ticket, `warranty_status = valid` con `warranty_expiry_date` y
  `warranty_delivery_date` correctas segun `warranty_start_type`.
- [ ] **CA03**: Producto con garantia **vencida** → badge "Fuera de garantia" y `warranty_status = expired`;
  el agendado sigue disponible y **no** aparece ningun paso de pago.
- [ ] **CA04**: Producto sin `warranty_tracking` o sin duracion → badge "Sin datos de garantia" y
  `warranty_status = unknown`, sin excepciones.
- [ ] **CA05**: POST valido → ticket creado en el team Service con `partner_id` del usuario, el tag del
  problema, la descripcion (incluidas las aclaraciones de direccion), `product_id`,
  `service_visit_address_id`, las fotos **efectivamente adjuntas** en el chatter (no descartadas por el
  filtro de adjuntos de portal), y redirect **303** a la URL derivada de `invite.redirect_url` (con
  `invite_token`, `filter_appointment_type_ids` y `service_ticket_id`). La pagina de Citas responde
  **200** (no 403) aunque existan otros tipos de cita activos, y el cliente ve el ticket en
  `/my/tickets` (es follower).
- [ ] **CA06**: Con el fallback "No esta en la lista / No lo se" → ticket sin `product_id`, con el
  modelo en texto libre y la antiguedad en la descripcion, `warranty_status = unknown`, y el mismo
  redirect a agendar.
- [ ] **CA07**: POST con un `product_id` que **no** esta entre las entregas del partner (param
  manipulado) → se rechaza, no se crea ticket (anti-IDOR).
- [ ] **CA08**: POST con una `visit_address_id` que no pertenece al commercial partner → se rechaza
  (anti-IDOR).
- [ ] **CA09**: Fotos: mas de 10 archivos, un archivo >10 MB, o un no-imagen disfrazado (mimetype real
  distinto de `image/*`) → se rechazan con aviso y el ticket se crea con las validas, que quedan
  visibles como adjuntos del ticket para el usuario portal **y** para el backoffice.
- [ ] **CA10**: Al confirmar la cita en la pagina nativa de Citas → `calendar.event` con
  `service_ticket_id` seteado y **tarea FSM** creada en `team.fsm_project_id`, con `partner_id` = la
  direccion de visita y `planned_date_begin`/`date_deadline` = `start`/`stop` del evento.
- [ ] **CA11**: La descripcion de esa tarea FSM incluye el bloque de garantia (estado, vencimiento,
  fecha de entrega) y las fotos del ticket quedan en el chatter de la tarea.
- [ ] **CA12**: El detalle del ticket en el portal muestra el bloque Service (producto o modelo
  declarado, garantia, y la cita con link a `/calendar/view/<token>`); si no hay evento activo, muestra
  el boton "Schedule visit".
- [ ] **CA13**: Un `service_ticket_id` inexistente, de otro partner, o de un ticket que **ya** tiene
  evento activo → se ignora: la cita se crea sin tarea FSM y sin vinculo, sin error para el cliente.
- [ ] **CA14**: Cancelar la cita desde el portal (evento archivado) → las tareas FSM abiertas del ticket
  quedan en `1_canceled`, hay mensaje en el ticket y el portal vuelve a ofrecer "Schedule visit".
- [ ] **CA15**: Reagendar la cita (cambio de `start`/`stop`) → `planned_date_begin`/`date_deadline` de la
  tarea FSM abierta se sincronizan.
- [ ] **CA16**: Desarchivar la cita → se repone la ultima tarea cancelada del ticket (estado abierto) con
  las fechas del evento.
- [ ] **CA17**: Backoffice: el form del ticket muestra direccion de visita, cita, y garantia con
  decoracion por estado; el form de la tarea FSM muestra la garantia readonly.
- [ ] **CA18**: `/my/tickets` tiene el boton "New Service Request" que lleva a `/my/service/new`.
- [ ] **CA19**: Tras instalar el modulo existen: team "Service" con `use_fsm=True` y
  `privacy_visibility='portal'`, tipo de cita "Service Visit" (2 h, `users`, `is_published=False`,
  **sin staff asignado**), `appointment.invite` con `short_code='service'` y los 7 `helpdesk.tag` con
  nombres calificados. El tipo **no** aparece en `/appointment` publico; su `redirect_url` abre la
  pagina de agendado sin 403; y mientras no haya staff asignado **no ofrece horarios** (los slots
  default L-V 9-12 / 14-17 que crea el core quedan a la espera de la config funcional).
- [ ] **CA20**: Usuario portal **sin entregas** → lista vacia, el fallback de texto libre permite crear
  el ticket y agendar igual.
- [ ] **CA21**: Cliente que cancela su cita y reserva de nuevo desde la pagina a la que lo devuelve el
  portal → la cita nueva queda **vinculada al mismo ticket** (`service_ticket_id`) y genera una tarea
  FSM nueva; la tarea de la cita cancelada queda en `1_canceled`.
- [ ] **CA22**: Un agente que abre **a mano** "Create a Field Service task" desde el ticket y elige otro
  cliente → la tarea se crea con **el cliente que eligio el agente** (no se pisa con la direccion de
  visita), pero **si** incluye el bloque de garantia en la descripcion.

## Referencias al core

> Anclajes `path:L#` verificados sobre el checkout de v19 (core/enterprise en
> `/home/leandro/projects/nexit/19.0`, fuera del root del enjambre → rutas absolutas). Los anclajes a
> modulos del propio repo van relativos al repo de addons.

| Que | Anclaje (`path:L#`) | Por que importa |
|-----|---------------------|-----------------|
| Hook de params extra del submit de Citas | `/home/leandro/projects/nexit/19.0/enterprise/appointment/controllers/appointment.py:L869` | `_get_extra_calendar_event_params(**kwargs)` devuelve `{}`; es el punto de inyeccion de `service_ticket_id` (D13). |
| Merge de esos params en el `create` del evento | `/home/leandro/projects/nexit/19.0/enterprise/appointment/controllers/appointment.py:L885` | `calendar.event` se crea sudo con `**(extra_calendar_event_params or {})` (L885-897) → el campo llega al `create` del modelo. |
| Validacion nativa del `invite_token` | `/home/leandro/projects/nexit/19.0/enterprise/appointment/controllers/appointment.py:L858` | El invite se resuelve por `access_token` (L858-861) → habilita un tipo **no publicado** (D28). |
| Redirect post-submit | `/home/leandro/projects/nexit/19.0/enterprise/appointment/controllers/appointment.py:L898` | `/calendar/view/<access_token>` — la URL que el portal del ticket ofrece para gestionar/cancelar la cita. |
| **URL correcta de agendado (fix del 403)** | `/home/leandro/projects/nexit/19.0/enterprise/appointment/models/appointment_invite.py:L102` | `redirect_url` (campo computado) — de aca sale la URL; el compute esta en L290-310 y los params en `_get_redirect_url_parameters` (L356), que emite `filter_appointment_type_ids`. |
| **Causa del 403** (validacion del invite) | `/home/leandro/projects/nexit/19.0/enterprise/appointment/models/appointment_invite.py:L375` | `_check_appointments_params` (L375-386): si los tipos del invite no coinciden **exactamente** con `filter_appointment_type_ids`, devuelve False → Forbidden. |
| Quien levanta "todos los tipos activos" | `/home/leandro/projects/nexit/19.0/enterprise/appointment/controllers/appointment.py:L464` | `_fetch_and_check_private_appointment_types`: sin `filter_appointment_type_ids` compara el invite contra **todos** los tipos activos → falla con 2+ tipos. |
| Filtro de adjuntos en `message_post` | `/home/leandro/projects/nexit/19.0/odoo/addons/mail/models/mail_thread.py:L2416` | `_process_attachments_for_post` (L2416-2423): para usuarios no internos solo sobreviven los adjuntos **pendientes** (`mail.compose.message`) creados por el mismo `uid` → obliga al patron pendiente + reasignacion (D11). |
| Controller de cancelacion (a heredar) | `/home/leandro/projects/nexit/19.0/enterprise/appointment/controllers/calendar.py:L19` | `class AppointmentCalendarController(CalendarController)` — clase del override de `appointment_cancel` (def en L133). |
| Redirect de cancelacion sin nuestro param | `/home/leandro/projects/nexit/19.0/enterprise/appointment/controllers/calendar.py:L146` | `redirect_url = appointment_invite.redirect_url + '&state=cancel'` — no lleva `service_ticket_id`: de aca sale la cita huerfana que arregla D34. |
| Ventana de cancelacion | `/home/leandro/projects/nexit/19.0/enterprise/appointment/controllers/calendar.py:L157` | `_get_prevent_cancel_status` → `'no_time_left'` (L163-164) si falta menos que `min_cancellation_hours` (default **1.0**, `/home/leandro/projects/nexit/19.0/enterprise/appointment/models/appointment_type.py:L159`). |
| Auto-creacion de slots default | `/home/leandro/projects/nexit/19.0/enterprise/appointment/models/appointment_type.py:L296` | `_compute_category` crea `_get_default_slots()` si el tipo no tiene slots (L296-300); el rango L-V 9-12 / 14-17 esta en `_get_default_range_slots` (L647-660). Por eso la semilla **no puede** nacer sin slots (D29). |
| Default de staff del tipo de cita | `/home/leandro/projects/nexit/19.0/enterprise/appointment/models/appointment_type.py:L180` | `staff_user_ids` con `default=lambda self: self.env.user` (L180-185) → la semilla lo vacia con `eval="[(6, 0, [])]"` (D28). |
| Precedente exacto del override del hook | `/home/leandro/projects/nexit/19.0/enterprise/appointment_hr_recruitment/controllers/appointment.py:L7` | `class ...(AppointmentController)` + `super()` + `sudo().search` de un param custom: el patron a copiar (L7-17). |
| Params custom sobreviven slots → info | `/home/leandro/projects/nexit/19.0/enterprise/appointment/static/src/interactions/appointment_select_appointment_slot.js:L280` | `commonUrlParams = new URLSearchParams(window.location.search)` → todo query param de la pagina de slots viaja al paso `/info`. |
| Params custom sobreviven info → submit | `/home/leandro/projects/nexit/19.0/enterprise/appointment/views/appointment_templates_registration.xml:L30` | El `<form action=".../submit?#{keep_query('*')}">` reenvia `service_ticket_id` al submit. |
| Ruta de la pagina de agendado | `/home/leandro/projects/nexit/19.0/enterprise/appointment/controllers/appointment.py:L185` | `/appointment/<int:appointment_type_id>` — destino del redirect 303 del POST. |
| Cancelacion desde el portal = archive | `/home/leandro/projects/nexit/19.0/enterprise/appointment/models/calendar_event.py:L424` | `action_cancel_meeting()` termina en `action_archive()` (L424-438) → la cancelacion se detecta por `active=False` en `write` (D17). |
| `access_token` del evento | `/home/leandro/projects/nexit/19.0/enterprise/appointment/models/calendar_event.py:L80` | Token que arma el link `/calendar/view/<token>` del portal. |
| Wizard FSM: valores de la tarea | `/home/leandro/projects/nexit/19.0/enterprise/helpdesk_fsm/wizard/create_task.py:L29` | `_generate_task_values()` — metodo a heredar para inyectar direccion de visita + garantia. |
| Wizard FSM: creacion + mensaje nativo | `/home/leandro/projects/nexit/19.0/enterprise/helpdesk_fsm/wizard/create_task.py:L39` | `action_generate_task()` crea la tarea y postea el link en el ticket: se reusa tal cual (D14). |
| Defaults nativos del wizard | `/home/leandro/projects/nexit/19.0/enterprise/helpdesk_fsm/models/helpdesk_ticket.py:L32` | `action_generate_fsm_task()` (L32-51) muestra los defaults correctos (`name`, `partner_id`, `project_id` sudo) a replicar al instanciar el wizard. |
| Proyecto FSM del team | `/home/leandro/projects/nexit/19.0/enterprise/helpdesk_fsm/models/helpdesk_team.py:L10` | `fsm_project_id` (compute store, editable) — de donde sale el `project_id` de la tarea. |
| Tareas FSM del ticket | `/home/leandro/projects/nexit/19.0/enterprise/helpdesk_fsm/models/helpdesk_ticket.py:L11` | `fsm_task_ids` (o2m por `helpdesk_ticket_id`, dominio `is_fsm`) — sobre el que operan cancelacion/sync. |
| `use_fsm` del team | `/home/leandro/projects/nexit/19.0/enterprise/helpdesk/models/helpdesk_team.py:L100` | Flag que habilita FSM en el team; lo enciende la semilla del team Service. |
| Producto/lote del ticket (ya existen) | `/home/leandro/projects/nexit/19.0/enterprise/helpdesk_stock/models/helpdesk_ticket.py:L12` | `product_id` (L12, con `groups="stock.group_stock_user"`), `suitable_product_ids` (L17, **idem grupo**), `has_partner_picking` (L23, **idem grupo**), `lot_id` (L25, **sin** esa restriccion) (L12-27): **no redefinir**. **Precision (m7)**: solo `product_id`/`suitable_product_ids`/`has_partner_picking` llevan `groups=`; `lot_id` (y `tracking`, related de `product_id.tracking`) **no** — de ahi que el sudo del compute se justifique especificamente por `product_id`. |
| Criterio nativo de "productos del cliente" | `/home/leandro/projects/nexit/19.0/enterprise/helpdesk_stock/models/helpdesk_ticket.py:L31` | `_compute_suitable_product_ids` (L31-81): ventas confirmadas + entregas `outgoing` `done` del commercial partner — criterio que espeja `_get_partner_service_products` (D25). |
| Hook de valores del portal del ticket | `/home/leandro/projects/nexit/19.0/enterprise/helpdesk/controllers/portal.py:L36` | `_ticket_get_page_view_values` — donde inyectar los valores del bloque Service. |
| Rutas del portal de tickets | `/home/leandro/projects/nexit/19.0/enterprise/helpdesk/controllers/portal.py:L154` | `/my/tickets` (L154) y `tickets_followup` (L159-165, con `_document_check_access` sudo) — templates a heredar. |
| Templates del portal de helpdesk | `/home/leandro/projects/nexit/19.0/enterprise/helpdesk/views/helpdesk_portal_templates.xml:L41` | `portal_helpdesk_ticket` (L41, boton "New Service Request") y `tickets_followup` (L110, bloque Service). |
| Form del ticket (backoffice) | `/home/leandro/projects/nexit/19.0/enterprise/helpdesk/views/helpdesk_ticket_views.xml:L357` | `helpdesk_ticket_view_form` — vista a heredar para el grupo Service. |
| Form de la tarea (vista a heredar) | `/home/leandro/projects/nexit/19.0/odoo/addons/project/views/project_task_views.xml:L322` | `view_task_form2` — la vista que hereda T08 (el flujo FSM la usa: `/home/leandro/projects/nexit/19.0/enterprise/helpdesk_fsm/wizard/create_task.py:L61`). |
| Constraint de fechas planificadas | `/home/leandro/projects/nexit/19.0/enterprise/project_enterprise/models/project_task.py:L41` | `_planned_dates_check (planned_date_begin <= date_deadline)` (L41-44) → los dos campos van en **un solo** `write`. |
| Record rule portal de tickets | `/home/leandro/projects/nexit/19.0/enterprise/helpdesk/security/helpdesk_security.xml:L91` | `helpdesk_portal_ticket_rule` (dominio en L94-99): exige `team_privacy_visibility = 'portal'` **y** partner follower → justifica la semilla del team y el `partner_id` en el create. |
| `privacy_visibility` del team | `/home/leandro/projects/nexit/19.0/enterprise/helpdesk/models/helpdesk_team.py:L64` | Selection con `'portal'` (default del core); la semilla lo fija explicito. |
| El create nativo suscribe al partner | `/home/leandro/projects/nexit/19.0/enterprise/helpdesk/models/helpdesk_ticket.py:L619` | "make customer follower": con `partner_id` en los vals, el ticket suscribe al cliente (L619-633) → sin eso el portal no lo veria. |
| Tag: unicidad de nombre | `/home/leandro/projects/nexit/19.0/enterprise/helpdesk/models/helpdesk_tag.py:L20` | `_name_uniq = models.Constraint('unique (name)')` → nombres semilla calificados (D28). |
| Pickings de reemplazo | `/home/leandro/projects/nexit/19.0/enterprise/helpdesk_stock/models/stock_picking.py:L13` | `stock.picking.is_replacement` — se excluye del helper de entregas (D25). |
| `planned_date_begin` de la tarea | `/home/leandro/projects/nexit/19.0/enterprise/project_enterprise/models/project_task.py:L26` | Campo de inicio planificado (via `industry_fsm` → `project_enterprise`); junto con `date_deadline` recibe las fechas de la cita. |
| `date_deadline` de la tarea | `/home/leandro/projects/nexit/19.0/odoo/addons/project/models/project_task.py:L183` | Fin planificado en v19 (ya no `planned_date_end`). |
| Estados cerrados de la tarea | `/home/leandro/projects/nexit/19.0/odoo/addons/project/models/project_task.py:L86` | `CLOSED_STATES` con `'1_canceled'` — valor exacto para cancelar/reponer (D17/D18). |
| `appointment.type` (campos de la semilla) | `/home/leandro/projects/nexit/19.0/enterprise/appointment/models/appointment_type.py:L61` | `appointment_duration` (L61), `schedule_based_on` (L171), `staff_user_ids` (L180), `slot_ids` (L175), `is_published` (L208). |
| `appointment.invite` | `/home/leandro/projects/nexit/19.0/enterprise/appointment/models/appointment_invite.py:L17` | Modelo del invite: `short_code` como `_rec_name` y `access_token` que habilita el tipo sin publicar. |
| `helpdesk.tag` | `/home/leandro/projects/nexit/19.0/enterprise/helpdesk/models/helpdesk_tag.py:L10` | Modelo de los 7 tipos de problema semilla. |
| Wizard nativo de acceso portal | `/home/leandro/projects/nexit/19.0/odoo/addons/portal/wizard/portal_wizard.py:L133` | `action_grant_access()` — el que usa el backoffice para invitar manualmente (D5) y el que usara el modulo hermano. |
| Garantia efectiva (cadena de config) | `sk_customer_product_warranty/models/product.py:L90` | `product.product._get_warranty_info()` (L90-109): variante → plantilla → categoria; **unica** fuente de duracion/unidad/inicio. |
| Bug de propagacion a variantes | `sk_customer_product_warranty/models/product.py:L50` | `_prepare_variant_values` propaga `warranty_tracking` solo a variantes **nuevas** → variantes viejas quedan sin garantia (edge case `unknown`). |
| Fecha de garantia en el lote | `sk_customer_product_warranty/models/stock_lot.py:L8` | `stock.lot.warranty_expiry_date` — hoy siempre vacia (sin tracking serial); prioridad futura (D22). |
| Mapeo de unidades a `relativedelta` | `sk_customer_product_warranty/models/stock_move_line.py:L57` | `day/week/month/year` (L57-68): el calculo del service usa **el mismo** mapeo para no divergir. |
| Patron endurecido de fotos | `website_sale_installation_appointment/controllers/website_sale_installation_appointment.py:L163` | `_save_installation_photos` (L163-209): `guess_mimetype` del contenido real, limites `MAX_PHOTOS`/`MAX_PHOTO_SIZE`, create sudo del adjunto. |
| Patron de copia de fotos al chatter | `website_sale_installation_appointment/models/sale_order.py:L145` | `_post_installation_photos` (L145-167): `copy({'res_model': 'mail.compose.message', 'res_id': 0})` + `message_post(attachment_ids=...)`. |

## Documentacion afectada

| Archivo | Accion | Que reflejar |
|---------|--------|-------------|
| `helpdesk_service_appointment/README.md` | crear | Objetivo de negocio (reemplazo del JotForm), flujo del cliente paso a paso, modelos/campos agregados, calculo de garantia sin series y sus limitaciones, datos semilla, **configuracion funcional obligatoria** (asignar **staff** al tipo de cita —sin staff no ofrece horarios— y ajustar los **slots default** L-V 9-12 / 14-17 que crea el core, `fsm_project_id` del team, `warranty_tracking` + plazos de las cerraduras con el bug de variantes, `stock.group_stock_user` para los usuarios de helpdesk, procedimiento telefonico), gotchas (sin series, sin cobro, sync de una via, ventana `min_cancellation_hours` de 1 h en la que el cliente **no** puede cancelar y hay que reprogramar desde el backoffice, reagendado = cancelar + reservar de nuevo). |
| `helpdesk_service_appointment/static/description/index.html` | crear | Presentacion de la funcionalidad visible: formulario de portal, badge de garantia, agendado con disponibilidad real, tarea FSM con fotos y garantia, gestion/cancelacion desde el portal. |
| `helpdesk_service_appointment/i18n/es_419.po` | crear | Traduccion es_419 de los strings de UI (form portal, badges, bloque Service, mensajes de error/warning). |
| `odoo_customization_sunra/README.md` (raiz del repo) | actualizar | Fila del modulo `helpdesk_service_appointment` en el indice de modulos. |

## Plan del cambio en curso

> Build inicial del modulo (spec-first: hoy solo existe esta spec). **Precondicion**: @scaffold crea la
> estructura y el `__manifest__.py` (`author="Sunra"`, `license="LGPL-3"`, `version="1.0.0"`,
> `category="Website/Website"`, `depends=["helpdesk_fsm","helpdesk_stock","website_appointment","sk_customer_product_warranty"]`)
> **antes** de T01; por eso ninguna tarea lo referencia como dependencia. Cada tarea que agrega un
> archivo lo declara tambien en `models/__init__.py` / `data` del manifest segun corresponda. El repo
> **no** tiene `.swarm.conf` → sin tarea de tests por politica.

| Tarea | Descripcion | Depende de | Archivos | Cubre |
|-------|-------------|------------|----------|-------|
| **T01** | `product.product`: `_get_partner_service_products(partner)` (`_read_group` sudo de entregas `done`/`outgoing`, `is_replacement=False`, por commercial partner, con `date:min`/`date:max` normalizados a Date con tz del usuario, productos devueltos en sudo) + `_get_service_warranty(first_delivery, last_delivery, lot=None)` (cadena `_get_warranty_info` + `relativedelta`, prioridad al lote, `manufacture` sin lote → `unknown`). | — | `models/product_product.py`, `models/__init__.py` | CA02, CA03, CA04 |
| **T02** | `helpdesk.ticket`: campos `service_visit_address_id`, `service_event_ids`, `service_event_id` + snapshot de garantia (`warranty_status`, `warranty_expiry_date`, `warranty_delivery_date`, compute stored con `sudo()` interno y **batcheo por commercial partner**), `_compute_service_event_id`, `_get_service_appointment_url()` (via `invite.redirect_url`), helpers de fotos (`_get_service_photo_attachments`, `_post_service_photos`). | T01 | `models/helpdesk_ticket.py`, `models/__init__.py` | CA02, CA03, CA04, CA12 |
| **T03** | `calendar.event`: campo `service_ticket_id`; override `create` (savepoint + `_service_generate_fsm_task`: wizard FSM sudo con **contexto limpio** + `hsa_from_appointment=True`, fechas `planned_date_begin`/`date_deadline` en **un solo write**, fotos, mensajes) y `write` (cancelacion `active=False` → `1_canceled`, unarchive → reponer, cambio de `start`/`stop` → sync). | T02 | `models/calendar_event.py`, `models/__init__.py` | CA10, CA13, CA14, CA15, CA16 |
| **T04** | Wizard `helpdesk.create.fsm.task`: override `_generate_task_values()` con `partner_id` = direccion de visita **solo bajo `hsa_from_appointment`** (el camino manual queda intacto) y bloque de garantia (`Markup` + `escape`) al inicio de la descripcion, siempre. | T02 | `wizard/helpdesk_create_fsm_task.py`, `wizard/__init__.py`, `__init__.py` | CA10, CA11, CA22 |
| **T05** | Controller de portal `/my/service/new` (GET/POST): `_prepare_service_form_values` (contacto, direcciones, cerraduras con badge, tags, antiguedad, limites), validaciones anti-IDOR (producto en entregas, direccion del commercial partner, tag semilla), create sudo del ticket, `_save_service_photos` endurecido con adjuntos **pendientes** + `message_post`, redirect 303 al agendado. | T02 | `controllers/helpdesk_service_appointment.py`, `controllers/__init__.py`, `__init__.py` | CA01, CA05, CA06, CA07, CA08, CA09, CA20 |
| **T06** | Controller de Citas: override de `_get_extra_calendar_event_params` (guard de entero, `exists()`, chequeo de commercial partner o usuario interno, anti-doble-agendado) **+ override de `appointment_cancel`** que reinyecta `service_ticket_id` en la URL de vuelta (D34). | T03 | `controllers/appointment.py`, `controllers/__init__.py` | CA10, CA13, CA21 |
| **T07** | Templates de portal: `portal_service_new` (form completo con badges y fallback), inherit de `helpdesk.portal_helpdesk_ticket` (boton "New Service Request") e inherit de `helpdesk.tickets_followup` (bloque Service con cita / "Schedule visit") + valores en `_ticket_get_page_view_values`. | T05 | `views/helpdesk_service_appointment_templates.xml`, `controllers/helpdesk_service_appointment.py`, `__manifest__.py` | CA01, CA02, CA03, CA04, CA06, CA12, CA18, CA20 |
| **T08** | Vistas de backoffice: inherit del form (y list opcional) del ticket con el grupo Service + decoraciones de garantia; related readonly `service_warranty_status` / `service_warranty_expiry_date` en `project.task` + inherit de `project.view_task_form2`. | T02 | `models/project_task.py`, `models/__init__.py`, `views/helpdesk_ticket_views.xml`, `views/project_task_views.xml`, `__manifest__.py` | CA17 |
| **T09** | Datos semilla `noupdate="1"`: team "Service" (`use_fsm=True`, `privacy_visibility='portal'`), tipo de cita "Service Visit" (2 h, `users`, `is_published=False`, `staff_user_ids` vaciado con `eval="[(6, 0, [])]"`), `appointment.invite` `short_code='service'` y los 7 `helpdesk.tag` con nombres calificados ("Lock ...", por el `UNIQUE(name)`). | — | `data/helpdesk_service_appointment_data.xml`, `__manifest__.py` | CA19 |
| **T10** | Documentacion y cierre: `README.md` del modulo (incluida la config funcional obligatoria) + `static/description/index.html` + fila en el README raiz del repo + `i18n/es_419.po`, y `version="1.0.0"` en el manifest == `Version` de esta spec (estado spec → `implemented`). | T01, T02, T03, T04, T05, T06, T07, T08, T09 | `README.md`, `static/description/index.html`, `../README.md`, `i18n/es_419.po`, `__manifest__.py`, `specs/helpdesk_service_appointment.md` | — (doc + version sync) |

## Notas de implementacion

- **Por que el `create` de `calendar.event` y no el controller** (D14): el hook
  `_get_extra_calendar_event_params` solo puede devolver **valores del evento**, no efectos
  colaterales; y el evento nace en el controller nativo con `sudo()` y contextos especiales. Poner la
  generacion de la tarea en la capa **modelo** hace que tambien funcione si un usuario interno agenda
  la cita desde Calendar seteando `service_ticket_id` a mano, sin duplicar logica en el controller.
- **La URL de agendado es el punto mas fragil del modulo** (D13): `invite.redirect_url` no es una
  comodidad, es la **unica** forma correcta de abrir un tipo de cita **no publicado** desde afuera. La
  version "obvia" (`/appointment/<id>?invite_token=<token>`) funciona en una base con un solo tipo de
  cita activo y empieza a devolver **403** en cuanto hay dos — es decir, funciona en una demo limpia y
  falla en la base real de Sunra, que ya tiene el tipo de instalacion. Cualquier refactor de esa URL
  tiene que seguir emitiendo `filter_appointment_type_ids`.
- **Fotos y usuarios portal** (D11): el patron "creo el adjunto apuntando al registro y lo posteo" es lo
  natural y **no funciona** para un usuario portal: `mail.thread` descarta esos adjuntos y el
  `message_post` queda sin fotos, sin error. Hay que crearlos **pendientes** y dejar que `message_post`
  los reasigne. El modulo de instalacion tiene el mismo patron en `_post_installation_photos`.
- **Minimal footprint**: no se reimplementa nada de FSM ni de Citas. La tarea se crea con el **wizard
  nativo** (`_generate_task_values` + `action_generate_task`, que ya postea el link en el ticket), el
  agendado usa la **pagina nativa** de Citas (slots, capacidad, invite), el portal reusa
  `_ticket_get_page_view_values` y las fotos copian el patron ya endurecido del modulo de instalacion.
  Lo unico realmente nuevo es el **formulario de portal**, el **vinculo evento↔ticket** y el **calculo
  de garantia sin series**.
- **`models/project_task.py` (T08)** existe solo porque las vistas de Odoo no traversan rutas con
  puntos: mostrar la garantia en el form de la tarea exige dos campos `related` readonly. Sin logica y
  sin `store` — la informacion "de verdad" viaja en la descripcion de la tarea (T04), que es lo que el
  tecnico lee en el celular.
- **Sudo en el compute de garantia**: `helpdesk_stock` declara `product_id` con
  `groups="stock.group_stock_user"`. Un compute **stored** que dependa de ese campo se recalcula cuando
  cualquier usuario toca `partner_id`; sin `sudo()` interno, un agente de helpdesk sin el grupo de
  stock veria `AccessError` al guardar el ticket. Es el gotcha mas facil de romper de todo el modulo.
- **Garantia sin series (D20)**: se verifico en codigo que `stock.lot.warranty_expiry_date` solo se
  escribe si `product.tracking == 'serial'`; como Sunra no usa series, ese campo esta siempre vacio y
  calcular desde entregas es la **unica** via. Se reusa `_get_warranty_info()` (no se duplica la cadena
  variante→plantilla→categoria) y el **mismo** mapeo de `relativedelta` que el modulo de garantias, para
  que un cambio de criterio se propague desde una sola fuente.
- **Snapshot stored vs compute vivo (D24)**: stored porque el estado de garantia que importa es el del
  **momento del reclamo** (es lo que se le informa al cliente y lo que lee el tecnico), y porque evita
  recalcular entregas en cada lectura del portal.
- **Contexto limpio al crear la tarea (T03)**: el `create` del evento corre con el contexto que arma el
  controller nativo de Citas (`mail_notify_author`, `mail_create_nolog`, `mail_create_nosubscribe`,
  `skip_contact_description`, `allowed_company_ids` del staff). Si ese contexto se hereda al wizard, la
  tarea FSM nace sin followers ni mensaje de creacion y potencialmente en la compania equivocada. Se
  instancia el wizard con contexto explicito, y ahi mismo va la clave `hsa_from_appointment=True` (D33).
- **Fechas de la tarea en un solo `write`**: `project_enterprise` valida
  `planned_date_begin <= date_deadline` por constraint SQL. Escribir primero el inicio (contra un
  `date_deadline` viejo o nulo) puede volar el constraint; los dos campos van juntos, siempre.
- **Override del wizard acotado por contexto (D33)**: un override incondicional de
  `_generate_task_values` cambiaria el comportamiento del boton nativo "Create a Field Service task"
  para **todos** los tickets de service, pisando el cliente que eligio el agente. El gate por contexto
  mantiene el efecto dentro de nuestro flujo — es la diferencia entre extender y secuestrar.
- **Sync de una sola via (D19)**: sincronizar tarea → cita implicaria escribir en `calendar.event`
  desde `project.task.write`, con riesgo de loop con el propio `write` del evento (que ya escribe la
  tarea). Se documenta la limitacion: si el tecnico mueve la tarea, la cita del cliente no cambia.
- **Robustez del agendado (D15)**: el cliente ya reservo su lugar cuando se crea el evento; un fallo al
  generar la tarea (team mal configurado, permisos) no debe traducirse en un error 500 en la cara del
  cliente. Savepoint + nota en el chatter deja el problema visible para el backoffice sin perder la cita.
- **Anti-doble-agendado por ticket (D16/D32)**: se eligio validar por **ticket** (no por partner) porque
  un cliente puede tener varias cerraduras con fallas distintas; lo que no tiene sentido es un mismo
  reclamo con dos visitas simultaneas.
- **Tipo de cita despublicado (D28)**: `is_published=False` + `appointment.invite` es el mecanismo
  nativo para links "privados". Evita que el tipo Service aparezca en `/appointment` publico junto a los
  tipos comerciales, sin necesidad de reglas ni controllers extra.
- **La semilla del tipo de cita no puede ser "vacia"**: el core auto-crea slots default (L-V 9-12 /
  14-17) desde el compute de `category`, y `staff_user_ids` defaultea al usuario que instala. Se acepta
  lo primero (se documenta que hay que ajustarlos) y se neutraliza lo segundo (`eval="[(6, 0, [])]"`):
  con staff vacio el tipo **no ofrece horarios**, que es el estado seguro — mejor "no agendable hasta
  configurar" que "agendable con el tecnico equivocado". El README lo lista como paso de puesta en marcha.
- **Reagendado del cliente (D34)**: se eligio el override chico de `appointment_cancel` (reinyectar un
  query param en el `Location`) sobre alternativas mas invasivas (template propio de cancelacion,
  controller de rebooking propio) porque es el minimo cambio que evita citas huerfanas y degrada al
  comportamiento nativo si algo no matchea.
- **Desarrollo hermano (fuera de esta spec)**: la **auto-invitacion portal** al confirmar una venta con
  instalacion se implementa en `website_sale_installation_appointment` (v1.0.3 → 1.1.0), en su
  `_action_confirm()` existente, filtrando por `_is_installation_required()` y envuelta en savepoint +
  try para que un fallo (email faltante o duplicado) nunca bloquee la confirmacion de la venta. Vive
  ahi porque depende de la nocion de "venta con instalacion" de ese modulo; este modulo solo **consume**
  el resultado (que el cliente tenga usuario portal). Si el partner no lo tiene, el backoffice lo invita
  con el wizard nativo (D5).
