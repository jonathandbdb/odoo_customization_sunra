# Spec de modulo: website_sale_installation_appointment

| Campo | Valor |
|-------|-------|
| **Modulo** | `website_sale_installation_appointment` |
| **Version** | `1.10.0` (== `version` del `__manifest__.py`, formato `x.x.x`) |
| **Serie Odoo** | `19` (informativa) |
| **Estado** | `verified` |
| **Actualizado** | `2026-09-11` |

> Cliente: **Miluan SRL / Nokey** (eCommerce de cerraduras inteligentes, `nokey.odoo.com`).
> Repo: `extra-addons/odoo_customization_sunra`. Licencia LGPL-3, autor Sunra.
> `depends`: `website_sale`, `delivery`, `website_appointment_sale`, `sale_project`.
>
> **Nota de version**: el modulo paso a `1.10.0` — sobre el `1.9.0` (marca del correo de
> recordatorio, D43) se sumo el **rediseño del paso de instalacion del checkout** en 3 bloques
> tipo acordeon (direccion · turno y fotos · pago) y la **guia de fotos definitiva** (3 tomas
> "asi si" + 3 "asi no", con las fotos reales del cliente), aprobados por el cliente el
> **11/09/2026**. Las decisiones nuevas son **D44..D56** y el plan **T01..T12** cerro en esta misma
> fecha (implementacion + T12 de cierre): `version` del manifest y `Version` de esta spec quedan
> sincronizadas en `1.10.0`.
>
> **Pasada `analyze` de @reviewer (11/09/2026)**: sus hallazgos estan **incorporados en sitio** en
> las secciones afectadas (no se agregan tareas nuevas). Lo principal: CA35 reescrito en coherencia
> con D52, origen y conversion de las 6 fotos en T05, guarda de **carrito anonimo** en
> `_save_installation_address()`, `callback` en el link de edicion de la direccion (D12/D45),
> algoritmo explicito de `SaleOrder.write()`, `markupsafe.escape()` + idioma de la **compañia** en
> `_get_installation_task_notes()`, baja de `_get_frontend_writable_fields()` (sin consumidor) y
> correccion de anclajes.
>
> **Residuos cerrados al implementar (11/09/2026)**: (a) el aviso de carrito anonimo/sin direccion
> ahora tambien se señaliza **en el render** (GET), no solo al escribir — `installation_address_missing`
> en `_prepare_installation_values()`/`_get_installation_block_states()`, ver Metodos y Vistas; (b) el
> criterio de baja de `msgid` obsoletos de las fotos paso a ser "**todas** las entradas cuyo `#:`
> apunte a `installation_photo_examples`" (D55/T10), no un rango de lineas fijo; (c) `i18n/es_419.po`
> se reconstruyo entero desde un export real (`odoo.tools.translate.trans_export`) contra el arch
> final, no a mano linea por linea — evita msgids inventados o desalineados.

## Objetivo

Vender desde el eCommerce un **envio con instalacion incluida** y que esa venta quede **agendada como
Cita** (app Citas) con las **fotos del lugar**, la **tarea de Field Service** del instalador y el
cliente **invitado al portal**; y que el metodo de envio pueda ademas **incluir sin cargo las pilas**
que el producto necesita, generando automaticamente la linea de pedido en $0 (el costo ya esta
integrado en el servicio de instalacion).

## Decisiones vigentes

> Decisiones de diseño que rigen HOY. Si una decision nueva pisa una vieja, se **edita la fila**.
> Lo asumido sin confirmacion del usuario va marcado `[ASUNCION]`.

| # | Decision | Valor vigente |
|---|----------|---------------|
| D1 | ¿Como se marca que un envio lleva instalacion? | Opt-in **por metodo de envio**: `delivery.carrier.installation_appointment_type_id`. Vacio = envio normal. |
| D2 | ¿Que tipo de cita se acepta para instalacion? | Solo tipos con **paso de pago** y **producto de reserva** que genere tarea o tenga precio; se frena con `ValidationError` al guardar el carrier. |
| D3 | ¿Como aparece/desaparece el paso "Instalacion" del checkout? | Filtrando el dominio de pasos (`website._get_allowed_steps_domain()`), no con vistas condicionales: el core calcula solo el paso siguiente/anterior. **Sigue siendo UN solo paso del core** (`/shop/installation`, `sequence 400`, entre Direccion 250 y Pago 999): el rediseño en 3 bloques (D44) vive **adentro** de ese paso — no se agregan pasos al wizard ni rutas nuevas, asi el calculo de siguiente/anterior y el wizard visual del core quedan intactos. |
| D4 | ¿Que valida el upload publico de fotos? | Mimetype **real del contenido** (no el declarado), 10 MB por archivo, 10 fotos por pedido. Minimo configurable por carrier (`installation_min_photos`; 0 = opcional). |
| D5 | ¿Se puede pagar sin agendar / sin fotos? | No: gate en `_check_cart_is_ready_to_be_paid()` + `_get_shop_payment_errors()`, y `shop_payment()` redirige al paso en vez de mostrar el error. |
| D6 | ¿Donde ve la cuadrilla las fotos? | Se copian al chatter de la **Cita** y de la **tarea de FSM** despues de `super()._action_confirm()`. |
| D7 | ¿El cliente de una instalacion recibe portal? | Si, **incondicional** para pedidos con `installation_required`, via el `portal.wizard` nativo. Idempotente (usuario activo o archivado → no-op con nota en el chatter). Nunca rompe la confirmacion (savepoint + log). |
| D8 | ¿Y las citas agendadas FUERA del eCommerce (link compartido)? | `appointment.type.installation_fsm_project_id` → la tarea de FSM la crea este modulo en `calendar.event.create()`, y se sincroniza al reprogramar/cancelar/desarchivar. |
| D9 | ¿Como se evita que el cliente escriba cualquier cosa en el formulario de la cita? | Campo propio `appointment.question.answer_format` (libre/entero/numero/telefono/documento): emite `type`/`inputmode`/`pattern` reales y **revalida en el servidor**. |
| D10 | ¿Donde se muestran los diagramas de medidas? | Dentro del bucle de preguntas, justo antes de la pregunta marcada con `appointment.question.installation_measure_guide` (un solo lugar sirve para los dos caminos). |
| D11 | ¿Una sola instalacion por pedido? | Si: reagendar reemplaza la reserva anterior (`_remove_previous_installation_bookings`). |
| D12 | ¿Nombre de la empresa en el checkout? ¿Donde se **carga** la direccion? | Se saca `#company_name_div` heredando `website_sale.address_form_fields` (NO desactivando `address_b2b`, que se lleva la Responsabilidad de ARCA de `l10n_ar`). **La direccion se sigue cargando en el paso del core** (`/shop/address`): el modulo **no** agrega un segundo formulario de direccion (D45). En nuestro paso solo se **muestra en resumen**, con link "editar" a `/shop/address?partner_id=<partner de envio>&address_type=delivery&callback=/shop/installation` y con los dos datos nuevos que el core no tiene (D46, D47). El **`callback` es lo que hace que *Guardar* vuelva al paso de instalacion** y no al checkout: el core redirige a `callback or '/shop/checkout'` (`odoo/addons/website_sale/controllers/main.py:L1234`, `:L1236`) y usa el mismo valor para el link *Descartar* (`:L1184`). El parametro viaja **nativo**, sin codigo nuestro: `shop_address(**query_params)` (`odoo/addons/website_sale/controllers/main.py:L1099`) → `_prepare_address_form_values(callback=…)` → `shop_address_submit(callback=…)`. |
| D13 | ¿Como se marca que un envio incluye las pilas? | **Segundo opt-in independiente**, `delivery.carrier.includes_free_batteries` (Boolean). No se ata a `installation_appointment_type_id`: mañana otro envio puede incluir pilas sin agendar cita. |
| D14 | ¿Donde se configura que pilas lleva un producto? | En la **ficha del producto** (`product.template`): `free_battery_product_id` + `free_battery_qty`. |
| D15 | ¿En que unidad se expresa `free_battery_qty`? | En la **UoM del producto de pila elegido** (el producto real del cliente se vende en "Paquete de 4": `1` = un paquete = 4 pilas). El `string`/`help` lo dicen explicitamente y la vista muestra la UoM al lado. La linea se crea **sin** pasar `product_uom_id` para que el ORM tome la UoM propia del producto. |
| D16 | ¿Una linea por cerradura o una por pila? | `[ASUNCION]` **Una por producto de pila**, con la suma: dos cerraduras distintas que usan la misma pila dan UNA linea. El pedido del usuario no lo especifica; agrupar es lo que menos ensucia el carrito y la factura. |
| D17 | ¿Como se mantiene la linea sincronizada? | Reconciliacion **idempotente desde cero** en cada llamada (crea lo que falta, ajusta cantidades, borra lo que sobra). Clave: `(pedido, producto, is_free_battery_line)`. Nunca incremental. Precedente interno: `_apply_payment_price_rule` de `website_sale_payment_method_price`. |
| D18 | ¿Como se marca la linea gratis? | Flag tecnico propio `sale.order.line.is_free_battery_line`. **NO** se usa `is_delivery=True` por dos motivos: (a) `unlink()` de una linea `is_delivery` **pone `carrier_id = False`** en el pedido (`odoo/addons/delivery/models/sale_order_line.py:L29`) → borrar la linea de pilas **desarmaria el metodo de envio**; (b) `_show_in_cart()` excluye las lineas de envio y la linea quedaria **oculta**, contra D20. |
| D19 | ¿Se cuelga la linea de la cerradura con `linked_line_id`? | **No.** (a) contamina el `name` en la **factura** con `"Option for: <cerradura>"`; (b) `ondelete='cascade'` es un `ON DELETE CASCADE` de SQL: borrar la cerradura evaporaria la linea **sin correr ningun `unlink()` Python** ni los `@api.ondelete` del core; (c) la colision de carrito se resuelve mejor con `_cart_find_product_line`. |
| D20 | ¿La linea gratis se ve en el carrito? | **Si, se ve, pero no se puede tocar** (decision del usuario): sin selector de cantidad y sin boton Eliminar. `[ASUNCION]` que el **link al producto** tambien se apague — es efecto colateral de `_is_sellable()` y es coherente (la pila no se vende sola), pero no lo pidio el usuario. La garantia real no es el HTML (ver D21). |
| D21 | ¿Que impide que el cliente la borre por el endpoint? | Nada a nivel HTTP — y no hace falta: `_cart_update_line_quantity()` llama a `_verify_cart_after_update()` **despues** de aplicar el cambio, asi que la re-sincronizacion **auto-cura** la linea en el **mismo request**. La defensa es una propiedad del diseño, no el ocultamiento cosmetico. |
| D22 | ¿Como se garantiza el precio 0? | En `_get_display_price()` (el load-bearing: cubre el camino normal y el forzado de `_compute_price_unit`), no con `price_unit=0` en el create (que no marca la linea como precio manual). |
| D23 | ¿Y el descuento? | `_compute_pricelist_item_id()` → `False` para la linea gratis, para que `_recompute_prices()` no le ponga `discount > 0` (una tarifa `percentage` prenderia la columna **Descuento en todo el PDF** y el precio tachado en el carrito). Precedente literal: `delivery`. |
| D24 | ¿Que pasa si el cliente agrega la MISMA pila como producto suelto? | `[ASUNCION]` Se crea una linea **separada y paga** (`_cart_find_product_line()` filtra las lineas gratis, asi `_cart_add` no fusiona). El que quiere pilas de repuesto las paga. |
| D25 | ¿"Volver a pedir" re-agrega la pila? | `[ASUNCION]` No: `_is_reorder_allowed()` → `False` (si no, se re-agregaria **sin** el flag y a precio de tarifa). |
| D26 | ¿Pedidos armados en el backend (venta telefonica)? | Cubiertos con `@api.onchange('order_line', 'carrier_id')` (sincronizacion **en memoria** con `Command.*`, como el core con las lineas de combo) + red de seguridad en `action_confirm()`. |
| D27 | ¿Donde va la red de seguridad al confirmar? | En **`action_confirm()` antes del `super()`** (state todavia `draft`/`sent`). **No** en `_action_confirm()`: ahi el `state` ya es `'sale'` y borrar lineas choca con `_unlink_except_confirmed`. El override existente de `_action_confirm()` (fotos + portal) queda intacto. |
| D28 | ¿La linea gratis se ve en la factura? | Si, a $0. **Aceptado explicitamente por el usuario** (deja constancia de que las pilas fueron entregadas). |
| D29 | ¿El comportamiento no-editable depende de publicar la pila? | No: se override-ea `_is_sellable()`. Hoy da `False` por accidente de datos (las pilas estan **despublicadas**), pero el funcional evaluaba publicarlas y eso reactivaria el selector de cantidad. El override lo hace independiente del estado de publicacion. |
| D30 | ¿Se publican los productos de pila en el sitio? | No hace falta (la linea se crea server-side, la pila no se vende sola). Pueden quedar despublicados; publicarlas no debe cambiar el comportamiento (D29). |
| D31 | ¿Como se avisa en el checkout que las pilas van incluidas? | *(reescrita por el rediseño — D52)* Con **una sola linea** en el renglon corto al pie del acordeon, con `t-if`/`t-else` sobre `order.carrier_id.includes_free_batteries`: "van incluidas sin cargo" / "tenes que tener 4 u 8 AA/AAA el dia de la instalacion". Va **fuera** de cualquier `t-if` de texto configurable, asi que se ve tambien con `message_intro` cargado, y lleva `o_not_editable` (D42). **Que reemplaza**: el diseño anterior tenia el `<li>` historico condicionado **dentro** del `t-else` del checklist mas un bloque de aviso aparte; existia asi para no tocar el `msgid` ya traducido. Con el rediseño esos textos se reescriben igual (D53), y una sola linea con dos ramas hace **imposible** que los dos mensajes convivan — el defecto que vigilaba CA37 deja de ser alcanzable. |
| D32 | ¿Sobre que estados actua la sincronizacion? | `[ASUNCION]` Solo `draft`/`sent`. En un pedido confirmado, ajustar/borrar lineas es trabajo del backoffice (y chocaria con `_unlink_except_confirmed`). |
| D33 | ¿El flag se copia al duplicar el pedido? | **Si**: `is_free_battery_line` va **sin `copy=`** (default `True`). El molde correcto es `is_delivery` del core, que tampoco lo declara (`odoo/addons/delivery/models/sale_order_line.py:L9`). Con `copy=False` el duplicado quedaria con la linea a $0 **sin el flag** → el primer recompute la llevaria a precio de tarifa y el sync, al no reconocerla, **crearia una segunda linea gratis** (doble cantidad de pilas, la mitad facturada). ⚠️ El `copy=False` de `is_payment_method_discount` del modulo hermano **NO es el molde**: esa linea es un descuento atado al medio de pago que se re-elige en el checkout; esta es una linea de producto que se entrega. No unificar los dos flags. |
| D34 | ¿Que pasa con el control de stock del eCommerce? | Se override-ea `_check_availability()` → `True` para la linea gratis. `website_sale_stock` es `auto_install` y esta **instalado** en la base: su `_check_cart_is_ready_to_be_paid` tira `ValidationError` si una linea storable sin *Sell when Out-of-Stock* supera el stock libre. Con *Pilas AA* (tmpl 411) ya en `allow_out_of_stock_order = false` y **stock 0**, el cliente quedaria **sin poder pagar** por un producto que no eligio y que no puede borrar (D20/D21 lo auto-curan): checkout muerto. No se resuelve "por configuracion" — los datos reales ya contradicen ese requisito. **Por que el override no queda sombreado**: `website_sale_stock` **no** esta en nuestro `depends` (agregarlo arrastraria `stock`: footprint peor), pero el orden de carga es `(phase, depth, order_name)` con `depth` = camino mas largo a `base` (`odoo/odoo/modules/module_graph.py:L175`, `:L225`): dependemos de `website_appointment_sale` → `website_sale`, asi que `depth(nuestro) >= depth(website_sale)+2` mientras `depth(website_sale_stock) = depth(website_sale)+1` → **cargamos despues y ganamos el MRO**. ⚠️ Riesgo latente: si un cambio de `depends` empata la profundidad, el desempate es alfabetico (`website_sale_installation_appointment` < `website_sale_stock`) y quedariamos **primeros**, con el override convertido en **codigo muerto** y el checkout muerto en silencio. **CA32 es el tripwire** de esa regresion, cubierto por el test de `tests/test_free_batteries.py` (plan `1.8.0`, cerrado). |
| D35 | ¿El `name` de la linea nombra el metodo de envio? | **No.** Se usa un texto sin el nombre del carrier (*"Included with your shipping method — no extra charge."*) para no tener estado que sincronizar: el sync solo escribe `product_uom_qty`, asi que al pasar a **otro** envio que tambien incluye pilas (el futuro que pide D13) el nombre horneado quedaria mintiendo en el carrito **y en la factura**. Ademas la descripcion se arma en el **idioma del cliente**. |
| D36 | ¿El sync puede tocar lineas ya facturadas o entregadas? | **No**: se excluyen del `write` y del `unlink` las lineas con `qty_invoiced` o `qty_delivered` distintos de 0. `state in ('draft','sent')` **no** implica "nada facturado": un pedido facturado que el backoffice devuelve a presupuesto ("Set to Quotation") vuelve a `draft` con `qty_invoiced != 0`, y `_check_line_unlink` solo bloquea en `state == 'sale'`. Mismo criterio que `_remove_delivery_line` del core. |
| D37 | ¿Que engaches cubren el backend? | Tres, complementarios: el `@api.onchange` (carga interactiva), **`set_delivery_line()`** (el boton **Add shipping** → wizard `choose.delivery.carrier` escribe por `write`, los onchange **no** corren) y `action_confirm()` (red final). `_set_delivery_method()` **no se reemplaza**: es el unico que cubre el camino de **quitar** el envio, donde `set_delivery_line` no se llama. |
| D38 | ¿Y si la pila configurada es de otra compañia? | `free_battery_product_id` lleva `check_company=True` + domain de compañia (la base tiene 2 compañias), y el agregado **saltea** el producto incompatible en vez de romper. `product_id` de `sale.order.line` es `check_company=True` y el `sudo()` del sync **no** exime de `_check_company`: sin esto, una mala configuracion daria **error 500 en cada request del carrito** del visitante publico. |
| D39 | ¿Cantidades no positivas? | Solo se acumulan lineas con `product_uom_qty > 0`, y los `needs` que quedan en `<= 0` se descartan (caen en `to_unlink`). Un pedido con la cerradura en `-1` (nota de credito preparada como pedido negativo) generaria una linea de pilas **negativa** → `stock_delivery` crearia un movimiento de **devolucion** de pilas que el cliente nunca entrego; y `+1 / -1` dejaria una linea en 0 en el carrito y en el PDF. |
| D41 | ¿Donde se pinta el aviso de "pilas incluidas"? | *(reescrita por el rediseño — D52)* En el **renglon corto al pie del acordeon**, junto a la garantia, condicionado **solo** a `order.carrier_id.includes_free_batteries` y fuera de todo `t-if`/`t-else` de texto configurable. Rationale **intacto**: la logica **condicional a datos** tiene que vivir en la plantilla —un campo de texto configurable no puede expresar una condicion—, mientras los textos **estaticos** del cliente van en campos (criterio de D42). **Los dos criterios conviven**: prosa estatica → campo; texto que depende del estado del pedido → plantilla. |
| D42 | ¿Por que los textos del cliente van en campos y no en las plantillas? *(current-state, decision del commit `e5526ae`)* | Porque **editar una plantilla desde el editor web crea una copia COW por sitio que deja de recibir las actualizaciones del modulo**: asi se vacio la guia de fotos en produccion, en los dos flujos, sin que ningun deploy la arreglara. El checklist sale del campo **nativo** `message_intro` y la consigna de fotos del campo nuevo `installation_photos_message`; vacios → el texto por defecto del modulo. Van **por tipo de cita** a proposito: el del eCommerce cobra online y el del link cobra el dia del turno, asi que las condiciones difieren. **Corolario operativo**: cuando el modulo cambia su texto **por defecto** (ej. la consigna de fotos, que pasa de "2 cosas" a 3 tomas — D51), el registro **ya cargado** en produccion no se entera: se corrige **como dato**, desde la ficha del tipo de cita en el backend (nunca desde el editor web, que dispara la copia COW). T11 lo cubre. **Corolario para el rediseño**: la misma trampa obliga a marcar `o_not_editable` a nivel
**contenedor** — el `div.accordion#installation_accordion` (toda la prosa estatica de T07:
encabezados de bloque, razones del candado, duracion, condicion de pago, avisos de cada bloque) y,
aparte, el `div` que envuelve el template `installation_photo_examples` (fotos reales del cliente,
el mismo que ya sufrio la copia COW en produccion) — en vez de marcar cada elemento suelto: un
elemento nuevo agregado adentro sin su clase propia queda igual **protegido** por el contenedor
(fix de revision M6, que encontro texto suelto sin marcar). Quedan **fuera** de esa marca el
`oe_structure` (existe para que el cliente ponga snippets) y los `t-field` de `message_intro` /
`installation_photos_message` (son campos, no plantilla: se editan en el backend). |
| D40 | ¿La cantidad convierte UoM de la **cerradura**? | `[ASUNCION]` **No**: `free_battery_qty * line.product_uom_qty` se toma tal cual, porque hoy las cerraduras se venden en **Units**. Si mañana una se vende en "Caja de 6", 1 caja pediria 1 paquete en vez de 6. Fix conocido de una linea: `line.product_uom_id._compute_quantity(line.product_uom_qty, line.product_id.uom_id)` (molde: `odoo/addons/delivery/models/sale_order_line.py:L24`). Las cerraduras **dentro de un combo** si aportan pilas (deseable), pero configurar pilas en la plantilla del combo **y** en el item las contaria dos veces. |
| D43 | ¿Que compañia sella el correo de una cita de instalacion (logo/colores del layout de notificacion)? | *(Plane #38, 2026-09-07; corregido tras review — ver nota abajo)* **Causa raiz real**: la confirmacion Y el recordatorio de la cita se mandan por el **mismo camino** — `_notify_attendees()` (`odoo/addons/calendar/models/calendar_attendee.py:L124-196`) → `message_notify()` sobre el `calendar.event` — asi que no es que "la confirmacion viaja sobre el pedido": tambien viaja sobre la cita. La diferencia es **cuando** corre cada uno: la confirmacion la dispara el `create()` del attendee dentro del **request web** del checkout (`enterprise/appointment/models/calendar_attendee.py:L16-44`), donde `env.company` ya es la del sitio/cliente; el recordatorio lo dispara el **cron** de alarmas (`odoo/addons/calendar/models/calendar_alarm_manager.py:L182-202`, `_send_reminder`), cuyo `env.company` es la del usuario tecnico del cron. El logo/colores del layout los pinta `_notify_by_email_prepare_rendering_context()` (`odoo/addons/mail/models/mail_thread.py:L3606-3719`, el calculo en `:L3657-3666`), que arma `company` leyendo `record.company_id` **directo** — no via `_mail_get_companies()` — y cae a `env.company` porque `calendar.event` no tiene ese campo. Fix con **dos** overrides en `calendar.event`, ambos reusando el mismo resolvedor: `_mail_get_companies()` (compania del `record_company_id`/alias domain/reply-to — molde `odoo/addons/mail/models/models.py:L128-140`, uso real en `message_notify` `odoo/addons/mail/models/mail_thread.py:L2831`) y `_notify_by_email_prepare_rendering_context()` (el que **si** pinta el layout, molde de override `odoo/addons/sale/models/sale_order.py:L1758`). Orden de resolucion en ambos: (1) compania del **pedido de venta** que origino la cita — el mas viejo (por `id`) entre los no cancelados, `sale.order.line.calendar_event_id`, porque duplicar un pedido copia ese vinculo sin `copy=False` (`enterprise/website_appointment_sale/models/sale_order_line.py:L11`); (2) compania del **organizador** (`user_id.company_id`); (3) compania de **quien creo la cita** (`create_uid.company_id`, mismo heuristico que usa el propio core para citas sin usuario, `odoo/addons/calendar/controllers/main.py:L66`); (4) lo que resuelva el `super()` con el `default` recibido. **Efecto colateral deseado** de `_mail_get_companies()`: el reply-to/alias domain del recordatorio tambien queda con el dominio de la compañia del pedido (verificado en produccion: cada compañia tiene su propio dominio de alias — `nokey.odoo.com`, `sunra.odoo.com`, `sunraprueba.odoo.com`, `miluanprueba.odoo.com` — todos manejados por la misma instancia), asi que un recordatorio de un pedido de Nokey con reply-to de Nokey es lo correcto, no un accidente a corregir. **Nota de la correccion**: la primera version de este fix (T13, primer intento) solo tenia el override de `_mail_get_companies()` y documentaba mal la causa (creia que la confirmacion no pasaba por `calendar.event`, y citaba `mail_thread.py:2330`, que es de `message_post`, no del recordatorio). El logo seguia mal porque ese metodo **no** interviene en el layout. |
| D44 | ¿Como se estructura el paso `/shop/installation`? | *(rediseño aprobado 11/09/2026)* En **3 bloques tipo acordeon** (Bootstrap `collapse`, **sin JS nuevo**): *Paso 1 · Installation address*, *Paso 2 · Appointment and photos*, *Paso 3 · Payment*. Los tres **se ven desde el inicio** (pedido textual del cliente: "veo cuales son todos los pasos y se me van habilitando"); el completado se resume con **tilde** + su resumen en el encabezado, el bloqueado con **candado** y la razon ("Se habilita al completar el paso N"). El bloque bloqueado **no renderiza su cuerpo** (no hay controles deshabilitados que igual se puedan postear a mano). El estado lo calcula el **servidor** (`sale.order._get_installation_block_states()`), no la plantilla (AGENTS.md: nada de logica de negocio en vistas). **El rotulo del bloque 3 sale del dato, no de una constante**: se toma de `next_website_checkout_step.name`, porque el paso siguiente **no siempre es Payment** — entre 400 y 999 existe el paso nativo *Extra Info* (`/shop/extra_info`, `sequence 500`, `odoo/addons/website_sale/data/data.xml:L82-85`), publicado por sitio solo si la vista `website_sale.extra_info` esta activa (`odoo/addons/website_sale/models/website.py:L959-960`). **El candado es presentacional**: no reemplaza ningun gate — `/shop/installation/submit` y `/shop/payment` siguen validando server-side (D5/D21). |
| D45 | ¿Que es "la direccion de instalacion"? | **Es la direccion de entrega del pedido** (`sale.order.partner_shipping_id`): la que el core ya pide en `/shop/address` y la que Field Service ya usa para la tarea del instalador (`enterprise/industry_fsm_sale/models/sale_order.py:L118`, `enterprise/industry_fsm_sale/models/project_task.py:L237`). **No** se crea otro modelo ni otro formulario de direccion: dos fuentes de verdad terminan con el instalador yendo a la direccion equivocada, y el core ya valida/normaliza esa. El link **editar** del Paso 1 apunta a `/shop/address?partner_id=<id>&address_type=delivery&callback=/shop/installation`: el `callback` (nativo del core, D12) es lo que devuelve al cliente **a nuestro paso** despues de guardar o descartar, en vez de dejarlo en `/shop/checkout`. |
| D46 | ¿Como se resuelve "entre calles"? | Campo nuevo **`res.partner.between_streets`** (Char), **un solo campo libre** ("Peru y Chile"), editable desde el Paso 1. `[ASUNCION]` **opcional**: es clave en provincia pero no puede frenar a quien compra en ciudad. La maqueta aprobada mostraba **dos** inputs: se unifica en **uno** — es un dato que el instalador lee de corrido y dos campos obligan a inventar la segunda esquina cuando la cuadra tiene una sola referencia. Va en el **partner** (no en el pedido) porque describe el domicilio, no la venta. |
| D47 | ¿Donde van las indicaciones para el instalador? | Campo nuevo **`sale.order.installation_notes`** (Text, "Notes for the installer", opcional), editable en el Paso 1. Va en el **pedido** y no en el partner porque es de **esta** instalacion ("porton negro, timbre PB, avisar antes de subir"), no del domicilio para siempre. Se propaga a la **descripcion de la tarea de FSM** junto con `between_streets`: el instalador lee el tablero de Field Service, no la ficha del contacto. |
| D48 | ¿Como se sabe que el Paso 1 esta cumplido? | Campo **`sale.order.installation_address_confirmed`** (Boolean, `copy=False`, default `False`) que setea el boton **Confirm address** del Paso 1, junto con el guardado de `between_streets` + `installation_notes`. **Vuelve a `False`** ante cualquier cambio posterior de la direccion: `sale.order.write()` (cambia `partner_shipping_id`) y `res.partner.write()` (se editan los campos de domicilio del partner de envio), molde literal del core (`odoo/addons/website_sale/models/res_partner.py:L58`). Default `False` → **no hace falta migracion**: los pedidos viejos solo tienen que apretar el boton. |
| D49 | ¿Como se escriben esos campos desde el frontend publico? | **Solo** por nuestra ruta `/shop/installation/submit` (rama `confirm_installation_address`), con `sudo()` **acotado campo por campo** — el visitante publico no escribe `res.partner` ni `sale.order` — y con **truncado server-side** del largo (`installation_notes` 1000, `between_streets` 100). **NO** se extiende `res.partner._get_frontend_writable_fields()`: esa lista es un **filtro de entrada** de `_parse_form_data()` (`odoo/addons/portal/controllers/portal.py:L594`, `:L598`), y como el formulario de direccion del core **no renderiza** `between_streets`, el campo nunca llega por ahi — sumarlo seria codigo sin consumidor (minimal footprint). Si algun dia se decide meterlo en el form del core, ahi si hay que sumarlo, con el molde `odoo/addons/website_sale/models/res_partner.py:L40` (que **suma** al `super()`; ojo: ese override **no** lleva `@api.model`, aunque la base si — `odoo/addons/portal/models/res_partner.py:L10`). |
| D50 | ¿La confirmacion de la direccion bloquea el pago? | `[ASUNCION]` **Si**: `_get_installation_errors()` suma un mensaje mas ("Please confirm the installation address."). Se reusa el gate que ya existe (D5) en vez de inventar otro, y evita el estado incoherente "Paso 1 pendiente + Paso 3 habilitado" para quien agendo por otro camino (link, backoffice). Criterio conservador: bloquea de mas, nunca de menos. Si el cliente prefiere lo contrario, se saca **esa sola linea** y el Paso 3 queda colgado solo de turno + fotos (el Paso 2 sigue bloqueado igual por D44). |
| D51 | ¿Cuantas fotos y de que? | **3**: (1) frente de la puerta con la manija, (2) canto/espesor, (3) marco. **No existe "desde adentro"**: la tercera columna placeholder (recuadro con icono) se elimina. La guia suma **3 ejemplos de "asi no"**: borrosa/oscura, cortada, tapada por la mano. El minimo real del carrier ya es `installation_min_photos = 3`, asi que el texto por defecto que decia "necesitamos ver 2 cosas" **contradecia el dato**: se corrige en el modulo (texto por defecto) y en produccion como dato (D42 / T11). El **gate** sigue siendo `installation_min_photos` del carrier (hoy `3`): la guia es didactica y el progreso dice *"N de `installation_min_photos`"*, no un 3 horneado. |
| D52 | ¿Donde van los avisos (pago, duracion, garantia, pilas)? | **Repartidos en el bloque donde aplican**, no todos juntos arriba: duracion (2 a 4 h) → Paso 2; condicion de pago → Paso 3; **garantia + pilas en un renglon corto** al pie del acordeon. El renglon de pilas sigue la regla de D31/D41 (condicional a `includes_free_batteries`), pero ahora es **una sola linea con `t-if`/`t-else`**: las dos versiones pasan a ser mutuamente excluyentes **por construccion**, con lo que el defecto que vigila CA37 deja de ser posible. |
| D53 | ¿Como se habla en el paso? | **Una sola voz: voseo**. Hoy convive "Subi/Elegi/Agenda" con "Ayudanos/Sube/Asegurate/Abre" (dos traductores distintos). Los strings **nuevos van en ingles con `_()`** (AGENTS.md) y la voz se fija en la **traduccion** `i18n/es_419.po`, el locale que el modulo ya usa; las entradas viejas con "tu/usted" se reescriben ahi mismo. |
| D54 | ¿Como se evita repetir el intro en la pagina de la cita? | Condicionando por **carrito**, no por URL: `appointment.type._is_installation_checkout_source()` devuelve `True` cuando `request.cart` requiere instalacion **con ese** tipo de cita, y el override de `appointment_info` apaga tambien en ese caso el bloque nativo de `message_intro`. **Por que no un parametro en la URL de "Agendar"**: el flujo nativo navega varias veces (calendario → `/appointment/<id>/info?...` que arma el **core**) y el parametro **se pierde** en el camino. `request.cart` esta disponible en cualquier pagina del frontend (`odoo/addons/website_sale/models/ir_http.py:L32`). El camino del **link compartido** (sin carrito) sigue viendo el intro arriba del calendario (D8). |
| D55 | ¿De donde salen las fotos de la guia? | De las **6 fotos reales** que entrego el cliente, que hoy viven **fuera del repo** en `/home/leandro/Descargas/nokey-propuesta-fuente/mk/` como **PNG de 240–540 KB**: `foto-ok-frente.png` (600×800), `foto-ok-canto.png` (600×800), `foto-ok-marco.png` (600×800), `foto-no-borrosa.png` (600×804), `foto-no-cortada.png` (600×804), `foto-no-obstruida.png` (600×773). Se **convierten a JPEG** (calidad ~82, ancho maximo 600 px) y se copian al repo en `static/src/img/` con nombres estables: `photo_ok_front.jpg`, `photo_ok_edge.jpg`, `photo_ok_frame.jpg`, `photo_bad_blurry.jpg`, `photo_bad_cropped.jpg`, `photo_bad_obstructed.jpg` (sin prefijo `installation_`: ya viven dentro de `static/src/img/` del modulo; las de **medidas** A/B **no se renombran** — diff minimo). Las dos de ejemplo viejas (`installation_example_lock.jpg`, `installation_example_door_edge.jpg`) **se dan de baja** junto con sus `msgid` de alt y pie. **Criterio de baja** (corregido tras revision, el rango de lineas fijo quedaba incompleto): **todas** las entradas de `i18n/es_419.po` cuyo `#:` apunte a `…installation_photo_examples` (no un rango de lineas — el archivo se reconstruye completo en T10). Nunca se linkean externas (AGENTS.md). |
| D56 | ¿El mapa de confirmacion del punto entra en este cambio? | **No**: es **etapa aparte (issue Plane #69)**. La maqueta aprobada lo muestra al pie del Paso 1, pero necesita proveedor de mapas, geocoding y coordenadas en el pedido — nada de eso entra aca. Este cambio cierra el Paso 1 con el boton **Confirm address**; el mapa se sumara despues, dentro del mismo bloque. |

## Alcance

### Incluye

**Envio con instalacion (existente)**
- Opt-in por metodo de envio (tipo de cita + fotos minimas) y campos espejo en el pedido.
- Paso de checkout condicional `/shop/installation` — hoy, **3 bloques tipo acordeon** (direccion, turno + fotos, pago) con guia y subida de fotos.
- Gate de pago (sin cita o sin fotos no se paga) con redireccion al paso.
- Copia de las fotos a la Cita y a la tarea de FSM; titulo estable de la tarea.
- Invitacion automatica al portal al confirmar.
- Formato de respuesta validado en las preguntas de cita (cliente + servidor) y guia de medidas junto a la pregunta.
- **Textos del cliente configurables por tipo de cita** (D42): checklist "antes de agendar" desde el campo nativo `message_intro` y consigna de las fotos desde `installation_photos_message`, con el texto por defecto del modulo como respaldo, en los dos caminos; en el tipo de cita del link el checklist se sube **arriba del calendario**, y en el checkout se lee **dentro del Paso 2** y **no se repite** en la pagina del turno (D54).
- Camino sin eCommerce: cita por link compartido → tarea de FSM creada/sincronizada por el modulo.
- Paso de checkout como dato por website (`post_init_hook` / `uninstall_hook`).
- **Marca correcta del correo de recordatorio de la cita** (D43): el layout de notificacion
  (logo/colores) usa la compañia del pedido que origino la cita y, en su defecto, la del
  organizador o de quien la creo — no la del usuario que corre el cron de alarmas.

**Pilas incluidas sin costo (feature del *Plan del cambio en curso*)**
- Configuracion por producto (`free_battery_product_id`, `free_battery_qty` en la UoM del producto de pila) y opt-in por metodo de envio (`includes_free_batteries`).
- Generacion automatica, agregada por producto de pila, de la linea de pedido en **$0**, sincronizada de forma idempotente en el carrito web, en el backend (onchange) y al confirmar.
- Defensa del precio 0 y del descuento 0 en todos los caminos de recomputo del core.
- Linea visible pero no editable en el carrito, con auto-curacion si el cliente la manipula por el endpoint.
- Texto del checkout condicional (pilas incluidas vs. pilas a cargo del cliente).
- Suite inicial de tests de los flujos troncales de esta feature.

**Paso de instalacion en 3 bloques + guia de fotos definitiva (feature del *Plan del cambio en curso*)**
- Paso `/shop/installation` reestructurado en **3 bloques tipo acordeon** (direccion · turno y
  fotos · pago), con el estado de cada bloque (tilde / numero / candado) calculado en el servidor.
- **Direccion de instalacion = direccion de entrega del pedido** (`partner_shipping_id`), mostrada
  en resumen con link "editar" al paso del core, mas los dos datos que el core no tiene:
  **entre calles** (`res.partner.between_streets`) e **indicaciones para el instalador**
  (`sale.order.installation_notes`), cerrados con el boton *Confirm address*
  (`installation_address_confirmed`).
- **Propagacion al instalador**: entre calles + indicaciones en la **descripcion de la tarea de
  Field Service** (la direccion ya la toma el nativo de `partner_shipping_id`).
- **Guia de fotos definitiva**: 3 tomas "asi si" (frente, canto, marco) y 3 "asi no" (borrosa,
  cortada, tapada), con las fotos reales del cliente; progreso "N de <minimo>"; texto por defecto
  de la consigna alineado al minimo real (3 y no 2).
- **Avisos repartidos** por bloque (duracion, pago, garantia/pilas) y **una sola voz (voseo)** en
  `i18n/es_419.po`.
- **Sin repetir** el intro (`message_intro`) en la pagina de la cita cuando se llega desde el
  checkout; por el link compartido se sigue viendo.

### NO incluye

- **Publicar los productos de pila en el sitio**: no se necesita (la linea se crea server-side); si el funcional los publica, el comportamiento no cambia (D29/D30).
- **Usar `optional_product_ids` / `accessory_product_ids` para las pilas**: es otro mecanismo y peor para el requerimiento — el cliente tendria que agregarlas a mano y pagarlas.
- **Override de `_get_estimated_weight` / `_match_weight`** para excluir la linea del peso. *Omision deliberada, verificada*: las pilas tienen `weight` NULL, el carrier de instalacion tiene `max_weight = 0` (sin limite) y no hay reglas de tarifa por peso → no cambia ninguna tarifa. Ademas, el metodo que castiga los productos sin peso, `_get_invalid_delivery_weight_lines` (`odoo/addons/delivery/models/sale_order_line.py:L36`), **solo lo llaman las integraciones de carriers de terceros de enterprise** (`delivery_dhl_rest`, `delivery_ups_rest`, `delivery_usps_rest`, `delivery_sendcloud`, `delivery_bpost`, `delivery_easypost` y sus versiones legacy) y el test del core (`odoo/addons/delivery/tests/test_delivery_cost.py:L295`): con un carrier `fixed` **ninguno de esos caminos se ejecuta**. **No "arreglar" sin cambiar antes esa configuracion** (si algun dia se instala un carrier de tercero real, revisar esta omision).
- **Override de `_get_update_prices_lines()`** (`odoo/addons/delivery/models/sale_order.py:L49` lo hace para las lineas de envio). *Omision deliberada, verificada*: no solo es redundante — `_recompute_prices()` → `_compute_price_unit(force)` → `_reset_price_unit()` → `_get_display_price()` (`odoo/addons/sale/models/sale_order_line.py:L623`) ya devuelve 0 — sino que es **preferible dejar la linea DENTRO del recordset**: asi le llega el `lines_to_recompute.discount = 0.0` de `_recompute_prices` (`odoo/addons/sale/models/sale_order.py:L1379`). Excluirla habria dejado pegado un `discount` viejo.
- **Xpath sobre `should_show_quantity_selector`** (patron de `website_sale_loyalty`). *Omision deliberada*: redundante — con `_is_sellable() == False`, `odoo/addons/website_sale/views/templates.xml:L3002` ya cae en la rama `t-else` (input readonly, sin botones `-`/`+`).
- **Override de `_recompute_cart()`** (precedente del modulo hermano). *Omision deliberada*: las cantidades solo cambian por caminos que ya llaman a `_verify_cart_after_update()`, y el precio 0 lo garantiza `_get_display_price()`; el hermano lo necesita porque su descuento depende de los totales que se recomputan ahi.
- **Override de `_remove_delivery_line()`**. *Omision deliberada*: sus dos llamadores relevantes ya estan enganchados — `_verify_cart_after_update()` (`odoo/addons/website_sale/models/sale_order.py:L674`, camino `only_services`) y `_set_delivery_method()` (`:L853`).
- **Campo de "origen" de la linea (que cerradura la genero) ni modelo hijo o2m**: la reconciliacion es por `(pedido, producto, flag)` (D16/D17); un campo de origen no tendria consumidor.
- **Descuento/precio por medio de pago**: es del modulo hermano `website_sale_payment_method_price`.
- **Costo de instalacion por distancia** (workstream 4 de la reunion): modulos aparte, en otro repo.
- **Mapa de confirmacion del punto** en el Paso 1 (esta en la maqueta aprobada): **etapa aparte,
  issue Plane #69** (D56). Necesita proveedor de mapas, geocoding y coordenadas en el pedido.
- **Segundo formulario de direccion / modelo propio de "direccion de instalacion"**: la direccion
  es `partner_shipping_id` y se edita en el paso del core (D45). Duplicarla daria dos fuentes de
  verdad y el instalador iria a la que quedo vieja.
- **Dos campos separados de "entre calles"** (como muestra la maqueta): se unifica en un solo
  campo libre (D46).
- **Pasos nuevos en el wizard del checkout**: el acordeon vive **dentro** del paso existente
  (D3/D44). Un paso por bloque multiplicaria requests y rompe el "veo todos los pasos" del cliente.
- **Migracion de datos** para `installation_address_confirmed`: es Boolean con default `False`; los
  carritos en curso solo tienen que apretar *Confirm address* (y no hay `migrations/` — ver
  *Notas de implementacion*).
- **Geocoding / validacion externa de la direccion**: el core ya valida los campos obligatorios
  (`_get_mandatory_delivery_address_fields`, `odoo/addons/portal/controllers/portal.py:L318`);
  este cambio no agrega validacion propia de direcciones.
- **Tocar `migrations/1.3.0/`**: ver *Notas de implementacion* (deuda conocida, declarada fuera de alcance por el usuario).

## Modelos

### Nuevos

No aplica: el modulo no define modelos propios, solo extiende modelos de `odoo/` y `enterprise/`.

### Extendidos

| Modelo | `_inherit` | Que se agrega |
|--------|-----------|--------------|
| `delivery.carrier` | `delivery.carrier` | Opt-in de instalacion (tipo de cita + fotos minimas) y **opt-in de pilas incluidas** (`includes_free_batteries`) + constrains de configuracion |
| `product.template` | `product.template` | **Configuracion de pilas del producto** (`free_battery_product_id`, `free_battery_qty`) + constrain de configuracion |
| **`res.partner`** *(nuevo en este cambio)* | `res.partner` | **Entre calles** (`between_streets`) y **reset de la confirmacion de direccion** cuando se edita el domicilio (D46, D48). La escritura desde el frontend la hace nuestra ruta con `sudo()` acotado: **no** se extiende `_get_frontend_writable_fields()` (D49) |
| `sale.order` | `sale.order` | Campos espejo de la instalacion, gate de pago, copia de fotos, invitacion al portal; agregacion y sincronizacion de las lineas de pilas + engaches de carrito/backend/confirmacion; **notas para el instalador, confirmacion de la direccion y estado de los 3 bloques del paso** (D44, D47, D48) |
| `sale.order.line` | `sale.order.line` | Deteccion de la linea de la reserva y titulo de la tarea de FSM; flag `is_free_battery_line` y las 5 defensas de precio/edicion; **entre calles + notas en la `description` de la tarea de FSM** (D47) |
| `appointment.type` | `appointment.type` | Proyecto de FSM para citas fuera del eCommerce, pedido de fotos y minimo, consigna de las fotos configurable (`installation_photos_message`) y **deteccion de "vengo del checkout"** para no repetir el intro (D54) |
| `appointment.question` | `appointment.question` | Formato de respuesta validado y marca de la guia de medidas |
| `calendar.booking` | `calendar.booking` | Aclaracion en la descripcion de la linea ("incluido en el metodo de envio") |
| `calendar.event` | `calendar.event` | Tarea de FSM de la cita agendada fuera del eCommerce + sincronizacion y fotos; **compañia del correo de la cita** (recordatorio) resuelta por el pedido/organizador (D43) |
| `website` | `website` | Paso de checkout condicional |

**Controllers** (`controllers/website_sale_installation_appointment.py`): `WebsiteSaleInstallation(WebsiteSale)`
(paso del checkout + overrides de pago) y `AppointmentInstallation(WebsiteAppointmentSale)` (validacion de
respuestas, fotos y vuelta al paso). **Con este cambio** el primero suma la rama de confirmacion de la
direccion en `/shop/installation/submit` y los valores de los 3 bloques en `_prepare_installation_values()`;
el segundo no cambia.

## Campos

| Modelo | Campo | Tipo | String | Requerido | Default | Restricciones |
|--------|-------|------|--------|-----------|---------|--------------|
| **`res.partner`** | **`between_streets`** *(nuevo)* | Char | Between streets | No | — | `[ASUNCION]` **opcional** (D46); `help` con ejemplo ("e.g. Peru and Chile"); visible en la ficha del contacto (backend) y en el Paso 1 del checkout; el POST publico lo **trunca a 100 caracteres** (D49) |
| `delivery.carrier` | `installation_appointment_type_id` | Many2one `appointment.type` | Installation Appointment Type | No | — | `ondelete="restrict"`; `_check_installation_appointment_type` |
| `delivery.carrier` | `installation_min_photos` | Integer | Minimum Installation Photos | No | `1` | `>= 0` (`_check_installation_min_photos`) |
| `delivery.carrier` | **`includes_free_batteries`** *(nuevo)* | Boolean | Includes Free Batteries | No | `False` | — |
| `product.template` | **`free_battery_product_id`** *(nuevo)* | Many2one `product.product` | Free Battery Product | No | — | `ondelete="restrict"`, **`check_company=True`** + domain de compañia (D38); `_check_free_battery_config` |
| `product.template` | **`free_battery_qty`** *(nuevo)* | Integer | Free Batteries Quantity | No | `0` | `>= 0`; va junto con el producto; en la **UoM del producto de pila** (`_check_free_battery_config`) |
| `product.template` | **`free_battery_uom_name`** *(nuevo)* | Char (related, no store) | Battery Unit | No | — | `related="free_battery_product_id.uom_name"`, `readonly=True` — **reusa el campo del core** (`odoo/addons/product/models/product_template.py:L123`, `uom_name = related='uom_id.name'`): un hop menos y precedente literal. Existe solo para **mostrar la UoM al lado de la cantidad** (riesgo funcional #1, D15): sin un campo, el XML no puede renderizar `free_battery_product_id.uom_id` |
| `sale.order` | `installation_appointment_type_id` | Many2one `appointment.type` | Installation Appointment Type | No | — | `related="carrier_id.installation_appointment_type_id"`, `readonly` |
| `sale.order` | `installation_required` | Boolean (compute) | Installation Required | No | — | `_compute_installation_required` (no store) |
| `sale.order` | `installation_booking_id` | Many2one `calendar.booking` (compute) | Installation Booking | No | — | `_compute_installation_booking_id` |
| `sale.order` | `installation_event_id` | Many2one `calendar.event` (compute) | Installation Appointment | No | — | `_compute_installation_event_id` |
| `sale.order` | `installation_photo_ids` | Many2many `ir.attachment` | Installation Photos | No | — | tabla `sale_order_installation_photo_rel`; `copy=False` |
| `sale.order` | `installation_photo_count` | Integer (compute) | Installation Photos Count | No | — | `_compute_installation_photo_count` |
| `sale.order` | **`installation_notes`** *(nuevo)* | Text | Notes for the installer | No | — | opcional; **`copy=False`** (es de **esta** venta, como `installation_photo_ids`); se propaga a la `description` de la tarea de FSM (D47); el POST publico lo **trunca a 1000 caracteres** (D49) |
| `sale.order` | **`installation_address_confirmed`** *(nuevo)* | Boolean | Installation Address Confirmed | No | `False` | **`copy=False`**; lo setea el boton del Paso 1 y lo **resetea** todo cambio posterior de la direccion (D48); default `False` → **sin migracion** |
| `sale.order.line` | **`is_free_battery_line`** *(nuevo)* | Boolean | Is a Free Battery Line | No | `False` | **sin `copy=`** (default `True` — D33, critico para el duplicado de pedidos); flag tecnico, no va en vistas |
| `appointment.type` | `installation_fsm_project_id` | Many2one `project.project` | Field Service Project | No | — | `domain=[('is_fsm','=',True)]` |
| `appointment.type` | `installation_request_photos` | Boolean | Ask for Site Photos | No | `False` | — |
| `appointment.type` | `installation_min_photos` | Integer | Minimum Site Photos | No | `0` | — |
| `appointment.type` | `installation_photos_message` | Html | Site Photos Message | No | — | `translate=True`, `sanitize_attributes=False` (espeja el `message_intro` nativo). Vacio = texto por defecto del modulo |
| `appointment.question` | `answer_format` | Selection | Answer Format | Si | `free` | `free`/`integer`/`decimal`/`phone`/`identification` |
| `appointment.question` | `installation_measure_guide` | Boolean | Show Measuring Guide | No | `False` | — |
| `calendar.event` | `installation_task_id` | Many2one `project.task` | Installation Task | No | — | `copy=False`, `ondelete="set null"`, `index="btree_not_null"` |

**Textos obligatorios de los campos nuevos de pilas** (el funcional los lee para configurar; la
ambiguedad de la UoM es el riesgo #1 de esta feature):

- `free_battery_qty`: `string="Free Batteries Quantity"`, `help` que diga **explicitamente** que la
  cantidad se expresa en la **unidad de medida del producto de pila elegido**, con ejemplo:
  *"…in the battery product's own unit of measure: for batteries sold in packs of 4, 1 means one pack (4 batteries)."*
  Si se lee como "cantidad de pilas" y el funcional escribe `4`, se despachan **16** pilas.
- `free_battery_product_id`: `help` que aclare que las pilas se agregan **sin cargo** solo si el
  metodo de envio elegido tiene *Includes Free Batteries*.
- `includes_free_batteries`: `help` que aclare que agrega las pilas configuradas en los productos del
  carrito a **$0** porque el costo ya esta cubierto por este metodo de envio, **y que avise de no
  repetir el pedido de pilas en el `message_intro` del tipo de cita** (es el unico lugar donde el
  funcional esta mirando en el momento exacto en que prende el flag).

## Metodos

### Existentes

> Los que **cambian con el plan en curso** (rediseño del paso) van marcados *(se extiende)*; el
> resto es current-state y no se toca.

#### `sale.order`
- `_compute_installation_required()` — `@api.depends('carrier_id.installation_appointment_type_id')`; `installation_required = bool(tipo de cita del carrier)`.
- `_compute_installation_booking_id()` / `_compute_installation_event_id()` — primera reserva / primera cita de las lineas cuyo `appointment_type_id` es el del carrier.
- `_compute_installation_photo_count()` — `len(installation_photo_ids)`.
- `_is_installation_required()` — `any(...)` sobre el recordset (lo usan controllers y templates).
- `_is_installation_scheduled()` — `bool(booking or event)`.
- `_get_installation_errors()` *(se extiende)* — lista de mensajes: **falta confirmar la direccion** (`[ASUNCION]` D50) / falta agendar / faltan N fotos. Devuelve `[]` si el pedido no requiere instalacion. Es el gate unico: lo consumen `_check_cart_is_ready_to_be_paid()`, `shop_payment()`, `_get_shop_payment_errors()` y el estado del **Paso 3** del acordeon.
- `_check_cart_is_ready_to_be_paid()` — **override**: `ValidationError` con los errores de instalacion antes del `super()`.
- `_action_confirm()` — **override**: `super()` primero (el nativo crea Cita y tarea) y despues `_sync_installation_photos()` + `_grant_portal_access_after_installation_sale()`. **No se toca en esta feature** (ver D27).
- `_sync_installation_photos()` / `_post_installation_photos(target)` — copian las fotos al chatter de la Cita y de las tareas (`sudo`, adjuntos copiados sin dueño).
- `_grant_portal_access_after_installation_sale()` — invitacion nativa al portal, idempotente, aislada en `savepoint`, con nota en el chatter ante cualquier problema.

#### `sale.order.line`
- `_is_installation_booking_line()` — la linea es la reserva de la instalacion del carrier del pedido.
- `_timesheet_create_task_prepare_values(project)` *(se extiende)* — **override** de `sale_project`: `name = "<pedido> - <tipo de cita>"` y, con este cambio, `description` con **entre calles + notas para el instalador** (D47).

#### `delivery.carrier`
- `_check_installation_appointment_type()` — `@api.constrains`: el tipo de cita debe tener paso de pago + producto, y ese producto generar tarea o tener precio.
- `_check_installation_min_photos()` — `@api.constrains`: `>= 0`.

#### `appointment.question`
- `_effective_answer_format()`, `_answer_input_attrs()`, `_validate_answer(value)` — formato efectivo, atributos HTML reales y validacion de servidor (entero/decimal/telefono/DNI-CUIT via `stdnum.ar`).

#### `calendar.event`
- `create()` / `write()` — **overrides**: generan la tarea de FSM de las citas con `installation_fsm_project_id` (aislado en savepoint) y la mantienen en linea al reprogramar/cancelar/desarchivar.
- `_installation_generate_fsm_task()`, `_installation_cancel_task()`, `_installation_restore_task()`, `_installation_post_photos(attachments)`.
- `_mail_get_companies(default=False)` — **override** (D43): resolvedor de "que compania es esta
  cita" — pedido que la origino (el mas viejo, no cancelado) > organizador (`user_id.company_id`) >
  quien la creo (`create_uid.company_id`) > `super()` con el `default`. Influye en `record_company_id`
  del `mail.message`, el alias domain del reply-to y el Return-Path — **no** en el logo/colores.
- `_notify_by_email_prepare_rendering_context(...)` — **override** (D43): el que **si** pinta el
  logo/colores del layout de notificacion (`render_context['company']` y `['website_url']`), llamando
  a `super()` y reusando `_mail_get_companies()` como resolvedor. Corrige el correo de
  **recordatorio** de la cita (Plane #38); el de confirmacion usa el mismo camino y no regresiona.
  La compañia resuelta se escribe con **`.sudo()`**, igual que el core (`odoo/addons/mail/models/mail_thread.py:L3660`):
  QWeb lee `company.name`/`uses_default_logo`/colores y `res.company` tiene reglas por grupo que
  acotan la lectura a las compañias del usuario (`odoo/odoo/addons/base/security/base_security.xml:L105-125`),
  asi que sin el `sudo()` un empleado que postea en el chatter de una cita de **otra** compañia
  (caso real: cita por link compartido, sin pedido, organizador de la otra compañia) se comeria un
  `AccessError` al renderizar. El recordatorio no estaba afectado (el cron corre como root), pero el
  chatter manual si.

#### `calendar.booking`
- `_get_description()` — **override**: agrega "Included in the … shipping method — no extra charge." a la descripcion de la linea de la reserva.

#### `website`
- `_get_allowed_steps_domain()` — **override**: saca `/shop/installation` del dominio cuando el carrito no requiere instalacion.

#### Controllers
- `shop_installation()` / `shop_installation_submit()` *(se extiende)* / `shop_installation_photo_remove()` — paso del checkout y endpoints publicos de fotos. `shop_installation_submit()` suma la rama **`confirm_installation_address`** (D49).
- `shop_payment()` / `_get_shop_payment_errors(order)` — **overrides**: redireccion al paso y errores de pago.
- `appointment_type_id_form()` / `appointment_form_submit()` / `_get_customer_partner()` / `_redirect_to_payment()` — **overrides** del flujo de citas (errores de formato, fotos, partner del carrito, vuelta al paso).
- `create_installation_photos(uploads, available_slots, res_model, res_id)` — helper compartido de validacion/creacion de adjuntos.
- `_prepare_installation_values(order_sudo)` *(se extiende)* — valores del paso; suma el estado de los 3 bloques, el partner de envio, la URL de edicion de la direccion y el href del paso siguiente.

---

### Nuevos — feature de pilas incluidas

### `ProductTemplate._check_free_battery_config()`

- **Proposito**: frenar la configuracion de pilas que no se puede aplicar.
- **Decoradores**: `@api.constrains("free_battery_product_id", "free_battery_qty")`
- **Logica** (por registro):
  1. Si `free_battery_qty < 0` → `ValidationError`.
  2. Si hay `free_battery_product_id` **sin** `free_battery_qty` (`<= 0`), o `free_battery_qty > 0` **sin** producto → `ValidationError` (los dos campos van juntos; si no, el opt-in queda a medias y nadie se entera).
  3. Si `free_battery_product_id.product_tmpl_id == self` → `ValidationError` (un producto no puede ser su propia pila).
- **Retorna**: `None`
- **Errores**: `ValidationError` con `_()` en ingles, mencionando el producto y que la cantidad va en la UoM del producto de pila.

### `SaleOrder._get_free_battery_needs()`

- **Proposito**: cuantas pilas de cada producto de pila deberia llevar el pedido sin cargo.
- **Decoradores**: ninguno
- **Logica**:
  1. `self.ensure_one()`.
  2. Si `not self.carrier_id.includes_free_batteries` → devolver `{}` (no-op total; el metodo de envio manda).
  3. Recorrer `self.order_line` **excluyendo**: `is_free_battery_line`, `is_delivery`, `display_type` (secciones/notas), `is_downpayment` y `_is_global_discount()` (esas dos ultimas por robustez: no son productos vendidos).
     Las lineas con `combo_item_id` **no** se excluyen: una cerradura dentro de un combo **si** aporta pilas (deseado). ⚠️ Si se configuran pilas en la plantilla del combo **y** en el item, se cuentan dos veces (D40).
  4. Saltear las lineas con `product_uom_qty <= 0` (D39: un pedido negativo generaria una linea de pilas negativa y `stock_delivery` haria un movimiento de **devolucion** de pilas nunca entregadas).
  5. Por linea: `tmpl = line.product_id.product_tmpl_id`; si `tmpl.free_battery_product_id` y `tmpl.free_battery_qty > 0` → acumular `needs[tmpl.free_battery_product_id] += tmpl.free_battery_qty * line.product_uom_qty`.
     **Sin conversion de UoM de la cerradura** (D40, asuncion declarada: hoy se venden en Units).
     **Filtro defensivo de compañia** (D38): saltear el producto de pila cuyo `company_id` no sea compatible con `order.company_id`, en vez de dejar que el `create()` de la linea tire `UserError` de compañia y devuelva un **500** al visitante publico.
  6. Descartar las entradas que quedaron en `<= 0` y devolver el dict (**agrupado por producto de pila**: dos cerraduras que comparten la pila dan una sola entrada con la suma — D16).
- **Retorna**: `dict {product.product: float}`
- **Errores**: ninguno (es de lectura; sirve igual en onchange sobre registros `NewId`). **Nunca debe romper el request del carrito**: ante configuracion incompatible, saltea.

### `SaleOrder._prepare_free_battery_line_vals(battery_product, qty)`

- **Proposito**: vals de la linea gratis, compartidos por el camino de base de datos y el de onchange.
- **Decoradores**: ninguno
- **Logica**:
  1. `self.ensure_one()`.
  2. `name` = descripcion de venta del producto + `"\n"` + `_("Included with your shipping method — no extra charge.")`, armado **en el idioma del cliente** (`with_context(lang=...)`, molde `odoo/addons/delivery/models/sale_order.py:L207` o `self._get_lang()` como `enterprise/website_appointment_sale/models/sale_order.py:L83`; si no, un pedido armado en el backend por un usuario en otro idioma deja la descripcion en ingles en una factura es_419).
     ⚠️ **Sin el nombre del carrier** (D35): el sync solo escribe `product_uom_qty`, asi que un nombre horneado quedaria mintiendo al pasar a otro envio que tambien incluya pilas. El criterio de "no se lee como un segundo cargo" se mantiene igual que en `calendar_booking._get_description()`; se ve tambien en la factura (D28).
  3. `vals = {"product_id": battery_product.id, "product_uom_qty": qty, "price_unit": 0.0, "is_free_battery_line": True, "name": name}`.
  4. `sequence` = `self.order_line[-1].sequence + 1` si hay lineas (va al final), como `_prepare_delivery_line_vals`.
  5. **NO** incluir `product_uom_id`: el ORM toma la UoM propia del producto (D15). **NO** incluir `linked_line_id` (D19). **NO** incluir `order_id`: lo agrega el camino de base de datos (el de onchange usa `Command.create` dentro del o2m).
  6. **NO** forzar `tax_ids`: los impuestos los resuelve el compute del core (impuestos del producto + posicion fiscal). Sobre `price_unit = 0` el impuesto liquida 0.
- **Retorna**: `dict`
- **Errores**: ninguno

### `SaleOrder._sync_free_battery_lines()`

- **Proposito**: reconciliar las lineas de pilas del pedido contra lo que deberia haber (crear / ajustar / borrar), de forma **idempotente**.
- **Decoradores**: ninguno
- **Logica**:
  1. Si `self.env.context.get("wsia_skip_battery_sync")` → return. Es un guard **puramente defensivo**: hoy **no existe** ningun camino de recursion real (ningun `create`/`write` de linea vuelve a entrar a los engaches); se deja por simetria con `wspmp_skip_recompute` del modulo hermano y para que un engache futuro no se muerda la cola. No leerlo como "hay una recursion".
  2. Recorrer el recordset y, **por cada `order`**, saltear las que tengan `state` fuera de `("draft", "sent")` (D32).
  3. `needs = order._get_free_battery_needs()`; `existing = order.order_line.filtered("is_free_battery_line")`.
  4. **Congelar** (`frozen`) las lineas de `existing` con `qty_invoiced` o `qty_delivered` distintos de 0: no se escriben ni se borran (D36). El resto es material de reconciliacion.
  5. Recorrer `needs`: tomar la **primera** linea reconciliable de ese producto (`existing.filtered(...)[:1]`); si existe y la cantidad difiere (`float_compare` con la precision `Product Unit`) → `write({"product_uom_qty": qty})`; si no existe → `create(vals | {"order_id": order.id})`.
  6. `to_unlink` = las lineas reconciliables de `existing` que (a) son de un producto que ya no esta en `needs`, o (b) son duplicados del producto (se conserva una sola por producto) → `unlink()`.
  7. Todas las escrituras con `.sudo()` y `with_context(wsia_skip_battery_sync=True)`.
     `sudo` porque lo dispara el **visitante publico** del checkout, que no puede crear/escribir/borrar `sale.order.line` (mismo criterio y molde que `_create_delivery_line` del core y que el modulo hermano).
- **Retorna**: `None`
- **Errores**: ninguno propio. Se recalcula **desde cero** en cada llamada: correrlo dos veces seguidas no cambia nada.
- **Por que el guard de facturado/entregado**: `state in ('draft','sent')` **no** implica "nada facturado". `_check_line_unlink` (`odoo/addons/sale/models/sale_order_line.py:L1452`) solo bloquea con `state == 'sale'`, asi que un pedido facturado devuelto a presupuesto ("Set to Quotation") volveria a `draft` con `qty_invoiced != 0` y el sync podria escribir/borrar esas lineas. El core hace exactamente esta distincion en `_remove_delivery_line` (`odoo/addons/delivery/models/sale_order.py:L59`).

### `SaleOrder._verify_cart_after_update()`

- **Proposito**: engache **canonico** del carrito web (su docstring del core dice que es donde van los chequeos globales, una vez por request).
- **Decoradores**: ninguno (override)
- **Logica**: `res = super()._verify_cart_after_update()` → `self._sync_free_battery_lines()` → `return res`.
- **Retorna**: lo que devuelva el `super()`
- **Errores**: ninguno
- **Cubre**: agregar/quitar cerraduras, cambiar cantidades y la **auto-curacion** si el cliente manipula la linea gratis por `/shop/cart/update` (D21). Precedente: `website_sale_loyalty`.

### `SaleOrder._set_delivery_method(delivery_method, rate=None)`

- **Proposito**: reaccionar al cambio de metodo de envio (aparecer o desaparecer las pilas).
- **Decoradores**: ninguno (override)
- **Logica**: `res = super()._set_delivery_method(delivery_method, rate=rate)` → `self._sync_free_battery_lines()` → `return res`.
- **Retorna**: lo que devuelva el `super()` (`None` en el core)
- **Errores**: ninguno
- **Nota**: es el embudo de la seleccion de envio **del checkout** (`shop_set_delivery_method`), asi que cubre tanto pasar al envio con pilas como salir de el — **incluido el camino de quitar el envio**, donde `set_delivery_line()` no se llama (`odoo/addons/website_sale/models/sale_order.py:L864`). Por eso este override **no** se reemplaza por el de `set_delivery_line()`: son complementarios (D37).

### `SaleOrder.set_delivery_line(carrier, amount)`

- **Proposito**: cubrir el flujo **real** de asignacion de envio en el backoffice.
- **Decoradores**: ninguno (override)
- **Logica**: `res = super().set_delivery_line(carrier, amount)` → `self._sync_free_battery_lines()` → `return res`.
- **Retorna**: lo que devuelva el `super()` (`True` en el core)
- **Errores**: ninguno
- **Por que**: el modo normal de poner envio en el backend es el boton **Add shipping** → wizard `choose.delivery.carrier` → `order.set_delivery_line(carrier, amount)` (`odoo/addons/delivery/models/sale_order.py:L67`), que escribe por **`write`**: los `@api.onchange` **no corren**. Sin este engache, el vendedor manda el **presupuesto en PDF sin las pilas** y estas aparecen solas al confirmar → el pedido confirmado no coincide con lo que firmo el cliente (D37).

### `SaleOrder._onchange_free_battery_lines()`

- **Proposito**: que el pedido armado en el **backend** (venta telefonica, sin eCommerce) tambien traiga la linea de pilas.
- **Decoradores**: `@api.onchange("order_line", "carrier_id")`
- **Logica** (todo **en memoria**, sin tocar la base):
  1. `needs = self._get_free_battery_needs()`; `free_lines = self.order_line.filtered("is_free_battery_line")`.
  2. Por producto de `needs`: si hay linea gratis de ese producto, `line.product_uom_qty = qty` (asignacion en memoria); si no, acumular un `Command.create(self._prepare_free_battery_line_vals(product, qty))`.
  3. Acumular `Command.delete(line.id)` para las lineas gratis que sobran (producto que ya no aplica o duplicados).
  4. `self.order_line = delete_commands + create_commands` — mismo patron que el core usa para las lineas de combo en `@api.onchange('order_line')`.
- **Retorna**: `None`
- **Errores**: ninguno
- **Notas**:
  - **No** se puede reusar `_sync_free_battery_lines()` aca: en un onchange `self` es un registro virtual (`NewId`) y un `create()` real escribiria en la base. Precedente del core: la sincronizacion de lineas de combo (`odoo/addons/sale/models/sale_order.py:L936`), y `delivery` ya tiene su propio `@api.onchange('order_line', ...)` (`odoo/addons/delivery/models/sale_order.py:L42`).
  - **Naming**: se llama `_onchange_free_battery_lines` y **no** `_onchange_order_line` a proposito — ese nombre **pisaria** el onchange del core que sincroniza las lineas de combo (`odoo/addons/sale/models/sale_order.py:L936`). Es una desviacion deliberada de la convencion `_onchange_<campo>` de `AGENTS.md`.
  - Este engache cubre la **carga interactiva**; el boton *Add shipping* del backoffice lo cubre `set_delivery_line()` y la red final es `action_confirm()` (D37).

### `SaleOrder.action_confirm()`

- **Proposito**: red de seguridad — que ningun pedido se confirme con las pilas desincronizadas (backend sin onchange disparado, importaciones, API).
- **Decoradores**: ninguno (override **nuevo**; el override existente de `_action_confirm()` no se toca)
- **Logica**: `self._sync_free_battery_lines()` **antes** del `super()` (con el `state` todavia `draft`/`sent`, altas y bajas son legales) → `return super().action_confirm()`.
- **Retorna**: lo que devuelva el `super()`
- **Errores**: ninguno
- **Por que aca y no en `_action_confirm()`**: `action_confirm()` hace `self.write(self._prepare_confirmation_values())` **antes** de llamar a `_action_confirm()` (`odoo/addons/sale/models/sale_order.py:L1183`), asi que dentro de `_action_confirm()` el `state` ya es `'sale'` y el `unlink()` chocaria con el guard nativo `_unlink_except_confirmed`.

### `SaleOrder._cart_find_product_line(*args, **kwargs)`

- **Proposito**: que un alta manual de la misma pila **no se fusione** con la linea gratis.
- **Decoradores**: ninguno (override)
- **Logica**: `lines = super()._cart_find_product_line(*args, **kwargs)` → `return lines.filtered(lambda line: not line.is_free_battery_line)`.
- **Retorna**: recordset `sale.order.line`
- **Errores**: ninguno
- **Por que**: el domain del core (`odoo/addons/website_sale/models/sale_order.py:L430`) matchea por `product_id` + `product_uom_id` + custom attrs + `linked_line_id` + `combo_item_id`, y **no** conoce nuestro flag: `_cart_add` sumaria la cantidad sobre la linea gratis y se perderia el precio 0 de la parte gratuita. Filtrando, el alta manual crea una linea **separada y paga** (D24). Precedente de estilo: `enterprise/website_appointment_sale/models/sale_order.py:L58`.

### `SaleOrderLine._get_display_price()`

- **Proposito**: **la** garantia del precio 0 (D22).
- **Decoradores**: ninguno (override)
- **Logica**: si `self.is_free_battery_line` → `return 0.0`; si no, `return super()._get_display_price()`.
- **Retorna**: `float`
- **Errores**: ninguno
- **Por que es el load-bearing**: `_compute_price_unit` (`odoo/addons/sale/models/sale_order_line.py:L587`) recalcula al cambiar `product_id`/`product_uom_id`/`product_uom_qty` — y esta linea cambia de cantidad cada vez que cambia la cantidad de cerraduras. Crear con `price_unit=0` **no alcanza**: `_add_precomputed_values` (`:L1358`) copia `price_unit` a `technical_price_unit`, con lo que `has_manual_price` da `False` y la linea **no** cuenta como precio manual. Y el camino forzado (`force_price_recomputation=True`) tambien termina en `_reset_price_unit()` (`:L619`) → `_get_display_price()` (`:L623`). Este override cubre **los dos caminos**.

### `SaleOrderLine._compute_pricelist_item_id()`

- **Proposito**: que la linea gratis no arrastre descuento (D23).
- **Decoradores**: los del `super()` (`@api.depends` del core; no se redeclaran)
- **Logica**: separar `free_lines = self.filtered("is_free_battery_line")`; `super(SaleOrderLine, self - free_lines)._compute_pricelist_item_id()`; `free_lines.pricelist_item_id = False`. Molde literal: `odoo/addons/delivery/models/sale_order_line.py:L59`.
- **Retorna**: `None`
- **Errores**: ninguno
- **Por que**: `_recompute_prices()` (`odoo/addons/sale/models/sale_order.py:L1372`) hace `lines.discount = 0.0` + `_compute_discount()`, y `_compute_discount` sale por `continue` cuando `not line.pricelist_item_id._show_discount()` (`odoo/addons/sale/models/sale_order_line.py:L807`). Sin esto, una tarifa `percentage` dejaria `discount > 0` y prenderia la **columna Descuento en todo el PDF** y el precio tachado en el carrito.

### `SaleOrderLine._check_validity()`

- **Proposito**: defensa en profundidad contra `prevent_zero_price_sale`.
- **Decoradores**: ninguno (override)
- **Logica**: si `self.is_free_battery_line` → `return` (temprano, sin llamar al `super()`); si no, `return super()._check_validity()`.
- **Retorna**: `None`
- **Errores**: ninguno (justamente evita el `UserError` del core)
- **Por que**: en el camino normal no se llama (la linea se crea con `sudo().create()`, fuera de `_cart_add`/`_cart_update_line_quantity`), pero el endpoint publico `/shop/cart/update` con el `line_id` real llega a `_cart_update_order_line` → `_check_validity` (`odoo/addons/website_sale/models/sale_order.py:L554`) y, con `prevent_zero_price_sale` prendido, el `UserError` **abortaria el request antes de que la re-sincronizacion pueda auto-curar** (D21).

### `SaleOrderLine._is_reorder_allowed()`

- **Proposito**: que "Volver a pedir" no re-agregue la pila (D25).
- **Decoradores**: ninguno (override)
- **Logica**: `return super()._is_reorder_allowed() and not self.is_free_battery_line`.
- **Retorna**: `bool`
- **Errores**: ninguno
- **Por que**: el filtro del core (`odoo/addons/website_sale/controllers/reorder.py:L33` → `_is_reorder_allowed` → `_show_in_cart()`) solo excluye `is_delivery`/`display_type`/`combo_item_id`: la linea gratis pasa y se re-agregaria **sin** el flag y **a precio de tarifa**.

### `SaleOrderLine._is_sellable()`

- **Proposito**: que la linea se vea pero **no sea editable ni clickeable** en el carrito, con independencia de si el producto de pila esta publicado (D20/D29).
- **Decoradores**: ninguno (override)
- **Logica**: `return super()._is_sellable() and not self.is_free_battery_line`.
- **Retorna**: `bool`
- **Errores**: ninguno
- **Que se obtiene gratis, sin tocar templates** (todos verificados en `odoo/addons/website_sale/`):
  - `odoo/addons/website_sale/views/templates.xml:L3002` — el selector cae en la rama `t-else`: input **readonly y sin botones `-`/`+`**.
  - `odoo/addons/website_sale/views/templates.xml:L2829` — el link al producto deja de ser clickeable (correcto: la pila no se vende sola).
  - `odoo/addons/website_sale/models/sale_order_line.py:L122` — `_should_show_strikethrough_price()` queda falsy: **tambien** suprime el precio tachado (segunda capa, complementaria de `pricelist_item_id = False`, que es el que apaga la columna Descuento del PDF).
  - `odoo/addons/website_sale/views/templates.xml:L3066` — oculta el precio por unidad de medida.
  - `odoo/addons/website_sale/controllers/cart.py:L388` — excluye la linea de las sugerencias de "pedidos anteriores".
- **Por que el override existe igual**: hoy `_is_sellable()` ya daria `False` **por accidente de datos** (los productos de pila estan despublicados), pero el funcional evaluaba publicarlos; con `is_published = True` el selector de cantidad volveria a ser editable. El override hace el comportamiento independiente de la publicacion. Precedentes en la propia cadena de dependencias: `enterprise/website_appointment_sale/models/sale_order_line.py:L19` (linea de la cita: visible pero no editable, el mismo requisito) y `odoo/addons/website_sale_loyalty/models/sale_order_line.py:L38`.

### `SaleOrderLine._check_availability()`

- **Proposito**: que el control de stock del eCommerce no trabe el checkout por la linea gratis (D34).
- **Decoradores**: ninguno (override de `website_sale_stock`)
- **Logica**: si `self.is_free_battery_line` → `return True`; si no, `return super()._check_availability()`.
- **Retorna**: `bool`
- **Errores**: ninguno (justamente evita el `ValidationError` del gate de pago)
- **Por que**: `website_sale_stock` es `auto_install: True` y esta **instalado** en la base del cliente. Su `_check_cart_is_ready_to_be_paid` (`odoo/addons/website_sale_stock/models/sale_order.py:L124`) tira `ValidationError` si alguna linea falla `_check_availability()` (`odoo/addons/website_sale_stock/models/sale_order_line.py:L39`: `is_storable and not allow_out_of_stock_order and cart_qty > free_qty`). Y la condicion de falla **ya esta armada**: *Pilas AA - Energizer* (tmpl 411) tiene `allow_out_of_stock_order = false` con **stock 0** (la AAA, 412, sigue en `true`). La linea gratis se crea server-side, sin pasar por `_verify_updated_quantity`, asi que entra completa: el cliente quedaria **sin poder pagar** por un producto que no eligio y que **no puede eliminar** (la auto-curacion lo repone). Es un checkout muerto sin salida del lado del cliente, por eso se resuelve en codigo y no como requisito de configuracion.
- **Notas**:
  - El aviso de **aprovisionar stock** de pilas sigue vigente (el picking las mostrara como no disponibles y ademas se **apaga el mail de carrito abandonado**, ver Edge cases), pero eso es logistica, no un bloqueo del checkout.
  - **`website_sale_stock` no va en `depends`** (arrastraria `stock`). El override gana el MRO por el orden de carga (`depth` mayor); el razonamiento y el riesgo latente estan en **D34**, y **CA32 es el tripwire** si alguna vez se invierte.

---

### Nuevos — rediseño del paso de instalacion (plan en curso)

> **Descartado: override de `ResPartner._get_frontend_writable_fields()`** (D49). Esa lista es el
> **filtro de entrada** de `_parse_form_data()` (`odoo/addons/portal/controllers/portal.py:L594`,
> `:L598`): solo escribe los campos que **llegan en el form** y estan en la lista. El formulario de
> direccion del core **no renderiza** `between_streets`, asi que el campo nunca viaja por ahi y el
> override no tendria consumidor (minimal footprint). Nuestra ruta escribe el campo **explicitamente**
> con `sudo()` y no depende de la lista. Si alguna vez se agrega el input al form del core, ahi si hay
> que sumarlo, con el molde `odoo/addons/website_sale/models/res_partner.py:L40`.

### `ResPartner.write(vals)`

- **Proposito**: que editar el domicilio **despues** de confirmarlo tire abajo la confirmacion del
  Paso 1 (D48).
- **Decoradores**: ninguno (override)
- **Logica**:
  1. `res = super().write(vals)`.
  2. Si `vals` no toca ninguno de `{"name", "street", "street2", "city", "zip", "state_id",
     "country_id", "between_streets"}` → `return res` (guard barato, igual forma que el `write` del
     core, `odoo/addons/website_sale/models/res_partner.py:L58`).
  3. Buscar `sale.order` con `.sudo()`: `state in ('draft', 'sent')`, `website_id != False`,
     `partner_shipping_id in self.ids`, `installation_address_confirmed = True` → escribir
     `installation_address_confirmed = False`.
- **Retorna**: lo que devuelva el `super()`
- **Errores**: ninguno
- **Nota de orden**: nuestra propia ruta escribe **primero el partner y despues el flag** — al reves,
  este override apagaria la confirmacion que se acaba de encender. Es un requisito de secuencia, no
  un guard de contexto (no hace falta uno).

### `SaleOrder.write(vals)`

- **Proposito**: idem cuando cambia **el contacto** de envio (el cliente elige otra direccion en
  `/shop/address`).
- **Decoradores**: ninguno (override)
- **Logica** (orden exacto, para no depender de que el `super()` deje el valor viejo):
  1. **Antes** del `super()`, si `"partner_shipping_id" in vals`:
     `affected = self.filtered(lambda o: o.installation_address_confirmed and o.partner_shipping_id.id != int(vals["partner_shipping_id"]))`
     (si `vals` no trae el campo, `affected` queda vacio y el override es un no-op).
  2. `res = super().write(vals)`.
  3. `affected.write({"installation_address_confirmed": False})` — **re-entrada segura**: esa segunda
     escritura no trae `partner_shipping_id`, asi que el paso 1 la deja pasar sin recursion.
- **Retorna**: `res` (lo que devuelva el `super()`)
- **Errores**: ninguno
- **Por que hacen falta los dos overrides**: son dos caminos distintos — **elegir otra** direccion
  (cambia `partner_shipping_id` del pedido) y **editar la misma** (cambia el `res.partner`). El core
  usa exactamente esta division en su propio `write` de partner y en el compute de
  `partner_shipping_id` (`odoo/addons/sale/models/sale_order.py:L406`).
- ⚠️ **Limite conocido y aceptado**: `partner_shipping_id` es **computado almacenado**
  (`odoo/addons/sale/models/sale_order.py:L406`). Si cambia por **recompute** al cambiar `partner_id`,
  el valor nuevo no pasa por `vals` y el override **no se entera**: la confirmacion no se cae. Se
  acepta — en el checkout el cliente se identifica (paso 250) **antes** del paso 400, asi que ese
  recompute ya ocurrio cuando el Paso 1 se confirma; y si el backoffice cambia el cliente de un pedido
  con instalacion, lo revisa a mano.

### `SaleOrder._get_installation_block_states()`

- **Proposito**: **unico** lugar donde se decide que bloque esta hecho, cual esta abierto y cual
  bloqueado (D44). La plantilla solo pinta.
- **Decoradores**: ninguno
- **Logica**:
  1. `self.ensure_one()`.
  2. `address = "done" if self.installation_address_confirmed else "todo"`.
  3. `schedule`: `"locked"` si `address != "done"`; `"done"` si `_is_installation_scheduled()` **y**
     `installation_photo_count >= carrier_id.installation_min_photos`; si no, `"todo"`.
  4. `payment`: `"todo"` (habilitado) si **no** hay `_get_installation_errors()`; si no, `"locked"`.
  5. `open` = el **primer** bloque en `"todo"` en el orden `address` → `schedule` → `payment`; si no
     hay ninguno en `"todo"`, `"payment"`. (No existe el caso "los tres resueltos": `payment` solo
     puede valer `"todo"` —habilitado— o `"locked"`, nunca `"done"`.)
- **Retorna**: `dict` — `{"address": str, "schedule": str, "payment": str, "open": str}` con estados
  `done` / `todo` / `locked`.
- **Errores**: ninguno
- **Nota**: `payment` se calcula con el gate que **ya existe** (`_get_installation_errors()`), asi que
  el acordeon y el servidor **no pueden** discrepar **en lo que es de instalacion** (turno, fotos,
  direccion confirmada): si el Paso 3 se ve con candado, `/shop/payment` redirige seguro (D5). Al
  reves **no** es garantia total: el core valida ademas carrier y direccion de entrega
  (`_check_cart_is_ready_to_be_paid`, `odoo/addons/website_sale/models/sale_order.py:L914-930`), asi
  que un Paso 3 abierto significa "no falta nada **de instalacion**", no "el pago no va a rebotar por
  ningun motivo". El candado es **presentacional**; la validacion vive en el servidor.

### `SaleOrder._get_installation_task_notes()`

- **Proposito**: armar el bloque de texto que el instalador lee en la tarea de FSM (entre calles +
  indicaciones), en un solo lugar reusable.
- **Decoradores**: ninguno
- **Logica**: `self.ensure_one()`; **reasigna `self`** (no una variable nueva) a
  `self.with_context(lang=self.company_id.partner_id.lang or self.env.lang)` — molde de
  `_prepare_free_battery_line_vals` — y junta, si estan, `partner_shipping_id.between_streets`
  ("Between streets: …") y `installation_notes` ("Notes for the installer: …"); devuelve `""` si no
  hay nada. **Fix de revision (M3)**: guardar el context en una variable separada (`order = self.
  with_context(...)`) es **inerte**, porque `_()` resuelve el idioma leyendo el `self` del frame del
  **llamador** (`odoo/tools/translate.py`), no la variable a la que se lo asigna — de ahi la
  reasignacion literal de `self`.
  - **Escapado obligatorio**: los dos valores los escribe el **visitante publico**, y el destino
    (`project.task.description`) es un campo **Html** (`odoo/addons/project/models/project_task.py:L153`).
    Cada valor pasa por `markupsafe.escape()` y el resultado se arma como `Markup` (`<br/>` entre
    lineas); nunca se concatena texto crudo del cliente en el HTML.
  - **Idioma de las etiquetas**: el de la **compañia** (`self.company_id.partner_id.lang`, con
    fallback a `self.env.lang`), **no** el del comprador. El lector es la cuadrilla interna que abre
    la tarea en Field Service; el criterio del idioma del cliente
    (`_prepare_free_battery_line_vals`) aplica a lo que el cliente lee —descripcion de linea,
    factura—, no a esto.
- **Retorna**: `Markup` (HTML seguro; vacio → `""`)
- **Errores**: ninguno

### `SaleOrderLine._timesheet_create_task_prepare_values(project)` *(se extiende)*

- **Proposito**: que entre calles + indicaciones lleguen a la **tarea del instalador**.
- **Decoradores**: ninguno (override ya existente)
- **Logica**: al `values` que ya devuelve (con el `name` estable) se le **antepone** al
  `description` el resultado de `order_id._get_installation_task_notes()` cuando la linea es la de la
  reserva (`_is_installation_booking_line()`) y hay algo que decir.
  - **Fix de revision (C1, critico)**: el `description` que trae `super()` **ya es HTML** (armado
    por `sale_project`/`website_appointment_sale` como `str` plano), asi que se concatena envuelto
    en `Markup(description)`. Sin ese `Markup()`, `Markup.__add__(str)` **escapa** el operando
    derecho y el instalador ve el codigo fuente del bloque de preguntas y respuestas del turno en
    vez del HTML renderizado — verificado en `odoo shell` comparando la concatenacion con y sin el
    fix. No reintroduce riesgo: el HTML que se envuelve no lo escribe el visitante (eso ya lo
    escapa `_get_installation_task_notes()` con `markupsafe.escape()` linea por linea), lo arma el
    propio core.
- **Retorna**: `dict`
- **Errores**: ninguno
- **Por que la descripcion y no el chatter**: el instalador abre la tarea en el tablero de Field
  Service; la descripcion se ve en el formulario, el chatter hay que desplegarlo. La **direccion** no
  se copia: el nativo ya pone `partner_id = partner_shipping_id` cuando el proyecto es FSM
  (`enterprise/industry_fsm_sale/models/sale_order.py:L123`).
- ⚠️ **Limite conocido**: si el producto de la cita usara `task_template_id`, el core arma los vals
  por otro camino (`_prepare_task_template_vals`, `odoo/addons/sale_project/models/sale_order_line.py:L285`)
  que **no pasa** por este override. Hoy el producto de reserva no usa plantilla (ver *Edge cases*).

### `AppointmentType._is_installation_checkout_source()`

- **Proposito**: saber si el visitante llego a la pagina del turno **desde el checkout**, para no
  repetirle el intro que ya leyo (D54).
- **Decoradores**: ninguno
- **Logica**:
  1. `self.ensure_one()`.
  2. `cart = getattr(request, "cart", None) if request else None` — misma forma defensiva que
     `website._get_allowed_steps_domain()` (el metodo tambien corre fuera de un request web).
  3. `return bool(cart) and cart._is_installation_required() and cart.installation_appointment_type_id == self`.
- **Retorna**: `bool`
- **Errores**: ninguno
- **Por que el carrito y no un parametro en la URL**: entre el boton "Agendar" y el formulario del
  turno el **core** navega solo (`/appointment/<id>` → `/appointment/<id>/info?...`), asi que un
  parametro propio se pierde. `request.cart` lo setea el frontend en cada request
  (`odoo/addons/website_sale/models/ir_http.py:L32`), incluidas las paginas de `appointment`.

### `WebsiteSaleInstallation._save_installation_address(order_sudo, post)` *(controller)*

- **Proposito**: guardar los dos datos del Paso 1 y cerrar el bloque (D48/D49).
- **Decoradores**: ninguno (helper del controller)
- **Logica**:
  1. **Guarda de carrito anonimo (obligatoria)**: si `order_sudo._is_anonymous_cart()`
     (`odoo/addons/website_sale/models/sale_order.py:L880`) → **no se escribe nada**: se deja el aviso
     "cargá primero la dirección" (con link a `/shop/address`) y se vuelve al paso **sin** marcar la
     confirmacion. **Por que**: `/shop/installation` es `auth="public"` y `shop_installation()` solo
     corre `_check_cart()`
     (`extra-addons/odoo_customization_sunra/website_sale_installation_appointment/controllers/website_sale_installation_appointment.py:L82`,
     `:L84`), asi que en un carrito anonimo `partner_shipping_id` es el **partner publico compartido**:
     escribirle `between_streets` ensuciaria un contacto global de la base para todos los visitantes.
  2. `partner_sudo = order_sudo.partner_shipping_id`; si no hay → mismo camino que el punto 1 (aviso +
     link, sin confirmar). No deberia pasar (Direccion es `sequence 250` y el paso, `400`).
  3. `partner_sudo.sudo().write({"between_streets": (post.get("between_streets") or "").strip()[:100]})`
     — **solo ese campo**, nunca `post` completo (el visitante es publico), y **truncado** server-side.
     **Solo si cambio** (fix de revision M8, D48 conservador): si el valor truncado es igual al
     `between_streets` ya guardado, **no** se escribe — re-confirmar sin tocar el campo no debe
     disparar el reset de `installation_address_confirmed` de `ResPartner.write()` en **otros**
     carritos `draft` del mismo partner (este pedido se re-confirma explicitamente en el punto 4).
  4. `order_sudo.write({"installation_notes": (post.get("installation_notes") or "").strip()[:1000],
     "installation_address_confirmed": True})` — **despues** del partner (ver `ResPartner.write`), con
     el mismo truncado.
  5. Devolver `request.redirect(INSTALLATION_STEP_HREF)`.
- **Retorna**: respuesta HTTP (redirect al paso)
- **Errores**: ninguno propio. `between_streets` es opcional (`[ASUNCION]` D46): vacio tambien
  confirma. Carrito anonimo → no confirma y avisa (punto 1).
- **`sudo()` justificado**: el que aprieta el boton es el visitante publico del checkout, que no
  escribe `res.partner` ni `sale.order`. El alcance esta acotado **por campo** (dos campos) y **por
  largo** (100 / 1000 caracteres), nunca por `post`.
- **Señalizado tambien en el render (GET), no solo al escribir**: esta guarda evita el POST invalido,
  pero sin una señal para el `GET` inicial el cliente anonimo veria el resumen del partner publico y
  el `<form>` como si pudiera completarlos, y recien al enviar se enteraria. `_prepare_installation_values()`
  expone `installation_address_missing` (mismo criterio: `_is_anonymous_cart() or not partner_shipping_id`)
  para que el Paso 1 pinte el aviso **en lugar de** el resumen y el `<form>` desde el primer render.

### `WebsiteSaleInstallation.shop_installation_submit(**post)` *(se extiende)*

- **Proposito**: una sola ruta POST para el paso; se le suma la rama de la direccion.
- **Decoradores**: los que ya tiene (`@route`, `auth="public"`, `methods=["POST"]`, `website=True`)
- **Logica** (orden de las ramas, sin cambiar las existentes):
  1. `_check_cart` + `_is_installation_required()` (igual que hoy).
  2. `remove_photo_id` → quitar foto (igual que hoy).
  3. **`confirm_installation_address` → `_save_installation_address(order_sudo, post)`** *(nuevo)*.
  4. Fotos: igual que hoy. El formulario de fotos manda **siempre** `stay_on_step` (ahora en la
     plantilla, no solo desde el JS), asi que la subida **siempre vuelve al paso**: la unica salida
     hacia el pago es el link del Paso 3.
  5. **Rama final `return request.redirect(self._get_installation_next_step_href())`**
     (`controllers/website_sale_installation_appointment.py:L120`, `:L125`, y el helper en `:L288`):
     con la plantilla nueva ya **no la alcanza la UI** (el input oculto viaja siempre). **Se conserva
     igual**, como fallback defensivo para un POST sin `stay_on_step` (pagina cacheada de la version
     anterior, cliente que postea el form a mano) — borrarla obligaria a reescribir el flujo por una
     ganancia nula. Queda **documentada como fallback**, no como camino vivo.
- **Retorna**: respuesta HTTP
- **Errores**: ninguno nuevo
- **Nota**: el paso pasa a tener **dos `<form>`** (direccion y fotos). Cada uno postea a la misma
  ruta con su marcador; no comparten estado.

### `WebsiteSaleInstallation._prepare_installation_values(order_sudo)` *(se extiende)*

- **Proposito**: pasarle a la plantilla todo lo que necesita para pintar los 3 bloques, sin logica en
  el XML.
- **Logica**: a lo que ya arma (`errors`, `warnings`, `appointment_type`, `installation_slot_label`,
  `installation_photos`, `max_photos`, `min_photos`, `photo_count`) se le suman:
  - `block_states` = `order_sudo._get_installation_block_states()` (D44),
  - `installation_address` = `order_sudo.partner_shipping_id` (para el resumen; el formato de la
    direccion lo da `_display_address()`, `odoo/odoo/addons/base/models/res_partner.py:L1196`),
  - `installation_address_missing` = `order_sudo._is_anonymous_cart() or not order_sudo.partner_shipping_id`
    *(hallazgo del `analyze`, corregido)*: sin este valor la plantilla no tenia forma de saber, **en
    el `GET`**, que el partner de envio es el publico compartido — el cliente anonimo veia el resumen
    y el `<form>` del Paso 1 como si pudiera completarlos, y el aviso de `_save_installation_address()`
    recien aparecia al enviar. Con el flag, el Paso 1 pinta el aviso "cargá primero la direccion" +
    link a `/shop/address` **en lugar de** el resumen y el `<form>`, desde el primer render,
  - `installation_address_edit_url` =
    `/shop/address?partner_id=<id>&address_type=delivery&callback=/shop/installation` (los dos primeros
    parametros, forma literal del core, `odoo/addons/website_sale/views/templates.xml:L3658`; el
    **`callback` es lo que devuelve al cliente a nuestro paso** despues de guardar o descartar —
    `odoo/addons/website_sale/controllers/main.py:L1234`, `:L1236` y `:L1184`— y viaja nativo por
    `shop_address(**query_params)`, `odoo/addons/website_sale/controllers/main.py:L1099`, sin codigo
    nuestro).
  - El href del Paso 3 **no se agrega**: ya viene en `next_website_checkout_step_href` del
    `request.website._get_checkout_step_values()` que el metodo mezcla al final
    (`odoo/addons/website_sale/models/website.py:L981`, el dict en `:L1012`). ⚠️
    `current_website_checkout_step_href` es un **string**; los que son **record** son
    `previous_website_checkout_step` y `next_website_checkout_step` (no existe
    `current_website_checkout_step`). El **rotulo** del bloque 3 sale de
    `next_website_checkout_step.name`, no de la constante "Payment" (D44).
- **Retorna**: `dict`
- **Errores**: ninguno

## Vistas

### `delivery.carrier` form (`view_delivery_carrier_form`, hereda `delivery.view_delivery_carrier_form`)
- Dentro del grupo `name="delivery_details"`: `installation_appointment_type_id`, `installation_min_photos` (`invisible="not installation_appointment_type_id"`) y **`includes_free_batteries`** (nuevo, mismo grupo — es donde el funcional ya configura este metodo de envio).

### `product.template` form (`product_template_view_form`, hereda `product.product_template_form_view`) — **nueva vista**
- Dentro del grupo `name="upsell"` ("Upsell & Cross-Sell") de la pestaña **Sales** (`odoo/addons/product/views/product_views.xml:L143`), junto a `optional_product_ids` (`odoo/addons/sale/views/product_template_views.xml:L12`) y `accessory_product_ids` (`odoo/addons/website_sale/views/product_views.xml:L169`):
  - `free_battery_product_id`, con `domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]"` (misma forma que el vecino `optional_product_ids`, `odoo/addons/sale/views/product_template_views.xml:L16`; la auto-referencia la cubre el constrain, no el domain, porque el campo apunta a `product.product` y el `id` del form es el del template).
  - `free_battery_qty`, seguido de **`free_battery_uom_name`** (`readonly`): la UoM real del producto de pila queda **a la derecha del numero**, para que `1` se lea como "un paquete de 4" y nunca como "una pila" (D15, riesgo funcional #1). **Mecanismo unico**: es un campo related del modelo, no un label estatico ni un `t` auxiliar. **Implementacion real** (correccion post-review sobre la spec original, que decia `nolabel="1"` en un solo `<field>`): `<label for="free_battery_qty" invisible="not free_battery_product_id"/>` + `<div class="o_row" invisible="not free_battery_product_id"><field name="free_battery_qty"/><field name="free_battery_uom_name" readonly="1" class="oe_inline"/></div>` — el patron canonico de Odoo para pegar una UoM al numero (molde: `is_storable`/`qty_available` + `uom_name` en `odoo/addons/stock/views/product_views.xml:L182-199`), mejor que la alternativa literal de la spec.

### `sale.order` form (`view_order_form`, hereda `sale.view_order_form`)
- `installation_required` invisible (para las condiciones), y pestaña **Installation** (`invisible="not installation_required"`) con tipo de cita, reserva, cita y las fotos (`widget="many2many_binary"`).
- **Nuevo en este cambio**: en esa misma pestaña, `installation_notes` (textarea) y `installation_address_confirmed` (**readonly**: lo setea el cliente en el checkout, el backoffice solo lo mira) — el vendedor que atiende por telefono tiene que poder leer lo que escribio el cliente sin abrir el portal.
- La linea de pilas **no** agrega nada a esta vista: es una linea de pedido normal con el flag tecnico oculto.

### `res.partner` form (`res_partner_view_form`, hereda `base.view_partner_form`) — **nueva vista**
- `between_streets` junto a los campos de direccion (dentro del bloque de `street`/`street2`/`city`), para que el backoffice y la cuadrilla lo vean en la ficha del contacto. Es un dato del **domicilio**, no de la venta (D46).
- Archivo nuevo `views/res_partner_views.xml`, declarado en `data` del manifest.

### `appointment.type` form / `appointment.question` form y list
- Tirador de `sequence` y `answer_format` en la lista de preguntas del tipo de cita; `installation_fsm_project_id`, `installation_request_photos`, `installation_min_photos` en `group name="right_details"`.
- `installation_photos_message` en la pestaña **Comunicacion** (`page name="messages"`), despues de `message_confirmation` y con su separador: es donde el funcional ya entra a editar los mensajes del cliente. **Sin `invisible`**: el tipo del eCommerce pide las fotos en el paso del checkout (tiene `installation_request_photos` apagado) y necesita el texto igual.
- `answer_format` (oculto para `select`/`radio`/`checkbox`) e `installation_measure_guide` en la ficha de la pregunta, y en su lista.

### Templates del checkout / carrito
- `installation` (`/shop/installation`) — **reestructurado en 3 bloques tipo acordeon** (D44). De
  arriba hacia abajo: encabezado ("Let's get your installation ready" + "Three steps. Each one opens
  when you finish the previous one."), el `oe_structure` que ya existia, los avisos/errores de arriba
  (**acotados**, ver abajo) y el **acordeon** con los tres bloques.
  - **Un mensaje, un solo lugar**: la **razon del candado** de cada bloque ("Se habilita al completar
    el paso N", "falta el turno", "faltan fotos", "falta confirmar la direccion") **reemplaza** al
    `alert` superior para esos estados: se leen **en el bloque que los resuelve**. El `alert` de arriba
    queda **solo** para los errores de submit que no pertenecen a ningun bloque (archivo que no es
    imagen, > 10 MB, mas de 10 fotos), que ya viajan por `warnings` de sesion. Asi el cliente no lee
    dos veces lo mismo con dos redacciones distintas.
  - **Cada bloque se pinta con su estado de `block_states`** (`done` → tilde + resumen en el
    encabezado; `todo` → numero; `locked` → candado + "Complete step N first"), y **el bloqueado no
    renderiza su cuerpo**.
  - **Paso 1 · Installation address** — resumen de `installation_address` (nombre +
    `_display_address()`, `odoo/odoo/addons/base/models/res_partner.py:L1196`), link **editar** a
    `installation_address_edit_url` (paso del core, D45/D12) y un `<form>` propio con
    `between_streets` (input) e `installation_notes` (textarea), boton **Confirm address**
    (`name="confirm_installation_address"`) y el `csrf_token`. Con el bloque en `done`, el encabezado
    muestra la direccion resumida + entre calles. **Con `installation_address_missing` en `True`**
    (carrito anonimo o, defensivamente, sin `partner_shipping_id`) el cuerpo **no** muestra el resumen
    ni el `<form>`: en su lugar, un aviso "cargá primero la dirección" con link a `/shop/address`
    (hallazgo del `analyze`, corregido — antes solo se cortaba al escribir, no en el render).
  - **Paso 2 · Appointment and photos** — `message_intro` del tipo de cita **si esta cargado** (aca,
    no arriba de todo: es el "antes de agendar"), la linea de **duracion** (2 a 4 h, D52), el boton
    **Schedule the installation** (con **margen superior**: hoy queda pegado al texto) o el slot
    elegido + **Change**, y debajo las fotos: `installation_photos_message` +
    `installation_photo_examples` + las fotos ya subidas + el input + el **progreso "N de `min_photos`"**
    (barra `progress` de Bootstrap, sin JS). El `<form>` de fotos lleva **`stay_on_step` como input
    oculto** (antes lo inyectaba solo el JS) y su boton de submit pasa a decir **Upload photos**: la
    navegacion al pago vive solo en el Paso 3.
    ⚠️ **Contrato con el JS (T07 no lo puede romper)**: el `<form>` conserva el atributo
    `data-installation-photos="1"` y sigue **dentro** del contenedor `id="shop_installation"` —los dos
    juntos son el `selector` de la Interaction
    (`static/src/js/installation_photos.js:L17`)— y el boton de submit conserva
    `name="installation_continue"` (`:L33`), que es el que el JS deshabilita mientras sube. **Solo
    cambia la etiqueta visible** del boton, no su `name` ni el contenedor.
  - **Paso 3 · Payment** — con candado mientras haya `errors`; habilitado, es un `<a>` a
    `next_website_checkout_step_href` (el mismo valor que usa el boton principal del core,
    `odoo/addons/website_sale/views/templates.xml:L3432`) con la condicion de pago (D52). El **rotulo**
    del bloque sale de `next_website_checkout_step.name`, **no** de la constante "Payment": entre el
    400 y el 999 puede colarse el paso nativo *Extra Info* (`/shop/extra_info`, `sequence 500`,
    `odoo/addons/website_sale/data/data.xml:L82-85`) si la vista `website_sale.extra_info` esta activa
    en el sitio (`odoo/addons/website_sale/models/website.py:L959-960`); el href ya es el correcto, el
    titulo tambien tiene que serlo (D44). El paso sigue con `show_navigation_button = False`: el boton principal del core **no** se dibuja y no hay
    dos botones compitiendo.
  - **Renglon corto al pie** (D52): garantia (1 año) + pilas, esto ultimo con `t-if`/`t-else` sobre
    `order.carrier_id.includes_free_batteries` — "van incluidas" / "tenes que tener 4 u 8 AA/AAA el
    dia de la instalacion". **Las dos versiones pasan a ser mutuamente excluyentes por construccion**
    (misma linea), asi que el defecto que vigilaba CA37 (el `<li>` historico conviviendo con el
    aviso) **ya no puede ocurrir**: desaparece el `<li>` suelto dentro del `t-else` del checklist y
    desaparece el bloque aparte del aviso. Sigue llevando **`o_not_editable`** (D42: tocarlo desde el
    editor web congela una copia COW por sitio).
  - **`o_not_editable` a nivel contenedor**: no alcanza con el renglon del pie ni con marcar cada
    elemento suelto — la clase va en el `div.accordion#installation_accordion` (cubre toda la prosa
    **estatica** de los tres bloques: encabezados, razones del candado, duracion, condicion de pago,
    garantia y pilas, incluidos los avisos que un primer intento elemento-por-elemento dejo afuera —
    fix de revision M6) y, aparte, en el `div` que envuelve el template `installation_photo_examples`
    (fotos reales del cliente, el template que ya sufrio la copia COW en produccion) — por la misma
    trampa COW que documenta D42 (un retoque desde el editor web congela la copia del sitio y el
    modulo deja de poder actualizarla). Quedan **fuera a proposito**: el `oe_structure` (existe
    justamente para que el cliente ponga snippets) y los `t-field` de `message_intro` /
    `installation_photos_message` (son **campos**, se editan en el backend).
  - Debajo del acordeon queda el link **Back** al paso anterior (`previous_website_checkout_step`),
    como hoy.
  ⚠️ **Impacto en `i18n/es_419.po`**: el `msgid` del `<li>` historico de las pilas y los textos del
  checklist por defecto **se dan de baja** (el checklist por defecto deja de existir; el aviso de
  pilas renace como el renglon del pie con `t-if`/`t-else`, D52/D53) — a diferencia de D31, que se
  habia cuidado de no tocarlos. Las entradas viejas quedan obsoletas y se reemplazan por las nuevas
  (nodos de texto nuevos, no una edicion in-place), todas en **voseo** (T07(e)/T10).
- `installation_photos_message`: sigue el patron `t-if="not is_html_empty(...)"` / `t-else` (texto por
  defecto del modulo), llamado con `t-call` desde los **dos** caminos — el paso del checkout y el
  formulario de la cita del link. **Cambia el texto por defecto** (D51): pasa a pedir **3 fotos**
  (frente con la manija, canto, marco), una sola cantidad, sin mencionar "desde adentro" ni "2
  cosas". El registro cargado en produccion se corrige **como dato** (D42, T11).
- `installation_measure_guide`: sin cambios (los diagramas A/B siguen junto a la pregunta marcada).
- `installation_photo_examples` — **redefinido** (D51/D55): dos filas en vez de una.
  - **"Asi si"** (3 columnas, con tilde): `photo_ok_front.jpg` (frente de la puerta con la manija),
    `photo_ok_edge.jpg` (canto/espesor), `photo_ok_frame.jpg` (marco). Desaparece la tercera columna
    placeholder ("desde adentro": recuadro con icono), que ya no existe como toma.
  - **"Asi no"** (3 columnas, con cruz): `photo_bad_blurry.jpg` (borrosa u oscura),
    `photo_bad_cropped.jpg` (cortada, falta parte), `photo_bad_obstructed.jpg` (tapada por la mano),
    cada una con su motivo en el pie.
  - Las fotos son **verticales (~3:4)**: el `aspect-ratio: 12 / 5` actual (apaisado) se reemplaza por
    uno vertical con `object-fit: cover`, si no recorta justo lo que hay que mirar.
  - Lo llaman con `t-call` los dos caminos (checkout y formulario del link): un solo lugar para
    mantener.
- `appointment_form` (hereda `appointment.appointment_form`): errores de formato, `enctype` multipart, guia de medidas junto a la pregunta marcada, input de fotos (con `installation_photos_message` arriba) e inputs con `type`/`pattern` reales.
- `appointment_info` (hereda `appointment.appointment_info`): el bloque nativo de `message_intro` del
  final (`enterprise/appointment/views/appointment_templates_appointments.xml:L231`) se apaga en
  **dos** casos: (a) en el tipo de cita **del link** (`installation_fsm_project_id`), donde el
  checklist **sube arriba del calendario** para leerse antes de elegir el turno; y (b) *(nuevo, D54)*
  cuando el visitante **viene del checkout** (`appointment_type._is_installation_checkout_source()`),
  porque ya lo leyo en el Paso 2 — ahi no se agrega nada arriba, simplemente no se repite. El bloque
  que se agrega arriba sigue yendo **fuera** de `o_appointment_info_main` (que es `o_not_editable`)
  para que el `t-field` siga siendo editable en linea.
- `address_form_fields` / `delivery_address_list`: sin "Nombre de la empresa"; titulo "Installation address" cuando el pedido requiere instalacion.
- **Nuevo en `views/website_sale_templates.xml`**: heredar `website_sale.cart_lines` para ocultar el **boton Eliminar** de la linea gratis, en los dos nodos (los dos tienen `name=` estable, y la variable del bucle es `line` — `odoo/addons/website_sale/views/templates.xml:L2880`):
  - desktop: `//div[@name='o_wsale_cart_line_button_container']//a[hasclass('js_delete_product')]` → `t-if="not line.is_free_battery_line"` (`:L2954`)
  - mobile: `//div[@name='o_wsale_cart_line_button_container_mobile']//button[hasclass('js_delete_product')]` → `t-if="not line.is_free_battery_line"` (`:L2974`)
  - ⚠️ **No** ocultar los contenedores completos: el de desktop tambien contiene el selector de cantidad cuando la linea es de combo.
  - El **selector de cantidad** y el **link al producto** no necesitan xpath: los cubre `_is_sellable()`.

> **XML IDs de las vistas**: las **nuevas** de este cambio (`res_partner_view_form`,
> `product_template_view_form`) siguen la convencion de AGENTS.md (`{model}_view_{tipo}`, con el `name`
> espejando el id). Las **existentes** (`view_delivery_carrier_form`, `view_order_form`, heredadas de
> los ids del core) **no se renombran**: cambiarles el XML ID obligaria a un `ir.model.data` de
> migracion por pura cosmetica, contra la regla de **diff minimo**. Queda dicho para que no se lea como
> un olvido en la proxima review.

### Assets
- `static/src/js/installation_photos.js` (Interaction, selector `#shop_installation form[data-installation-photos]`) **se mantiene y se simplifica**: deja de inyectar el input oculto `stay_on_step` (ahora lo lleva la plantilla) y conserva el feedback ("Uploading photos…") y el deshabilitado del boton. **Sin JS nuevo**: el acordeon es `collapse` de Bootstrap, que ya viene en `web.assets_frontend`, y los estados los renderiza el servidor.
- Sin CSS/SCSS propio: los estados se pintan con utilidades de Bootstrap y clases del tema.

### Datos
- `website.checkout.step` `checkout_step_installation` (`sequence 400`, `step_href /shop/installation`), replicado por website en el `post_init_hook` y limpiado en el `uninstall_hook`.

## Seguridad

- **Modelos nuevos**: ninguno → **no hay cambios en ACLs, grupos ni record rules** (no aplica).
- Los campos nuevos viven en modelos del core y heredan su seguridad: `product.template` y
  `delivery.carrier` son de configuracion (`sales_team.group_sale_manager` / `base.group_system` segun
  el modelo), `sale.order.line.is_free_battery_line` es un flag tecnico que no se expone en vistas.
- **`sudo()` justificado** (y comentado en el codigo, como el resto del modulo): la creacion, escritura
  y borrado de las lineas de pilas las dispara el **visitante publico** del checkout, que no tiene
  permisos sobre `sale.order.line`. Es el mismo criterio que `_create_delivery_line` del core
  (`odoo/addons/delivery/models/sale_order.py:L239`) y que `_apply_payment_price_rule` del modulo
  hermano. No expone datos: la operacion es sobre el carrito del propio visitante.
- El `sudo()` **no** relaja el gate de negocio: lo que decide si se agregan pilas es la configuracion
  (`includes_free_batteries` + configuracion del producto), no el usuario.
- **`sudo()` de la confirmacion de la direccion** (cambio en curso): el visitante publico del checkout
  no escribe `res.partner` ni `sale.order`, asi que `_save_installation_address()` escribe con `sudo()`
  **campo por campo** (`between_streets` en el partner de **envio del propio carrito**; `installation_notes` +
  `installation_address_confirmed` en **ese** pedido). Nunca se pasa el `post` completo a un `write()`:
  eso convertiria la ruta en un editor arbitrario de contactos. Mismo criterio que el core, que acota lo
  escribible desde el frontend con `_get_frontend_writable_fields()`
  (`odoo/addons/portal/controllers/portal.py:L594`) — nosotros **no** extendemos esa lista (D49): la
  acotacion la hace la propia ruta.
- **Carrito anonimo**: el paso es `auth="public"` y `shop_installation()` solo valida el carrito
  (`_check_cart`). En un carrito anonimo `partner_shipping_id` es el **partner publico compartido**, asi
  que `_save_installation_address()` **frena antes de escribir** con `order_sudo._is_anonymous_cart()`
  (`odoo/addons/website_sale/models/sale_order.py:L880`): avisa que hay que cargar la direccion, linkea
  a `/shop/address` y **no** confirma. Sin esa guarda, cualquier visitante podria escribir
  `between_streets` en un contacto global de la base.
- **Limite de tamaño en el POST publico**: `installation_notes` se trunca a **1000** caracteres y
  `between_streets` a **100**, server-side, en `_save_installation_address()`. Los dos campos son de
  texto libre y el endpoint es publico: sin tope, un POST puede inflar la fila del pedido/contacto y el
  PDF/descripcion de la tarea que los reusa.
- `between_streets` es un campo mas de `res.partner`: hereda su seguridad (ACL/record rules del core) y
  no agrega modelos nuevos → **sigue sin haber cambios de ACLs, grupos ni record rules**.

## Reglas de negocio

**Envio con instalacion (existente)**
1. **RB01**: Un metodo de envio con `installation_appointment_type_id` exige agendar instalacion; sin el, el pedido es un envio normal y el paso no existe.
2. **RB02**: Un tipo de cita sin paso de pago o sin producto de reserva no puede asociarse a un metodo de envio → `ValidationError`.
3. **RB03**: Sin cita agendada, o con menos fotos que `installation_min_photos`, el carrito no se puede pagar (y `/shop/payment` redirige al paso).
4. **RB04**: Reagendar reemplaza la reserva anterior: queda **una sola** linea de instalacion en el carrito.
5. **RB05**: Al confirmarse el pedido, las fotos se copian al chatter de la Cita y de la tarea de FSM.
6. **RB06**: Al confirmarse un pedido con instalacion, se invita al cliente al portal; si ya tiene usuario (activo o archivado) o no tiene email, no se hace nada y queda nota en el chatter. Un fallo nunca rompe la confirmacion.
7. **RB07**: Una cita de un tipo con `installation_fsm_project_id`, agendada fuera del eCommerce, genera tarea de FSM sin asignar; reprogramarla mueve las fechas de la tarea y cancelarla la cancela.
8. **RB08**: Las respuestas del formulario se validan segun `answer_format` en el navegador **y** en el servidor.

**Pilas incluidas**
9. **RB09**: Las pilas se agregan **solo** si el metodo de envio elegido tiene `includes_free_batteries`. Sin ese flag, el modulo es un no-op total sobre el pedido.
10. **RB10**: Por cada linea vendible del pedido (excluidas la de envio, las de pilas y las secciones/notas) cuyo producto tenga pilas configuradas, se necesitan `free_battery_qty * product_uom_qty` unidades del producto de pila, **en la UoM de ese producto**.
11. **RB11**: Las necesidades se **agrupan por producto de pila**: un producto de pila = **una** linea, con la suma.
12. **RB12**: La linea de pilas siempre vale **0**: `price_unit = 0`, `discount = 0` y `pricelist_item_id = False`, en todos los caminos de recomputo (cambio de cantidad, `/shop/payment`, recomputo forzado de precios).
13. **RB13**: La sincronizacion es **idempotente**: se recalcula desde cero (crea, ajusta y borra) y correrla dos veces no cambia nada. Se dispara al actualizar el carrito, al cambiar de metodo de envio, en el onchange del backend y al confirmar (antes del `super()`).
14. **RB14**: Solo se sincroniza en `draft`/`sent`. Un pedido confirmado no se toca.
15. **RB15**: La linea gratis se **ve** en el carrito pero no se puede editar ni eliminar desde la UI; si el cliente la manipula por el endpoint publico, queda **re-sincronizada en el mismo request**.
16. **RB16**: Agregar manualmente el mismo producto de pila crea una linea **separada y paga**; la linea gratis no se fusiona ni cambia de precio.
17. **RB17**: "Volver a pedir" un pedido con pilas gratis no re-agrega la pila.
18. **RB18**: Configuracion invalida del producto (producto sin cantidad, cantidad sin producto, cantidad negativa, producto que es su propia pila) → `ValidationError`.
19. **RB19**: La factura del pedido incluye la linea de pilas a **0** (constancia de la entrega).
20. **RB20**: El **renglon corto al pie del paso** dice que las pilas **van incluidas** cuando el metodo de envio las incluye, y las pide ("4 u 8 AA/AAA el dia de la instalacion") cuando no. Son **dos ramas de la misma linea**: nunca se ven las dos (D52).
21. **RB21**: **Duplicar** un pedido con pilas gratis produce **una sola** linea de pilas, a 0 y con el flag puesto (el flag se copia — D33).
22. **RB22**: La linea gratis **nunca** bloquea el pago por stock, aunque el producto de pila tenga *Sell when Out-of-Stock* apagado y stock 0 (D34).
23. **RB23**: El sync **no** toca lineas de pilas con cantidad facturada o entregada distinta de 0 (D36), y **no** genera lineas con cantidad `<= 0` (D39).
24. **RB24**: Una pila configurada en una compañia incompatible con el pedido **se saltea**: no se crea la linea y el carrito **no se rompe** (D38).

**Paso de instalacion en 3 bloques (feature en curso)**
25. **RB25**: El paso `/shop/installation` muestra **siempre los tres bloques** (direccion · turno y
    fotos · pago). El estado de cada uno lo calcula el servidor
    (`_get_installation_block_states()`); el bloque **bloqueado no renderiza su cuerpo** y dice que
    falta.
26. **RB26**: La **direccion de instalacion es `partner_shipping_id`**. El Paso 1 la **muestra** y
    manda a editarla al paso del core (`/shop/address`): el modulo nunca escribe calle, ciudad,
    codigo postal ni pais.
27. **RB27**: *Confirm address* guarda `between_streets` (en el partner de envio) e
    `installation_notes` (en el pedido) y pone `installation_address_confirmed = True`. `between_streets`
    es **opcional** (`[ASUNCION]` D46): vacio tambien confirma.
28. **RB28**: Cambiar la direccion despues de confirmar —elegir otro contacto de envio **o** editar
    el mismo— vuelve `installation_address_confirmed` a `False` y con eso el Paso 2 se bloquea otra
    vez.
29. **RB29**: Sin direccion confirmada no se puede agendar ni subir fotos (Paso 2 bloqueado) y el
    pago queda bloqueado (`[ASUNCION]` D50: la direccion sin confirmar es un error mas de
    `_get_installation_errors()`).
30. **RB30**: El Paso 3 es un **link al paso siguiente del core**
    (`next_website_checkout_step_href`) y se habilita **solo** cuando `_get_installation_errors()`
    esta vacio. El gate del servidor no cambia: `/shop/payment` sigue redirigiendo al paso si algo
    falta (RB03).
31. **RB31**: La guia pide **3 fotos** (frente con la manija, canto, marco) y muestra **3 ejemplos de
    "asi no"** (borrosa, cortada, tapada). El progreso dice "N de `installation_min_photos`": el
    numero que gatilla es el del **carrier**, no el de la guia.
32. **RB32**: Entre calles e indicaciones llegan al instalador en la **descripcion de la tarea de
    Field Service**; la direccion ya la pone el nativo al **crear** la tarea desde el pedido
    (`partner_id = partner_shipping_id`, `enterprise/industry_fsm_sale/models/sale_order.py:L123`).
    ⚠️ RB32 se apoya en **ese** camino, no en el recompute: `_compute_partner_id`
    (`enterprise/industry_fsm_sale/models/project_task.py:L237`) esta condicionado a que el usuario
    tenga `account.group_delivery_invoice_address`, asi que sin ese grupo el recompute no fuerza la
    direccion de entrega — la creacion si.
33. **RB33**: Llegando **desde el checkout**, la pagina del turno **no repite** `message_intro`; por
    el **link compartido** se sigue mostrando arriba del calendario (D8/D54).

## Edge cases

**Existentes**
- **Sin proveedor de pago habilitado**: el pedido no se confirma → la reserva (`calendar.booking`) queda pendiente y la limpia el garbage collector nativo (2-6 meses).
- **Cancelar el pedido** archiva la Cita (comportamiento nativo de `website_appointment_sale`).
- **Cambiar a envio normal despues de agendar**: el paso deja de mostrarse; la linea de la reserva queda en el carrito hasta que el cliente la quite.
- **Fotos HEIC de iPhone**: se rechazan por mimetype real, avisando **con el nombre del archivo**.
- **Invitado que edita el mail en el formulario de la cita**: el nativo crea un contacto nuevo; no se puede impedir sin bloquear los campos.
- **`sequence` de `appointment.question` es global**: reordenar afecta a todos los tipos que reutilicen la pregunta.
- **Sin servidor de correo saliente**: el usuario portal se crea pero el mail de invitacion no sale.
- **Deuda de configuracion en la base local**: el `appointment.type` id 1 ("prueba") al que apunta el carrier 3 tiene `has_payment_step = false` y **sin producto**, combinacion que `_check_installation_appointment_type` **prohibe** → el circuito de cita no se puede ejercitar end-to-end en esa base tal como esta. **No afecta a las pilas** (dependen solo de `includes_free_batteries`, y escribir solo ese campo no dispara ese constrain). No se arregla en esta feature.


**Paso en 3 bloques (feature en curso)**
- **Carrito sin instalacion**: nada de esto existe — el paso se filtra del dominio (D3) y ni la
  direccion, ni las notas, ni la confirmacion se piden.
- **Pedido sin `partner_shipping_id`**: no deberia pasar (el paso de Direccion es `sequence 250` y el
  nuestro `400`). Si igual pasara, el Paso 1 muestra el link para cargarla y **no** se puede
  confirmar: nunca se escribe sobre un partner vacio.
- **Carrito anonimo** (`/shop/installation` es `auth="public"` y el visitante todavia no cargo
  direccion): `partner_shipping_id` es el **partner publico compartido** de la base. El Paso 1 muestra
  el aviso "cargá primero la dirección" con link a `/shop/address`, y *Confirm address* **no escribe
  nada ni confirma** — lo corta `order_sudo._is_anonymous_cart()`
  (`odoo/addons/website_sale/models/sale_order.py:L880`) antes del `write`. Sin esa guarda, un POST
  desde un carrito anonimo escribiria `between_streets` en un contacto **compartido por todos los
  visitantes**.
- **Cliente que confirma, vuelve atras y edita la MISMA direccion**: la confirmacion se cae (RB28) y
  el acordeon lo lleva de nuevo al Paso 1. ⚠️ Por eso la ruta escribe **primero el partner y despues
  el flag**: al reves, el `write()` de `res.partner` apagaria la confirmacion recien encendida.
- **Cliente que elige OTRO contacto de envio**: mismo efecto, por el `write()` de `sale.order`
  (`partner_shipping_id`). Las notas del pedido **no** se borran (siguen siendo de esta venta); lo
  que se pierde es la confirmacion.
- **Dos pedidos abiertos del mismo cliente a la misma direccion**: `between_streets` es del partner,
  asi que lo comparten (es el domicilio); `installation_notes` es de cada pedido. Editar el partner
  desde un carrito **resetea la confirmacion de los dos** (el `write()` busca por
  `partner_shipping_id`): es conservador y correcto — los dos tienen que volver a confirmar.
- **Reagendar desde el Paso 2**: sigue quedando una sola linea de instalacion (D11/RB04); si el
  cliente cancela la reserva, el bloque vuelve a `todo` y el Paso 3 se cierra solo.
- **Cliente sin JavaScript**: el acordeon de Bootstrap no colapsa/despliega, pero **los encabezados
  de los tres bloques y el cuerpo del bloque abierto se renderizan igual** (el `show` sale del
  servidor), y las fotos se suben con el boton *Upload photos*. No queda nadie sin poder terminar.
- **`installation_min_photos` distinto de 3** (por ejemplo bajado a 2 en el carrier): el progreso y
  el gate usan el numero del **carrier**; la guia sigue mostrando las tres tomas (es didactica). Si
  se pone en `0`, las fotos son opcionales y el Paso 2 se completa solo con el turno.
- **`message_intro` cargado con el checklist viejo** (caso de produccion): quedaria repitiendo los
  avisos que ahora estan repartidos por bloque (duracion, pago, garantia, pilas). **No es un bug del
  codigo**: se corrige como **dato** en la ficha del tipo de cita (T11) y queda documentado como
  requisito de configuracion.
- **Producto de la cita con `task_template_id`**: el core arma los vals de la tarea por
  `_prepare_task_template_vals` (`odoo/addons/sale_project/models/sale_order_line.py:L285`), que **no
  pasa** por nuestro override → entre calles y notas **no** llegarian a la tarea. Hoy el producto de
  reserva no usa plantilla; si algun dia se configura una, hay que enganchar tambien ese camino.
- **Tarea de FSM de una cita agendada por el link** (D8, sin pedido): no hay `installation_notes` ni
  `partner_shipping_id` — la tarea se sigue creando como hoy, sin el bloque de notas.
- **Pedido armado en el backoffice**: `installation_address_confirmed` queda en `False` (nadie apreto
  el boton) y el vendedor lo ve en la pestaña **Installation**. No bloquea la confirmacion del pedido
  desde el backend: el gate es del **checkout web** (`_check_cart_is_ready_to_be_paid`), no de
  `action_confirm()`.
- **Duplicar un pedido**: `installation_notes` e `installation_address_confirmed` son `copy=False` →
  el duplicado arranca sin confirmar, igual que las fotos (`installation_photo_ids`).

**Feature de pilas**
- **Producto sin pilas configuradas o carrier sin el flag**: no se crea ninguna linea (no-op), y si habia lineas gratis de un estado anterior, se borran.
- **UoM del producto de pila ("Paquete de 4")**: `free_battery_qty = 1` despacha **un paquete** (4 pilas). Si el funcional lo lee como "cantidad de pilas" y escribe `4`, se despachan **16**. Mitigacion: `string`/`help` explicitos + la UoM visible en la vista (D15).
- **Dos cerraduras distintas con la misma pila**: una sola linea con la suma (RB11).
- **Cambio de cantidad de la cerradura**: la cantidad de pilas se recalcula (no se apila).
- **Cambio de metodo de envio**: pasar a uno sin el flag borra las lineas gratis; volver al que las incluye las vuelve a crear.
- **Cliente que borra la linea gratis por `/shop/cart/update`**: se re-crea en el mismo request (RB15). El HTML solo la esconde de la UI; la garantia es la re-sincronizacion.
- **Cliente que agrega la misma pila como producto suelto**: dos lineas — la gratis (0) y la suya (precio de tarifa, $6.000/paquete). ⚠️ **Con la configuracion real (stock 0 y sin *Sell when Out-of-Stock*) el alta se rechaza antes**, por el control nativo de `website_sale_stock` (que ademas cuenta la linea gratis en el `product_qty_in_cart`): no llega a crearse ninguna linea. No es un defecto de la feature — es lo correcto — pero explica por que CA21 solo se puede ejercitar con stock cargado o con la venta sin stock habilitada.
- **Producto de pila publicado** (el funcional evaluaba publicarlo): la linea gratis sigue sin selector de cantidad ni link, por el override de `_is_sellable()` (D29).
- **`prevent_zero_price_sale`**: hoy esta **sin setear** en los dos sitios (Nokey id 1, Sunra id 3). Si alguien lo prende, la linea gratis sigue funcionando (`_check_validity` sale temprano).
- **Pilas storable con stock 0**: al confirmar, el picking mostrara las pilas como **no disponibles** hasta que se cargue stock. Ademas, mientras el producto de pila este agotado, la linea gratis **apaga el mail de carrito abandonado** de ese carrito (`_filter_can_send_abandoned_cart_mail` → `_all_product_available()` → `_is_sold_out()`, `odoo/addons/website_sale_stock/models/sale_order.py:L134` y `:L140`). Es aviso de configuracion (hay que aprovisionarlas), no un bug del modulo — pero es una razon comercial concreta para hacerlo.
- **Impuestos**: el producto de pila tiene VAT 21%, pero sobre `price_unit = 0` el impuesto liquida 0. El total del pedido no cambia.
- **Producto de pila eliminado**: `ondelete="restrict"` frena el borrado mientras haya productos que lo referencien (evita que el opt-in quede a medias sin que nadie se entere, ya que un `set null` de SQL no dispara `@api.constrains`).
- **Pedido confirmado / facturado**: no se sincroniza (RB14); ajustar pilas ahi es trabajo del backoffice.
- **Pedido facturado que vuelve a presupuesto** ("Set to Quotation"): queda en `draft` con `qty_invoiced != 0`. El sync **congela** esas lineas (no las escribe ni las borra — D36) y sigue reconciliando el resto.
- **Duplicar un presupuesto** (flujo cotidiano del vendedor): el duplicado conserva la linea a $0 **con el flag** (D33), asi el sync la reconoce y solo ajusta la cantidad. Con `copy=False` habria quedado cobrada y duplicada.
- **Pila con *Sell when Out-of-Stock* apagado y stock 0** (configuracion **real** de tmpl 411): el checkout **no se traba** gracias a `_check_availability()` (D34). Sin ese override el cliente no podia pagar ni eliminar la linea.
- **Pedido con cantidades negativas** (nota de credito preparada como pedido negativo): no se genera linea de pilas (D39), ni negativa ni en 0.
- **Pedido con `+1` y `-1` de la MISMA cerradura, EN SIMULTANEO** (dos lineas distintas, no una secuencia de +1 luego editada a -1): el filtro por linea (D39, `product_uom_qty <= 0`) descarta solo la linea `-1`; la `+1` manda igual → se crea **una linea de 1 paquete**, no cero, aunque el neto de cerraduras en el pedido sea 0. Es contraintuitivo (0 cerraduras netas → igual se despacha 1 paquete de pilas) pero es la consecuencia directa de filtrar por linea, no por producto agregado: no se corrige (el escenario de dos lineas simultaneas del mismo producto sin fusionar es en si mismo un caso raro/manual, no el flujo del carrito web que si fusiona por `_cart_find_product_line`).
- **Pila configurada en otra compañia**: se saltea (D38) — nunca un 500 en el carrito del visitante publico.
- **Cerradura dentro de un combo**: aporta pilas (deseado). Si se configuran pilas en la plantilla del combo **y** en el item, se cuentan **dos veces** (D40): configurarlas en un solo nivel.
- **Cerradura vendida en una UoM que no sea Units** (ej. "Caja de 6"): la cantidad **no se convierte** hoy (D40, asuncion declarada) — pediria 1 paquete por caja.
- **`message_intro` que contradice el aviso** (config, no codigo): si el funcional deja en `message_intro` el punto "tenes que tener 4 u 8 pilas" y el carrier **incluye** las pilas, el cliente lee las dos cosas: el checklist configurado pidiendoselas y el aviso diciendo que van incluidas. El aviso **no puede** saber que dice el texto libre del campo; se resuelve como **requisito de configuracion** (T11 lo corrige como dato y T12 lo documenta): con carrier que incluye pilas, ese punto sale de `message_intro`.
- **`invoice_policy` del producto de pila**: con `'order'` (lo que ya tienen 411/412) la linea llega a la factura, que es la razon de ser de D28. Si alguien lo pasa a `'delivery'` con stock 0, la linea no se facturaria.
- **Multi-compañia / multi-sitio**: la configuracion de pilas es por producto y por metodo de envio,
  que ya son registros por compañia/sitio. El modulo **si** agrega logica de compañia propia para el
  correo de la cita (D43): `calendar.event._notify_by_email_prepare_rendering_context()` (el hook
  que pinta el logo/colores del layout) resuelve la compañia del pedido que origino la cita (o, en su
  defecto, la del organizador o de quien la creo), en vez de la del usuario que dispara la
  notificacion — cron de alarmas para el recordatorio, request del checkout para la confirmacion.

## Criterios de aceptacion

> `CA01`–`CA13`, `CA14`–`CA36` y `CA38`: comportamiento **ya implementado** del modulo
> (current-state; el plan en curso no los vuelve a cubrir). `CA35`/`CA36` vienen del commit
> `e5526ae` de otro dev y `CA37` quedo fuera de orden numerico por ese rebase; `CA38` es el fix
> de marca del correo de recordatorio (D43, Plane #38).
> **`CA39`–`CA48`: rediseño del paso de instalacion y guia de fotos** — son los que cubre el
> **plan del cambio en curso**, junto con `CA02`, `CA29`, `CA35` y `CA37`, que se **reescriben** porque el
> rediseño cambia lo que hay que verificar (no se renumeran: los numeros ya viajaron a tests y
> commits).

**Envio con instalacion (existente)**
- [ ] **CA01**: Carrito con un producto etiquetado como instalable → el metodo *Envio con instalacion* aparece en el checkout.
- [ ] **CA02**: Elegir ese metodo → el paso *Instalacion* aparece en el wizard con los **tres bloques** (direccion · turno y fotos · pago) visibles desde el inicio, cada uno con su estado.
- [ ] **CA03**: Ir directo a `/shop/payment` sin agendar → redirige al paso de instalacion (no muestra el error suelto en el pago).
- [ ] **CA04**: Agendar dia y hora → vuelve al paso con el slot visible en la zona horaria del cliente.
- [ ] **CA05**: Intentar pagar con menos fotos que `installation_min_photos` → error de fotos faltantes.
- [ ] **CA06**: Subir un archivo que no es imagen (HEIC / >10 MB / mas de 10 fotos) → se rechaza con aviso que nombra el archivo.
- [ ] **CA07**: Pagar → se crea la Cita y la tarea de FSM, con fecha, direccion, respuestas y las fotos en los dos chatters.
- [ ] **CA08**: Repetir con *Envio normal* → el paso *Instalacion* no aparece en ningun momento.
- [ ] **CA09**: Confirmar con un cliente sin usuario → queda creado el usuario portal y se manda la invitacion; con usuario activo/archivado o sin email → no-op con nota en el chatter y sin romper la confirmacion.
- [ ] **CA10**: Asociar a un metodo de envio un tipo de cita sin paso de pago o sin producto → `ValidationError`.
- [ ] **CA11**: Responder una pregunta con formato `integer`/`decimal`/`phone`/`identification` con un valor invalido → se frena en el navegador y tambien en el servidor (vuelve al formulario con el detalle).
- [ ] **CA12**: Agendar por el link compartido en un tipo con `installation_fsm_project_id` → tarea de FSM creada sin asignar; reprogramar mueve las fechas, cancelar cancela la tarea, desarchivar la repone.
- [ ] **CA13**: Reagendar desde el paso → queda **una sola** linea de instalacion en el carrito.

**Textos configurables (commit `e5526ae`; `CA35` reescrito por el rediseño)**
- [ ] **CA35** *(reescrito — D52)*: Cargar `message_intro` en el tipo de cita → ese texto se ve **dentro del
  Paso 2** (el "antes de agendar") y, en el tipo **del link**, sigue **arriba del calendario** y no al final.
  Vaciarlo → el Paso 2 **no muestra ningun checklist**: el checklist por defecto del modulo **deja de
  existir** (sus `msgid` se dan de baja en T10) porque los avisos pasan a estar **repartidos por bloque**
  (duracion en el Paso 2, condicion de pago en el Paso 3, garantia y pilas en el renglon del pie — D52). El
  unico texto configurable que conserva **default propio** del modulo es `installation_photos_message` (CA36).
- [ ] **CA36**: Cargar `installation_photos_message` → esa consigna se ve arriba del input de fotos en **los dos** caminos (checkout y formulario del link); vaciarla → vuelve el texto por defecto.

**Pilas incluidas (feature en curso)**
- [ ] **CA14**: Cerradura con pilas configuradas + metodo de envio con `includes_free_batteries` → aparece la linea de pilas a **0**, con cantidad = `free_battery_qty * cantidad de cerraduras`, en la **UoM del producto de pila**.
- [ ] **CA15**: Cambiar la cantidad de cerraduras → la cantidad de pilas se ajusta (no se apila ni se duplica la linea).
- [ ] **CA16**: Cambiar a un metodo de envio **sin** `includes_free_batteries` → la linea de pilas **desaparece**; volver al que las incluye → reaparece.
- [ ] **CA17**: Dos cerraduras distintas que comparten el mismo producto de pila → **UNA** linea con la suma.
- [ ] **CA18**: Renderizar `/shop/payment` (dispara `_recompute_cart` → `_recompute_prices` con `force_price_recomputation=True`) → el precio de la linea sigue en **0**.
- [ ] **CA19**: Cambiar la cantidad (camino **no** forzado de `_compute_price_unit`) → el precio sigue en **0**.
- [ ] **CA20**: Con una tarifa con descuento configurada → la linea gratis queda con `discount == 0` y `pricelist_item_id == False`: no se prende la columna Descuento del PDF ni el precio tachado en el carrito.
- [ ] **CA21**: Agregar manualmente el mismo producto de pila al carrito → se crea una linea **separada y paga**; la linea gratis no se fusiona ni cambia de precio.
  ⚠️ **Como validarlo**: con la configuracion real (tmpl 411 storable, *Sell when Out-of-Stock* apagado, **stock 0**) el alta **no crea ninguna linea** y sale el warning nativo *"… has not been added to your cart since it is not available"* — `website_sale_stock._verify_updated_quantity` (`odoo/addons/website_sale_stock/models/sale_order.py:L22`) calcula `free_qty = 0` y `_get_cart_qty` (`:L102`) **cuenta tambien nuestra linea gratis** (`_get_common_product_lines`, `:L120`, no filtra el flag) → `allowed_line_qty <= 0`, y `_cart_find_product_line` nunca entra en juego. Eso es comportamiento **nativo y correcto** (no se vende lo que no hay), ajeno a esta feature: **CA21 y su test en `tests/test_free_batteries.py` (plan `1.8.0`, cerrado) se validan con stock cargado o con *Sell when Out-of-Stock* activado**.
- [ ] **CA22**: "Volver a pedir" un pedido que tenia pilas gratis → la pila **no** se re-agrega al carrito nuevo.
- [ ] **CA23**: Armar el pedido en el **backend** (sin eCommerce): (a) al cargar lineas y metodo de envio a mano, la linea de pilas aparece por el onchange; (b) asignando el envio con el boton **Add shipping** (wizard `choose.delivery.carrier`, que escribe por `write` y **no** dispara onchange), la linea aparece igual — de modo que el **presupuesto en PDF ya la incluye**; (c) si ninguno de los dos se disparo, al confirmar queda sincronizada.
- [ ] **CA24**: Borrar la linea gratis (o cambiarle la cantidad) por `/shop/cart/update` con su `line_id` real → queda **re-creada/ajustada en el mismo request**.
- [ ] **CA25**: Cerradura **sin** pilas configuradas, o carrier sin el flag → **no** se crea ninguna linea (no-op), y las lineas gratis previas se limpian.
- [ ] **CA26**: Configuracion invalida (producto sin cantidad, cantidad sin producto, cantidad negativa, producto que es su propia pila) → `ValidationError` al guardar el producto.
- [ ] **CA27**: En el carrito, la linea gratis **se ve** pero no ofrece selector de cantidad editable, ni link al producto, ni boton **Eliminar** (desktop y mobile).
- [ ] **CA28**: **Publicar** el producto de pila (`is_published = True`) **no** habilita el selector de cantidad ni el link de la linea gratis (regresion que previene el override de `_is_sellable()`).
- [ ] **CA29**: En el renglon corto al pie del acordeon, con un carrier que **incluye** pilas se
  lee que van incluidas sin cargo y con uno que **no**, se lee que hay que tenerlas el dia de la
  instalacion. Se ve **en los dos casos**, tambien con `message_intro` cargado (el renglon esta
  fuera de cualquier `t-if`/`t-else` del checklist configurable — D41/D52).
- [ ] **CA37**: El aviso de pilas y el pedido de pilas son **la misma linea** con `t-if`/`t-else`
  (D52): es **imposible** que convivan. Verificar en **ingles y en es_419** que con el carrier que
  las incluye se lee solo "incluidas" y con el que no, solo "tenes que tener 4 u 8 AA/AAA", y
  que ninguno de los dos depende de si `message_intro` esta cargado o traducido. ⚠️ El diseño
  anterior (un `<li>` dentro del `t-else` del checklist + un bloque de aviso aparte) **se elimina**;
  con el, el `msgid` viejo del `<li>` queda obsoleto en `i18n/es_419.po` (T10).
- [ ] **CA30**: La **factura** del pedido muestra la linea de pilas a 0, con la descripcion que aclara que va incluida (requiere `invoice_policy = 'order'` en el producto de pila — ya es el caso en los tmpl 411/412). **Sin tarea propia en el plan**: no necesita codigo nuevo, es consecuencia de D28 + esa configuracion; se verifica a mano.
- [ ] **CA31**: **Duplicar** un pedido que tiene la linea de pilas gratis → el duplicado queda con **UNA** linea de pilas, a **$0** y **con el flag**; al confirmarlo no se crea una segunda ni se cobra ninguna.
- [ ] **CA32**: Producto de pila con *Sell when Out-of-Stock* **apagado** y **stock 0** (configuracion real de tmpl 411) → el carrito **se puede pagar**: `_check_cart_is_ready_to_be_paid` no tira `ValidationError` por la linea gratis.
- [ ] **CA33**: Pedido con la cerradura en cantidad **`-1`** o con `+1` y `-1` que se cancelan → **no** se crea linea de pilas negativa ni en 0 (y si habia una, se borra).
- [ ] **CA34**: Cerradura de una compañia con una pila configurada en **otra** compañia → el carrito **no rompe** (sin `UserError`/500): la pila se saltea y no se crea la linea.

**Marca del correo de la cita (fix Plane #38)**
- [ ] **CA38**: Una cita de instalacion cuyo pedido de venta es de una compañia (ej. Miluan SRL /
  Nokey) → el **layout renderizado** (logo, nombre y colores) del correo de **recordatorio** de esa
  cita usa **esa** compañia, aunque el usuario que corre el cron de alarmas
  (`ir_cron_scheduler_alarm`) tenga otra compañia (ej. YG S.A. / Sunra) como compañia por defecto.
  El correo de **confirmacion** sigue saliendo bien (mismo camino, no regresiona). Sin pedido
  asociado (cita agendada por link compartido, sin venta) → se usa la compañia del organizador de
  la cita, y si tampoco hay organizador, la de quien la creo. **Se valida renderizando la
  notificacion de verdad** (no solo el resolvedor `_mail_get_companies()`, que no pinta el layout —
  ver Notas de implementacion).

**Paso de instalacion en 3 bloques + guia de fotos (feature en curso)**
- [ ] **CA39**: En `/shop/installation` se ven **los tres bloques desde el inicio**, en orden y
  numerados (*Paso 1 · Installation address*, *Paso 2 · Appointment and photos*, *Paso 3 · Payment*),
  con el completado en **tilde** (mas su resumen en el encabezado), el pendiente con su **numero** y
  el bloqueado con **candado** + la razon. El bloqueado **no muestra su cuerpo**.
- [ ] **CA40**: El Paso 1 muestra la **direccion de entrega** del pedido (nombre, calle, piso/depto,
  localidad) y el link **editar** abre
  `/shop/address?partner_id=<partner de envio>&address_type=delivery&callback=/shop/installation`; al
  **Guardar** (y tambien al **Descartar**) el navegador **vuelve al paso de instalacion** —no a
  `/shop/checkout`— y el resumen refleja lo editado. El `callback` es nativo del core
  (`odoo/addons/website_sale/controllers/main.py:L1234`, `:L1236`, `:L1184`): no hay redireccion propia.
- [ ] **CA41**: Cargar *entre calles* + *indicaciones para el instalador* y apretar **Confirm
  address** → se guardan (`res.partner.between_streets` y `sale.order.installation_notes`), el bloque
  queda con tilde y el Paso 2 se habilita. Recargar la pagina **mantiene** el estado. Confirmar **sin**
  entre calles tambien cierra el bloque (campo opcional, `[ASUNCION]` D46).
- [ ] **CA42**: Antes de confirmar la direccion, el Paso 2 esta **bloqueado**: no hay boton para
  agendar ni input de fotos en el HTML (no es un control deshabilitado, directamente no se renderiza).
- [ ] **CA43**: Cambiar la direccion **despues** de confirmar —(a) editar el mismo contacto desde
  `/shop/address`, (b) elegir otro contacto de envio— → el Paso 1 vuelve a **pendiente**, el Paso 2 se
  bloquea y el Paso 3 tambien. Las indicaciones ya cargadas **no se borran**.
- [ ] **CA44**: El Paso 3 esta con **candado** mientras falte turno, fotos (menos que
  `installation_min_photos`) o la confirmacion de la direccion; cuando no falta nada, es un **link**
  al paso siguiente del core (`next_website_checkout_step_href` → `/shop/payment`, con *Extra Info*
  desactivado, que es la configuracion real — D44). Ir a `/shop/payment` a mano en el estado
  bloqueado **sigue redirigiendo** al paso (RB03/CA03).
- [ ] **CA45**: La guia de fotos muestra **3 tomas "asi si"** (frente con la manija, canto, marco) y
  **3 "asi no"** (borrosa, cortada, tapada por la mano) con su motivo; **no existe** la toma "desde
  adentro" ni el recuadro placeholder. El progreso dice **"N de `installation_min_photos`"** (3 con la
  configuracion real del carrier) y avanza al subir cada foto. La
  consigna por defecto (`installation_photos_message` vacio) habla de **3 fotos** y no de "2 cosas".
- [ ] **CA46**: Pagar un pedido con entre calles e indicaciones cargadas → la **tarea de Field
  Service** queda con esos datos en la **descripcion** y con la **direccion de entrega** como contacto
  (lo ultimo ya es nativo). Sin ninguno de los dos datos, la descripcion queda como hoy.
- [ ] **CA47**: Entrar a la pagina del turno **desde el checkout** (boton *Schedule the installation*)
  → el intro del tipo de cita (`message_intro`) **no** aparece al final de la pagina. Entrar por el
  **link compartido** (tipo con `installation_fsm_project_id`, sin carrito) → se sigue viendo **arriba
  del calendario**.
- [ ] **CA48**: Todos los textos del paso hablan **de vos** (voseo) en es_419 — no conviven "Subi" y
  "Sube"/"Asegurate"— y los strings nuevos estan en **ingles** en el codigo, con su entrada traducida
  en `i18n/es_419.po`.

## Referencias al core

> Anclajes `path:L#` verificados sobre el workspace (`odoo/`, `enterprise/`) y sobre el repo de
> customizaciones. **No inventar**: cada fila se leyo del archivo.

| Que | Anclaje (`path:L#`) | Por que importa |
|-----|---------------------|-----------------|
| Hook canonico del carrito web | `odoo/addons/website_sale/models/sale_order.py:L674` | `_verify_cart_after_update()` — su docstring dice que es el lugar de los chequeos globales, una vez por request |
| Auto-curacion tras cambiar una linea | `odoo/addons/website_sale/models/sale_order.py:L496` | `_cart_update_line_quantity()` llama al hook **despues** de aplicar el cambio → la linea se re-sincroniza en el mismo request |
| Idem, alta al carrito | `odoo/addons/website_sale/models/sale_order.py:L394` | `_cart_add` tambien pasa por el hook (salvo `skip_cart_verification`) |
| Precedente exacto del override del hook | `odoo/addons/website_sale_loyalty/models/sale_order.py:L185` | `super()` primero y despues la sincronizacion propia |
| Cambio de metodo de envio | `odoo/addons/website_sale/models/sale_order.py:L853` | `_set_delivery_method(delivery_method, rate=None)` — embudo de la seleccion de envio |
| Endpoint que lo llama | `odoo/addons/website_sale/controllers/delivery.py:L58` | `shop_set_delivery_method` → confirma que el override cubre el cambio de carrier |
| Quitar la linea de envio | `odoo/addons/website_sale/models/sale_order.py:L825` / `odoo/addons/delivery/models/sale_order.py:L54` | Sus llamadores ya estan enganchados → no hace falta override propio |
| Molde de creacion de linea de servicio | `odoo/addons/delivery/models/sale_order.py:L203` | `_prepare_delivery_line_vals` — no pasa `product_uom_id`; el ORM toma la UoM del producto |
| Creacion con `sudo()` | `odoo/addons/delivery/models/sale_order.py:L239` | `_create_delivery_line` — precedente del `sudo()` para el visitante publico |
| Campo de UoM en v19 | `odoo/addons/sale/models/sale_order_line.py:L132` | Es **`product_uom_id`** (no `product_uom`, de versiones viejas) |
| Recomputo de precio | `odoo/addons/sale/models/sale_order_line.py:L587` | `_compute_price_unit` depende de `product_id`/`product_uom_id`/`product_uom_qty`: nuestra linea cambia de cantidad seguido |
| Por que `price_unit=0` no alcanza | `odoo/addons/sale/models/sale_order_line.py:L1358` | `_add_precomputed_values` copia `price_unit` a `technical_price_unit` → `has_manual_price` da `False` |
| Camino forzado del precio | `odoo/addons/sale/models/sale_order_line.py:L619` y `:L623` | `_reset_price_unit()` llama a `_get_display_price()`: un solo override cubre los dos caminos |
| Metodo a override-ear para el precio 0 | `odoo/addons/sale/models/sale_order_line.py:L639` | `_get_display_price()` — la garantia del 0 |
| Recomputo de precios de la orden | `odoo/addons/sale/models/sale_order.py:L1372` | `_recompute_prices()` resetea `discount` y recomputa |
| Guard del descuento | `odoo/addons/sale/models/sale_order_line.py:L807` | `_compute_discount` sale por `continue` si `not pricelist_item_id._show_discount()` |
| Molde literal a copiar | `odoo/addons/delivery/models/sale_order_line.py:L59` | `_compute_pricelist_item_id()` → `False` para las lineas de envio |
| Omision verificada de `_get_update_prices_lines` | `odoo/addons/delivery/models/sale_order.py:L49` | El equivalente de `delivery`; en nuestro caso es redundante **y peor** (`:L623` ya da 0 y el `discount = 0.0` de `:L1379` conviene que le llegue) |
| Reset del descuento en el recomputo | `odoo/addons/sale/models/sale_order.py:L1379` | `lines_to_recompute.discount = 0.0` — razon para NO excluir la linea del recordset |
| Semantica de `copy` en campos computados | `odoo/odoo/orm/fields.py:L449` | Un compute recibe `copy=False` **salvo** `store=True` y no `readonly`: por eso `price_unit` y `name` **si** se copian |
| Campos que si se copian | `odoo/addons/sale/models/sale_order_line.py:L177` y `:L121` | `price_unit` y `name` son `store=True, readonly=False` → el duplicado conserva el $0 y la descripcion |
| Molde del flag copiable | `odoo/addons/delivery/models/sale_order_line.py:L9` | `is_delivery` se declara **sin `copy=`** (copiable): el flag tecnico analogo del core |
| Guard de stock del eCommerce | `odoo/addons/website_sale_stock/models/sale_order.py:L124` | `_check_cart_is_ready_to_be_paid` tira `ValidationError` si una linea falla `_check_availability()` |
| Condicion de indisponibilidad | `odoo/addons/website_sale_stock/models/sale_order_line.py:L39` | `is_storable and not allow_out_of_stock_order and cart_qty > free_qty` — metodo a override-ear |
| Guard de facturado del core | `odoo/addons/sale/models/sale_order.py:L1452` | `_check_line_unlink` bloquea solo con `state == 'sale'` → `draft` no implica "no facturado" |
| Precedente del guard `qty_invoiced` | `odoo/addons/delivery/models/sale_order.py:L59` | `_remove_delivery_line` solo borra las lineas con `qty_invoiced == 0` |
| Flujo real de envio en el backend | `odoo/addons/delivery/models/sale_order.py:L67` | `set_delivery_line()` — lo llama el wizard **Add shipping** por `write` (sin onchange) |
| Camino de **quitar** el envio | `odoo/addons/website_sale/models/sale_order.py:L864` | `_set_delivery_method` retorna antes de `set_delivery_line` → los dos overrides son complementarios |
| `check_company` de la linea | `odoo/addons/sale/models/sale_order_line.py:L88` | `product_id` es `check_company=True`; el `sudo()` no exime de `_check_company` |
| Domain de compañia del vecino | `odoo/addons/sale/views/product_template_views.xml:L16` | Forma a copiar para `free_battery_product_id` |
| Idioma de la descripcion | `odoo/addons/delivery/models/sale_order.py:L207` y `enterprise/website_appointment_sale/models/sale_order.py:L83` | `context['lang'] = partner.lang` / `self._get_lang()` — molde para armar el `name` |
| Conversion de UoM (si algun dia hace falta) | `odoo/addons/delivery/models/sale_order_line.py:L24` | `product_uom_id._compute_quantity(qty, product_id.uom_id)` — fix de D40 |
| `unlink()` de una linea de envio | `odoo/addons/delivery/models/sale_order_line.py:L29` | Pone `carrier_id = False` en el pedido → segundo motivo de D18 |
| Metodo del peso sin llamadores locales | `odoo/addons/delivery/models/sale_order_line.py:L36` y `odoo/addons/delivery/tests/test_delivery_cost.py:L295` | `_get_invalid_delivery_weight_lines` solo lo usan los carriers de terceros de enterprise y el test |
| Lineas fuera del recomputo de precio | `odoo/addons/sale/models/sale_order_line.py:L601` | `_compute_price_unit` saltea `is_downpayment` y `_is_global_discount()` → la linea de descuento global del modulo hermano no interactua |
| Gate de precio 0 del eCommerce | `odoo/addons/website_sale/models/sale_order_line.py:L102` y `odoo/addons/website_sale/models/sale_order.py:L554` | `_check_validity()` con `prevent_zero_price_sale` abortaria el request antes de la auto-curacion |
| Filtro de "Volver a pedir" | `odoo/addons/website_sale/models/sale_order_line.py:L85` y `odoo/addons/website_sale/controllers/reorder.py:L33` | `_is_reorder_allowed()` → `_show_in_cart()` no conoce nuestro flag |
| Por que no `is_delivery=True` | `odoo/addons/website_sale/models/sale_order_line.py:L80` | `_show_in_cart()` excluye `is_delivery` → ocultaria la linea, contra D20 |
| Linea visible pero no editable | `odoo/addons/website_sale/models/sale_order_line.py:L124` | `_is_sellable()` — punto de extension establecido (base: `is_published and not is_delivery`) |
| Precedente en la propia cadena de deps | `enterprise/website_appointment_sale/models/sale_order_line.py:L19` | La linea de la cita: mismo requisito (se ve, no se edita) |
| Otro precedente | `odoo/addons/website_sale_loyalty/models/sale_order_line.py:L38` | `_is_sellable()` para las lineas de premio |
| Selector de cantidad readonly | `odoo/addons/website_sale/views/templates.xml:L3002` | `should_show_quantity_selector and line._is_sellable()` → rama `t-else` sin `-`/`+` |
| Link al producto | `odoo/addons/website_sale/views/templates.xml:L2829` | Tambien colgado de `_is_sellable()` |
| Precio tachado | `odoo/addons/website_sale/models/sale_order_line.py:L122` | `_should_show_strikethrough_price()` usa `_is_sellable()`: segunda capa sobre el descuento |
| Precio por UoM | `odoo/addons/website_sale/views/templates.xml:L3066` | Idem |
| Sugerencias de pedidos anteriores | `odoo/addons/website_sale/controllers/cart.py:L388` | Excluye las lineas no sellable |
| Botones a ocultar por xpath | `odoo/addons/website_sale/views/templates.xml:L2954` y `:L2974` | Contenedores con `name=` estable (desktop/mobile); nada del core ata el boton Eliminar a `_is_sellable()` |
| Variable del bucle del carrito | `odoo/addons/website_sale/views/templates.xml:L2880` | `t-foreach="website_sale_order.website_order_line" t-as="line"` → la condicion es `line.is_free_battery_line` |
| Colision de alta manual | `odoo/addons/website_sale/models/sale_order.py:L403` y `:L430` | El domain de `_cart_find_product_line` no filtra por nuestro flag → fusionaria el alta con la linea gratis |
| Precedente de estilo del override | `enterprise/website_appointment_sale/models/sale_order.py:L58` | `_cart_find_product_line` filtrado para las lineas de reserva |
| Por que la red va en `action_confirm()` | `odoo/addons/sale/models/sale_order.py:L1167` y `:L1183` | El `write(_prepare_confirmation_values())` pasa el `state` a `'sale'` **antes** de `_action_confirm()` → ahi el `unlink()` choca con `_unlink_except_confirmed` |
| Contaminacion del `name` con `linked_line_id` | `odoo/addons/sale/models/sale_order_line.py:L436` | Appendea `"Option for: <producto>"` (se veria en la factura) → D19 |
| Sincronizacion de lineas en el backend | `odoo/addons/sale/models/sale_order.py:L936` | `@api.onchange('order_line')` del core: manipula `self.order_line` con `Command.*` **en memoria** (patron del onchange de pilas) |
| Precedente de onchange en `delivery` | `odoo/addons/delivery/models/sale_order.py:L42` | Ya existe un `@api.onchange('order_line', ...)` en la cadena |
| Grupo de la vista de producto | `odoo/addons/product/views/product_views.xml:L143` | `group name="upsell"` ("Upsell & Cross-Sell") en la pestaña Sales |
| Vecinos del grupo | `odoo/addons/sale/views/product_template_views.xml:L12` y `odoo/addons/website_sale/views/product_views.xml:L169` | `optional_product_ids` / `accessory_product_ids` — donde van los campos nuevos |
| Recomputo del carrito (omitido) | `odoo/addons/website_sale/models/sale_order.py:L932` | `_recompute_cart()` — no se override-ea (ver *NO incluye*) |
| Precedente interno: sync idempotente | `extra-addons/odoo_customization_sunra/website_sale_payment_method_price/models/sale_order.py:L110` | `_apply_payment_price_rule()` — limpia y aplica, nunca apila; `sudo()` comentado; guard de contexto `wspmp_skip_recompute` (`:L146`) |
| Precedente interno: flag tecnico | `extra-addons/odoo_customization_sunra/website_sale_payment_method_price/models/sale_order_line.py:L8` | `is_payment_method_discount` — molde del `help` de `is_free_battery_line` ("without guessing by product") |
| Campo nativo del checklist | `enterprise/appointment/models/appointment_type.py:L147` | `message_intro` (Html, `translate=True`, `sanitize_attributes=False`) — el que usa el modulo para el checklist configurable (D42) |
| Donde el core pinta `message_intro` | `enterprise/appointment/views/appointment_templates_appointments.xml:L233` | Al final de la pagina del turno, bajo "Descripcion" → por eso el modulo lo sube arriba del calendario |
| Template y bloque no editable | `enterprise/appointment/views/appointment_templates_appointments.xml:L75` y `:L92` | `appointment_info` y `o_appointment_info_main` (`o_not_editable`): el bloque nuevo va **fuera** para seguir siendo editable en linea |
| Helper del patron campo-vacio | `odoo/odoo/tools/mail.py:L490` | `is_html_empty()` — el `t-if`/`t-else` de los textos configurables |
| `msgid` obsoletos del checklist y del `<li>` de pilas *(baja verificada en T10)* | `i18n/es_419.po` (ya no existen) | El criterio de baja **no fue un rango de lineas fijo** (quedaba corto/desalineado apenas se tocaba el archivo): T10 reconstruyo el `.po` entero desde un export real (`odoo.tools.translate.trans_export` contra el arch final) y descarto ahi los msgids que dejaron de aparecer — entre ellos el checklist por defecto completo y el `<li>` *"You'll need 4 or 8 AA/AAA batteries…"* |
| `msgid` de las 2 fotos de ejemplo viejas *(baja verificada en T10)* | `i18n/es_419.po` (ya no existen) | **Criterio correcto** (post-review): **todas** las entradas cuyo `#:` apunte a `…installation_photo_examples`, no un rango de lineas — el rango citado en una version anterior de esta spec quedaba corto (faltaban 2 entradas) |
| Nodos que T07 elimina (checklist por defecto, estado pre-rediseño) | `views/website_sale_installation_templates.xml` (version anterior a T07, ya no existe) | El par `t-if`/`t-else` de `message_intro` (vacio → `<ul>` con el `<li>` de pilas dentro del `t-else`, D41 viejo) **desaparece entero**: el checklist por defecto deja de existir y el aviso de pilas renace como el renglon del pie con su propio `t-if`/`t-else` (D52) |
| Template de la consigna de fotos | `extra-addons/odoo_customization_sunra/website_sale_installation_appointment/views/website_sale_installation_templates.xml:L41` | `installation_photos_message` (current-state), llamado desde `:L322` (Paso 2 del checkout, tras T07) y desde `views/appointment_templates.xml:L37` (formulario del link) |
| Campo nuevo del otro dev | `extra-addons/odoo_customization_sunra/website_sale_installation_appointment/models/appointment_type.py:L31` | `installation_photos_message` — Html traducible, vacio = texto por defecto |
| Checklist arriba del calendario | `extra-addons/odoo_customization_sunra/website_sale_installation_appointment/views/appointment_templates.xml:L72` | Override `appointment_info`: apaga el bloque nativo (`:L78`) y agrega el de arriba (`:L82`) |
| Campo en la pestaña Comunicacion | `extra-addons/odoo_customization_sunra/website_sale_installation_appointment/views/appointment_type_views.xml:L33` | Donde se configura `installation_photos_message` |
| Donde cuelga el opt-in del carrier | `extra-addons/odoo_customization_sunra/website_sale_installation_appointment/views/delivery_carrier_views.xml:L9` | `group name="delivery_details"` — mismo grupo para `includes_free_batteries` |
| Base de `_mail_get_companies()` | `odoo/addons/mail/models/models.py:L128-140` | `_mail_get_companies(default=False)` — cae al `default` cuando el modelo no tiene `company_id` (caso de `calendar.event`); **no** pinta el layout (solo `record_company_id`/alias domain/reply-to) |
| Caller real de `_mail_get_companies()` en la notificacion | `odoo/addons/mail/models/mail_thread.py:L2831` | Dentro de `message_notify()`: `msg_values['record_company_id'] = self._mail_get_companies(default=self.env.company)[self.id].id`. (`:L2330` es de `message_post()`, **no** del camino de la cita) |
| **El hook que si pinta el logo/colores del layout** | `odoo/addons/mail/models/mail_thread.py:L3606-3719` | `_notify_by_email_prepare_rendering_context()`; el calculo de `company`/`website_url` esta en `:L3657-3666` y lee `record.company_id` **directo** (no via `_mail_get_companies()`) — punto de extension real del fix D43 |
| Camino comun de confirmacion Y recordatorio | `odoo/addons/calendar/models/calendar_attendee.py:L124-L196` | `_notify_attendees()` → `message_notify()` sobre el `calendar.event`, una llamada **por asistente** (no en lote) |
| Disparador de la confirmacion (request web) | `enterprise/appointment/models/calendar_attendee.py:L16-L44` | `_send_invitation_emails()` override — corre en el `create()` del attendee, dentro del request del checkout: `env.company` ya es la del sitio |
| Disparador del recordatorio (cron) | `odoo/addons/calendar/models/calendar_alarm_manager.py:L182-L202` | `_send_reminder()`, `@api.model`, comentario propio del core "Executed via cron": `env.company` es la del usuario tecnico del cron |
| Molde del fallback organizador/creador | `odoo/addons/calendar/controllers/main.py:L66` | `company = event.user_id and event.user_id.company_id or event.create_uid.company_id` — heuristico nativo para citas sin compañia propia |
| Vinculo cita ↔ pedido usado por el fix | `enterprise/website_appointment_sale/models/sale_order_line.py:L10-11` | `sale.order.line.calendar_event_id` (M2o directo, seteado por `calendar.booking`) **sin `copy=False`**: un pedido duplicado copia el vinculo, de ahi el criterio "el mas viejo, no cancelado, gana" |
| Molde de override de `_notify_by_email_prepare_rendering_context` | `odoo/addons/sale/models/sale_order.py:L1758`, `odoo/addons/project/models/project_task.py:L1506`, `odoo/addons/crm/models/crm_lead.py:L2103` | Los tres llaman a `super()` y pisan claves del dict devuelto (`subtitles` en su caso); mismo patron para pisar `company`/`website_url` |

| **— Rediseño del paso (cambio en curso) —** | | |
| Modelo del paso de checkout | `odoo/addons/website_sale/models/website_checkout_step.py:L7` y `:L19` | `website.checkout.step` (`sequence`, `step_href`, labels) y `_get_next_checkout_step()`: el paso sigue siendo **uno solo**, el acordeon va adentro (D3/D44) |
| Secuencias de los pasos del core | `odoo/addons/website_sale/data/data.xml:L74` y `:L90` | Address `250` · Payment `999` → el paso de instalacion (`400`) corre **siempre despues** de la direccion: en `/shop/installation` ya hay `partner_shipping_id` |
| Valores de navegacion del checkout | `odoo/addons/website_sale/models/website.py:L981-1012` | `_get_checkout_step_values()` devuelve `current_website_checkout_step_href` (**string**), `previous_website_checkout_step` y `next_website_checkout_step` (**records**) y `next_website_checkout_step_href` (string). ⚠️ **No existe** `current_website_checkout_step` como record; el rotulo del Paso 3 sale de `next_website_checkout_step.name` |
| Layout del checkout | `odoo/addons/website_sale/views/templates.xml:L3776` | `checkout_layout` y sus parametros (`show_navigation_button`, que nuestro paso ya pone en `False`) |
| Boton principal del wizard | `odoo/addons/website_sale/views/templates.xml:L3432` | `name="website_sale_main_button"` colgado de `next_website_checkout_step_href`: molde del link del **Paso 3** |
| Formulario de direccion del core | `odoo/addons/website_sale/controllers/main.py:L1099-1103` | `/shop/address` con `partner_id`, `address_type` y `**query_params` — destino del link "editar" del Paso 1; el `callback` viaja por `query_params` sin codigo nuestro |
| Vuelta al paso tras guardar/descartar | `odoo/addons/website_sale/controllers/main.py:L1234`, `:L1236` y `:L1184` | `callback or '/shop/checkout'` al guardar y `discard_url` al descartar: por eso el link del Paso 1 lleva `&callback=/shop/installation` (D12/D45, CA40) |
| Carrito anonimo | `odoo/addons/website_sale/models/sale_order.py:L880` | `_is_anonymous_cart()` — la guarda que impide que `_save_installation_address()` escriba sobre el **partner publico compartido** (§Seguridad) |
| `description` de la tarea es Html | `odoo/addons/project/models/project_task.py:L153` | El destino de `_get_installation_task_notes()`: por eso se escapa con `markupsafe.escape()` y se devuelve `Markup` |
| Paso nativo entre el 400 y el 999 | `odoo/addons/website_sale/data/data.xml:L82-85` y `odoo/addons/website_sale/models/website.py:L959-960` | *Extra Info* (`/shop/extra_info`, `sequence 500`), publicado por sitio solo si la vista `website_sale.extra_info` esta activa: el Paso 3 **no siempre** es el pago, por eso el rotulo sale del dato (D44) |
| URL literal de edicion | `odoo/addons/website_sale/views/templates.xml:L3658` | `/shop/address?partner_id={{...}}&address_type=billing` — forma a copiar con `delivery` |
| Titulo de la direccion de entrega | `odoo/addons/website_sale/views/templates.xml:L3489` | `delivery_address_list` (el template que el modulo ya hereda para decir "Installation address") |
| Guardado de la direccion desde el frontend | `odoo/addons/portal/controllers/portal.py:L594` y `:L598` | `_parse_form_data()`: la whitelist es un **filtro de los campos que llegan en el form** (`if key in partner_fields and key in authorized_partner_fields`). Como el form del core no renderiza `between_streets`, sumarlo a la lista no tendria consumidor (D49) |
| Whitelist base | `odoo/addons/portal/models/res_partner.py:L10-19` | `_get_frontend_writable_fields()` (`@api.model`) — el set de campos que el portal deja escribir desde el frontend |
| Override de la whitelist (**no se implementa**) | `odoo/addons/website_sale/models/res_partner.py:L40` | **Suma** campos, no reemplaza; molde **por si algun dia** `between_streets` entra al form del core (D49 lo descarta hoy: sin consumidor). ⚠️ Este override **no** lleva `@api.model`, aunque la base si |
| Reset por edicion del partner | `odoo/addons/website_sale/models/res_partner.py:L49` y `:L58` | Dominio de pedidos afectados + `write()` guardado por un set de campos: molde literal del reset de `installation_address_confirmed` |
| Direccion de entrega del pedido | `odoo/addons/sale/models/sale_order.py:L160` y `:L406` | `partner_shipping_id` y su compute — el campo que **es** la direccion de instalacion (D45) |
| La tarea de FSM va a la direccion de entrega | `enterprise/industry_fsm_sale/models/sale_order.py:L118` y `:L123` | `_get_sale_order_partner_id()` y `_timesheet_create_task_prepare_values()` fuerzan `partner_shipping_id` cuando el proyecto es FSM |
| Idem, recompute del contacto de la tarea | `enterprise/industry_fsm_sale/models/project_task.py:L237` | `_compute_partner_id` → `sale_order_id.partner_shipping_id`, pero **condicionado** a `has_group('account.group_delivery_invoice_address')`: RB32 se apoya en el camino de **creacion** (`sale_order.py:L123`), que no tiene esa condicion |
| Vals de la tarea (clave `description`) | `odoo/addons/sale_project/models/sale_order_line.py:L252` y `:L273` | Donde se agregan entre calles + notas para el instalador (D47) |
| Camino alternativo de creacion de tarea | `odoo/addons/sale_project/models/sale_order_line.py:L285` | `_prepare_task_template_vals` — **no** pasa por nuestro override (limite documentado en *Edge cases*) |
| Formato del resumen de direccion | `odoo/odoo/addons/base/models/res_partner.py:L1196` | `_display_address()` — formato por pais, se reusa en el Paso 1 en vez de concatenar campos a mano |
| `request.cart` en todo el frontend | `odoo/addons/website_sale/models/ir_http.py:L32` | Se setea en `_frontend_pre_dispatch()` → tambien existe en `/appointment/...`: base de D54 |
| Intro nativo de la pagina del turno | `enterprise/appointment/views/appointment_templates_appointments.xml:L231-234` | El bloque que se apaga cuando se llega desde el checkout (D54). Es el **mismo** bloque del final que ya se apaga en el tipo del link: apagarlo no rompe ese camino, que muestra su copia arriba del calendario |
| Gate de pago del core | `odoo/addons/website_sale/models/sale_order.py:L907` y `:L914-930` | `_is_cart_ready()` / `_check_cart_is_ready_to_be_paid()` — el gate sobre el que se apoya el estado del Paso 3. Valida **ademas** carrier y direccion de entrega: un Paso 3 abierto significa "no falta nada **de instalacion**", no "el pago no puede rebotar" |
| Campos obligatorios de la direccion | `odoo/addons/portal/controllers/portal.py:L318` | `_get_mandatory_delivery_address_fields()` — el core ya valida la direccion; el modulo no duplica esa validacion |
| Paso propio y su ruta | `extra-addons/odoo_customization_sunra/website_sale_installation_appointment/models/website.py:L7` | `INSTALLATION_STEP_HREF` + patron defensivo `getattr(request, "cart", None)` que reusa D54 |
| Ruta POST del paso | `extra-addons/odoo_customization_sunra/website_sale_installation_appointment/controllers/website_sale_installation_appointment.py:L99` | `shop_installation_submit()` — donde entra la rama `confirm_installation_address` |
| El paso es publico y solo chequea el carrito | `extra-addons/odoo_customization_sunra/website_sale_installation_appointment/controllers/website_sale_installation_appointment.py:L82` y `:L84` | `shop_installation()` con `auth="public"` + `_check_cart()`: de ahi la guarda de carrito anonimo |
| Salida al pago que queda como fallback | `extra-addons/odoo_customization_sunra/website_sale_installation_appointment/controllers/website_sale_installation_appointment.py:L120`, `:L125` y `:L288` | La rama sin `stay_on_step` y `_get_installation_next_step_href()`: con la plantilla nueva no las alcanza la UI; **se conservan** como fallback defensivo (T04/T07) |
| Valores del paso | `extra-addons/odoo_customization_sunra/website_sale_installation_appointment/controllers/website_sale_installation_appointment.py:L202` | `_prepare_installation_values()` — donde se suman `block_states` y la direccion |
| Template del paso *(post-T07: reestructurado)* | `extra-addons/odoo_customization_sunra/website_sale_installation_appointment/views/website_sale_installation_templates.xml:L136` | `installation` — reestructurado en 3 bloques tipo acordeon |
| JS de las fotos (contrato de la plantilla) *(post-T07)* | `extra-addons/odoo_customization_sunra/website_sale_installation_appointment/static/src/js/installation_photos.js:L17` y `:L33` | `static selector = "#shop_installation form[data-installation-photos]"` y `button[name='installation_continue']`: T07 conservo el `id`, el `data-` y el `name` del boton. La inyeccion de `stay_on_step` (antes en el JS) se elimino: ahora es un input oculto estatico en la plantilla (ver `installation_photos.js` sin esa linea) |

## Documentacion afectada

| Archivo | Accion | Que reflejar |
|---------|--------|-------------|
| `website_sale_installation_appointment/README.md` | actualizar | (a) **Version** → `1.10.0`; (b) *Contenido del paso Instalacion* **reescrito**: los 3 bloques, que habilita cada uno y donde quedaron los avisos (duracion, pago, garantia/pilas); (c) *Imagenes*: las **6 fotos nuevas** de la guia y la **baja** de `installation_example_lock.jpg` / `installation_example_door_edge.jpg`; (d) *Textos configurables*: `message_intro` pasa a leerse **dentro del Paso 2** y **no se repite** en la pagina del turno cuando se viene del checkout; (e) *Configuracion*: el paso de **dato** para actualizar `installation_photos_message` (y revisar `message_intro`) en produccion; (f) *Gotchas*: la confirmacion de direccion **se cae** si despues se edita la direccion, `between_streets` es del **contacto** y `installation_notes` del **pedido**, y sin JS el acordeon no colapsa (se ve igual); (g) *Validacion manual*: los pasos de CA39–CA48 |
| `website_sale_installation_appointment/static/description/index.html` | actualizar | Funcionalidad visible nueva: el paso de instalacion en **3 bloques** (direccion · turno y fotos · pago) y la **guia de fotos definitiva** (3 "asi si" + 3 "asi no") |
| `odoo_customization_sunra/README.md` (raiz del repo) | actualizar | Sumar "paso de instalacion en 3 bloques + guia de fotos" al resumen de la fila del modulo en el indice |
| `website_sale_installation_appointment/specs/website_sale_installation_appointment.md` | actualizar | Esta spec: `Estado` → `implemented` y `Version` sincronizada con el manifest (`1.10.0`) al cerrar T12 |

## Plan del cambio

> **Plan del cambio CERRADO (11/09/2026)**: rediseño del paso de instalacion (3 bloques) + guia de
> fotos definitiva, aprobado por el cliente el 11/09/2026 e implementado el mismo dia. **T01..T10 y
> T12 quedaron ejecutados**; **T11 queda pendiente** (es un paso de **dato en produccion**, no de
> codigo — no aplica a esta base de desarrollo, ver su fila). Los planes anteriores estan **cerrados**
> y no se acumulan aca: pilas incluidas (T01..T12 de la version `1.8.0`) y marca del correo de
> recordatorio (T13 de la `1.9.0`) viven en el historial de git; su resultado esta descrito como
> **current-state** en *Decisiones vigentes*, *Metodos*, *Vistas* y `CA01`–`CA38`.

| Tarea | Descripcion | Depende de | Archivos | Cubre |
|-------|-------------|------------|----------|-------|
| **T01** ✅ | `res.partner`: campo `between_streets` (Char, opcional, `help` con ejemplo) + vista nueva que lo muestra junto a los campos de direccion. **Sin** override de `_get_frontend_writable_fields()`: el form de direccion del core no renderiza el campo, asi que la whitelist no tendria consumidor — lo escribe nuestra ruta con `sudo()` acotado (D49) | — | `models/res_partner.py` (nuevo), `models/__init__.py`, `views/res_partner_views.xml` (nuevo), `__manifest__.py` | CA41, CA46 |
| **T02** ✅ | `sale.order`: campos `installation_notes` (Text, `copy=False`) e `installation_address_confirmed` (Boolean, `copy=False`, default `False`) + los dos en la pestaña **Installation** del form (el flag **readonly**) | — | `models/sale_order.py`, `views/sale_order_views.xml` | CA41 |
| **T03** ✅ | Estado y gates: `sale.order._get_installation_block_states()` (D44), `_get_installation_errors()` suma la direccion sin confirmar (`[ASUNCION]` D50) y los **dos resets** de la confirmacion — `sale.order.write()` (cambia `partner_shipping_id`) y `res.partner.write()` (se edita el domicilio del partner de envio, molde `odoo/addons/website_sale/models/res_partner.py:L58`) | T01, T02 | `models/sale_order.py`, `models/res_partner.py` | CA42, CA43, CA44 |
| **T04** ✅ | Controller: `_prepare_installation_values()` suma `block_states`, el partner de envio y la URL de edicion **con `&callback=/shop/installation`** (D12/D45); `shop_installation_submit()` suma la rama `confirm_installation_address` → `_save_installation_address()` con (a) **guarda de carrito anonimo** (`order_sudo._is_anonymous_cart()` → aviso + link a `/shop/address`, **sin** confirmar), (b) `sudo()` **acotado a los dos campos**, (c) **truncado** server-side (`installation_notes` 1000, `between_streets` 100) y (d) partner **antes** que el flag. La rama final sin `stay_on_step` y `_get_installation_next_step_href()` (`:L117`, `:L122`, `:L245`) **se conservan** como fallback defensivo: ya no las alcanza la UI, pero borrarlas no aporta nada | T03 | `controllers/website_sale_installation_appointment.py` | CA40, CA41, CA43, CA44 |
| **T05** ✅ | Imagenes (ejecutable, D55): **origen** `/home/leandro/Descargas/nokey-propuesta-fuente/mk/` — `foto-ok-frente.png` (600×800), `foto-ok-canto.png` (600×800), `foto-ok-marco.png` (600×800), `foto-no-borrosa.png` (600×804), `foto-no-cortada.png` (600×804), `foto-no-obstruida.png` (600×773); PNG de 240–540 KB. **Convertir a JPEG** (calidad ~82, ancho maximo 600 px, con `convert`/ImageMagick o PIL) y guardarlas en `static/src/img/` como `photo_ok_front.jpg`, `photo_ok_edge.jpg`, `photo_ok_frame.jpg`, `photo_bad_blurry.jpg`, `photo_bad_cropped.jpg`, `photo_bad_obstructed.jpg`. **Dar de baja** `installation_example_lock.jpg` + `installation_example_door_edge.jpg` (**todas** las entradas de `i18n/es_419.po` cuyo `#:` apunte a `…installation_photo_examples`, las da de baja T10). Las de **medidas** A/B no se tocan ni se renombran | — | `static/src/img/*` | CA45 |
| **T06** ✅ | Templates de fotos: `installation_photo_examples` **redefinido** (fila "asi si" con las 3 tomas + fila "asi no" con los 3 motivos, relacion de aspecto vertical) y **texto por defecto** de `installation_photos_message` reescrito a **3 fotos** (D51) | T05 | `views/website_sale_installation_templates.xml` | CA45 |
| **T07** ✅ | Template `installation` **reestructurado en 3 bloques** (D44): encabezado, acordeon con estados desde `block_states`, Paso 1 (resumen + editar + entre calles + notas + *Confirm address*), Paso 2 (`message_intro`, duracion, boton de agendar **con margen superior**, fotos + progreso "N de min"), Paso 3 (candado / link a `next_website_checkout_step_href`), **renglon corto** de garantia + pilas con `t-if`/`t-else` (D52) y el link **Back**. El form de fotos lleva `stay_on_step` oculto y el JS **deja de inyectarlo**. **Restricciones de esta tarea**: (a) el `<form>` de fotos conserva `data-installation-photos="1"`, sigue dentro de `id="shop_installation"` y su submit conserva `name="installation_continue"` —son el `selector` y el boton de `installation_photos.js:L17`/`:L33`; solo cambia la **etiqueta visible**—; (b) `o_not_editable` va a nivel **contenedor** —`div.accordion#installation_accordion` y el `div` que envuelve `installation_photo_examples`— en vez de elemento por elemento, dejando fuera el `oe_structure` y los `t-field` de `message_intro` / `installation_photos_message` (D42, fix de revision M6); (c) el rotulo del Paso 3 sale de `next_website_checkout_step.name` (D44); (d) los mensajes "falta X" viven **solo** en la razon del candado del bloque — el `alert` de arriba queda para los errores de submit; (e) el `message_intro` vacio **no** pinta checklist por defecto (D52/CA35) | T03, T04, T06 | `views/website_sale_installation_templates.xml`, `static/src/js/installation_photos.js` | CA02, CA29, CA35, CA37, CA39, CA40, CA42, CA44, CA45 |
| **T08** ✅ | No repetir el intro (D54): `appointment.type._is_installation_checkout_source()` (defensivo con `request`) + el override de `appointment_info` apaga el bloque nativo tambien en ese caso | — | `models/appointment_type.py`, `views/appointment_templates.xml` | CA47 |
| **T09** ✅ | Propagacion al instalador: `sale.order._get_installation_task_notes()` — entre calles + notas, cada valor por `markupsafe.escape()` y retorno `Markup` (el destino `project.task.description` es Html, `odoo/addons/project/models/project_task.py:L153`), con las etiquetas *"Between streets:"* / *"Notes for the installer:"* en el idioma de la **compañia** (`order.company_id.partner_id.lang`: el lector es la cuadrilla interna) — y `sale.order.line._timesheet_create_task_prepare_values()` que lo antepone a `description` cuando la linea es la de la reserva | T01, T02 | `models/sale_order.py`, `models/sale_order_line.py` | CA46 |
| **T10** ✅ | `i18n/es_419.po`: entradas nuevas de **todos** los textos del paso rediseñado, **una sola voz (voseo)** (D53); ademas de la plantilla, cubre los `string`/`help` de los **campos nuevos** (`between_streets`, `installation_notes`, `installation_address_confirmed`) y las **etiquetas de la descripcion de la tarea de FSM** (*"Between streets:"* / *"Notes for the installer:"*, T09). **Ejecutado reconstruyendo el archivo completo** desde `odoo.tools.translate.trans_export` contra el arch final (no a mano linea por linea): se comparo el `.pot` resultante contra el `.po` viejo, se dieron de baja las entradas que dejaron de existir (el checklist por defecto completo, el `<li>` historico de las pilas y **todas** las entradas cuyo `#:` apunta a `installation_photo_examples`) y se tradujeron en voseo las genuinamente nuevas/reescritas; las entradas viejas ya estaban en voseo (nada que reescribir ahi) | T01, T02, T06, T07, T08, T09 | `i18n/es_419.po` | CA35, CA37, CA48 |
| **T11** ⏳ pendiente | **Dato en produccion** (no codigo): actualizar `installation_photos_message` del tipo de cita del checkout con la consigna de 3 fotos y **revisar `message_intro`** para que no repita los avisos que ahora estan repartidos por bloque. Se hace desde la ficha del tipo de cita en el **backend** (nunca desde el editor web: copia COW, D42) y queda documentado como paso de configuracion. **No aplica a esta base de desarrollo** (`nokey` local): es un paso operativo sobre la base de **produccion** (Odoo.sh), fuera del alcance de esta sesion de implementacion — queda pendiente para quien administre esa base | T06 | (sin archivos del repo) · se documenta en `README.md` en T12 | CA45 |
| **T12** ✅ | **Cierre**: documentacion (README del modulo, `static/description/index.html`, fila del README del repo — ver *Documentacion afectada*) + bump `version` del manifest `1.9.0` → **`1.10.0`** + `Estado` de esta spec a `implemented` con la `Version` sincronizada. Antes de cerrar, **confirmar que no entre basura al commit**: los `__pycache__/*.pyc` del modulo (incluido el huerfano de `migrations/1.3.0/`) estan cubiertos por `__pycache__/` en el `.gitignore` del repo — **verificado con `git check-ignore -v`**; si algun dia dejara de estarlo, se agrega antes del commit | T01..T11 | `README.md`, `static/description/index.html`, `../README.md`, `__manifest__.py`, `specs/website_sale_installation_appointment.md` | — (anti-drift + version sync) |

## Notas de implementacion

- **`carrier_id` no esta en ninguna vista de `sale.order`** (ni en `odoo/` ni en `enterprise/`; el
  flujo real del backend para asignarlo es el boton *Add shipping* → `set_delivery_line()`, no un
  `<field>` del formulario). Consecuencia para tests con `odoo.tests.Form`: el snapshot del
  onchange (`web/models/models.py`, `onchange()`) arma `cache_values` solo con los campos del
  `fields_spec` de la vista (los que el `Form` conoce); un campo AFUERA de esa vista **no** entra
  ahi, pero **si** se resuelve via el fallback a `record._origin[fname]` (`odoo/odoo/orm/fields.py`,
  rama `elif self.store and record._origin and not (...)`) si el registro sobre el que se abre el
  `Form` **ya tenia ese campo persistido en la base** *antes* de abrirlo. Por eso: no se puede
  **cambiar** el carrier desde un `Form` (`Form.__setattr__` tira `AssertionError`, el campo no
  esta en la vista), pero si se puede abrir un `Form` sobre un pedido que **ya tiene** `carrier_id`
  y editar otra cosa (ej. `order_line`): ahi el onchange sigue viendo el carrier real. El test de
  `tests/test_free_batteries.py` (plan `1.8.0`, cerrado) usa las dos variantes: `.new()` + llamada directa al metodo para la rama `Command.create` (mas simple,
  sin depender de este fallback), y `Form` sobre un pedido con `carrier_id` ya en base para la rama
  `Command.delete` (asi se prueba el trigger real `@api.onchange`, no solo el metodo).
- **Minimal footprint aplicado**: 5 campos nuevos (4 de negocio + 1 related de presentacion) y 6 overrides de defensa, cada uno con su razon
  verificada (ver *Metodos*). Lo que se evaluo y **se descarto por redundante o dañino** esta en
  *NO incluye* con el motivo, para que nadie lo "arregle" despues:
  `_get_update_prices_lines`, override de peso, xpath de `should_show_quantity_selector`,
  `_recompute_cart`, `_remove_delivery_line`, `linked_line_id`, campo de origen y modelo hijo o2m.
- **Dos caminos de sincronizacion, un solo calculo**: `_get_free_battery_needs()` y
  `_prepare_free_battery_line_vals()` los comparten el camino de base de datos
  (`_sync_free_battery_lines`, con `create/write/unlink` + `sudo`) y el de onchange (`Command.*` en
  memoria). No se pueden unificar: en un onchange `self` es `NewId` y un `create()` real escribiria
  en la base. El core hace lo mismo con las lineas de combo (`odoo/addons/sale/models/sale_order.py:L936`).
- **La defensa del carrito no es el HTML**: ocultar el selector y el boton Eliminar es cosmetico
  (nada impide un POST a `/shop/cart/update` con el `line_id` real). La garantia es que
  `_cart_update_line_quantity` llama a `_verify_cart_after_update()` **despues** de aplicar el
  cambio, asi que el override re-sincroniza en el mismo request. Documentado en D21/RB15 porque es
  una **propiedad del diseño**, no un accidente.
- **Riesgo funcional #1: la UoM.** El producto real del cliente ("Pilas AA - Energizer", tmpl 411 /
  variante 607, `PILAS_AA`) se vende en **"Paquete de 4"** (`uom.uom` 31, `relative_factor = 4.0`) a
  $6.000 el paquete en la tarifa del sitio ("Precio Público - Nokey", `product.pricelist` 22). Con
  `free_battery_qty = 4` se despacharian **16** pilas. Por eso el `string`, el `help` y la vista
  tienen que dejarlo inequivoco; el codigo nunca convierte unidades: crea la linea **sin**
  `product_uom_id` y deja que el ORM tome la UoM del producto.
- **Datos reales para la validacion manual**: carrier *Envio con Instalación* = `delivery.carrier`
  **3** (`fixed`, `fixed_price=0`, `free_over=false`, `max_weight=0`,
  `installation_appointment_type_id=1`); cerradura tmpl **466** / variante **686** (VAT 21%,
  `is_storable=False`, UoM Units); pilas tmpl **411**/**412** (variantes 607/608, VAT 21%,
  `is_storable=True`, **stock 0**, despublicadas); `website.prevent_zero_price_sale` **sin setear**
  en Nokey (1) y Sunra (3).
- **Aprovisionar stock de pilas**: son storable con stock 0, asi que los pickings las mostraran como
  no disponibles hasta que el cliente cargue existencias. Es configuracion, no codigo.
- **Deuda conocida, fuera de alcance**: existe un
  `migrations/1.3.0/__pycache__/end-reset_installation_view_overrides.cpython-312.pyc` **huerfano**
  (el `.py` nunca se commiteo). El usuario lo declaro fuera de alcance: **no se toca en esta feature**.
  Queda anotado para una limpieza dedicada.
- **Tests**: el repo `odoo_customization_sunra` **no** tiene `.swarm.conf`, asi que la politica de
  tests por repo no aplica; la suite `tests/test_free_batteries.py` se escribio en el plan `1.8.0`
  (cerrado) porque el usuario lo pidio explicitamente y el modulo no tenia `tests/`. Alcance acotado a los flujos troncales **de esta feature** (no se especifican
  tests del modulo preexistente). `TransactionCase` alcanza para todo lo de modelo (incluido
  `_cart_update_line_quantity`, que solo necesita el pedido con `website_id`); si algun helper del
  carrito exigiera `request`, usar `HttpCase` + `MockRequest` de `odoo.addons.website.tools`.
- **Dos mecanismos de texto que conviven** (D41 + D42): la **prosa estatica** del cliente va en campos del tipo de cita (`message_intro`, `installation_photos_message`) porque editar la plantilla desde el editor web crea una copia COW por sitio que se congela; el **texto que depende del estado del pedido** (aviso de pilas, condicionado a `includes_free_batteries`) va en la plantilla, porque un campo de texto no puede expresar una condicion. Criterio a aplicar en los proximos textos del modulo.
- **Rebase sobre `e5526ae`**: ese commit (textos configurables, otro dev) **no toca** `models/sale_order.py`, `models/sale_order_line.py`, `models/delivery_carrier.py` ni `views/website_sale_templates.xml`, asi que de las 12 tareas de **aquel** plan (`1.8.0`, cerrado) **solo la del aviso de pilas en la plantilla cambio de diseño** (el `<li>` objetivo quedo dentro de un `t-else` que solo se pinta si `message_intro` esta vacio). Ninguna otra tarea colisiona.
- **Interacciones con modulos vecinos, verificadas como INERTES** (no re-investigar):
  - **`website_sale_payment_method_price`** (modulo hermano, mismo repo): la linea de pilas contribuye **0** al total, asi que no mueve el descuento por medio de pago; y la linea de descuento global que ese modulo genera queda **fuera** de `_compute_price_unit` por `_is_global_discount()` (`odoo/addons/sale/models/sale_order_line.py:L601`), asi que nuestro `_get_display_price()` no la toca. **El orden de los overrides no importa.**
  - **Linea del booking de `website_appointment_sale`**: filtros disjuntos (`calendar_booking_ids` vs `is_free_battery_line`), y su propio `_cart_find_product_line` devuelve un recordset **vacio** cuando viene `calendar_booking_id`, con lo que nuestro `.filtered()` encadenado es un no-op.
- **Correccion sobre el metodo del peso**: `_get_invalid_delivery_weight_lines` **si** tiene llamadores de produccion, pero **solo** en las integraciones de carriers de terceros de enterprise (`delivery_dhl_rest`, `delivery_ups_rest`, `delivery_usps_rest`, `delivery_sendcloud`, `delivery_bpost`, `delivery_easypost` + legacy). Con el carrier `fixed` del cliente ninguno corre; la omision del override de peso sigue siendo correcta, pero el motivo es "ningun llamador **alcanzable en esta configuracion**", no "ningun llamador".
- **Naming deliberado**: el onchange se llama `_onchange_free_battery_lines`, no `_onchange_order_line`, porque ese nombre pisaria el onchange de combos del core (`odoo/addons/sale/models/sale_order.py:L936`). Desviacion consciente de la convencion `_onchange_<campo>` de `AGENTS.md`.
- **El guard `wsia_skip_battery_sync` es defensivo**: hoy **no hay** ningun camino de recursion real; se deja por simetria con el modulo hermano y para que un engache futuro no se muerda la cola.
- **`state` de la spec**: hoy esta en **`approved`** (el cliente aprobo el diseño el 11/09/2026 y el usuario
  aprobo esta spec; la pasada `analyze` de @reviewer del 11/09/2026 esta **incorporada en sitio**). Al cerrar
  T12 pasa a `implemented`; @reviewer/@testing la dejan `verified`.
- **Validacion manual del fix de marca del correo (D43, T13 del plan `1.9.0`, cerrado)**: crear/agendar una cita de instalacion sobre un pedido de una
  compañia (ej. Miluan SRL / Nokey) desde un usuario cuya compañia por defecto sea la otra (ej. YG
  S.A. / Sunra) y disparar el cron de alarmas (`ir_cron_scheduler_alarm`, Ajustes → Tecnico →
  Automatizacion → Acciones Planificadas — *Run Manually*) o esperar la ventana del recordatorio de
  la cita: el correo debe salir con el logo/colores/nombre de la compañia del **pedido**, no la del
  usuario del cron. Repetir con una cita **sin** pedido (agendada por el link compartido, D8): debe
  salir con la compañia del **organizador** (o de quien la creo, si tampoco hay organizador). El
  correo de **confirmacion** no deberia cambiar (ya salia bien: corre en el request del checkout,
  donde `env.company` ya es la del sitio).
- **Por que el primer intento de ese fix (T13 del plan `1.9.0`) no alcanzaba**: tenia solo el override de `_mail_get_companies()`,
  que resuelve "que compania es esta cita" pero **no** interviene en el layout del correo — eso lo
  pinta `_notify_by_email_prepare_rendering_context()` (armado de `render_context['company']`), que
  no llamaba a ese resolvedor. Los tests unitarios del resolvedor pasaban igual (verificaban la
  funcion correcta, aislada), lo que ocultaba que el sintoma (el logo mal) seguia sin arreglarse. El
  test que lo destapa es el de integracion (`test_notification_layout_uses_order_company_branding`),
  que renderiza la notificacion real con `MailCommon`/`mock_mail_gateway()` y lee el `body_html`
  generado, en vez de invocar el resolvedor directo.

### Notas del rediseño del paso (plan en curso)

- **Minimal footprint aplicado, otra vez**: 3 campos nuevos (uno en `res.partner`, dos en
  `sale.order`), **cero modelos**, **cero rutas nuevas**, **cero JS nuevo**. Lo que se reuso en vez de
  construir: `partner_shipping_id` como direccion de instalacion (D45), `/shop/address` como
  formulario de direccion (D12), `_get_installation_errors()` como gate del Paso 3 (D50),
  `next_website_checkout_step_href` del core como destino (D44), `collapse` de Bootstrap como
  acordeon, `_display_address()` como formato del resumen y `request.cart` como señal de "vengo del
  checkout" (D54).
- **Por que el estado se calcula en el servidor**: si el acordeon decidiera en QWeb cuando habilitar
  el Paso 3, tendriamos **dos** definiciones de "listo para pagar" (la de la vista y la de
  `_get_installation_errors()`) y se irian de sincro sola la primera vez que alguien toque una. Con
  `_get_installation_block_states()` hay una sola, y la vista solo pinta.
- **El orden de escritura del Paso 1 es load-bearing**: primero `res.partner` (entre calles), despues
  `sale.order` (notas + flag). Al reves, el override de `res.partner.write()` apagaria la
  confirmacion que se acaba de encender. Va comentado en el codigo, no solo aca.
- **La maqueta aprobada muestra mas de lo que entra**: dos inputs de "entre calles" (se unifican en
  uno, D46) y un **mapa de confirmacion del punto** al pie del Paso 1 (etapa aparte, issue Plane #69,
  D56). La spec sigue **la decision**, no el pixel de la maqueta; cuando entre el mapa, va **dentro**
  del Paso 1, sin mover el resto.
- **Sin migracion**: `installation_address_confirmed` es Boolean con default `False`, asi que los
  pedidos viejos arrancan "sin confirmar" y el propio paso los guia. Es coherente con la deuda ya
  declarada de `migrations/` (el modulo no tiene scripts y no se agregan en este cambio).
- **Tests**: el repo `odoo_customization_sunra` **no** tiene `.swarm.conf`, asi que la politica de
  tests por repo no aplica y **este plan no agrega suite**. Lo que si es obligatorio: que
  `tests/test_free_batteries.py` y `tests/test_calendar_event_mail_company.py` **sigan en verde** (el
  cambio toca `_get_installation_errors()` y `sale.order.write()`, que ellos no ejercitan hoy). Si el
  usuario quiere tests, el flujo troncal a cubrir es el gate de la direccion: confirmar → editar →
  que la confirmacion se caiga, y que `_get_installation_block_states()` devuelva `locked` en cadena.
  **Verificado al cerrar T12**: `test_free_batteries.py` corre **verde entero** (22/22, incluido CA32).
  `test_calendar_event_mail_company.py` falla en `setUpClass` — pero por un `ValidationError` de
  `_check_vat()` sobre el VAT de "Miluan SRL" (dato de la base `nokey` local, formato esperado
  `BE0477472701`), **no** por codigo de este cambio: se verifico aislando el nuevo `ResPartner.write()`
  (neutralizandolo temporalmente) y el mismo error se reproduce identico sin el, disparado por
  `MailCommon.setUpClass()` del core (cadena `mail_thread`/`website`/`ai_fields` → `_inverse_vat`)
  reusando `env.company` como `company_admin`. Deuda de datos preexistente de la base local, ajena a
  D44-D56/T01-T12; no se toca en esta feature (no es un dato de negocio de este modulo).
- **Lo que quedo como fallback y no como camino vivo** (hallazgo del `analyze`): con la plantilla nueva el
  form de fotos manda **siempre** `stay_on_step`, asi que la rama final de `shop_installation_submit()` y el
  helper `_get_installation_next_step_href()` (`controllers/website_sale_installation_appointment.py:L120`,
  `:L125`, `:L288`) dejan de ser alcanzables desde la UI. **Se conservan**: son la red para un POST sin el
  input oculto (pagina cacheada de la version anterior, cliente que postea el form a mano) y sacarlos obliga a
  reescribir el flujo por una ganancia nula. Que no se lea como codigo olvidado.
- **Un mensaje, un solo lugar**: los estados "falta X" se leen en la **razon del candado del bloque** que los
  resuelve; el `alert` de arriba queda solo para los errores de submit (archivo invalido, > 10 MB, mas de 10
  fotos). Antes del rediseño los dos decian lo mismo con redacciones distintas.
- **El candado no es seguridad**: es presentacion. `/shop/installation/submit` y `/shop/payment` siguen
  validando server-side (D5/D21), y el Paso 1 ademas frena el **carrito anonimo** antes de escribir
  (`_is_anonymous_cart()`): el endpoint es publico y el `partner_shipping_id` de un carrito anonimo es un
  contacto **compartido**.
- **Lo que NO se toca del paso**: el upload y la validacion de fotos (mimetype real, 10 MB, 10 fotos),
  el `oe_structure` de snippets, la guia de medidas A/B junto a la pregunta, el gate de
  `/shop/payment` y toda la logica de pilas. El rediseño es de **presentacion + dos datos nuevos**.
