# Spec de modulo: website_sale_installation_appointment

| Campo | Valor |
|-------|-------|
| **Modulo** | `website_sale_installation_appointment` |
| **Version** | `1.14.0` (== `version` del `__manifest__.py`, formato `x.x.x`) |
| **Serie Odoo** | `19` (informativa) |
| **Estado** | `implemented` |
| **Actualizado** | `2026-09-24` |
| **Depurado** | `2026-09-24` |

> Cliente: **Miluan SRL / Nokey** (eCommerce de cerraduras inteligentes, `nokey.odoo.com`).
> Repo: `extra-addons/odoo_customization_sunra`. Licencia LGPL-3, autor Sunra.
> `depends`: `website_sale`, `delivery`, `website_appointment_sale`, `sale_project`.

## Objetivo

Vender desde el eCommerce un **envio con instalacion incluida** y que esa venta quede **agendada como
Cita** (app Citas) con las **fotos del lugar**, la **direccion de instalacion**, la **tarea de Field
Service** del instalador y el cliente **invitado al portal**; permitir agendar la misma instalacion
**por un link compartido**, sin pasar por el eCommerce; y que el metodo de envio pueda ademas
**incluir sin cargo las pilas** que el producto necesita, generando automaticamente la linea de pedido
en $0 (el costo ya esta integrado en el servicio de instalacion).

## Decisiones vigentes

> Decisiones de diseño que rigen HOY. Si una decision nueva pisa una vieja, se **edita la fila**.
> Lo asumido sin confirmacion del usuario va marcado `[ASUNCION]`.

| # | Decision | Valor vigente |
|---|----------|---------------|
| D1 | ¿Como se marca que un envio lleva instalacion? | Opt-in **por metodo de envio**: `delivery.carrier.installation_appointment_type_id`. Vacio = envio normal. |
| D2 | ¿Que tipo de cita se acepta para instalacion? | Solo tipos con **paso de pago** y **producto de reserva** que genere tarea o tenga precio; se frena con `ValidationError` al guardar el carrier. |
| D3 | ¿Como aparece/desaparece el paso "Instalacion" del checkout? | Filtrando el dominio de pasos (`website._get_allowed_steps_domain()`), no con vistas condicionales: el core calcula solo el paso siguiente/anterior. Es **un solo paso del core** (`/shop/installation`, `sequence 400`, entre Direccion 250 y Pago 999): los 3 bloques (D44) viven **adentro** de ese paso — sin pasos extra en el wizard ni rutas nuevas, asi el calculo de siguiente/anterior y el wizard visual del core quedan intactos. |
| D4 | ¿Que valida el upload publico de fotos? | Mimetype **real del contenido** (no el declarado), 10 MB por archivo, 10 fotos por pedido. Minimo configurable por carrier (`installation_min_photos`; 0 = opcional). |
| D5 | ¿Se puede pagar sin agendar / sin fotos? | No: gate en `_check_cart_is_ready_to_be_paid()` + `_get_shop_payment_errors()`, y `shop_payment()` redirige al paso en vez de mostrar el error. |
| D6 | ¿Donde ve la cuadrilla las fotos? | Se copian al chatter de la **Cita** y de la **tarea de FSM** despues de `super()._action_confirm()`. |
| D7 | ¿El cliente de una instalacion recibe portal? | Si, **incondicional** para pedidos con `installation_required`, via el `portal.wizard` nativo. Idempotente (usuario activo o archivado → no-op con nota en el chatter). Nunca rompe la confirmacion (savepoint + log). |
| D8 | ¿Y las citas agendadas FUERA del eCommerce (link compartido)? | `appointment.type.installation_fsm_project_id` → la tarea de FSM la crea este modulo en `calendar.event.create()`, y se sincroniza al reprogramar/cancelar/desarchivar. |
| D9 | ¿Como se evita que el cliente escriba cualquier cosa en el formulario de la cita? | Campo propio `appointment.question.answer_format` (libre/entero/numero/telefono/documento): emite `type`/`inputmode`/`pattern` reales y **revalida en el servidor**. |
| D10 | ¿Donde se muestran los diagramas de medidas? | Dentro del bucle de preguntas, justo antes de la pregunta marcada con `appointment.question.installation_measure_guide` (un solo lugar sirve para los dos caminos). |
| D11 | ¿Una sola instalacion por pedido? | Si: reagendar descarta la reserva anterior (`_remove_previous_installation_bookings`). |
| D12 | ¿Nombre de la empresa en el checkout? ¿Donde se **carga** la direccion? | Se saca `#company_name_div` heredando `website_sale.address_form_fields` (NO desactivando `address_b2b`, que se lleva la Responsabilidad de ARCA de `l10n_ar`). **La direccion se carga en el paso del core** (`/shop/address`): el modulo **no** agrega un segundo formulario de direccion en el checkout (D45). En nuestro paso solo se **muestra en resumen**, con link "editar" a `/shop/address?partner_id=<partner de envio>&address_type=delivery&callback=/shop/installation` y con los dos datos que el core no tiene (D46, D47). El **`callback` es lo que hace que *Guardar* vuelva al paso de instalacion** y no al checkout: el core redirige a `callback or '/shop/checkout'` (`odoo/addons/website_sale/controllers/main.py:L1234`, `:L1236`) y usa el mismo valor para el link *Descartar* (`:L1184`). El parametro viaja **nativo**, sin codigo nuestro: `shop_address(**query_params)` (`odoo/addons/website_sale/controllers/main.py:L1099`) → `_prepare_address_form_values(callback=…)` → `shop_address_submit(callback=…)`. |
| D13 | ¿Como se marca que un envio incluye las pilas? | **Segundo opt-in independiente**, `delivery.carrier.includes_free_batteries` (Boolean). No se ata a `installation_appointment_type_id`: otro envio puede incluir pilas sin agendar cita. |
| D14 | ¿Donde se configura que pilas lleva un producto? | En la **ficha del producto** (`product.template`): `free_battery_product_id` + `free_battery_qty`. |
| D15 | ¿En que unidad se expresa `free_battery_qty`? | En la **UoM del producto de pila elegido** (el producto real del cliente se vende en "Paquete de 4": `1` = un paquete = 4 pilas). El `string`/`help` lo dicen explicitamente y la vista muestra la UoM al lado. La linea se crea **sin** pasar `product_uom_id` para que el ORM tome la UoM propia del producto. |
| D16 | ¿Una linea por cerradura o una por pila? | `[ASUNCION]` **Una por producto de pila**, con la suma: dos cerraduras distintas que usan la misma pila dan UNA linea. Agrupar es lo que menos ensucia el carrito y la factura. |
| D17 | ¿Como se mantiene la linea sincronizada? | Reconciliacion **idempotente desde cero** en cada llamada (crea lo que falta, ajusta cantidades, borra lo que sobra). Clave: `(pedido, producto, is_free_battery_line)`. Nunca incremental. Precedente interno: `_apply_payment_price_rule` de `website_sale_payment_method_price`. |
| D18 | ¿Como se marca la linea gratis? | Flag tecnico propio `sale.order.line.is_free_battery_line`. **NO** se usa `is_delivery=True` por dos motivos: (a) `unlink()` de una linea `is_delivery` **pone `carrier_id = False`** en el pedido (`odoo/addons/delivery/models/sale_order_line.py:L29`) → borrar la linea de pilas **desarmaria el metodo de envio**; (b) `_show_in_cart()` excluye las lineas de envio y la linea quedaria **oculta**, contra D20. |
| D19 | ¿Se cuelga la linea de la cerradura con `linked_line_id`? | **No.** (a) contamina el `name` en la **factura** con `"Option for: <cerradura>"`; (b) `ondelete='cascade'` es un `ON DELETE CASCADE` de SQL: borrar la cerradura evaporaria la linea **sin correr ningun `unlink()` Python** ni los `@api.ondelete` del core; (c) la colision de carrito se resuelve mejor con `_cart_find_product_line`. |
| D20 | ¿La linea gratis se ve en el carrito? | **Si, se ve, pero no se puede tocar** (decision del usuario): sin selector de cantidad y sin boton Eliminar. `[ASUNCION]` que el **link al producto** tambien se apague — es efecto colateral de `_is_sellable()` y es coherente (la pila no se vende sola). La garantia real no es el HTML (ver D21). |
| D21 | ¿Que impide que el cliente la borre por el endpoint? | Nada a nivel HTTP — y no hace falta: `_cart_update_line_quantity()` llama a `_verify_cart_after_update()` **despues** de aplicar el cambio, asi que la re-sincronizacion **auto-cura** la linea en el **mismo request**. La defensa es una propiedad del diseño, no el ocultamiento cosmetico. |
| D22 | ¿Como se garantiza el precio 0? | En `_get_display_price()` (el load-bearing: cubre el camino normal y el forzado de `_compute_price_unit`), no con `price_unit=0` en el create (que no marca la linea como precio manual). |
| D23 | ¿Y el descuento? | `_compute_pricelist_item_id()` → `False` para la linea gratis, para que `_recompute_prices()` no le ponga `discount > 0` (una tarifa `percentage` prenderia la columna **Descuento en todo el PDF** y el precio tachado en el carrito). Precedente literal: `delivery`. |
| D24 | ¿Que pasa si el cliente agrega la MISMA pila como producto suelto? | `[ASUNCION]` Se crea una linea **separada y paga** (`_cart_find_product_line()` filtra las lineas gratis, asi `_cart_add` no fusiona). El que quiere pilas de repuesto las paga. |
| D25 | ¿"Volver a pedir" re-agrega la pila? | `[ASUNCION]` No: `_is_reorder_allowed()` → `False` (si no, se re-agregaria **sin** el flag y a precio de tarifa). |
| D26 | ¿Pedidos armados en el backend (venta telefonica)? | Cubiertos con `@api.onchange('order_line', 'carrier_id')` (sincronizacion **en memoria** con `Command.*`, como el core con las lineas de combo) + red de seguridad en `action_confirm()`. |
| D27 | ¿Donde va la red de seguridad al confirmar? | En **`action_confirm()` antes del `super()`** (state todavia `draft`/`sent`). **No** en `_action_confirm()`: ahi el `state` es `'sale'` y borrar lineas choca con `_unlink_except_confirmed`. El override de `_action_confirm()` es el de fotos + portal + ubicacion de la cita (D62). |
| D28 | ¿La linea gratis se ve en la factura? | Si, a $0. **Aceptado explicitamente por el usuario** (deja constancia de que las pilas fueron entregadas). |
| D29 | ¿El comportamiento no-editable depende de publicar la pila? | No: se override-ea `_is_sellable()`. Con las pilas despublicadas daria `False` igual, pero publicarlas reactivaria el selector de cantidad. El override lo hace independiente del estado de publicacion. |
| D30 | ¿Se publican los productos de pila en el sitio? | No hace falta (la linea se crea server-side, la pila no se vende sola). Pueden quedar despublicados; publicarlas no cambia el comportamiento (D29). |
| D31 | ¿Como se avisa en el checkout que las pilas van incluidas? | Con **una sola linea** en el renglon corto al pie del acordeon, con `t-if`/`t-else` sobre `order.carrier_id.includes_free_batteries`: "van incluidas sin cargo" / "tenes que tener 4 u 8 AA/AAA el dia de la instalacion". Va **fuera** de cualquier `t-if` de texto configurable, asi que se ve tambien con `message_intro` cargado, y lleva `o_not_editable` (D42). Una sola linea con dos ramas hace **imposible** que los dos mensajes convivan (CA37). |
| D32 | ¿Sobre que estados actua la sincronizacion? | `[ASUNCION]` Solo `draft`/`sent`. En un pedido confirmado, ajustar/borrar lineas es trabajo del backoffice (y chocaria con `_unlink_except_confirmed`). |
| D33 | ¿El flag se copia al duplicar el pedido? | **Si**: `is_free_battery_line` va **sin `copy=`** (default `True`). El molde correcto es `is_delivery` del core, que tampoco lo declara (`odoo/addons/delivery/models/sale_order_line.py:L9`). Con `copy=False` el duplicado quedaria con la linea a $0 **sin el flag** → el primer recompute la llevaria a precio de tarifa y el sync, al no reconocerla, **crearia una segunda linea gratis** (doble cantidad de pilas, la mitad facturada). ⚠️ El `copy=False` de `is_payment_method_discount` del modulo hermano **NO es el molde**: esa linea es un descuento atado al medio de pago que se re-elige en el checkout; esta es una linea de producto que se entrega. No unificar los dos flags. |
| D34 | ¿Que pasa con el control de stock del eCommerce? | Se override-ea `_check_availability()` → `True` para la linea gratis. `website_sale_stock` es `auto_install` y esta **instalado** en la base: su `_check_cart_is_ready_to_be_paid` tira `ValidationError` si una linea storable sin *Sell when Out-of-Stock* supera el stock libre. Con *Pilas AA* (tmpl 411) en `allow_out_of_stock_order = false` y **stock 0**, el cliente quedaria **sin poder pagar** por un producto que no eligio y que no puede borrar (D20/D21 lo auto-curan): checkout muerto. No se resuelve "por configuracion" — los datos reales contradicen ese requisito. **Por que el override no queda sombreado**: `website_sale_stock` **no** esta en nuestro `depends` (agregarlo arrastraria `stock`), pero el orden de carga es `(phase, depth, order_name)` con `depth` = camino mas largo a `base` (`odoo/odoo/modules/module_graph.py:L175`, `:L225`): dependemos de `website_appointment_sale` → `website_sale`, asi que `depth(nuestro) >= depth(website_sale)+2` mientras `depth(website_sale_stock) = depth(website_sale)+1` → **cargamos despues y ganamos el MRO**. ⚠️ Riesgo latente: si un cambio de `depends` empata la profundidad, el desempate es alfabetico (`website_sale_installation_appointment` < `website_sale_stock`) y quedariamos **primeros**, con el override convertido en **codigo muerto** y el checkout muerto en silencio. **CA32 es el tripwire** de esa regresion, cubierto por `tests/test_free_batteries.py`. |
| D35 | ¿El `name` de la linea nombra el metodo de envio? | **No.** Se usa un texto sin el nombre del carrier (*"Included with your shipping method — no extra charge."*) para no tener estado que sincronizar: el sync solo escribe `product_uom_qty`, asi que al pasar a **otro** envio que tambien incluye pilas (D13) el nombre horneado quedaria mintiendo en el carrito **y en la factura**. La descripcion se arma en el **idioma del cliente**. |
| D36 | ¿El sync puede tocar lineas ya facturadas o entregadas? | **No**: se excluyen del `write` y del `unlink` las lineas con `qty_invoiced` o `qty_delivered` distintos de 0. `state in ('draft','sent')` **no** implica "nada facturado": un pedido facturado que el backoffice devuelve a presupuesto ("Set to Quotation") vuelve a `draft` con `qty_invoiced != 0`, y `_check_line_unlink` solo bloquea en `state == 'sale'`. Mismo criterio que `_remove_delivery_line` del core. |
| D37 | ¿Que engaches cubren el backend? | Tres, complementarios: el `@api.onchange` (carga interactiva), **`set_delivery_line()`** (el boton **Add shipping** → wizard `choose.delivery.carrier` escribe por `write`, los onchange **no** corren) y `action_confirm()` (red final). `_set_delivery_method()` es el unico que cubre el camino de **quitar** el envio, donde `set_delivery_line` no se llama. |
| D38 | ¿Y si la pila configurada es de otra compañia? | `free_battery_product_id` lleva `check_company=True` + domain de compañia (la base tiene 2 compañias), y el agregado **saltea** el producto incompatible en vez de romper. `product_id` de `sale.order.line` es `check_company=True` y el `sudo()` del sync **no** exime de `_check_company`: sin esto, una mala configuracion daria **error 500 en cada request del carrito** del visitante publico. |
| D39 | ¿Cantidades no positivas? | Solo se acumulan lineas con `product_uom_qty > 0`, y los `needs` que quedan en `<= 0` se descartan (caen en `to_unlink`). Un pedido con la cerradura en `-1` (nota de credito preparada como pedido negativo) generaria una linea de pilas **negativa** → `stock_delivery` crearia un movimiento de **devolucion** de pilas que el cliente nunca entrego; y `+1 / -1` dejaria una linea en 0 en el carrito y en el PDF. |
| D40 | ¿La cantidad convierte UoM de la **cerradura**? | `[ASUNCION]` **No**: `free_battery_qty * line.product_uom_qty` se toma tal cual, porque las cerraduras se venden en **Units**. Si una se vendiera en "Caja de 6", 1 caja pediria 1 paquete en vez de 6. La conversion es de una linea: `line.product_uom_id._compute_quantity(line.product_uom_qty, line.product_id.uom_id)` (molde: `odoo/addons/delivery/models/sale_order_line.py:L24`). Las cerraduras **dentro de un combo** si aportan pilas (deseable), pero configurar pilas en la plantilla del combo **y** en el item las contaria dos veces. |
| D41 | ¿Donde se pinta el aviso de "pilas incluidas"? | En el **renglon corto al pie del acordeon**, junto a la garantia, condicionado **solo** a `order.carrier_id.includes_free_batteries` y fuera de todo `t-if`/`t-else` de texto configurable. La logica **condicional a datos** vive en la plantilla —un campo de texto configurable no puede expresar una condicion—, mientras los textos **estaticos** del cliente van en campos (D42). **Los dos criterios conviven**: prosa estatica → campo; texto que depende del estado del pedido → plantilla. |
| D42 | ¿Por que los textos del cliente van en campos y no en las plantillas? | Porque **editar una plantilla desde el editor web crea una copia COW por sitio que deja de recibir las actualizaciones del modulo**: un retoque de la guia de fotos desde el editor la congela en ese sitio y ningun deploy la actualiza. El checklist sale del campo **nativo** `message_intro` y la consigna de fotos del campo `installation_photos_message`; vacios → el texto por defecto del modulo. Van **por tipo de cita** a proposito: el del eCommerce cobra online y el del link cobra el dia del turno, asi que las condiciones difieren. **Corolario operativo**: un texto **por defecto** del modulo no llega al registro ya cargado en produccion; ese se ajusta **como dato**, desde la ficha del tipo de cita en el backend (nunca desde el editor web). **Corolario de la plantilla**: por la misma trampa, la prosa estatica del modulo lleva `o_not_editable` a nivel **contenedor** — el `div.accordion#installation_accordion` (encabezados de bloque, razones del candado, duracion, condicion de pago, avisos de cada bloque), el `div` que envuelve `installation_photo_examples` (fotos reales del cliente), el bloque de direccion del formulario de la cita y los avisos de obligatoriedad (D61): un elemento agregado adentro sin clase propia queda igual **protegido**. Quedan **fuera** de esa marca el `oe_structure` (existe para que el cliente ponga snippets) y los `t-field` de `message_intro` / `installation_photos_message` (son campos, se editan en el backend). |
| D43 | ¿Que compañia sella el correo de una cita de instalacion (logo/colores del layout de notificacion)? | La confirmacion Y el recordatorio de la cita se mandan por el **mismo camino** — `_notify_attendees()` (`odoo/addons/calendar/models/calendar_attendee.py:L124-196`) → `message_notify()` sobre el `calendar.event`. La diferencia es **cuando** corre cada uno: la confirmacion la dispara el `create()` del attendee dentro del **request web** (`enterprise/appointment/models/calendar_attendee.py:L16-44`), donde `env.company` es la del sitio; el recordatorio lo dispara el **cron** de alarmas (`odoo/addons/calendar/models/calendar_alarm_manager.py:L182-202`, `_send_reminder`), cuyo `env.company` es la del usuario tecnico del cron. El logo/colores los pinta `_notify_by_email_prepare_rendering_context()` (`odoo/addons/mail/models/mail_thread.py:L3606-3719`, el calculo en `:L3657-3666`), que arma `company` leyendo `record.company_id` **directo** — no via `_mail_get_companies()` — y cae a `env.company` porque `calendar.event` no tiene ese campo. Por eso hay **dos** overrides en `calendar.event`, ambos con el mismo resolvedor: `_mail_get_companies()` (compañia del `record_company_id`/alias domain/reply-to — molde `odoo/addons/mail/models/models.py:L128-140`, uso real en `message_notify` `odoo/addons/mail/models/mail_thread.py:L2831`) y `_notify_by_email_prepare_rendering_context()` (el que **pinta** el layout, molde de override `odoo/addons/sale/models/sale_order.py:L1758`). Orden de resolucion: (1) compañia del **pedido de venta** que origino la cita — el mas viejo (por `id`) entre los no cancelados, `sale.order.line.calendar_event_id`, porque duplicar un pedido copia ese vinculo sin `copy=False` (`enterprise/website_appointment_sale/models/sale_order_line.py:L11`); (2) compañia del **organizador** (`user_id.company_id`); (3) compañia de **quien creo la cita** (`create_uid.company_id`, mismo heuristico que el core para citas sin usuario, `odoo/addons/calendar/controllers/main.py:L66`); (4) lo que resuelva el `super()` con el `default` recibido. **Efecto colateral deseado** de `_mail_get_companies()`: el reply-to/alias domain del recordatorio queda con el dominio de la compañia del pedido (cada compañia tiene su propio dominio de alias — `nokey.odoo.com`, `sunra.odoo.com`, `sunraprueba.odoo.com`, `miluanprueba.odoo.com` — en la misma instancia). |
| D44 | ¿Como se estructura el paso `/shop/installation`? | En **3 bloques tipo acordeon** (Bootstrap `collapse`, **sin JS nuevo**): *Paso 1 · Installation address*, *Paso 2 · Appointment and photos*, *Paso 3 · Payment*. Los tres **se ven desde el inicio** (pedido del cliente: "veo cuales son todos los pasos y se me van habilitando"); el completado se resume con **tilde** + su resumen en el encabezado, el bloqueado con **candado** y la razon ("Se habilita al completar el paso N"). El bloque bloqueado **no renderiza su cuerpo** (no hay controles deshabilitados que igual se puedan postear a mano). El estado lo calcula el **servidor** (`sale.order._get_installation_block_states()`), no la plantilla: una sola definicion de "listo para pagar", compartida con el gate. **El rotulo del bloque 3 sale del dato, no de una constante**: se toma de `next_website_checkout_step.name`, porque el paso siguiente **no siempre es Payment** — entre 400 y 999 existe el paso nativo *Extra Info* (`/shop/extra_info`, `sequence 500`, `odoo/addons/website_sale/data/data.xml:L82-85`), publicado por sitio solo si la vista `website_sale.extra_info` esta activa (`odoo/addons/website_sale/models/website.py:L959-960`). **El candado es presentacional**: `/shop/installation/submit` y `/shop/payment` validan server-side (D5/D21). |
| D45 | ¿Que es "la direccion de instalacion" en el checkout? | **Es la direccion de entrega del pedido** (`sale.order.partner_shipping_id`): la que el core pide en `/shop/address` y la que Field Service usa para la tarea del instalador (`enterprise/industry_fsm_sale/models/sale_order.py:L118`, `enterprise/industry_fsm_sale/models/project_task.py:L237`). **No** hay otro modelo ni otro formulario de direccion: dos fuentes de verdad terminan con el instalador yendo a la direccion equivocada, y el core ya valida/normaliza esa. El link **editar** del Paso 1 apunta a `/shop/address?partner_id=<id>&address_type=delivery&callback=/shop/installation` (D12). |
| D46 | ¿Como se resuelve "entre calles"? | Campo **`res.partner.between_streets`** (Char), **un solo campo libre** ("Peru y Chile"), editable desde el Paso 1. `[ASUNCION]` **opcional**: es clave en provincia pero no puede frenar a quien compra en ciudad. Un solo input y no dos: es un dato que el instalador lee de corrido, y dos campos obligan a inventar la segunda esquina cuando la cuadra tiene una sola referencia. Va en el **partner** (no en el pedido) porque describe el domicilio, no la venta. |
| D47 | ¿Donde van las indicaciones para el instalador? | Campo **`sale.order.installation_notes`** (Text, "Notes for the installer", opcional), editable en el Paso 1. Va en el **pedido** y no en el partner porque es de **esta** instalacion ("porton negro, timbre PB, avisar antes de subir"), no del domicilio para siempre. Se propaga a la **descripcion de la tarea de FSM** junto con `between_streets`: el instalador lee el tablero de Field Service, no la ficha del contacto. |
| D48 | ¿Como se sabe que el Paso 1 esta cumplido? | Campo **`sale.order.installation_address_confirmed`** (Boolean, `copy=False`, default `False`) que setea el boton **Confirm address** del Paso 1, junto con el guardado de `between_streets` + `installation_notes`. **Vuelve a `False`** ante cualquier cambio posterior de la direccion: `sale.order.write()` (cambia `partner_shipping_id`) y `res.partner.write()` (se editan los campos de domicilio del partner de envio), molde literal del core (`odoo/addons/website_sale/models/res_partner.py:L58`). Default `False` → sin migracion: los pedidos abiertos solo tienen que apretar el boton. |
| D49 | ¿Como se escriben esos campos desde el frontend publico? | **Solo** por nuestra ruta `/shop/installation/submit` (rama `confirm_installation_address`), con `sudo()` **acotado campo por campo** — el visitante publico no escribe `res.partner` ni `sale.order` — y con **truncado server-side** del largo (`installation_notes` 1000, `between_streets` 100). **NO** se extiende `res.partner._get_frontend_writable_fields()`: esa lista es un **filtro de entrada** de `_parse_form_data()` (`odoo/addons/portal/controllers/portal.py:L594`, `:L598`), y como el formulario de direccion del core **no renderiza** `between_streets`, el campo nunca llega por ahi — sumarlo seria codigo sin consumidor. Si algun dia el input entra al form del core, ahi se suma, con el molde `odoo/addons/website_sale/models/res_partner.py:L40` (que **suma** al `super()`; ese override **no** lleva `@api.model`, aunque la base si — `odoo/addons/portal/models/res_partner.py:L10`). |
| D50 | ¿La confirmacion de la direccion bloquea el pago? | `[ASUNCION]` **Si**: `_get_installation_errors()` suma un mensaje mas ("Please confirm the installation address."). Se reusa el gate de D5 en vez de inventar otro, y evita el estado incoherente "Paso 1 pendiente + Paso 3 habilitado" para quien agendo por otro camino (link, backoffice). Criterio conservador: bloquea de mas, nunca de menos. Si el cliente prefiere lo contrario, se saca **esa sola linea** y el Paso 3 queda colgado solo de turno + fotos (el Paso 2 sigue bloqueado igual por D44). |
| D51 | ¿Cuantas fotos y de que? | **3**: (1) frente de la puerta con la manija, (2) canto/espesor, (3) marco. La guia suma **3 ejemplos de "asi no"**: borrosa/oscura, cortada, tapada por la mano. El texto por defecto de la consigna pide esas 3 fotos, alineado al minimo real del carrier (`installation_min_photos = 3`). El **gate** es `installation_min_photos` del carrier: la guia es didactica y el progreso dice *"N de `installation_min_photos`"*, no un 3 horneado. |
| D52 | ¿Donde van los avisos (pago, duracion, garantia, pilas)? | **Repartidos en el bloque donde aplican**, no todos juntos arriba: duracion (2 a 4 h) → Paso 2; condicion de pago → Paso 3; **garantia + pilas en un renglon corto** al pie del acordeon. El renglon de pilas sigue la regla de D31/D41: **una sola linea con `t-if`/`t-else`**, las dos versiones mutuamente excluyentes **por construccion** (CA37). |
| D53 | ¿Como se habla en el paso? | **Una sola voz: voseo**. Los strings van en **ingles** en el codigo (AGENTS.md) y la voz se fija en la **traduccion** `i18n/es_419.po`, el locale del modulo: todas sus entradas en voseo ("Subi", "Elegi", "Agenda"), sin "tu/usted". |
| D54 | ¿Como se evita repetir el intro en la pagina de la cita? | Condicionando por **carrito**, no por URL: `appointment.type._is_installation_checkout_source()` devuelve `True` cuando `request.cart` requiere instalacion **con ese** tipo de cita, y el override de `appointment_info` apaga tambien en ese caso el bloque nativo de `message_intro`. **Por que no un parametro en la URL de "Agendar"**: el flujo nativo navega varias veces (calendario → `/appointment/<id>/info?...` que arma el **core**) y el parametro **se pierde** en el camino. `request.cart` esta disponible en cualquier pagina del frontend (`odoo/addons/website_sale/models/ir_http.py:L32`). El camino del **link compartido** (sin carrito) ve el intro arriba del calendario (D8). |
| D55 | ¿De donde salen las fotos de la guia? | De **6 fotos reales** del cliente, en el repo como JPEG (ancho maximo 600 px) en `static/src/img/`: `photo_ok_front.jpg`, `photo_ok_edge.jpg`, `photo_ok_frame.jpg`, `photo_bad_blurry.jpg`, `photo_bad_cropped.jpg`, `photo_bad_obstructed.jpg`. Las de **medidas** A/B conservan su nombre (`installation_measure_a_door_thickness.jpg`, `installation_measure_b_lock_length.jpg`). Nunca se linkean imagenes externas (AGENTS.md). |
| D56 | ¿El mapa de confirmacion del punto es parte del modulo? | **No**: es una etapa aparte. Necesita proveedor de mapas, geocoding y coordenadas en el pedido. El Paso 1 cierra con el boton **Confirm address**; si el mapa se suma, va **dentro** de ese bloque, sin mover el resto. |
| D57 | ¿Que pide el formulario de la cita cuando el cliente **viene del checkout**? | **Solo lo que no le preguntamos todavia.** Nombre, correo, notas y fotos ya se cargaron en el checkout, y las fotos subidas en el formulario de la cita no cuentan para el gate del Paso 2 (se guardan en la cita, no en el pedido): pedirlas ahi obligaria a subirlas dos veces. Se resuelve en **tres niveles**: (a) **codigo**, `appointment.type._is_installation_asking_photos()` = `installation_request_photos` **y** no venir del checkout (`_is_installation_checkout_source()`, D54), **tanto en la plantilla como en la validacion del controller** (con el gate solo en la plantilla, el controller rechazaria el turno por un campo que el cliente no tiene delante); (b) **codigo**, nombre y correo se colapsan a `input[type=hidden]` + una linea "Reservas como `<nombre>` `<mail>`" cuando ya los sabemos (el submit nativo los necesita; si `partner_data` viene vacio se cae al formulario nativo); (c) **dato**, la pregunta "Notas aclaratorias" va solo en el tipo del link —en el del checkout duplica "Indicaciones para el instalador" del Paso 1— (las preguntas son reutilizables entre tipos). El gate va en codigo y no solo en configuracion porque **el mismo tipo de cita puede usarse en los dos caminos**, y ahi ninguna configuracion los distingue. |
| D58 | ¿De donde sale la direccion cuando la cita se agenda **por el link**? | **Se la pide el formulario de la cita**, con un bloque propio: calle y numero (obligatorio), piso/depto, localidad (obligatorio), codigo postal y **entre calles**. Sin ese bloque el formulario crea un contacto solo con nombre y mail, y la tarea de Field Service sale **sin lugar al que ir**. Se activa con `appointment.type.installation_request_address`, y nunca se muestra en el camino del checkout (ahi la direccion es la de entrega del pedido y se confirma en el Paso 1, mismo criterio que D57). Los valores se escriben en el **contacto** que reserva —de donde la tarea toma la direccion— con criterio **todo o nada sobre la calle**: si el contacto no tiene domicilio se escribe la direccion completa; si ya lo tiene (cliente conocido, alta del backoffice) **no se le pisa nada** y lo declarado se postea en la cita **y en la tarea de Field Service**, que es donde mira la cuadrilla. Campo por campo ("solo los vacios") seria peor: un contacto con calle cargada pero sin localidad terminaria con la calle vieja y la localidad nueva, una direccion que no existe. El "entre calles" se **agrega al cuerpo de la tarea**, porque ninguna vista estandar de `project.task` imprime ese campo; como la tarea la crea el `create()` de la cita (antes de que el controller escriba la direccion), se **refresca** la descripcion — fuera de la condicion de escritura, para que el entre calles llegue igual cuando no se escribe el contacto. Todo el bloque corre dentro de un **savepoint**: la reserva ya esta hecha y un fallo escribiendo el contacto no puede costarle el turno al cliente. La direccion declarada ademas queda como **ubicacion de la cita** (D62). |
| D59 | ¿Como se ordena el formulario del link? | **En cuatro secciones numeradas**, con titulo y una linea de ayuda: **1 Tus datos** (nombre y correo), **2 Sobre tu puerta** (las preguntas del tipo de cita), **3 Direccion de instalacion** (el bloque de D58) y **4 Fotos del lugar**. En ese formulario la **etiqueta va arriba del campo** y a lo ancho: el nativo la pone en `col-sm-3` contra un `col-sm-9`, y con seis campos seguidos se lee como un muro. **Solo el camino del link**: el del checkout conserva el layout nativo (son dos campos). El gate es `appointment.type._is_installation_link_form()`, que reusa `installation_fsm_project_id` (el marcador de "agendado fuera del eCommerce", D8) y excluye el checkout. La clase marcadora del form va por `t-attf-class` **repitiendo la del core**: el nativo la declara estatica y en el render el atributo dinamico pisa al estatico (`ir_qweb.py:1946`). En el link, las etiquetas propias de los bloques de direccion y fotos (con su " *") van ocultas (`d-none`): las reemplaza el titulo de la seccion. |
| D60 | ¿Que direcciones se ofrecen para facturar cuando se destilda "Same as delivery address"? | **Todas las de facturacion del cliente, menos la que se usa como direccion de entrega, siempre que el pedido tenga productos entregables (`has_delivery`).** Es el mismo `res.partner`: ofrecerlo en las dos listas hace que editar "la de facturacion" edite tambien la de entrega/instalacion sin que el cliente se de cuenta. Se resuelve en la **plantilla** (`website_sale.billing_address_list`, override en `views/website_sale_templates.xml`): la lista es `billing_addresses - order.partner_shipping_id` si `has_delivery`, y `billing_addresses` completa si no (pedido `only_services`). **Por que la condicion no usa `use_delivery_as_billing`**: el core lo calcula al **renderizar** como `partner_invoice_id == partner_shipping_id` (`website_sale/controllers/main.py:1093-1095`), asi que apenas el cliente carga otra direccion de facturacion y la pagina se vuelve a dibujar (reload de bfcache al volver del pago, `checkout.js:49-53`; o el redirect tras *Agregar direccion*) esa igualdad no se da y la tarjeta de entrega reapareceria en la lista. Con `has_delivery` esa tarjeta **nunca** se ofrece como opcion de facturacion; para facturar a esa misma direccion se usa el switch, que es el mecanismo del core. La mecanica del switch es del core y **no es simetrica**: destildar no escribe nada; tildar **persiste** via `toggleBillingAddressRow` → `_selectMatchingBillingAddress()` → `updateAddress('billing', id)` → `rpc('/shop/update_address')` (`website_sale/static/src/interactions/checkout.js:106-135`, `:436-455`), que escribe `partner_invoice_id`. **Alcance sin gate de instalacion**: aplica a **todo** checkout con productos entregables (mismo criterio que el override de `address_form_fields`, a diferencia de `delivery_address_list`, que usa `_is_installation_required()`). **Residuo aceptado**: si **sin recargar** la pagina el cliente cambia la direccion de entrega a un partner que ademas figura en `billing_addresses`, el core puede resaltar esa tarjeta en la lista de facturacion (`_selectMatchingBillingAddress`, `checkout.js:436-455`); solo puede pasar con la **direccion propia del contacto**, la unica que aparece en las dos listas (`portal/controllers/portal.py:253-262`). Taparlo pide JS propio, desproporcionado para un caso tan acotado. |
| D61 | ¿Como sabe el cliente del link que las fotos y la direccion son obligatorias? | Con un **aviso visible en texto** (no solo el asterisco ni el globito nativo del navegador, que sale en el idioma del navegador y desaparece al instante) en cada bloque obligatorio del formulario de la cita: **Direccion** (siempre que el bloque exista, `_is_installation_asking_address()`: calle y localidad son siempre obligatorias) → *"Required: street and number, and town."*; **Fotos** (solo si el bloque existe, `_is_installation_asking_photos()`, **y** `installation_min_photos > 0`) → *"Required: upload at least N photo(s) to confirm the appointment."*, con N = `installation_min_photos` del tipo de cita. Estilo destacado: `text-danger` + icono `fa-exclamation-circle`, y `o_not_editable` (D42). **Una linea propia dentro de cada bloque**, no un parametro de `installation_form_section`: el encabezado de seccion solo se pinta en el camino del link (D59), pero los bloques existen tambien en un tipo que pide direccion/fotos **sin** proyecto de FSM (formulario nativo, sin secciones); la linea dentro del bloque se ve en los dos casos. Ubicacion: en **Direccion**, primera linea del bloque, arriba de los inputs (queda justo debajo del titulo de la seccion en el link); en **Fotos**, **inmediatamente arriba del input de archivos**, debajo de la consigna y de los ejemplos (la guia es larga y el aviso tiene que estar pegado al control que el cliente tiene que usar). **Sin JS nuevo** y sin cambiar la validacion: el `required` del input y la revalidacion del servidor siguen igual; el aviso es la explicacion legible de esa regla. El numero de fotos se pinta con `t-out` dentro del texto, asi que el catalogo lleva **dos terminos** alrededor del numero ("Required: upload at least" / "photo(s) to confirm the appointment."), el orden de palabras del castellano calza con esa division. Traduccion es_419: "Obligatorio: subí al menos" / "foto(s) para poder confirmar la cita." y "Obligatorio: calle y número, y localidad." |
| D62 | ¿La Cita muestra la direccion de instalacion? | **Si, en el campo nativo `calendar.event.location`** (Char, `odoo/addons/calendar/models/calendar_event.py:L139`), que ya se ve en la ficha de la cita (`odoo/addons/calendar/views/calendar_views.xml:L152`), en la lista (`:L91`, `optional="show"`), en el popover del Gantt de Citas (`enterprise/appointment/views/calendar_event_views.xml:L229-231`) y en el `.ics` que se descarga desde la cita (`odoo/addons/calendar/models/calendar_event.py:L1614`; el del correo de confirmacion no, porque ese correo sale dentro del `create()`, antes de escribir `location`). **Sin campos ni vistas nuevas.** El core llena `location` con la ubicacion del **tipo de cita** (`enterprise/appointment/models/appointment_type.py:L1225`); los tipos de instalacion no tienen ubicacion, asi que la cita queda vacia. Se escribe **solo si la cita no tiene `location`** (vacio o solo espacios): una ubicacion que venga del tipo de cita no se pisa. **Formato** (una linea): calle, piso/depto, CP + localidad, y ` (between streets: X)` si hay entre calles — p.ej. `Lamadrid 581, 2B, 1648 Tigre (entre calles: Peru y Chile)`; la etiqueta en el idioma de la **compañia** (lo lee la cuadrilla; mismo molde que `_installation_task_description()`). **Un solo helper**, `calendar.event._installation_fill_location(address)`, que formatea y escribe; `address` es cualquier mapping con las claves `street`, `street2`, `zip`, `city`, `between_streets` — un `dict` o un registro `res.partner` (los dos responden `address["street"]`). **Fuentes**: (a) **link** — lo **declarado** en el formulario (`address_vals`), aunque el contacto ya tuviera otra calle y no se le escriba (D58): la cita es de **esa** visita; dentro del savepoint de `_save_appointment_installation_address()`; (b) **checkout** — `partner_shipping_id` del pedido (D45), en `sale.order._action_confirm()` despues del `super()` (recien ahi existe la cita), sobre `installation_event_id.sudo()` (confirma el cliente publico o el procesamiento del pago); (c) **citas existentes** — backfill idempotente en `migrations/1.14.0/post-migrate.py` (ver *Metodos*). Escribir `location` **no reenvia invitaciones**: el `write()` del core solo re-notifica a los asistentes cuando cambia `start` (`odoo/addons/calendar/models/calendar_event.py:L855`); el campo es `tracking=True`, asi que el alta queda como nota de seguimiento en el chatter de la cita. |

## Alcance

### Incluye

**Envio con instalacion**
- Opt-in por metodo de envio (tipo de cita + fotos minimas) y campos espejo en el pedido.
- Paso de checkout condicional `/shop/installation` en **3 bloques tipo acordeon** (direccion, turno + fotos, pago) con guia y subida de fotos.
- Gate de pago (sin cita, sin fotos o sin direccion confirmada no se paga) con redireccion al paso.
- Copia de las fotos a la Cita y a la tarea de FSM; titulo estable de la tarea.
- **Direccion de instalacion en la Cita** (`location`), en los dos caminos y para las citas existentes (D62).
- Invitacion automatica al portal al confirmar.
- Formato de respuesta validado en las preguntas de cita (cliente + servidor) y guia de medidas junto a la pregunta.
- **Textos del cliente configurables por tipo de cita** (D42): checklist "antes de agendar" desde el campo nativo `message_intro` y consigna de las fotos desde `installation_photos_message`, con el texto por defecto del modulo como respaldo; en el tipo de cita del link el checklist va **arriba del calendario**, y en el checkout se lee **dentro del Paso 2** y **no se repite** en la pagina del turno (D54).
- Paso de checkout como dato por website (`post_init_hook` / `uninstall_hook`).
- **Marca correcta del correo de recordatorio de la cita** (D43).
- **Lista de facturacion del checkout sin repetir la direccion de entrega** (D60).

**Paso de instalacion en 3 bloques**
- Estado de cada bloque (tilde / numero / candado) calculado en el servidor.
- **Direccion de instalacion = direccion de entrega del pedido** (`partner_shipping_id`), mostrada en resumen con link "editar" al paso del core, mas **entre calles** (`res.partner.between_streets`) e **indicaciones para el instalador** (`sale.order.installation_notes`), cerrados con *Confirm address* (`installation_address_confirmed`).
- **Propagacion al instalador**: entre calles + indicaciones en la **descripcion de la tarea de Field Service** (la direccion la toma el nativo de `partner_shipping_id`).
- **Guia de fotos**: 3 tomas "asi si" (frente, canto, marco) y 3 "asi no" (borrosa, cortada, tapada), con las fotos reales del cliente; progreso "N de <minimo>"; subida automatica al elegir los archivos.
- **Avisos repartidos** por bloque (duracion, pago, garantia/pilas) y **una sola voz (voseo)** en `i18n/es_419.po`.

**Agenda por link compartido**
- Tarea de FSM creada/sincronizada por el modulo (D8).
- Formulario de la cita en 4 secciones numeradas (D59), con bloque de **direccion de instalacion** (D58) y de fotos, y **aviso visible de obligatoriedad** en ambos (D61).
- Viniendo del checkout, el formulario no repite nombre, correo ni fotos (D57).

**Pilas incluidas sin costo**
- Configuracion por producto (`free_battery_product_id`, `free_battery_qty` en la UoM del producto de pila) y opt-in por metodo de envio (`includes_free_batteries`).
- Generacion automatica, agregada por producto de pila, de la linea de pedido en **$0**, sincronizada de forma idempotente en el carrito web, en el backend (onchange + *Add shipping*) y al confirmar.
- Defensa del precio 0 y del descuento 0 en todos los caminos de recomputo del core.
- Linea visible pero no editable en el carrito, con auto-curacion si el cliente la manipula por el endpoint.
- Texto del checkout condicional (pilas incluidas vs. pilas a cargo del cliente).
- Suite de tests de los flujos troncales de las pilas (`tests/test_free_batteries.py`) y de la marca del correo (`tests/test_calendar_event_mail_company.py`).

### NO incluye

- **Publicar los productos de pila en el sitio**: no se necesita (la linea se crea server-side); si el funcional los publica, el comportamiento no cambia (D29/D30).
- **Usar `optional_product_ids` / `accessory_product_ids` para las pilas**: es otro mecanismo y peor para el requerimiento — el cliente tendria que agregarlas a mano y pagarlas.
- **Override de `_get_estimated_weight` / `_match_weight`** para excluir la linea del peso. *Omision deliberada, verificada*: las pilas tienen `weight` NULL, el carrier de instalacion tiene `max_weight = 0` (sin limite) y no hay reglas de tarifa por peso → no cambia ninguna tarifa. El metodo que castiga los productos sin peso, `_get_invalid_delivery_weight_lines` (`odoo/addons/delivery/models/sale_order_line.py:L36`), **solo lo llaman las integraciones de carriers de terceros de enterprise** (`delivery_dhl_rest`, `delivery_ups_rest`, `delivery_usps_rest`, `delivery_sendcloud`, `delivery_bpost`, `delivery_easypost` y sus variantes legacy) y el test del core (`odoo/addons/delivery/tests/test_delivery_cost.py:L295`): con un carrier `fixed` **ninguno de esos caminos se ejecuta**. Si algun dia se instala un carrier de tercero real, revisar esta omision.
- **Override de `_get_update_prices_lines()`** (`odoo/addons/delivery/models/sale_order.py:L49` lo hace para las lineas de envio). *Omision deliberada, verificada*: es redundante — `_recompute_prices()` → `_compute_price_unit(force)` → `_reset_price_unit()` → `_get_display_price()` (`odoo/addons/sale/models/sale_order_line.py:L623`) devuelve 0 — y es **preferible dejar la linea DENTRO del recordset**: asi le llega el `lines_to_recompute.discount = 0.0` de `_recompute_prices` (`odoo/addons/sale/models/sale_order.py:L1379`). Excluirla dejaria pegado un `discount` viejo.
- **Xpath sobre `should_show_quantity_selector`** (patron de `website_sale_loyalty`). *Omision deliberada*: redundante — con `_is_sellable() == False`, `odoo/addons/website_sale/views/templates.xml:L3002` cae en la rama `t-else` (input readonly, sin botones `-`/`+`).
- **Override de `_recompute_cart()`** (precedente del modulo hermano). *Omision deliberada*: las cantidades solo cambian por caminos que llaman a `_verify_cart_after_update()`, y el precio 0 lo garantiza `_get_display_price()`; el hermano lo necesita porque su descuento depende de los totales que se recomputan ahi.
- **Override de `_remove_delivery_line()`**. *Omision deliberada*: sus dos llamadores relevantes estan enganchados — `_verify_cart_after_update()` (`odoo/addons/website_sale/models/sale_order.py:L674`, camino `only_services`) y `_set_delivery_method()` (`:L853`).
- **Campo de "origen" de la linea (que cerradura la genero) ni modelo hijo o2m**: la reconciliacion es por `(pedido, producto, flag)` (D16/D17); un campo de origen no tendria consumidor.
- **Descuento/precio por medio de pago**: es del modulo hermano `website_sale_payment_method_price`.
- **Costo de instalacion por distancia**: modulos aparte, en otro repo.
- **Mapa de confirmacion del punto** en el Paso 1: etapa aparte (D56).
- **Segundo formulario de direccion / modelo propio de "direccion de instalacion" en el checkout**: la direccion es `partner_shipping_id` y se edita en el paso del core (D45).
- **Dos campos separados de "entre calles"**: un solo campo libre (D46).
- **Pasos nuevos en el wizard del checkout**: el acordeon vive **dentro** del paso (D3/D44).
- **Geocoding / validacion externa de la direccion**: el core valida los campos obligatorios (`_get_mandatory_delivery_address_fields`, `odoo/addons/portal/controllers/portal.py:L318`); el modulo no agrega validacion propia de direcciones del checkout.
- **Formulario del link**: material de la puerta como tarjetas con foto (necesita imagenes por respuesta, que `appointment.answer` no tiene), zona de arrastrar y soltar para las fotos, y panel lateral de resumen con links "Editar" (el nativo trae uno propio, con fecha, tipo y duracion).
- **Campo o vista nueva para la direccion en la Cita**: se usa el `location` nativo (D62).
- **Reenviar la invitacion de la cita al completar `location`**: el correo de confirmacion sale al crear la cita, antes de que se escriba la ubicacion (ver *Edge cases*).

## Modelos

### Nuevos

No aplica: el modulo no define modelos propios, solo extiende modelos de `odoo/` y `enterprise/`.

### Extendidos

| Modelo | `_inherit` | Que se agrega |
|--------|-----------|--------------|
| `delivery.carrier` | `delivery.carrier` | Opt-in de instalacion (tipo de cita + fotos minimas) y **opt-in de pilas incluidas** (`includes_free_batteries`) + constrains de configuracion |
| `product.template` | `product.template` | **Configuracion de pilas del producto** (`free_battery_product_id`, `free_battery_qty`) + constrain de configuracion |
| `res.partner` | `res.partner` | **Entre calles** (`between_streets`) y **reset de la confirmacion de direccion** cuando se edita el domicilio (D46, D48). La escritura desde el frontend la hace nuestra ruta con `sudo()` acotado (D49) |
| `sale.order` | `sale.order` | Campos espejo de la instalacion, gate de pago, copia de fotos, **ubicacion de la cita** (D62), invitacion al portal; agregacion y sincronizacion de las lineas de pilas + engaches de carrito/backend/confirmacion; notas para el instalador, confirmacion de la direccion y estado de los 3 bloques del paso (D44, D47, D48) |
| `sale.order.line` | `sale.order.line` | Deteccion de la linea de la reserva y titulo de la tarea de FSM; flag `is_free_battery_line` y las defensas de precio/edicion; entre calles + notas en la `description` de la tarea de FSM (D47) |
| `appointment.type` | `appointment.type` | Proyecto de FSM para citas fuera del eCommerce, pedido de fotos/direccion y minimo, consigna de las fotos configurable (`installation_photos_message`), deteccion de "vengo del checkout" (D54) y del formulario del link (D59) |
| `appointment.question` | `appointment.question` | Formato de respuesta validado y marca de la guia de medidas |
| `calendar.booking` | `calendar.booking` | Aclaracion en la descripcion de la linea ("incluido en el metodo de envio") |
| `calendar.event` | `calendar.event` | Tarea de FSM de la cita agendada fuera del eCommerce + sincronizacion y fotos; **ubicacion de la cita** desde la direccion de instalacion (D62); **compañia del correo de la cita** resuelta por el pedido/organizador (D43) |
| `website` | `website` | Paso de checkout condicional |

**Controllers** (`controllers/website_sale_installation_appointment.py`): `WebsiteSaleInstallation(WebsiteSale)`
(paso del checkout, confirmacion de la direccion y overrides de pago) y
`AppointmentInstallation(WebsiteAppointmentSale)` (validacion de respuestas, direccion y fotos del
formulario de la cita, partner del carrito y vuelta al paso).

**Migraciones**: `migrations/1.14.0/post-migrate.py` — backfill de `calendar.event.location` (D62).

## Campos

| Modelo | Campo | Tipo | String | Requerido | Default | Restricciones |
|--------|-------|------|--------|-----------|---------|--------------|
| `res.partner` | `between_streets` | Char | Between streets | No | — | `[ASUNCION]` **opcional** (D46); `help` con ejemplo ("e.g. Peru and Chile"); visible en la ficha del contacto (backend), en el Paso 1 del checkout y en el formulario del link; el POST publico lo **trunca a 100 caracteres** (D49) |
| `delivery.carrier` | `installation_appointment_type_id` | Many2one `appointment.type` | Installation Appointment Type | No | — | `ondelete="restrict"`; `_check_installation_appointment_type` |
| `delivery.carrier` | `installation_min_photos` | Integer | Minimum Installation Photos | No | `1` | `>= 0` (`_check_installation_min_photos`) |
| `delivery.carrier` | `includes_free_batteries` | Boolean | Includes Free Batteries | No | `False` | — |
| `product.template` | `free_battery_product_id` | Many2one `product.product` | Free Battery Product | No | — | `ondelete="restrict"`, **`check_company=True`** + domain de compañia (D38); `_check_free_battery_config` |
| `product.template` | `free_battery_qty` | Integer | Free Batteries Quantity | No | `0` | `>= 0`; va junto con el producto; en la **UoM del producto de pila** (`_check_free_battery_config`) |
| `product.template` | `free_battery_uom_name` | Char (related, no store) | Battery Unit | No | — | `related="free_battery_product_id.uom_name"`, `readonly=True` — **reusa el campo del core** (`odoo/addons/product/models/product_template.py:L123`, `uom_name = related='uom_id.name'`). Existe solo para **mostrar la UoM al lado de la cantidad** (D15): sin un campo, el XML no puede renderizar `free_battery_product_id.uom_id` |
| `sale.order` | `installation_appointment_type_id` | Many2one `appointment.type` | Installation Appointment Type | No | — | `related="carrier_id.installation_appointment_type_id"`, `readonly` |
| `sale.order` | `installation_required` | Boolean (compute) | Installation Required | No | — | `_compute_installation_required` (no store) |
| `sale.order` | `installation_booking_id` | Many2one `calendar.booking` (compute) | Installation Booking | No | — | `_compute_installation_booking_id` |
| `sale.order` | `installation_event_id` | Many2one `calendar.event` (compute) | Installation Appointment | No | — | `_compute_installation_event_id` |
| `sale.order` | `installation_photo_ids` | Many2many `ir.attachment` | Installation Photos | No | — | tabla `sale_order_installation_photo_rel`; `copy=False` |
| `sale.order` | `installation_photo_count` | Integer (compute) | Installation Photos Count | No | — | `_compute_installation_photo_count` |
| `sale.order` | `installation_notes` | Text | Notes for the installer | No | — | opcional; **`copy=False`** (es de **esta** venta, como `installation_photo_ids`); se propaga a la `description` de la tarea de FSM (D47); el POST publico lo **trunca a 1000 caracteres** (D49) |
| `sale.order` | `installation_address_confirmed` | Boolean | Installation Address Confirmed | No | `False` | **`copy=False`**; lo setea el boton del Paso 1 y lo **resetea** todo cambio posterior de la direccion (D48) |
| `sale.order.line` | `is_free_battery_line` | Boolean | Is a Free Battery Line | No | `False` | **sin `copy=`** (default `True` — D33, critico para el duplicado de pedidos); flag tecnico, no va en vistas |
| `appointment.type` | `installation_fsm_project_id` | Many2one `project.project` | Field Service Project | No | — | `domain=[('is_fsm','=',True)]` |
| `appointment.type` | `installation_request_photos` | Boolean | Ask for Site Photos | No | `False` | Pide las fotos en el **formulario de la cita**. En el camino del checkout el codigo las esconde (D57) |
| `appointment.type` | `installation_request_address` | Boolean | Ask for the Installation Address | No | `False` | Pide la direccion de instalacion en el formulario de la cita. Se tilda en los tipos agendados **fuera** del eCommerce (el link): ahi no hay pedido que la aporte (D58). Nunca se muestra en el camino del checkout |
| `appointment.type` | `installation_min_photos` | Integer | Minimum Site Photos | No | `0` | Minimo de fotos del formulario de la cita; `> 0` pinta el aviso de obligatoriedad (D61) |
| `appointment.type` | `installation_photos_message` | Html | Site Photos Message | No | — | `translate=True`, `sanitize_attributes=False` (espeja el `message_intro` nativo). Vacio = texto por defecto del modulo |
| `appointment.question` | `answer_format` | Selection | Answer Format | Si | `free` | `free`/`integer`/`decimal`/`phone`/`identification` |
| `appointment.question` | `installation_measure_guide` | Boolean | Show Measuring Guide | No | `False` | — |
| `calendar.event` | `installation_task_id` | Many2one `project.task` | Installation Task | No | — | `copy=False`, `ondelete="set null"`, `index="btree_not_null"` |

> `calendar.event.location` es **del core** (Char, `tracking=True`); el modulo solo lo completa (D62).

**Textos obligatorios de los campos de pilas** (el funcional los lee para configurar; la
ambiguedad de la UoM es el riesgo #1 de las pilas):

- `free_battery_qty`: `string="Free Batteries Quantity"`, `help` que diga **explicitamente** que la
  cantidad se expresa en la **unidad de medida del producto de pila elegido**, con ejemplo:
  *"…in the battery product's own unit of measure: for batteries sold in packs of 4, 1 means one pack (4 batteries)."*
  Si se lee como "cantidad de pilas" y el funcional escribe `4`, se despachan **16** pilas.
- `free_battery_product_id`: `help` que aclare que las pilas se agregan **sin cargo** solo si el
  metodo de envio elegido tiene *Includes Free Batteries*.
- `includes_free_batteries`: `help` que aclare que agrega las pilas configuradas en los productos del
  carrito a **$0** porque el costo esta cubierto por este metodo de envio, **y que avise de no
  repetir el pedido de pilas en el `message_intro` del tipo de cita** (es el unico lugar donde el
  funcional esta mirando en el momento exacto en que prende el flag).

## Metodos

### Envio con instalacion

#### `sale.order`
- `_compute_installation_required()` — `@api.depends('carrier_id.installation_appointment_type_id')`; `installation_required = bool(tipo de cita del carrier)`.
- `_compute_installation_booking_id()` / `_compute_installation_event_id()` — primera reserva / primera cita de las lineas cuyo `appointment_type_id` es el del carrier.
- `_compute_installation_photo_count()` — `len(installation_photo_ids)`.
- `_is_installation_required()` — `any(...)` sobre el recordset (lo usan controllers y templates).
- `_is_installation_scheduled()` — `bool(booking or event)`.
- `_get_installation_errors()` — lista de mensajes: **falta confirmar la direccion** (`[ASUNCION]` D50) / falta agendar / faltan N fotos. Devuelve `[]` si el pedido no requiere instalacion. Es el gate unico: lo consumen `_check_cart_is_ready_to_be_paid()`, `shop_payment()`, `_get_shop_payment_errors()` y el estado del **Paso 3** del acordeon.
- `_check_cart_is_ready_to_be_paid()` — **override**: `ValidationError` con los errores de instalacion antes del `super()`.
- `_action_confirm()` — **override**: `super()` primero (el nativo crea Cita y tarea) y despues `_sync_installation_photos()` + **`_sync_installation_location()`** (D62) + `_grant_portal_access_after_installation_sale()` (ver D27).
- `_sync_installation_photos()` / `_post_installation_photos(target)` — copian las fotos al chatter de la Cita y de las tareas (`sudo`, adjuntos copiados sin dueño).
- `_grant_portal_access_after_installation_sale()` — invitacion nativa al portal, idempotente, aislada en `savepoint`, con nota en el chatter ante cualquier problema.

#### `sale.order.line`
- `_is_installation_booking_line()` — la linea es la reserva de la instalacion del carrier del pedido.
- `_timesheet_create_task_prepare_values(project)` — **override** de `sale_project`: `name = "<pedido> - <tipo de cita>"` y `description` con **entre calles + notas para el instalador** (D47; detalle abajo).

#### `delivery.carrier`
- `_check_installation_appointment_type()` — `@api.constrains`: el tipo de cita debe tener paso de pago + producto, y ese producto generar tarea o tener precio.
- `_check_installation_min_photos()` — `@api.constrains`: `>= 0`.

#### `appointment.question`
- `_effective_answer_format()`, `_answer_input_attrs()`, `_validate_answer(value)` — formato efectivo, atributos HTML reales y validacion de servidor (entero/decimal/telefono/DNI-CUIT via `stdnum.ar`).

#### `calendar.event`
- `create()` / `write()` — **overrides**: generan la tarea de FSM de las citas con `installation_fsm_project_id` (aislado en savepoint) y la mantienen en linea al reprogramar/cancelar/desarchivar. El `write()` solo reacciona a `active`, `start` y `stop`: escribir `location` no toca la tarea.
- `_installation_generate_fsm_task()`, `_installation_cancel_task()`, `_installation_restore_task()`, `_installation_post_photos(attachments)`.
- `_installation_task_description(customer)` — cuerpo de la tarea de FSM: la descripcion de la cita mas el **"entre calles"** del contacto (D58). `Markup + Markup` (concatenar un `str` crudo escaparia el lado derecho) y la etiqueta en el idioma de la **compañia**, no del visitante: **reasigna `self`** con `with_context(lang=...)`, porque `_()` resuelve el idioma leyendo el `self` del frame del llamador (`odoo/tools/translate.py`), asi que guardar el context en otra variable seria inerte.
- `_mail_get_companies(default=False)` — **override** (D43): resolvedor de "que compañia es esta
  cita" — pedido que la origino (el mas viejo, no cancelado) > organizador (`user_id.company_id`) >
  quien la creo (`create_uid.company_id`) > `super()` con el `default`. Influye en `record_company_id`
  del `mail.message`, el alias domain del reply-to y el Return-Path — **no** en el logo/colores.
- `_notify_by_email_prepare_rendering_context(...)` — **override** (D43): el que pinta el
  logo/colores del layout de notificacion (`render_context['company']` y `['website_url']`), llamando
  a `super()` y reusando `_mail_get_companies()` como resolvedor. Cubre confirmacion y recordatorio.
  La compañia resuelta se escribe con **`.sudo()`**, igual que el core (`odoo/addons/mail/models/mail_thread.py:L3660`):
  QWeb lee `company.name`/`uses_default_logo`/colores y `res.company` tiene reglas por grupo que
  acotan la lectura a las compañias del usuario (`odoo/odoo/addons/base/security/base_security.xml:L105-125`),
  asi que sin el `sudo()` un empleado que postea en el chatter de una cita de **otra** compañia
  (cita por link compartido, sin pedido, organizador de la otra compañia) recibiria un
  `AccessError` al renderizar.

#### `calendar.booking`
- `_get_description()` — **override**: agrega "Included in the … shipping method — no extra charge." a la descripcion de la linea de la reserva.

#### `website`
- `_get_allowed_steps_domain()` — **override**: saca `/shop/installation` del dominio cuando el carrito no requiere instalacion.

#### Controllers
- `shop_installation()` / `shop_installation_submit()` / `shop_installation_photo_remove()` — paso del checkout y endpoints publicos de fotos y direccion.
- `shop_payment()` / `_get_shop_payment_errors(order)` — **overrides**: redireccion al paso y errores de pago.
- `appointment_type_id_form()` / `appointment_form_submit()` / `_get_customer_partner()` / `_redirect_to_payment()` — **overrides** del flujo de citas (errores de formato, direccion, fotos, partner del carrito, vuelta al paso). Los overrides de rutas del padre llevan **`@route()` desnudo** (sin argumentos): es el patron nativo para pisar un metodo que ya tiene ruta registrada sin redeclarar el path (`odoo/http.py:760-763`); sin el, Odoo lo auto-decora y avisa `The endpoint ... is not decorated by @route(), decorating it myself.` en cada regeneracion del routing map.
- `create_installation_photos(uploads, available_slots, res_model, res_id)` — helper compartido de validacion/creacion de adjuntos.
- `_prepare_installation_values(order_sudo)` — valores del paso (detalle abajo).
- `_get_installation_address_vals(post)` — lee y valida el bloque de direccion del formulario de la cita (D58): devuelve `(vals, errores)`, con los 5 valores (`street`, `street2`, `city`, `zip`, `between_streets`) **truncados server-side** a los mismos largos que declara el `maxlength` del input (el POST es publico) y calle y localidad obligatorias.
- `_save_appointment_installation_address(event, address_vals)` — detalle abajo (D58 + D62).

---

### Ubicacion de la cita (D62)

### `CalendarEvent._installation_fill_location(address)`

- **Proposito**: dejar la direccion de instalacion como `location` de las citas que no tienen
  ubicacion. Es el **unico** lugar que formatea esa linea (lo usan el link, el checkout y el backfill).
- **Decoradores**: ninguno.
- **Parametros**: `address` — mapping con las claves `street`, `street2`, `zip`, `city`,
  `between_streets`: el `dict` de `_get_installation_address_vals()` o un registro `res.partner`
  (`partner["street"]` devuelve el valor o `False`).
- **Logica**:
  1. `targets = self.filtered(lambda event: not (event.location or "").strip())`; si no hay → return.
  2. **Reasignar `self`** a `self.with_context(lang=self.env.company.partner_id.lang or self.env.lang)`
     (misma razon y molde que `_installation_task_description()`: la etiqueta la lee la cuadrilla).
  3. Armar la linea: `", ".join` de los fragmentos no vacios (con `.strip()`) de
     `address["street"]`, `address["street2"]` y `" ".join` de los no vacios de
     `address["zip"]`, `address["city"]`. Si la linea queda vacia (sin calle, piso, CP ni
     localidad) → return sin escribir: un "entre calles" solo no es una ubicacion.
  4. Si `address["between_streets"]` tiene texto, agregar
     `" (%s)" % _("between streets: %s", between_streets)`.
  5. `targets.write({"location": line})`.
- **Retorna**: `None`.
- **Errores**: ninguno. El `sudo()` es responsabilidad del llamador (los tres llamadores trabajan
  con la cita en `sudo`).
- **Por que "solo si esta vacia"**: el core llena `location` con la ubicacion del tipo de cita
  (`enterprise/appointment/models/appointment_type.py:L1225`); si un tipo de instalacion la tuviera
  cargada, es una decision de configuracion que el modulo no pisa. Hace ademas que el metodo sea
  **idempotente**: correrlo dos veces no cambia nada.

### `SaleOrder._sync_installation_location()`

- **Proposito**: que la Cita del checkout muestre la direccion de entrega (D45/D62).
- **Decoradores**: ninguno.
- **Logica**: por cada pedido con `installation_event_id` y `partner_shipping_id`:
  `order.installation_event_id.sudo()._installation_fill_location(order.partner_shipping_id)`.
- **Retorna**: `None`.
- **Errores**: ninguno. Sin savepoint (mismo criterio que `_sync_installation_photos()`: es un
  `write` de un Char sobre un registro que el mismo request acaba de crear).
- **Por que en `_action_confirm()` despues del `super()`**: la Cita la crea `website_appointment_sale`
  al confirmar/pagar la reserva; antes del `super()` no existe. El `sudo()` es porque quien confirma
  es el visitante publico o el procesamiento del pago.

### `AppointmentInstallation._save_appointment_installation_address(event, address_vals)` *(controller)*

- **Proposito**: guardar la direccion declarada en el formulario del link (D58) y dejarla como
  ubicacion de la cita (D62).
- **Logica**:
  1. `event.sudo()._installation_fill_location(address_vals)` — **primero y siempre**, con lo
     **declarado**, aunque el contacto ya tenga otra calle y no se le escriba nada (la cita es de
     **esa** visita) y aunque no haya `appointment_booker_id`.
  2. `partner_sudo = event.appointment_booker_id.sudo()` (nunca `partner_ids[:1]`, que arranca por el
     partner del **empleado**); si no hay → return.
  3. `declared` = los valores no vacios. Si el contacto **no** tiene `street` → `partner_sudo.write(declared)`.
     Si ya tiene → **no se escribe** y lo declarado se postea (con etiquetas legibles) en la cita y en
     `installation_task_id` con `message_post` (subtipo interno por defecto, `mail.mt_note`).
  4. **Fuera del `if`**: si hay tarea, `task.description = event._installation_task_description(partner_sudo)`
     (el entre calles llega a la tarea aunque no se escriba el contacto, CA51).
- **Retorna**: `None`.
- **Errores**: ninguno propio. El llamador (`appointment_form_submit()`) corre todo el metodo dentro
  de `request.env.cr.savepoint()` y loguea cualquier excepcion: la reserva ya esta hecha y un fallo
  aca no puede costarle el turno al cliente.

### Backfill `migrations/1.14.0/post-migrate.py`

- **Proposito**: completar `location` de las citas de instalacion que existen al actualizar a `1.14.0`.
- **Firma**: `migrate(cr, version)`; `env = api.Environment(cr, SUPERUSER_ID, {})`. Corre solo al
  actualizar desde una version menor (el loader antepone la serie: `1.14.0` → `19.0.1.14.0`,
  `odoo/odoo/modules/migration.py:L154`); en una instalacion nueva no corre (no hay citas).
- **Logica**:
  1. **Tipos de instalacion** (`with_context(active_test=False)`): los `appointment.type` con
     `installation_fsm_project_id` **o** referenciados por algun
     `delivery.carrier.installation_appointment_type_id`. Sin tipos → return.
  2. **Citas**: `calendar.event` activas con `appointment_type_id in tipos` y `location` vacio o
     `False` (el filtro final por `.strip()` lo hace el helper).
  3. Por cita, la fuente de la direccion, en orden:
     (a) el `partner_shipping_id` del pedido de la linea de venta que la origino
     (`sale.order.line.calendar_event_id`, pedidos no cancelados, el mas viejo por `id` — mismo
     criterio que D43), si ese partner tiene `street`;
     (b) si no, `appointment_booker_id`, si tiene `street`;
     (c) si no, la cita queda como esta.
  4. `event.with_context(mail_notrack=True)._installation_fill_location(partner)` — sin nota de
     seguimiento por cada cita (es completado de datos, no un cambio de un usuario).
- **Idempotente**: solo toca citas con `location` vacio y el helper no pisa; correrlo de nuevo no
  cambia nada. Loguea cuantas citas completo.

---

### Paso de instalacion en 3 bloques

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
- **Requisito de orden**: nuestra propia ruta escribe **primero el partner y despues el flag** — al
  reves, este override apagaria la confirmacion que se acaba de encender.

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
- **Retorna**: `res`
- **Errores**: ninguno
- **Por que hacen falta los dos overrides**: son dos caminos distintos — **elegir otra** direccion
  (cambia `partner_shipping_id` del pedido) y **editar la misma** (cambia el `res.partner`). El core
  usa esta division en su propio `write` de partner y en el compute de `partner_shipping_id`
  (`odoo/addons/sale/models/sale_order.py:L406`).
- ⚠️ **Limite aceptado**: `partner_shipping_id` es **computado almacenado**
  (`odoo/addons/sale/models/sale_order.py:L406`). Si cambia por **recompute** al cambiar `partner_id`,
  el valor nuevo no pasa por `vals` y el override **no se entera**. En el checkout el cliente se
  identifica (paso 250) **antes** del paso 400, asi que ese recompute ocurrio cuando el Paso 1 se
  confirma; si el backoffice cambia el cliente de un pedido con instalacion, lo revisa a mano.

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
     hay ninguno en `"todo"`, `"payment"` (`payment` solo vale `"todo"` o `"locked"`, nunca `"done"`).
- **Retorna**: `dict` — `{"address": str, "schedule": str, "payment": str, "open": str}` con estados
  `done` / `todo` / `locked`.
- **Errores**: ninguno
- **Nota**: `payment` se calcula con el gate de pago (`_get_installation_errors()`), asi que el
  acordeon y el servidor **no pueden** discrepar **en lo que es de instalacion** (turno, fotos,
  direccion confirmada). El core valida ademas carrier y direccion de entrega
  (`_check_cart_is_ready_to_be_paid`, `odoo/addons/website_sale/models/sale_order.py:L914-930`), asi
  que un Paso 3 abierto significa "no falta nada **de instalacion**", no "el pago no puede rebotar".

### `SaleOrder._get_installation_task_notes()`

- **Proposito**: armar el bloque de texto que el instalador lee en la tarea de FSM (entre calles +
  indicaciones), en un solo lugar reusable.
- **Decoradores**: ninguno
- **Logica**: `self.ensure_one()`; **reasigna `self`** a
  `self.with_context(lang=self.company_id.partner_id.lang or self.env.lang)` (ver
  `_installation_task_description()`) y junta, si estan, `partner_shipping_id.between_streets`
  ("Between streets: …") y `installation_notes` ("Notes for the installer: …"); devuelve `""` si no
  hay nada.
  - **Escapado obligatorio**: los dos valores los escribe el **visitante publico**, y el destino
    (`project.task.description`) es un campo **Html** (`odoo/addons/project/models/project_task.py:L153`).
    Cada valor pasa por `markupsafe.escape()` y el resultado se arma como `Markup` (`<br/>` entre
    lineas); nunca se concatena texto crudo del cliente en el HTML.
  - **Idioma de las etiquetas**: el de la **compañia**, **no** el del comprador: el lector es la
    cuadrilla interna. El idioma del cliente (`_prepare_free_battery_line_vals`) aplica a lo que el
    cliente lee —descripcion de linea, factura—.
- **Retorna**: `Markup` (HTML seguro; vacio → `""`)
- **Errores**: ninguno

### `SaleOrderLine._timesheet_create_task_prepare_values(project)`

- **Proposito**: que entre calles + indicaciones lleguen a la **tarea del instalador**.
- **Decoradores**: ninguno (override)
- **Logica**: al `values` del `super()` (con el `name` estable) se le **antepone** al
  `description` el resultado de `order_id._get_installation_task_notes()` cuando la linea es la de la
  reserva (`_is_installation_booking_line()`) y hay algo que decir.
  - El `description` que trae `super()` **ya es HTML** (armado por
    `sale_project`/`website_appointment_sale` como `str` plano), asi que se concatena envuelto en
    `Markup(description)`: sin eso, `Markup.__add__(str)` **escapa** el operando derecho y el
    instalador ve el codigo fuente del bloque de preguntas y respuestas. No reintroduce riesgo: ese
    HTML lo arma el core, no el visitante (lo del visitante ya viene escapado por
    `_get_installation_task_notes()`).
- **Retorna**: `dict`
- **Errores**: ninguno
- **Por que la descripcion y no el chatter**: el instalador abre la tarea en el tablero de Field
  Service; la descripcion se ve en el formulario, el chatter hay que desplegarlo. La **direccion** no
  se copia: el nativo pone `partner_id = partner_shipping_id` cuando el proyecto es FSM
  (`enterprise/industry_fsm_sale/models/sale_order.py:L123`).
- ⚠️ **Limite**: si el producto de la cita usara `task_template_id`, el core arma los vals por otro
  camino (`_prepare_task_template_vals`, `odoo/addons/sale_project/models/sale_order_line.py:L285`)
  que **no pasa** por este override (ver *Edge cases*).

### `AppointmentType._is_installation_asking_photos()` / `_is_installation_asking_address()`

- **Proposito**: decidir si el **formulario de la cita** pide las fotos y/o la direccion (D57/D58):
  `installation_request_photos` / `installation_request_address` **y ademas** no venir del
  checkout (`_is_installation_checkout_source()`).
- **Por que en codigo y no solo en configuracion**: el mismo tipo de cita puede usarse en los dos
  caminos, y ahi ninguna configuracion los distingue.
- **Los consumen la plantilla y el controller**: el gate tiene que estar en los dos, o el controller
  exigiria un campo que la plantilla no pinta.
- **Llamada defensiva**: los dos hacen `ensure_one()`, asi que el controller los invoca solo con el
  tipo de cita **existente** (`if appointment_type and ...`): un id borrado dejaria un `ValueError`
  sin capturar en un endpoint `auth="public"` (500) donde el core devuelve 404.

### `AppointmentType._is_installation_link_form()`

- **Proposito**: marcar el formulario del link (D59): `bool(installation_fsm_project_id)` y no venir
  del checkout.
- **Retorna**: `bool`

### `AppointmentType._is_installation_checkout_source()`

- **Proposito**: saber si el visitante llego a la pagina del turno **desde el checkout**, para no
  repetirle el intro que ya leyo (D54) ni volver a pedirle datos (D57).
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
     confirmacion. `/shop/installation` es `auth="public"` y `shop_installation()` solo corre
     `_check_cart()`, asi que en un carrito anonimo `partner_shipping_id` es el **partner publico
     compartido**: escribirle `between_streets` ensuciaria un contacto global de la base.
  2. `partner_sudo = order_sudo.partner_shipping_id`; si no hay → mismo camino que el punto 1 (aviso +
     link, sin confirmar).
  3. `partner_sudo.sudo().write({"between_streets": (post.get("between_streets") or "").strip()[:100]})`
     — **solo ese campo**, nunca `post` completo, y **truncado** server-side. **Solo si cambio**: si
     el valor truncado es igual al guardado, **no** se escribe — re-confirmar sin tocar el campo no
     debe disparar el reset de `ResPartner.write()` en **otros** carritos `draft` del mismo partner.
  4. `order_sudo.write({"installation_notes": (post.get("installation_notes") or "").strip()[:1000],
     "installation_address_confirmed": True})` — **despues** del partner (ver `ResPartner.write`).
  5. Devolver `request.redirect(INSTALLATION_STEP_HREF)`.
- **Retorna**: respuesta HTTP (redirect al paso)
- **Errores**: ninguno propio. `between_streets` es opcional (`[ASUNCION]` D46): vacio tambien
  confirma.
- **`sudo()` justificado**: el que aprieta el boton es el visitante publico del checkout, que no
  escribe `res.partner` ni `sale.order`. Alcance acotado **por campo** (dos campos) y **por largo**.

### `WebsiteSaleInstallation.shop_installation_submit(**post)`

- **Proposito**: una sola ruta POST para el paso.
- **Decoradores**: `@route`, `auth="public"`, `methods=["POST"]`, `website=True`
- **Logica** (orden de las ramas):
  1. `_check_cart` + `_is_installation_required()`.
  2. `remove_photo_id` → quitar foto.
  3. `confirm_installation_address` → `_save_installation_address(order_sudo, post)`.
  4. Fotos: validacion y alta (`create_installation_photos`). El formulario de fotos manda
     **siempre** `stay_on_step` (input oculto de la plantilla), asi que la subida **vuelve al paso**:
     la unica salida hacia el pago es el link del Paso 3.
  5. Rama final `return request.redirect(self._get_installation_next_step_href())`: la UI no la
     alcanza (el input oculto viaja siempre); es el **fallback defensivo** para un POST sin
     `stay_on_step` (pagina cacheada, cliente que postea el form a mano).
- **Retorna**: respuesta HTTP
- **Nota**: el paso tiene **dos `<form>`** (direccion y fotos). Cada uno postea a la misma ruta con
  su marcador; no comparten estado.

### `WebsiteSaleInstallation._prepare_installation_values(order_sudo)`

- **Proposito**: pasarle a la plantilla todo lo que necesita para pintar los 3 bloques, sin logica en
  el XML.
- **Logica**: arma `errors`, `warnings`, `appointment_type`, `installation_slot_label`,
  `installation_photos`, `max_photos`, `min_photos`, `photo_count` y ademas:
  - `block_states` = `order_sudo._get_installation_block_states()` (D44),
  - `installation_address` = `order_sudo.partner_shipping_id` (para el resumen; el formato lo da
    `_display_address()`, `odoo/odoo/addons/base/models/res_partner.py:L1196`),
  - `installation_address_missing` = `order_sudo._is_anonymous_cart() or not order_sudo.partner_shipping_id`:
    con el flag, el Paso 1 pinta el aviso "cargá primero la direccion" + link a `/shop/address`
    **en lugar de** el resumen y el `<form>`, desde el primer render (`GET`),
  - `installation_address_edit_url` =
    `/shop/address?partner_id=<id>&address_type=delivery&callback=/shop/installation` (forma literal
    del core, `odoo/addons/website_sale/views/templates.xml:L3658`; el `callback` devuelve al cliente a
    nuestro paso — D12).
  - El href del Paso 3 viene en `next_website_checkout_step_href` del
    `request.website._get_checkout_step_values()` que el metodo mezcla al final
    (`odoo/addons/website_sale/models/website.py:L981`, el dict en `:L1012`). ⚠️
    `current_website_checkout_step_href` es un **string**; los que son **record** son
    `previous_website_checkout_step` y `next_website_checkout_step` (no existe
    `current_website_checkout_step`). El **rotulo** del bloque 3 sale de
    `next_website_checkout_step.name` (D44).
- **Retorna**: `dict`
- **Errores**: ninguno

---

### Pilas incluidas

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
  3. Recorrer `self.order_line` **excluyendo**: `is_free_battery_line`, `is_delivery`, `display_type` (secciones/notas), `is_downpayment` y `_is_global_discount()` (no son productos vendidos).
     Las lineas con `combo_item_id` **no** se excluyen: una cerradura dentro de un combo **si** aporta pilas. ⚠️ Si se configuran pilas en la plantilla del combo **y** en el item, se cuentan dos veces (D40).
  4. Saltear las lineas con `product_uom_qty <= 0` (D39).
  5. Por linea: `tmpl = line.product_id.product_tmpl_id`; si `tmpl.free_battery_product_id` y `tmpl.free_battery_qty > 0` → acumular `needs[tmpl.free_battery_product_id] += tmpl.free_battery_qty * line.product_uom_qty`.
     **Sin conversion de UoM de la cerradura** (D40).
     **Filtro defensivo de compañia** (D38): saltear el producto de pila cuyo `company_id` no sea compatible con `order.company_id`, en vez de dejar que el `create()` de la linea tire `UserError` de compañia y devuelva un **500** al visitante publico.
  6. Descartar las entradas que quedaron en `<= 0` y devolver el dict (**agrupado por producto de pila** — D16).
- **Retorna**: `dict {product.product: float}`
- **Errores**: ninguno (es de lectura; sirve igual en onchange sobre registros `NewId`). **Nunca rompe el request del carrito**: ante configuracion incompatible, saltea.

### `SaleOrder._prepare_free_battery_line_vals(battery_product, qty)`

- **Proposito**: vals de la linea gratis, compartidos por el camino de base de datos y el de onchange.
- **Decoradores**: ninguno
- **Logica**:
  1. `self.ensure_one()`.
  2. `name` = descripcion de venta del producto + `"\n"` + `_("Included with your shipping method — no extra charge.")`, armado **en el idioma del cliente** (`with_context(lang=...)`, molde `odoo/addons/delivery/models/sale_order.py:L207` o `self._get_lang()` como `enterprise/website_appointment_sale/models/sale_order.py:L83`; sin eso un pedido armado en el backend por un usuario en otro idioma deja la descripcion en ingles en una factura es_419).
     ⚠️ **Sin el nombre del carrier** (D35). Se ve tambien en la factura (D28).
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
  1. Si `self.env.context.get("wsia_skip_battery_sync")` → return. Guard **puramente defensivo**: no existe ningun camino de recursion real (ningun `create`/`write` de linea vuelve a entrar a los engaches); se deja por simetria con `wspmp_skip_recompute` del modulo hermano y para que un engache futuro no se muerda la cola.
  2. Recorrer el recordset y, **por cada `order`**, saltear las que tengan `state` fuera de `("draft", "sent")` (D32).
  3. `needs = order._get_free_battery_needs()`; `existing = order.order_line.filtered("is_free_battery_line")`.
  4. **Congelar** (`frozen`) las lineas de `existing` con `qty_invoiced` o `qty_delivered` distintos de 0: no se escriben ni se borran (D36). El resto es material de reconciliacion.
  5. Recorrer `needs`: tomar la **primera** linea reconciliable de ese producto (`existing.filtered(...)[:1]`); si existe y la cantidad difiere (`float_compare` con la precision `Product Unit`) → `write({"product_uom_qty": qty})`; si no existe → `create(vals | {"order_id": order.id})`.
  6. `to_unlink` = las lineas reconciliables de `existing` que (a) son de un producto que no esta en `needs`, o (b) son duplicados del producto (se conserva una sola por producto) → `unlink()`.
  7. Todas las escrituras con `.sudo()` y `with_context(wsia_skip_battery_sync=True)`.
     `sudo` porque lo dispara el **visitante publico** del checkout, que no puede crear/escribir/borrar `sale.order.line` (mismo criterio y molde que `_create_delivery_line` del core y que el modulo hermano).
- **Retorna**: `None`
- **Errores**: ninguno propio. Se recalcula **desde cero** en cada llamada: correrlo dos veces seguidas no cambia nada.
- **Por que el guard de facturado/entregado**: `_check_line_unlink` (`odoo/addons/sale/models/sale_order_line.py:L1452`) solo bloquea con `state == 'sale'`; el core hace esta misma distincion en `_remove_delivery_line` (`odoo/addons/delivery/models/sale_order.py:L59`).

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
- **Nota**: es el embudo de la seleccion de envio **del checkout** (`shop_set_delivery_method`), asi que cubre pasar al envio con pilas y salir de el — **incluido el camino de quitar el envio**, donde `set_delivery_line()` no se llama (`odoo/addons/website_sale/models/sale_order.py:L864`). Por eso convive con el override de `set_delivery_line()` (D37).

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
  3. Acumular `Command.delete(line.id)` para las lineas gratis que sobran (producto que no aplica o duplicados).
  4. `self.order_line = delete_commands + create_commands` — mismo patron que el core usa para las lineas de combo en `@api.onchange('order_line')`.
- **Retorna**: `None`
- **Errores**: ninguno
- **Notas**:
  - **No** se puede reusar `_sync_free_battery_lines()`: en un onchange `self` es un registro virtual (`NewId`) y un `create()` real escribiria en la base. Precedente del core: la sincronizacion de lineas de combo (`odoo/addons/sale/models/sale_order.py:L936`), y `delivery` tiene su propio `@api.onchange('order_line', ...)` (`odoo/addons/delivery/models/sale_order.py:L42`). Los dos caminos comparten el calculo (`_get_free_battery_needs()` + `_prepare_free_battery_line_vals()`).
  - **Naming**: se llama `_onchange_free_battery_lines` y **no** `_onchange_order_line` a proposito — ese nombre **pisaria** el onchange del core que sincroniza las lineas de combo (`odoo/addons/sale/models/sale_order.py:L936`). Desviacion deliberada de la convencion `_onchange_<campo>` de `AGENTS.md`.
  - **Tests con `odoo.tests.Form`**: `carrier_id` no esta en ninguna vista de `sale.order` (ni en `odoo/` ni en `enterprise/`), asi que un `Form` no puede **cambiarlo** (`Form.__setattr__` tira `AssertionError`); si el pedido **ya tiene** `carrier_id` en base al abrir el `Form`, el onchange lo ve igual por el fallback a `record._origin[fname]` (`odoo/odoo/orm/fields.py`). `tests/test_free_batteries.py` usa `.new()` + llamada directa para la rama `Command.create` y `Form` sobre un pedido con carrier para la rama `Command.delete`.

### `SaleOrder.action_confirm()`

- **Proposito**: red de seguridad — que ningun pedido se confirme con las pilas desincronizadas (backend sin onchange disparado, importaciones, API).
- **Decoradores**: ninguno (override)
- **Logica**: `self._sync_free_battery_lines()` **antes** del `super()` (con el `state` todavia `draft`/`sent`, altas y bajas son legales) → `return super().action_confirm()`.
- **Retorna**: lo que devuelva el `super()`
- **Errores**: ninguno
- **Por que aca y no en `_action_confirm()`**: `action_confirm()` hace `self.write(self._prepare_confirmation_values())` **antes** de llamar a `_action_confirm()` (`odoo/addons/sale/models/sale_order.py:L1183`), asi que dentro de `_action_confirm()` el `state` es `'sale'` y el `unlink()` chocaria con `_unlink_except_confirmed`.

### `SaleOrder._cart_find_product_line(*args, **kwargs)`

- **Proposito**: que un alta manual de la misma pila **no se fusione** con la linea gratis.
- **Decoradores**: ninguno (override)
- **Logica**: `lines = super()._cart_find_product_line(*args, **kwargs)` → `return lines.filtered(lambda line: not line.is_free_battery_line)`.
- **Retorna**: recordset `sale.order.line`
- **Errores**: ninguno
- **Por que**: el domain del core (`odoo/addons/website_sale/models/sale_order.py:L430`) matchea por `product_id` + `product_uom_id` + custom attrs + `linked_line_id` + `combo_item_id`, y **no** conoce nuestro flag: `_cart_add` sumaria la cantidad sobre la linea gratis. Filtrando, el alta manual crea una linea **separada y paga** (D24). Precedente de estilo: `enterprise/website_appointment_sale/models/sale_order.py:L58`.

### `SaleOrderLine._get_display_price()`

- **Proposito**: **la** garantia del precio 0 (D22).
- **Decoradores**: ninguno (override)
- **Logica**: si `self.is_free_battery_line` → `return 0.0`; si no, `return super()._get_display_price()`.
- **Retorna**: `float`
- **Errores**: ninguno
- **Por que es el load-bearing**: `_compute_price_unit` (`odoo/addons/sale/models/sale_order_line.py:L587`) recalcula al cambiar `product_id`/`product_uom_id`/`product_uom_qty` — y esta linea cambia de cantidad cada vez que cambia la cantidad de cerraduras. Crear con `price_unit=0` **no alcanza**: `_add_precomputed_values` (`:L1358`) copia `price_unit` a `technical_price_unit`, con lo que `has_manual_price` da `False`. El camino forzado (`force_price_recomputation=True`) tambien termina en `_reset_price_unit()` (`:L619`) → `_get_display_price()` (`:L623`). Este override cubre **los dos caminos**.

### `SaleOrderLine._compute_pricelist_item_id()`

- **Proposito**: que la linea gratis no arrastre descuento (D23).
- **Decoradores**: los del `super()` (`@api.depends` del core; no se redeclaran)
- **Logica**: separar `free_lines = self.filtered("is_free_battery_line")`; `super(SaleOrderLine, self - free_lines)._compute_pricelist_item_id()`; `free_lines.pricelist_item_id = False`. Molde literal: `odoo/addons/delivery/models/sale_order_line.py:L59`.
- **Retorna**: `None`
- **Errores**: ninguno
- **Por que**: `_recompute_prices()` (`odoo/addons/sale/models/sale_order.py:L1372`) hace `lines.discount = 0.0` + `_compute_discount()`, y `_compute_discount` sale por `continue` cuando `not line.pricelist_item_id._show_discount()` (`odoo/addons/sale/models/sale_order_line.py:L807`).

### `SaleOrderLine._check_validity()`

- **Proposito**: defensa en profundidad contra `prevent_zero_price_sale`.
- **Decoradores**: ninguno (override)
- **Logica**: si `self.is_free_battery_line` → `return` (temprano, sin llamar al `super()`); si no, `return super()._check_validity()`.
- **Retorna**: `None`
- **Errores**: ninguno (evita el `UserError` del core)
- **Por que**: en el camino normal no se llama (la linea se crea con `sudo().create()`, fuera de `_cart_add`/`_cart_update_line_quantity`), pero el endpoint publico `/shop/cart/update` con el `line_id` real llega a `_cart_update_order_line` → `_check_validity` (`odoo/addons/website_sale/models/sale_order.py:L554`) y, con `prevent_zero_price_sale` prendido, el `UserError` **abortaria el request antes de que la re-sincronizacion pueda auto-curar** (D21).

### `SaleOrderLine._is_reorder_allowed()`

- **Proposito**: que "Volver a pedir" no re-agregue la pila (D25).
- **Decoradores**: ninguno (override)
- **Logica**: `return super()._is_reorder_allowed() and not self.is_free_battery_line`.
- **Retorna**: `bool`
- **Errores**: ninguno
- **Por que**: el filtro del core (`odoo/addons/website_sale/controllers/reorder.py:L33` → `_is_reorder_allowed` → `_show_in_cart()`) solo excluye `is_delivery`/`display_type`/`combo_item_id`: la linea gratis pasaria y se re-agregaria **sin** el flag y **a precio de tarifa**.

### `SaleOrderLine._is_sellable()`

- **Proposito**: que la linea se vea pero **no sea editable ni clickeable** en el carrito, con independencia de si el producto de pila esta publicado (D20/D29).
- **Decoradores**: ninguno (override)
- **Logica**: `return super()._is_sellable() and not self.is_free_battery_line`.
- **Retorna**: `bool`
- **Errores**: ninguno
- **Que se obtiene sin tocar templates** (verificados en `odoo/addons/website_sale/`):
  - `odoo/addons/website_sale/views/templates.xml:L3002` — el selector cae en la rama `t-else`: input **readonly y sin botones `-`/`+`**.
  - `odoo/addons/website_sale/views/templates.xml:L2829` — el link al producto deja de ser clickeable.
  - `odoo/addons/website_sale/models/sale_order_line.py:L122` — `_should_show_strikethrough_price()` queda falsy: suprime el precio tachado (segunda capa, complementaria de `pricelist_item_id = False`).
  - `odoo/addons/website_sale/views/templates.xml:L3066` — oculta el precio por unidad de medida.
  - `odoo/addons/website_sale/controllers/cart.py:L388` — excluye la linea de las sugerencias de "pedidos anteriores".
- **Precedentes** en la cadena de dependencias: `enterprise/website_appointment_sale/models/sale_order_line.py:L19` (linea de la cita: visible pero no editable) y `odoo/addons/website_sale_loyalty/models/sale_order_line.py:L38`.

### `SaleOrderLine._check_availability()`

- **Proposito**: que el control de stock del eCommerce no trabe el checkout por la linea gratis (D34).
- **Decoradores**: ninguno (override de `website_sale_stock`)
- **Logica**: si `self.is_free_battery_line` → `return True`; si no, `return super()._check_availability()`.
- **Retorna**: `bool`
- **Errores**: ninguno (evita el `ValidationError` del gate de pago)
- **Por que**: el `_check_cart_is_ready_to_be_paid` de `website_sale_stock` (`odoo/addons/website_sale_stock/models/sale_order.py:L124`) tira `ValidationError` si alguna linea falla `_check_availability()` (`odoo/addons/website_sale_stock/models/sale_order_line.py:L39`: `is_storable and not allow_out_of_stock_order and cart_qty > free_qty`), y *Pilas AA - Energizer* (tmpl 411) tiene `allow_out_of_stock_order = false` con **stock 0**. La linea gratis se crea server-side, sin pasar por `_verify_updated_quantity`: el cliente quedaria sin poder pagar ni eliminar la linea.
- **Nota**: el orden de carga que hace ganar el MRO sin tener `website_sale_stock` en `depends` esta en **D34**; **CA32 es el tripwire**.

## Vistas

### `delivery.carrier` form (`view_delivery_carrier_form`, hereda `delivery.view_delivery_carrier_form`)
- Dentro del grupo `name="delivery_details"`: `installation_appointment_type_id`, `installation_min_photos` (`invisible="not installation_appointment_type_id"`) e `includes_free_batteries` (es donde el funcional configura este metodo de envio).

### `product.template` form (`product_template_view_form`, hereda `product.product_template_form_view`)
- Dentro del grupo `name="upsell"` ("Upsell & Cross-Sell") de la pestaña **Sales** (`odoo/addons/product/views/product_views.xml:L143`), junto a `optional_product_ids` (`odoo/addons/sale/views/product_template_views.xml:L12`) y `accessory_product_ids` (`odoo/addons/website_sale/views/product_views.xml:L169`):
  - `free_battery_product_id`, con `domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]"` (misma forma que el vecino `optional_product_ids`, `odoo/addons/sale/views/product_template_views.xml:L16`; la auto-referencia la cubre el constrain, porque el campo apunta a `product.product` y el `id` del form es el del template).
  - `<label for="free_battery_qty" invisible="not free_battery_product_id"/>` + `<div class="o_row" invisible="not free_battery_product_id"><field name="free_battery_qty"/><field name="free_battery_uom_name" readonly="1" class="oe_inline"/></div>`: la UoM real del producto de pila queda **a la derecha del numero**, para que `1` se lea como "un paquete de 4" y nunca como "una pila" (D15). Patron canonico de Odoo para pegar una UoM al numero (molde: `qty_available` + `uom_name` en `odoo/addons/stock/views/product_views.xml:L182-199`).

### `sale.order` form (`view_order_form`, hereda `sale.view_order_form`)
- `installation_required` invisible (para las condiciones), y pestaña **Installation** (`invisible="not installation_required"`) con tipo de cita, reserva, cita, las fotos (`widget="many2many_binary"`), `installation_notes` (textarea) e `installation_address_confirmed` (**readonly**: lo setea el cliente en el checkout, el backoffice solo lo mira).
- La linea de pilas no agrega nada a esta vista: es una linea de pedido normal con el flag tecnico oculto.

### `res.partner` form (`res_partner_view_form`, hereda `base.view_partner_form`)
- `between_streets` junto a los campos de direccion (dentro del bloque de `street`/`street2`/`city`), para que el backoffice y la cuadrilla lo vean en la ficha del contacto (D46). Archivo `views/res_partner_views.xml`.

### `appointment.type` form / `appointment.question` form y list
- Tirador de `sequence` y `answer_format` en la lista de preguntas del tipo de cita; `installation_fsm_project_id`, `installation_request_photos`, `installation_request_address`, `installation_min_photos` en `group name="right_details"`.
- `installation_photos_message` en la pestaña **Comunicacion** (`page name="messages"`), despues de `message_confirmation` y con su separador. **Sin `invisible`**: el tipo del eCommerce pide las fotos en el paso del checkout (tiene `installation_request_photos` apagado) y necesita el texto igual.
- `answer_format` (oculto para `select`/`radio`/`checkbox`) e `installation_measure_guide` en la ficha de la pregunta, y en su lista.

### `calendar.event` (Cita)
- **Sin vistas propias**: la direccion de instalacion se ve por el campo nativo `location` en la ficha (`odoo/addons/calendar/views/calendar_views.xml:L152`), la lista (`:L91`) y el popover del Gantt de Citas (`enterprise/appointment/views/calendar_event_views.xml:L229-231`) (D62).

### Templates del checkout / carrito
- `installation` (`/shop/installation`) — **3 bloques tipo acordeon** (D44). De arriba hacia abajo:
  encabezado ("Let's get your installation ready" + "Three steps. Each one opens when you finish the
  previous one."), el `oe_structure`, los avisos/errores de arriba (**acotados**, ver abajo) y el
  **acordeon** con los tres bloques.
  - **Un mensaje, un solo lugar**: la **razon del candado** de cada bloque ("Se habilita al completar
    el paso N", "falta el turno", "faltan fotos", "falta confirmar la direccion") se lee **en el
    bloque que lo resuelve**. El `alert` de arriba queda **solo** para los errores de submit que no
    pertenecen a ningun bloque (archivo que no es imagen, > 10 MB, mas de 10 fotos), que viajan por
    `warnings` de sesion.
  - **Cada bloque se pinta con su estado de `block_states`** (`done` → tilde + resumen en el
    encabezado; `todo` → numero; `locked` → candado + "Complete step N first"), y **el bloqueado no
    renderiza su cuerpo**.
  - **Paso 1 · Installation address** — resumen de `installation_address` (nombre +
    `_display_address()`, `odoo/odoo/addons/base/models/res_partner.py:L1196`), link **editar** a
    `installation_address_edit_url` (D45/D12) y un `<form>` propio con `between_streets` (input) e
    `installation_notes` (textarea), boton **Confirm address** (`name="confirm_installation_address"`)
    y el `csrf_token`. Con el bloque en `done`, el encabezado muestra la direccion resumida + entre
    calles. Con `installation_address_missing` en `True` el cuerpo muestra, en lugar del resumen y
    del `<form>`, un aviso "cargá primero la dirección" con link a `/shop/address`.
  - **Paso 2 · Appointment and photos** — `message_intro` del tipo de cita **si esta cargado** (es el
    "antes de agendar"), la linea de **duracion** (2 a 4 h, D52), el boton **Schedule the
    installation** (con margen superior) o el slot elegido + **Change**, y debajo las fotos:
    `installation_photos_message` + `installation_photo_examples` + las fotos subidas + el input + el
    **progreso "N de `min_photos`"** (barra `progress` de Bootstrap). El `<form>` de fotos lleva
    **`stay_on_step` como input oculto** y su boton de submit dice **Upload photos**: la navegacion al
    pago vive solo en el Paso 3.
    ⚠️ **Contrato con el JS**: el `<form>` lleva `data-installation-photos="1"` y esta **dentro** del
    contenedor `id="shop_installation"` —los dos juntos son el `selector` de la Interaction de
    `static/src/js/installation_photos.js`— y el boton de submit lleva `name="installation_continue"`,
    que es el que el JS deshabilita mientras sube.
  - **Paso 3 · Payment** — con candado mientras haya `errors`; habilitado, es un `<a>` a
    `next_website_checkout_step_href` (el mismo valor que usa el boton principal del core,
    `odoo/addons/website_sale/views/templates.xml:L3432`) con la condicion de pago (D52). El **rotulo**
    sale de `next_website_checkout_step.name` (D44). El paso tiene `show_navigation_button = False`:
    el boton principal del core no se dibuja y no hay dos botones compitiendo.
  - **Renglon corto al pie** (D52): garantia (1 año) + pilas, esto ultimo con `t-if`/`t-else` sobre
    `order.carrier_id.includes_free_batteries` — "van incluidas" / "tenes que tener 4 u 8 AA/AAA el
    dia de la instalacion". Mutuamente excluyentes por construccion (CA37).
  - **`o_not_editable` a nivel contenedor** (D42): en el `div.accordion#installation_accordion` y en el
    `div` que envuelve `installation_photo_examples`. Quedan **fuera**: el `oe_structure` y los
    `t-field` de `message_intro` / `installation_photos_message`.
  - Debajo del acordeon, el link **Back** al paso anterior (`previous_website_checkout_step`).
- `installation_photos_message`: patron `t-if="not is_html_empty(...)"` / `t-else` (texto por
  defecto del modulo: 3 fotos — frente con la manija, canto, marco), llamado con `t-call` desde los
  **dos** caminos — el paso del checkout y el formulario de la cita.
- `installation_measure_guide`: los diagramas A/B junto a la pregunta marcada.
- `installation_photo_examples` (D51/D55): dos filas.
  - **"Asi si"** (3 columnas, con tilde): `photo_ok_front.jpg` (frente de la puerta con la manija),
    `photo_ok_edge.jpg` (canto/espesor), `photo_ok_frame.jpg` (marco).
  - **"Asi no"** (3 columnas, con cruz): `photo_bad_blurry.jpg` (borrosa u oscura),
    `photo_bad_cropped.jpg` (cortada, falta parte), `photo_bad_obstructed.jpg` (tapada por la mano),
    cada una con su motivo en el pie.
  - Fotos **verticales (~3:4)** con `object-fit: cover`, para no recortar lo que hay que mirar.
  - Lo llaman con `t-call` los dos caminos (checkout y formulario de la cita).
- `installation_form_section` — encabezado de seccion del formulario del link (D59): numero, titulo y
  linea de ayuda (`sec_num`, `sec_title`, `sec_help` por `t-set` del llamador), `o_not_editable`.
- `appointment_form` (hereda `appointment.appointment_form`):
  - errores de formato/direccion/fotos del servidor en un `alert` arriba del form; `enctype`
    multipart; inputs de las preguntas con `type`/`pattern` reales (D9); guia de medidas junto a la
    pregunta marcada (D10);
  - **camino del checkout** (D57): los `div.row` de **nombre** y **correo**
    (`//label[@for='name']/..` y `//label[@for='email']/..`, con `$0` en la rama `t-else`) se colapsan
    a `input[type=hidden]` + la linea "Reservas como ..." cuando `partner_data` trae los dos datos —
    `for` **no** es atributo traducible (a diferencia de `aria-label`), asi que el locator aguanta en
    `es_AR`;
  - **camino del link** (D59): clase `o_installation_sections` en el form (por `t-attf-class`,
    repitiendo la del core) y las 4 secciones numeradas (`installation_form_section`);
  - **bloque de direccion de instalacion** (`_is_installation_asking_address()`, D58), `o_not_editable`
    porque vive dentro de un `oe_structure` del core: calle y numero (`required`, maxlength 128),
    piso/depto (128), localidad (`required`, 64), CP (16) y entre calles (100). Su **primera linea**
    es el **aviso de obligatoriedad** (D61): *"Required: street and number, and town."*
    (`text-danger`, `fa-exclamation-circle`, `o_not_editable`), visible con o sin secciones;
  - **bloque de fotos** (`_is_installation_asking_photos()`, D57): `installation_photos_message` +
    `installation_photo_examples` + el input de archivos (`required` si `installation_min_photos`).
    **Inmediatamente arriba del input**, si `installation_min_photos > 0`, el **aviso de
    obligatoriedad** (D61): *"Required: upload at least `<span t-out="appointment_type.installation_min_photos"/>`
    photo(s) to confirm the appointment."* (`text-danger`, `fa-exclamation-circle`, `o_not_editable`);
  - los dos `position="before"` sobre `//t[@t-if='appointment_type.allow_guests']` dejan **direccion
    antes que fotos**: primero donde es, despues como es.
- `appointment_info` (hereda `appointment.appointment_info`): el bloque nativo de `message_intro` del
  final (`enterprise/appointment/views/appointment_templates_appointments.xml:L231`) se apaga en
  **dos** casos: (a) en el tipo de cita **del link** (`installation_fsm_project_id`), donde el
  checklist va **arriba del calendario** para leerse antes de elegir el turno; y (b) cuando el
  visitante **viene del checkout** (`appointment_type._is_installation_checkout_source()`, D54). El
  bloque de arriba va **fuera** de `o_appointment_info_main` (que es `o_not_editable`) para que el
  `t-field` siga siendo editable en linea.
- `address_form_fields` / `delivery_address_list`: sin "Nombre de la empresa"; titulo "Installation address" cuando el pedido requiere instalacion.
- `billing_address_list` (hereda `website_sale.billing_address_list`, en `views/website_sale_templates.xml`, D60): un xpath `position="attributes"` sobre el `<t t-set="addresses">` dentro de `//div[@id='billing_container']` con `t-value` = `billing_addresses - order.partner_shipping_id if has_delivery else billing_addresses` (resta de recordsets). `portal.address_list` (`odoo/addons/portal/views/address_templates.xml:L67-89`) soporta una lista vacia. No se toca `_prepare_address_data()` (`portal.py:238-279`): la exclusion es de presentacion.
- `cart_lines` (hereda `website_sale.cart_lines`, en `views/website_sale_templates.xml`): oculta el **boton Eliminar** de la linea gratis, en los dos nodos (los dos tienen `name=` estable, y la variable del bucle es `line` — `odoo/addons/website_sale/views/templates.xml:L2880`):
  - desktop: `//div[@name='o_wsale_cart_line_button_container']//a[hasclass('js_delete_product')]` → `t-if="not line.is_free_battery_line"` (`:L2954`)
  - mobile: `//div[@name='o_wsale_cart_line_button_container_mobile']//button[hasclass('js_delete_product')]` → `t-if="not line.is_free_battery_line"` (`:L2974`)
  - ⚠️ **No** ocultar los contenedores completos: el de desktop tambien contiene el selector de cantidad cuando la linea es de combo.
  - El selector de cantidad y el link al producto los cubre `_is_sellable()`.

> **Conflicto latente con `appointment_sms`**: nuestro `//input[@type='phone']` con
> `position="replace"` elimina el nodo que `appointment_sms` ancla con `position="after"`
> (`enterprise/appointment_sms/views/appointment_templates_registration.xml:4`). Ese modulo **no**
> esta instalado; si se instala, la pagina del turno rompe al combinar las vistas y hay que pasar
> nuestro override a `position="attributes"` o reordenar por `priority`.

> **XML IDs de las vistas**: `res_partner_view_form` y `product_template_view_form` siguen la
> convencion de AGENTS.md (`{model}_view_{tipo}`). `view_delivery_carrier_form` y `view_order_form`
> (espejan los ids del core) **no se renombran**: cambiarles el XML ID obligaria a un
> `ir.model.data` de migracion por pura cosmetica, contra la regla de **diff minimo**.

### Assets
- `static/src/js/installation_photos.js` (Interaction, selector `#shop_installation form[data-installation-photos]`): al elegir archivos en el input, **sube las fotos en el acto** (submit del form), muestra "Uploading photos…" y deshabilita el boton `installation_continue`. Sin JS, el boton *Upload photos* hace lo mismo. El acordeon es `collapse` de Bootstrap (`web.assets_frontend`) y los estados los renderiza el servidor.
- `static/src/scss/installation_form.scss`: estilos del formulario del link (D59), acotados a `.o_installation_sections` — encabezado de seccion (numero en circulo, titulo, ayuda) y la etiqueta arriba del campo a lo ancho. El checkout se pinta con utilidades de Bootstrap y clases del tema.

### Datos
- `website.checkout.step` `checkout_step_installation` (`sequence 400`, `step_href /shop/installation`), replicado por website en el `post_init_hook` y limpiado en el `uninstall_hook`.

## Seguridad

- **Modelos nuevos**: ninguno → **no hay ACLs, grupos ni record rules propios** (no aplica).
- Los campos viven en modelos del core y heredan su seguridad: `product.template` y
  `delivery.carrier` son de configuracion (`sales_team.group_sale_manager` / `base.group_system` segun
  el modelo), `sale.order.line.is_free_battery_line` es un flag tecnico que no se expone en vistas,
  `res.partner.between_streets` hereda las ACL/record rules del contacto.
- **`sudo()` de las lineas de pilas**: la creacion, escritura y borrado las dispara el **visitante
  publico** del checkout, que no tiene permisos sobre `sale.order.line`. Mismo criterio que
  `_create_delivery_line` del core (`odoo/addons/delivery/models/sale_order.py:L239`) y que
  `_apply_payment_price_rule` del modulo hermano. No expone datos: la operacion es sobre el carrito
  del propio visitante, y lo que decide si se agregan pilas es la configuracion, no el usuario.
- **`sudo()` de la confirmacion de la direccion del checkout**: `_save_installation_address()` escribe
  con `sudo()` **campo por campo** (`between_streets` en el partner de **envio del propio carrito**;
  `installation_notes` + `installation_address_confirmed` en **ese** pedido). Nunca se pasa el `post`
  completo a un `write()`. El core acota lo escribible desde el frontend con
  `_get_frontend_writable_fields()` (`odoo/addons/portal/controllers/portal.py:L594`); aca la
  acotacion la hace la propia ruta (D49).
- **Carrito anonimo**: en un carrito anonimo `partner_shipping_id` es el **partner publico
  compartido**, asi que `_save_installation_address()` **frena antes de escribir** con
  `order_sudo._is_anonymous_cart()` (`odoo/addons/website_sale/models/sale_order.py:L880`).
- **Limite de tamaño en los POST publicos**: `installation_notes` 1000 y `between_streets` 100 en el
  checkout; en el formulario de la cita, los 5 campos de direccion a los largos de su `maxlength`.
- **`sudo()` del bloque de direccion del formulario de la cita** (D58):
  `_save_appointment_installation_address()` escribe 5 campos fijos (`street`, `street2`, `city`,
  `zip`, `between_streets`) sobre **`event.appointment_booker_id`**, que es siempre el contacto del
  visitante que acaba de reservar: el `create()` nativo de la cita lo setea en el mismo dict
  (`enterprise/appointment/models/appointment_type.py:L1217`) con el partner que devuelve
  `_get_customer_partner()`, y ese, para un visitante publico, es un contacto **recien creado** por el
  propio submit (`enterprise/appointment/controllers/appointment.py:L800-824`, nunca busca por email)
  o —por el override de este modulo— el partner del **carrito no anonimo** del propio visitante.
  **No** se cae a `partner_ids[:1]`: ese recordset arranca por el partner del **empleado**
  (`enterprise/appointment/models/appointment_type.py:L1205`). Un valor vacio no borra dato del
  contacto. El aviso de lo declarado cuando no se escribe va por `message_post` con el subtipo interno
  por defecto (`mail.mt_note`): no le llega al cliente ni a los invitados de la cita.
- **`sudo()` de la ubicacion de la cita** (D62): se escribe **un solo campo** (`location`) de **la**
  cita del propio flujo — la que acaba de crear el submit del link, o `installation_event_id` del
  pedido que se confirma —, con el texto de la direccion de instalacion de esa misma visita. No
  expone datos nuevos: la direccion ya esta en el contacto/pedido que la cita referencia.

## Reglas de negocio

**Envio con instalacion**
1. **RB01**: Un metodo de envio con `installation_appointment_type_id` exige agendar instalacion; sin el, el pedido es un envio normal y el paso no existe.
2. **RB02**: Un tipo de cita sin paso de pago o sin producto de reserva no puede asociarse a un metodo de envio → `ValidationError`.
3. **RB03**: Sin cita agendada, con menos fotos que `installation_min_photos` o sin la direccion confirmada, el carrito no se puede pagar (y `/shop/payment` redirige al paso).
4. **RB04**: Reagendar descarta la reserva anterior: queda **una sola** linea de instalacion en el carrito.
5. **RB05**: Al confirmarse el pedido, las fotos se copian al chatter de la Cita y de la tarea de FSM.
6. **RB06**: Al confirmarse un pedido con instalacion, se invita al cliente al portal; si ya tiene usuario (activo o archivado) o no tiene email, no se hace nada y queda nota en el chatter. Un fallo nunca rompe la confirmacion.
7. **RB07**: Una cita de un tipo con `installation_fsm_project_id`, agendada fuera del eCommerce, genera tarea de FSM sin asignar; reprogramarla mueve las fechas de la tarea y cancelarla la cancela.
8. **RB08**: Las respuestas del formulario se validan segun `answer_format` en el navegador **y** en el servidor.

**Pilas incluidas**
9. **RB09**: Las pilas se agregan **solo** si el metodo de envio elegido tiene `includes_free_batteries`. Sin ese flag, el modulo es un no-op total sobre el pedido.
10. **RB10**: Por cada linea vendible del pedido (excluidas la de envio, las de pilas y las secciones/notas) cuyo producto tenga pilas configuradas, se necesitan `free_battery_qty * product_uom_qty` unidades del producto de pila, **en la UoM de ese producto**.
11. **RB11**: Las necesidades se **agrupan por producto de pila**: un producto de pila = **una** linea, con la suma.
12. **RB12**: La linea de pilas siempre vale **0**: `price_unit = 0`, `discount = 0` y `pricelist_item_id = False`, en todos los caminos de recomputo (cambio de cantidad, `/shop/payment`, recomputo forzado de precios).
13. **RB13**: La sincronizacion es **idempotente**: se recalcula desde cero (crea, ajusta y borra) y correrla dos veces no cambia nada. Se dispara al actualizar el carrito, al cambiar de metodo de envio, en el onchange del backend, en *Add shipping* y al confirmar (antes del `super()`).
14. **RB14**: Solo se sincroniza en `draft`/`sent`. Un pedido confirmado no se toca.
15. **RB15**: La linea gratis se **ve** en el carrito pero no se puede editar ni eliminar desde la UI; si el cliente la manipula por el endpoint publico, queda **re-sincronizada en el mismo request**.
16. **RB16**: Agregar manualmente el mismo producto de pila crea una linea **separada y paga**; la linea gratis no se fusiona ni cambia de precio.
17. **RB17**: "Volver a pedir" un pedido con pilas gratis no re-agrega la pila.
18. **RB18**: Configuracion invalida del producto (producto sin cantidad, cantidad sin producto, cantidad negativa, producto que es su propia pila) → `ValidationError`.
19. **RB19**: La factura del pedido incluye la linea de pilas a **0** (constancia de la entrega).
20. **RB20**: El **renglon corto al pie del paso** dice que las pilas **van incluidas** cuando el metodo de envio las incluye, y las pide ("4 u 8 AA/AAA el dia de la instalacion") cuando no. Son **dos ramas de la misma linea**: nunca se ven las dos (D52).
21. **RB21**: **Duplicar** un pedido con pilas gratis produce **una sola** linea de pilas, a 0 y con el flag puesto (D33).
22. **RB22**: La linea gratis **nunca** bloquea el pago por stock, aunque el producto de pila tenga *Sell when Out-of-Stock* apagado y stock 0 (D34).
23. **RB23**: El sync **no** toca lineas de pilas con cantidad facturada o entregada distinta de 0 (D36), y **no** genera lineas con cantidad `<= 0` (D39).
24. **RB24**: Una pila configurada en una compañia incompatible con el pedido **se saltea**: no se crea la linea y el carrito **no se rompe** (D38).

**Paso de instalacion en 3 bloques**
25. **RB25**: El paso `/shop/installation` muestra **siempre los tres bloques** (direccion · turno y
    fotos · pago). El estado de cada uno lo calcula el servidor
    (`_get_installation_block_states()`); el bloque **bloqueado no renderiza su cuerpo** y dice que
    falta.
26. **RB26**: La **direccion de instalacion del checkout es `partner_shipping_id`**. El Paso 1 la
    **muestra** y manda a editarla al paso del core (`/shop/address`): el checkout nunca escribe
    calle, ciudad, codigo postal ni pais.
27. **RB27**: *Confirm address* guarda `between_streets` (en el partner de envio) e
    `installation_notes` (en el pedido) y pone `installation_address_confirmed = True`.
    `between_streets` es **opcional** (`[ASUNCION]` D46): vacio tambien confirma.
28. **RB28**: Cambiar la direccion despues de confirmar —elegir otro contacto de envio **o** editar
    el mismo— vuelve `installation_address_confirmed` a `False` y con eso el Paso 2 se bloquea otra
    vez.
29. **RB29**: Sin direccion confirmada no se puede agendar ni subir fotos (Paso 2 bloqueado) y el
    pago queda bloqueado (`[ASUNCION]` D50).
30. **RB30**: El Paso 3 es un **link al paso siguiente del core**
    (`next_website_checkout_step_href`) y se habilita **solo** cuando `_get_installation_errors()`
    esta vacio. `/shop/payment` redirige al paso si algo falta (RB03).
31. **RB31**: La guia pide **3 fotos** (frente con la manija, canto, marco) y muestra **3 ejemplos de
    "asi no"** (borrosa, cortada, tapada). El progreso dice "N de `installation_min_photos`": el
    numero que gatilla es el del **carrier**, no el de la guia.
32. **RB32**: Entre calles e indicaciones llegan al instalador en la **descripcion de la tarea de
    Field Service**; la direccion la pone el nativo al **crear** la tarea desde el pedido
    (`partner_id = partner_shipping_id`, `enterprise/industry_fsm_sale/models/sale_order.py:L123`).
    ⚠️ RB32 se apoya en **ese** camino, no en el recompute: `_compute_partner_id`
    (`enterprise/industry_fsm_sale/models/project_task.py:L237`) esta condicionado a que el usuario
    tenga `account.group_delivery_invoice_address`.
33. **RB33**: Llegando **desde el checkout**, la pagina del turno **no repite** `message_intro`; por
    el **link compartido** se muestra arriba del calendario (D8/D54).

**Formulario de la cita y ubicacion**
34. **RB34**: En el formulario de la cita, cada bloque obligatorio muestra su aviso en texto: el de
    **direccion** siempre que el bloque exista; el de **fotos** solo si `installation_min_photos > 0`,
    con ese numero (D61). Con `installation_min_photos = 0` las fotos son opcionales y no hay aviso.
35. **RB35**: Toda Cita de instalacion con `location` vacio queda con la direccion de instalacion en
    `location`: la **declarada** en el formulario (link) o la de **entrega** del pedido (checkout).
    Una Cita con `location` cargado **no se toca** (D62).

## Edge cases

**Envio con instalacion**
- **Sin proveedor de pago habilitado**: el pedido no se confirma → la reserva (`calendar.booking`) queda pendiente y la limpia el garbage collector nativo (2-6 meses).
- **Cancelar el pedido** archiva la Cita (comportamiento nativo de `website_appointment_sale`).
- **Cambiar a envio normal despues de agendar**: el paso deja de mostrarse; la linea de la reserva queda en el carrito hasta que el cliente la quite.
- **Fotos HEIC de iPhone**: se rechazan por mimetype real, avisando **con el nombre del archivo**.
- **Invitado que edita el mail en el formulario de la cita**: el nativo crea un contacto nuevo; no se puede impedir sin bloquear los campos.
- **`sequence` de `appointment.question` es global**: reordenar afecta a todos los tipos que reutilicen la pregunta.
- **Sin servidor de correo saliente**: el usuario portal se crea pero el mail de invitacion no sale.
- **Configuracion de la base local**: el `appointment.type` id 1 ("prueba") al que apunta el carrier 3 tiene `has_payment_step = false` y **sin producto**, combinacion que `_check_installation_appointment_type` prohibe → el circuito de cita no se puede ejercitar end-to-end en esa base tal como esta. **No afecta a las pilas** (escribir solo `includes_free_batteries` no dispara ese constrain).
- **Multi-compañia / multi-sitio**: la configuracion de pilas es por producto y por metodo de envio, que son registros por compañia/sitio. El correo de la cita resuelve su compañia por el pedido/organizador/creador (D43), no por el usuario que dispara la notificacion.

**Paso en 3 bloques**
- **Carrito sin instalacion**: el paso se filtra del dominio (D3) y ni la direccion, ni las notas, ni la confirmacion se piden.
- **Pedido sin `partner_shipping_id`**: no deberia pasar (Direccion `sequence 250`, el paso `400`). Si pasa, el Paso 1 muestra el link para cargarla y **no** se puede confirmar.
- **Carrito anonimo**: el Paso 1 muestra el aviso "cargá primero la dirección" con link a `/shop/address`, y *Confirm address* **no escribe nada ni confirma** (`_is_anonymous_cart()`, `odoo/addons/website_sale/models/sale_order.py:L880`).
- **Cliente que confirma, vuelve atras y edita la MISMA direccion**: la confirmacion se cae (RB28) y el acordeon lo lleva de nuevo al Paso 1.
- **Cliente que elige OTRO contacto de envio**: mismo efecto, por el `write()` de `sale.order`. Las notas del pedido **no** se borran; lo que se pierde es la confirmacion.
- **Dos pedidos abiertos del mismo cliente a la misma direccion**: `between_streets` es del partner, asi que lo comparten; `installation_notes` es de cada pedido. Editar el partner desde un carrito **resetea la confirmacion de los dos**: conservador y correcto.
- **Reagendar desde el Paso 2**: queda una sola linea de instalacion (D11/RB04); si el cliente cancela la reserva, el bloque vuelve a `todo` y el Paso 3 se cierra solo.
- **Cliente sin JavaScript**: el acordeon no colapsa/despliega, pero **los encabezados de los tres bloques y el cuerpo del bloque abierto se renderizan igual** (el `show` sale del servidor), y las fotos se suben con el boton *Upload photos*.
- **`installation_min_photos` distinto de 3** (p.ej. 2 en el carrier): el progreso y el gate usan el numero del **carrier**; la guia muestra las tres tomas (es didactica). En `0`, las fotos son opcionales y el Paso 2 se completa solo con el turno.
- **Requisito de configuracion de los textos en produccion**: `message_intro` del tipo de cita del checkout no debe repetir los avisos que el paso reparte por bloque (duracion, pago, garantia, pilas) y, con un carrier que **incluye** pilas, no debe pedirlas; `installation_photos_message` cargado tiene que pedir las mismas 3 fotos de la guia. El aviso de pilas **no puede** saber que dice el texto libre: se ajusta como **dato**, desde la ficha del tipo de cita en el backend (D42).
- **Producto de la cita con `task_template_id`**: el core arma los vals de la tarea por `_prepare_task_template_vals` (`odoo/addons/sale_project/models/sale_order_line.py:L285`), que **no pasa** por nuestro override → entre calles y notas **no** llegarian a la tarea. El producto de reserva no usa plantilla; si se configura una, hay que enganchar tambien ese camino.
- **Tarea de FSM de una cita agendada por el link** (D8, sin pedido): no hay `installation_notes` ni `partner_shipping_id` — la tarea se crea sin el bloque de notas, con el entre calles del contacto (D58).
- **Pedido armado en el backoffice**: `installation_address_confirmed` queda en `False` (nadie apreto el boton) y el vendedor lo ve en la pestaña **Installation**. No bloquea la confirmacion desde el backend: el gate es del **checkout web**, no de `action_confirm()`.
- **Duplicar un pedido**: `installation_notes` e `installation_address_confirmed` son `copy=False` → el duplicado arranca sin confirmar, igual que las fotos.
- **Tests existentes**: el repo no tiene `.swarm.conf` (sin politica de tests por repo). `tests/test_free_batteries.py` y `tests/test_calendar_event_mail_company.py` tienen que seguir en verde. En la base `nokey` local, `test_calendar_event_mail_company.py` falla en `setUpClass` por un `ValidationError` de `_check_vat()` sobre el VAT de "Miluan SRL" (dato de la base, disparado por `MailCommon.setUpClass()` del core al reusar `env.company`), ajeno al codigo del modulo.

**Formulario de la cita y ubicacion**
- **Tipo que pide direccion o fotos sin proyecto de FSM** (formulario nativo, sin secciones): los bloques se pintan con su etiqueta propia (" *") y el aviso de obligatoriedad se ve igual, porque vive dentro del bloque (D61).
- **Envio con campos vacios**: el navegador frena con su globito nativo (atributo `required`); si el POST llega igual (sin JS, a mano), el servidor devuelve los errores en el `alert` de arriba con lo cargado. El aviso de D61 no cambia esa validacion.
- **Contacto que ya tenia otra calle** (link): el contacto no se toca (D58), pero la Cita queda con la direccion **declarada** en `location` (D62): la visita es a ese lugar.
- **Sin `appointment_booker_id`** (link): la ubicacion se escribe igual; lo que no se escribe es el contacto.
- **Solo "entre calles" sin calle ni localidad**: no pasa por el formulario (calle y localidad son obligatorias); el helper no escribe una ubicacion que sea solo "entre calles".
- **Correo de confirmacion de la cita**: sale al crearse la cita (antes de que se escriba `location`), asi que no muestra la direccion; el `write()` del core no reenvia invitaciones por un cambio de `location` (solo por `start`, `odoo/addons/calendar/models/calendar_event.py:L855`). La direccion se ve en la cita, en el Gantt, en el `.ics` que se descarga desde la cita y en los recordatorios posteriores.
- **Tipo de cita con ubicacion propia** (`appointment.type.location_id`): la Cita nace con esa ubicacion y el modulo no la pisa (D62).
- **Cambio posterior de la direccion de entrega de un pedido confirmado**: `location` queda con la direccion del momento de la confirmacion; actualizarla es trabajo del backoffice (se edita en la ficha de la cita).
- **Backfill sobre una cita sin pedido ni contacto con calle**: queda sin `location` (no hay de donde sacarla).
- **Tracking**: `location` es `tracking=True`: el alta desde el link o el checkout queda como nota de seguimiento interna en la cita; el backfill corre con `mail_notrack`.

**Pilas incluidas**
- **Producto sin pilas configuradas o carrier sin el flag**: no se crea ninguna linea (no-op), y si habia lineas gratis de un estado anterior del carrito, se borran.
- **UoM del producto de pila ("Paquete de 4")**: `free_battery_qty = 1` despacha **un paquete** (4 pilas). Si el funcional escribe `4` pensando en pilas, se despachan **16**. Mitigacion: `string`/`help` explicitos + la UoM visible en la vista (D15).
- **Dos cerraduras distintas con la misma pila**: una sola linea con la suma (RB11).
- **Cambio de cantidad de la cerradura**: la cantidad de pilas se recalcula (no se apila).
- **Cambio de metodo de envio**: pasar a uno sin el flag borra las lineas gratis; volver al que las incluye las vuelve a crear.
- **Cliente que borra la linea gratis por `/shop/cart/update`**: se re-crea en el mismo request (RB15).
- **Cliente que agrega la misma pila como producto suelto**: dos lineas — la gratis (0) y la suya (precio de tarifa). ⚠️ **Con stock 0 y sin *Sell when Out-of-Stock*** el alta se rechaza antes, por el control nativo de `website_sale_stock` (que cuenta la linea gratis en el `product_qty_in_cart`): no se crea ninguna linea. Es lo correcto; por eso CA21 se ejercita con stock cargado o con la venta sin stock habilitada.
- **Producto de pila publicado**: la linea gratis sigue sin selector de cantidad ni link (D29).
- **`prevent_zero_price_sale`**: sin setear en los dos sitios (Nokey id 1, Sunra id 3). Si alguien lo prende, la linea gratis sigue funcionando (`_check_validity` sale temprano).
- **Pilas storable con stock 0**: al confirmar, el picking muestra las pilas como **no disponibles** hasta que se cargue stock. Mientras el producto de pila este agotado, la linea gratis **apaga el mail de carrito abandonado** de ese carrito (`_filter_can_send_abandoned_cart_mail` → `_all_product_available()` → `_is_sold_out()`, `odoo/addons/website_sale_stock/models/sale_order.py:L134` y `:L140`). Es configuracion (aprovisionarlas), no un bug.
- **Impuestos**: el producto de pila tiene VAT 21%, pero sobre `price_unit = 0` el impuesto liquida 0.
- **Producto de pila eliminado**: `ondelete="restrict"` frena el borrado mientras haya productos que lo referencien (un `set null` de SQL no dispararia `@api.constrains` y el opt-in quedaria a medias).
- **Pedido confirmado / facturado**: no se sincroniza (RB14).
- **Pedido facturado que vuelve a presupuesto**: queda en `draft` con `qty_invoiced != 0`; el sync **congela** esas lineas (D36) y reconcilia el resto.
- **Duplicar un presupuesto**: el duplicado conserva la linea a $0 **con el flag** (D33), el sync la reconoce y solo ajusta la cantidad.
- **Pila con *Sell when Out-of-Stock* apagado y stock 0** (tmpl 411): el checkout **no se traba** (D34).
- **Pedido con cantidades negativas**: no se genera linea de pilas (D39).
- **Pedido con `+1` y `-1` de la MISMA cerradura en dos lineas simultaneas**: el filtro por linea (D39) descarta solo la `-1`; la `+1` manda → se crea **una linea de 1 paquete** aunque el neto sea 0. Consecuencia directa de filtrar por linea; el carrito web fusiona por `_cart_find_product_line`, asi que es un caso manual.
- **Pila configurada en otra compañia**: se saltea (D38).
- **Cerradura dentro de un combo**: aporta pilas. Configurar pilas en la plantilla del combo **y** en el item las cuenta **dos veces** (D40).
- **Cerradura vendida en una UoM que no sea Units**: la cantidad **no se convierte** (D40).
- **`invoice_policy` del producto de pila**: con `'order'` (411/412) la linea llega a la factura (D28). Con `'delivery'` y stock 0, no se facturaria.
- **Modulos vecinos inertes**: `website_sale_payment_method_price` — la linea de pilas contribuye **0** al total y la linea de descuento global de ese modulo queda fuera de `_compute_price_unit` por `_is_global_discount()` (`odoo/addons/sale/models/sale_order_line.py:L601`); el orden de los overrides no importa. Linea del booking de `website_appointment_sale` — filtros disjuntos, y su `_cart_find_product_line` devuelve vacio cuando viene `calendar_booking_id`, asi que nuestro `.filtered()` encadenado es un no-op.

## Criterios de aceptacion

> **Datos de referencia para la validacion manual** (base del cliente): carrier *Envio con
> Instalación* = `delivery.carrier` **3** (`fixed`, `fixed_price=0`, `free_over=false`,
> `max_weight=0`, `installation_appointment_type_id=1`); cerradura tmpl **466** / variante **686**
> (VAT 21%, `is_storable=False`, UoM Units); pilas tmpl **411**/**412** (variantes 607/608, VAT 21%,
> `is_storable=True`, **stock 0**, despublicadas, UoM "Paquete de 4" `uom.uom` 31, $6.000 el paquete
> en la tarifa "Precio Público - Nokey", `product.pricelist` 22); `website.prevent_zero_price_sale`
> sin setear en Nokey (1) y Sunra (3).

**Envio con instalacion**
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

**Textos configurables**
- [ ] **CA35**: Cargar `message_intro` en el tipo de cita → ese texto se ve **dentro del Paso 2** (el "antes de agendar") y, en el tipo **del link**, **arriba del calendario** y no al final. Vaciarlo → el Paso 2 **no muestra ningun checklist**: los avisos estan **repartidos por bloque** (duracion en el Paso 2, condicion de pago en el Paso 3, garantia y pilas en el renglon del pie — D52). El unico texto configurable con **default propio** del modulo es `installation_photos_message` (CA36).
- [ ] **CA36**: Cargar `installation_photos_message` → esa consigna se ve arriba del input de fotos en **los dos** caminos (checkout y formulario del link); vaciarla → vuelve el texto por defecto.

**Pilas incluidas**
- [ ] **CA14**: Cerradura con pilas configuradas + metodo de envio con `includes_free_batteries` → aparece la linea de pilas a **0**, con cantidad = `free_battery_qty * cantidad de cerraduras`, en la **UoM del producto de pila**.
- [ ] **CA15**: Cambiar la cantidad de cerraduras → la cantidad de pilas se ajusta (no se apila ni se duplica la linea).
- [ ] **CA16**: Cambiar a un metodo de envio **sin** `includes_free_batteries` → la linea de pilas **desaparece**; volver al que las incluye → reaparece.
- [ ] **CA17**: Dos cerraduras distintas que comparten el mismo producto de pila → **UNA** linea con la suma.
- [ ] **CA18**: Renderizar `/shop/payment` (dispara `_recompute_cart` → `_recompute_prices` con `force_price_recomputation=True`) → el precio de la linea sigue en **0**.
- [ ] **CA19**: Cambiar la cantidad (camino **no** forzado de `_compute_price_unit`) → el precio sigue en **0**.
- [ ] **CA20**: Con una tarifa con descuento configurada → la linea gratis queda con `discount == 0` y `pricelist_item_id == False`: no se prende la columna Descuento del PDF ni el precio tachado en el carrito.
- [ ] **CA21**: Agregar manualmente el mismo producto de pila al carrito → se crea una linea **separada y paga**; la linea gratis no se fusiona ni cambia de precio. ⚠️ Se valida con stock cargado o con *Sell when Out-of-Stock* activado: con stock 0, `website_sale_stock._verify_updated_quantity` (`odoo/addons/website_sale_stock/models/sale_order.py:L22`) calcula `free_qty = 0` y `_get_cart_qty` (`:L102`) cuenta tambien la linea gratis (`_get_common_product_lines`, `:L120`) → el alta no crea ninguna linea (comportamiento nativo correcto).
- [ ] **CA22**: "Volver a pedir" un pedido que tenia pilas gratis → la pila **no** se re-agrega al carrito nuevo.
- [ ] **CA23**: Armar el pedido en el **backend**: (a) al cargar lineas y metodo de envio a mano, la linea de pilas aparece por el onchange; (b) asignando el envio con **Add shipping** (wizard `choose.delivery.carrier`, por `write`, sin onchange), la linea aparece igual — el **presupuesto en PDF ya la incluye**; (c) si ninguno de los dos se disparo, al confirmar queda sincronizada.
- [ ] **CA24**: Borrar la linea gratis (o cambiarle la cantidad) por `/shop/cart/update` con su `line_id` real → queda **re-creada/ajustada en el mismo request**.
- [ ] **CA25**: Cerradura **sin** pilas configuradas, o carrier sin el flag → **no** se crea ninguna linea (no-op), y las lineas gratis previas se limpian.
- [ ] **CA26**: Configuracion invalida (producto sin cantidad, cantidad sin producto, cantidad negativa, producto que es su propia pila) → `ValidationError` al guardar el producto.
- [ ] **CA27**: En el carrito, la linea gratis **se ve** pero no ofrece selector de cantidad editable, ni link al producto, ni boton **Eliminar** (desktop y mobile).
- [ ] **CA28**: **Publicar** el producto de pila (`is_published = True`) **no** habilita el selector de cantidad ni el link de la linea gratis.
- [ ] **CA29**: En el renglon corto al pie del acordeon, con un carrier que **incluye** pilas se lee que van incluidas sin cargo y con uno que **no**, se lee que hay que tenerlas el dia de la instalacion. Se ve **en los dos casos**, tambien con `message_intro` cargado (D41/D52).
- [ ] **CA37**: El aviso de pilas y el pedido de pilas son **la misma linea** con `t-if`/`t-else` (D52): es **imposible** que convivan. Verificar en **ingles y en es_419** que con el carrier que las incluye se lee solo "incluidas" y con el que no, solo "tenes que tener 4 u 8 AA/AAA", y que ninguno depende de si `message_intro` esta cargado o traducido.
- [ ] **CA30**: La **factura** del pedido muestra la linea de pilas a 0, con la descripcion que aclara que va incluida (requiere `invoice_policy = 'order'` en el producto de pila, como en 411/412). Se verifica a mano.
- [ ] **CA31**: **Duplicar** un pedido que tiene la linea de pilas gratis → el duplicado queda con **UNA** linea de pilas, a **$0** y **con el flag**; al confirmarlo no se crea una segunda ni se cobra ninguna.
- [ ] **CA32**: Producto de pila con *Sell when Out-of-Stock* **apagado** y **stock 0** (tmpl 411) → el carrito **se puede pagar**: `_check_cart_is_ready_to_be_paid` no tira `ValidationError` por la linea gratis.
- [ ] **CA33**: Pedido con la cerradura en cantidad **`-1`** o con `+1` y `-1` que se cancelan → **no** se crea linea de pilas negativa ni en 0 (y si habia una, se borra).
- [ ] **CA34**: Cerradura de una compañia con una pila configurada en **otra** compañia → el carrito **no rompe** (sin `UserError`/500): la pila se saltea y no se crea la linea.

**Marca del correo de la cita**
- [ ] **CA38**: Una cita de instalacion cuyo pedido de venta es de una compañia (ej. Miluan SRL / Nokey) → el **layout renderizado** (logo, nombre y colores) del correo de **recordatorio** usa **esa** compañia, aunque el usuario del cron de alarmas (`ir_cron_scheduler_alarm`) tenga otra compañia por defecto (ej. YG S.A. / Sunra). El correo de **confirmacion** sale con la misma compañia. Sin pedido asociado (cita por link) → la compañia del organizador, y si no hay organizador, la de quien la creo. **Se valida renderizando la notificacion de verdad** (`test_notification_layout_uses_order_company_branding` lee el `body_html` generado con `MailCommon`/`mock_mail_gateway()`; el resolvedor `_mail_get_companies()` aislado no pinta el layout). A mano: disparar el cron de alarmas (*Run Manually*) sobre una cita de un pedido de Nokey desde un usuario de Sunra.

**Paso de instalacion en 3 bloques + guia de fotos**
- [ ] **CA39**: En `/shop/installation` se ven **los tres bloques desde el inicio**, en orden y numerados (*Paso 1 · Installation address*, *Paso 2 · Appointment and photos*, *Paso 3 · Payment*), con el completado en **tilde** (mas su resumen en el encabezado), el pendiente con su **numero** y el bloqueado con **candado** + la razon. El bloqueado **no muestra su cuerpo**.
- [ ] **CA40**: El Paso 1 muestra la **direccion de entrega** del pedido (nombre, calle, piso/depto, localidad) y el link **editar** abre `/shop/address?partner_id=<partner de envio>&address_type=delivery&callback=/shop/installation`; al **Guardar** (y al **Descartar**) el navegador **vuelve al paso de instalacion** —no a `/shop/checkout`— y el resumen refleja lo editado (`callback` nativo, `odoo/addons/website_sale/controllers/main.py:L1234`, `:L1236`, `:L1184`).
- [ ] **CA41**: Cargar *entre calles* + *indicaciones para el instalador* y apretar **Confirm address** → se guardan (`res.partner.between_streets` y `sale.order.installation_notes`), el bloque queda con tilde y el Paso 2 se habilita. Recargar la pagina **mantiene** el estado. Confirmar **sin** entre calles tambien cierra el bloque (`[ASUNCION]` D46).
- [ ] **CA42**: Antes de confirmar la direccion, el Paso 2 esta **bloqueado**: no hay boton para agendar ni input de fotos en el HTML.
- [ ] **CA43**: Cambiar la direccion **despues** de confirmar —(a) editar el mismo contacto desde `/shop/address`, (b) elegir otro contacto de envio— → el Paso 1 vuelve a **pendiente**, el Paso 2 se bloquea y el Paso 3 tambien. Las indicaciones cargadas **no se borran**.
- [ ] **CA44**: El Paso 3 esta con **candado** mientras falte turno, fotos (menos que `installation_min_photos`) o la confirmacion de la direccion; cuando no falta nada, es un **link** al paso siguiente del core (`next_website_checkout_step_href` → `/shop/payment`, con *Extra Info* desactivado — D44). Ir a `/shop/payment` a mano en el estado bloqueado **redirige** al paso (RB03/CA03).
- [ ] **CA45**: La guia de fotos muestra **3 tomas "asi si"** (frente con la manija, canto, marco) y **3 "asi no"** (borrosa, cortada, tapada por la mano) con su motivo. El progreso dice **"N de `installation_min_photos`"** y avanza al subir cada foto; elegir los archivos los sube en el acto. La consigna por defecto (`installation_photos_message` vacio) pide **3 fotos**.
- [ ] **CA46**: Pagar un pedido con entre calles e indicaciones cargadas → la **tarea de Field Service** queda con esos datos en la **descripcion** y con la **direccion de entrega** como contacto. Sin ninguno de los dos datos, la descripcion es la del core.
- [ ] **CA47**: Entrar a la pagina del turno **desde el checkout** (boton *Schedule the installation*) → `message_intro` **no** aparece al final de la pagina. Entrar por el **link compartido** (tipo con `installation_fsm_project_id`, sin carrito) → se ve **arriba del calendario**.
- [ ] **CA48**: Todos los textos del paso hablan **de vos** (voseo) en es_419 y los strings estan en **ingles** en el codigo, con su entrada traducida en `i18n/es_419.po`.

**Formulario de la cita**
- [x] **CA49**: Viniendo del checkout, el formulario de la cita **no** vuelve a pedir nombre, correo ni fotos: muestra "Reservas como `<nombre>` `<mail>`" y solo las preguntas que el checkout no hace. El turno se reserva sin subir ninguna foto ahi.
- [x] **CA50**: Entrando por el link (`/book/...`), el formulario pide la direccion de instalacion: calle y numero y localidad **obligatorias**, piso/depto, CP y entre calles opcionales.
- [x] **CA51**: Al reservar por el link, el contacto creado queda con la direccion cargada y la tarea de Field Service la muestra; el "entre calles" aparece en el cuerpo de la tarea.
- [x] **CA52**: Si el contacto que reserva **ya tenia** calle cargada, no se le pisa **ningun** campo de la direccion: lo declarado queda como mensaje en la cita **y en la tarea de Field Service**.
- [x] **CA53**: El formulario del **link** se ve en 4 secciones numeradas (Tus datos · Sobre tu puerta · Direccion de instalacion · Fotos del lugar), con la etiqueta arriba del campo.
- [x] **CA54**: El formulario del **checkout** conserva el layout nativo: sin secciones, sin bloque de direccion y sin input de fotos.
- [ ] **CA56**: En el formulario del **link** con `installation_min_photos > 0`, inmediatamente arriba del input de fotos se lee, en rojo y con icono, *"Obligatorio: subí al menos N foto(s) para poder confirmar la cita."* (es_419) con N = `installation_min_photos`; en ingles, *"Required: upload at least N photo(s) to confirm the appointment."*. Con `installation_min_photos = 0` el aviso no aparece. En un tipo que pide fotos **sin** proyecto de FSM (formulario nativo, sin secciones) el aviso tambien se ve. Desde el editor web el aviso no es editable.
- [ ] **CA57**: En el formulario del **link**, la primera linea del bloque de direccion (debajo del titulo "Direccion de instalacion") dice, en rojo y con icono, *"Obligatorio: calle y número, y localidad."* (es_419); en un tipo que pide direccion **sin** proyecto de FSM tambien se ve. Desde el editor web no es editable.

**Ubicacion de la cita**
- [ ] **CA58**: Reservar por el **link** con la direccion *Lamadrid 581*, piso *2B*, CP *1648*, localidad *Tigre*, entre calles *Peru y Chile* → la Cita queda con `location` = `Lamadrid 581, 2B, 1648 Tigre (entre calles: Peru y Chile)` y se ve en la ficha, en la lista de citas, en el popover del Gantt de Citas y en el `.ics` que se descarga desde la cita (no en el adjunto del correo de confirmacion, que sale antes). Si el contacto **ya tenia otra calle** (CA52), la Cita queda igual con la direccion **declarada**.
- [ ] **CA59**: Pagar/confirmar un pedido del **checkout** con instalacion → la Cita queda con `location` = la direccion de entrega del pedido (`partner_shipping_id`), con su entre calles si lo tiene.
- [x] **CA60**: Con un tipo de cita de instalacion que tiene **ubicacion propia** (`location_id`), la Cita conserva esa ubicacion en los dos caminos: el modulo no pisa un `location` cargado.
- [x] **CA61**: Actualizar el modulo a `1.14.0` sobre una base con citas de instalacion sin ubicacion → las que tienen pedido quedan con la direccion de entrega del pedido, las del link con la del contacto que reservo (si tiene calle), y las que ya tenian `location` no cambian. Correr el `-u` de nuevo no cambia nada.

**Lista de facturacion del checkout**
- [ ] **CA55**: Con productos entregables (`has_delivery = True`), la lista de facturacion **nunca** muestra la tarjeta de la direccion de entrega: al destildar "Same as delivery address" quedan solo *Add Address* y las otras direcciones de facturacion del cliente (si tiene). Con un pedido `only_services` (`has_delivery = False`) la lista queda completa (D60).

**Modulo sin historia**
- [x] **CA62**: `python3 .claude/scripts/history_lint.py --module <modulo>` sale sin errores sobre spec, comentarios/docstrings de `.py`/`.xml`/`.js`, `README.md` e `index.html`, y `history_lint.py --seal` escribe la fila `Depurado` en esta spec.

## Referencias al core

> Anclajes `path:L#` verificados sobre el workspace (`odoo/`, `enterprise/`). Lo interno del modulo se
> cita por **archivo + metodo**, sin numero de linea.

| Que | Anclaje (`path:L#`) | Por que importa |
|-----|---------------------|-----------------|
| Hook canonico del carrito web | `odoo/addons/website_sale/models/sale_order.py:L674` | `_verify_cart_after_update()` — su docstring dice que es el lugar de los chequeos globales, una vez por request |
| Auto-curacion tras cambiar una linea | `odoo/addons/website_sale/models/sale_order.py:L496` | `_cart_update_line_quantity()` llama al hook **despues** de aplicar el cambio → la linea se re-sincroniza en el mismo request |
| Idem, alta al carrito | `odoo/addons/website_sale/models/sale_order.py:L394` | `_cart_add` tambien pasa por el hook (salvo `skip_cart_verification`) |
| Precedente exacto del override del hook | `odoo/addons/website_sale_loyalty/models/sale_order.py:L185` | `super()` primero y despues la sincronizacion propia |
| Cambio de metodo de envio | `odoo/addons/website_sale/models/sale_order.py:L853` | `_set_delivery_method(delivery_method, rate=None)` — embudo de la seleccion de envio |
| Endpoint que lo llama | `odoo/addons/website_sale/controllers/delivery.py:L58` | `shop_set_delivery_method` → el override cubre el cambio de carrier |
| Quitar la linea de envio | `odoo/addons/website_sale/models/sale_order.py:L825` / `odoo/addons/delivery/models/sale_order.py:L54` | Sus llamadores estan enganchados → no hace falta override propio |
| Molde de creacion de linea de servicio | `odoo/addons/delivery/models/sale_order.py:L203` | `_prepare_delivery_line_vals` — no pasa `product_uom_id`; el ORM toma la UoM del producto |
| Creacion con `sudo()` | `odoo/addons/delivery/models/sale_order.py:L239` | `_create_delivery_line` — precedente del `sudo()` para el visitante publico |
| Campo de UoM en v19 | `odoo/addons/sale/models/sale_order_line.py:L132` | Es **`product_uom_id`** |
| Recomputo de precio | `odoo/addons/sale/models/sale_order_line.py:L587` | `_compute_price_unit` depende de `product_id`/`product_uom_id`/`product_uom_qty` |
| Por que `price_unit=0` no alcanza | `odoo/addons/sale/models/sale_order_line.py:L1358` | `_add_precomputed_values` copia `price_unit` a `technical_price_unit` → `has_manual_price` da `False` |
| Camino forzado del precio | `odoo/addons/sale/models/sale_order_line.py:L619` y `:L623` | `_reset_price_unit()` llama a `_get_display_price()`: un solo override cubre los dos caminos |
| Metodo a override-ear para el precio 0 | `odoo/addons/sale/models/sale_order_line.py:L639` | `_get_display_price()` |
| Recomputo de precios de la orden | `odoo/addons/sale/models/sale_order.py:L1372` | `_recompute_prices()` resetea `discount` y recomputa |
| Guard del descuento | `odoo/addons/sale/models/sale_order_line.py:L807` | `_compute_discount` sale por `continue` si `not pricelist_item_id._show_discount()` |
| Molde literal a copiar | `odoo/addons/delivery/models/sale_order_line.py:L59` | `_compute_pricelist_item_id()` → `False` para las lineas de envio |
| Omision verificada de `_get_update_prices_lines` | `odoo/addons/delivery/models/sale_order.py:L49` | El equivalente de `delivery`; en nuestro caso es redundante **y peor** |
| Reset del descuento en el recomputo | `odoo/addons/sale/models/sale_order.py:L1379` | `lines_to_recompute.discount = 0.0` — razon para NO excluir la linea del recordset |
| Semantica de `copy` en campos computados | `odoo/odoo/orm/fields.py:L449` | Un compute recibe `copy=False` **salvo** `store=True` y no `readonly`: por eso `price_unit` y `name` **si** se copian |
| Campos que si se copian | `odoo/addons/sale/models/sale_order_line.py:L177` y `:L121` | `price_unit` y `name` son `store=True, readonly=False` → el duplicado conserva el $0 y la descripcion |
| Molde del flag copiable | `odoo/addons/delivery/models/sale_order_line.py:L9` | `is_delivery` se declara **sin `copy=`** |
| Orden de carga de modulos | `odoo/odoo/modules/module_graph.py:L175` y `:L225` | `(phase, depth, order_name)`: por que el override de `_check_availability()` gana el MRO (D34) |
| Guard de stock del eCommerce | `odoo/addons/website_sale_stock/models/sale_order.py:L124` | `_check_cart_is_ready_to_be_paid` tira `ValidationError` si una linea falla `_check_availability()` |
| Condicion de indisponibilidad | `odoo/addons/website_sale_stock/models/sale_order_line.py:L39` | `is_storable and not allow_out_of_stock_order and cart_qty > free_qty` |
| Guard de facturado del core | `odoo/addons/sale/models/sale_order.py:L1452` | `_check_line_unlink` bloquea solo con `state == 'sale'` |
| Precedente del guard `qty_invoiced` | `odoo/addons/delivery/models/sale_order.py:L59` | `_remove_delivery_line` solo borra las lineas con `qty_invoiced == 0` |
| Flujo real de envio en el backend | `odoo/addons/delivery/models/sale_order.py:L67` | `set_delivery_line()` — lo llama el wizard **Add shipping** por `write` (sin onchange) |
| Camino de **quitar** el envio | `odoo/addons/website_sale/models/sale_order.py:L864` | `_set_delivery_method` retorna antes de `set_delivery_line` |
| `check_company` de la linea | `odoo/addons/sale/models/sale_order_line.py:L88` | `product_id` es `check_company=True`; el `sudo()` no exime de `_check_company` |
| Domain de compañia del vecino | `odoo/addons/sale/views/product_template_views.xml:L16` | Forma a copiar para `free_battery_product_id` |
| Idioma de la descripcion | `odoo/addons/delivery/models/sale_order.py:L207` y `enterprise/website_appointment_sale/models/sale_order.py:L83` | `context['lang'] = partner.lang` / `self._get_lang()` |
| Conversion de UoM (D40) | `odoo/addons/delivery/models/sale_order_line.py:L24` | `product_uom_id._compute_quantity(qty, product_id.uom_id)` |
| `unlink()` de una linea de envio | `odoo/addons/delivery/models/sale_order_line.py:L29` | Pone `carrier_id = False` en el pedido → D18 |
| Metodo del peso sin llamadores locales | `odoo/addons/delivery/models/sale_order_line.py:L36` y `odoo/addons/delivery/tests/test_delivery_cost.py:L295` | `_get_invalid_delivery_weight_lines` solo lo usan los carriers de terceros de enterprise y el test |
| Lineas fuera del recomputo de precio | `odoo/addons/sale/models/sale_order_line.py:L601` | `_compute_price_unit` saltea `is_downpayment` y `_is_global_discount()` |
| Gate de precio 0 del eCommerce | `odoo/addons/website_sale/models/sale_order_line.py:L102` y `odoo/addons/website_sale/models/sale_order.py:L554` | `_check_validity()` con `prevent_zero_price_sale` abortaria el request antes de la auto-curacion |
| Filtro de "Volver a pedir" | `odoo/addons/website_sale/models/sale_order_line.py:L85` y `odoo/addons/website_sale/controllers/reorder.py:L33` | `_is_reorder_allowed()` → `_show_in_cart()` no conoce nuestro flag |
| Por que no `is_delivery=True` | `odoo/addons/website_sale/models/sale_order_line.py:L80` | `_show_in_cart()` excluye `is_delivery` → ocultaria la linea, contra D20 |
| Linea visible pero no editable | `odoo/addons/website_sale/models/sale_order_line.py:L124` | `_is_sellable()` — punto de extension (base: `is_published and not is_delivery`) |
| Precedente en la cadena de deps | `enterprise/website_appointment_sale/models/sale_order_line.py:L19` | La linea de la cita: se ve, no se edita |
| Otro precedente | `odoo/addons/website_sale_loyalty/models/sale_order_line.py:L38` | `_is_sellable()` para las lineas de premio |
| Selector de cantidad readonly | `odoo/addons/website_sale/views/templates.xml:L3002` | `should_show_quantity_selector and line._is_sellable()` → rama `t-else` sin `-`/`+` |
| Link al producto | `odoo/addons/website_sale/views/templates.xml:L2829` | Colgado de `_is_sellable()` |
| Precio tachado | `odoo/addons/website_sale/models/sale_order_line.py:L122` | `_should_show_strikethrough_price()` usa `_is_sellable()` |
| Precio por UoM | `odoo/addons/website_sale/views/templates.xml:L3066` | Idem |
| Sugerencias de pedidos anteriores | `odoo/addons/website_sale/controllers/cart.py:L388` | Excluye las lineas no sellable |
| Botones a ocultar por xpath | `odoo/addons/website_sale/views/templates.xml:L2954` y `:L2974` | Contenedores con `name=` estable (desktop/mobile) |
| Variable del bucle del carrito | `odoo/addons/website_sale/views/templates.xml:L2880` | `t-as="line"` → la condicion es `line.is_free_battery_line` |
| Colision de alta manual | `odoo/addons/website_sale/models/sale_order.py:L403` y `:L430` | El domain de `_cart_find_product_line` no filtra por nuestro flag |
| Precedente de estilo del override | `enterprise/website_appointment_sale/models/sale_order.py:L58` | `_cart_find_product_line` filtrado para las lineas de reserva |
| Por que la red va en `action_confirm()` | `odoo/addons/sale/models/sale_order.py:L1167` y `:L1183` | El `write(_prepare_confirmation_values())` pasa el `state` a `'sale'` **antes** de `_action_confirm()` |
| Contaminacion del `name` con `linked_line_id` | `odoo/addons/sale/models/sale_order_line.py:L436` | Appendea `"Option for: <producto>"` → D19 |
| Sincronizacion de lineas en el backend | `odoo/addons/sale/models/sale_order.py:L936` | `@api.onchange('order_line')` del core con `Command.*` **en memoria** |
| Precedente de onchange en `delivery` | `odoo/addons/delivery/models/sale_order.py:L42` | Existe un `@api.onchange('order_line', ...)` en la cadena |
| Grupo de la vista de producto | `odoo/addons/product/views/product_views.xml:L143` | `group name="upsell"` en la pestaña Sales |
| Vecinos del grupo | `odoo/addons/sale/views/product_template_views.xml:L12` y `odoo/addons/website_sale/views/product_views.xml:L169` | `optional_product_ids` / `accessory_product_ids` |
| UoM related del core | `odoo/addons/product/models/product_template.py:L123` | `uom_name = related='uom_id.name'` — lo reusa `free_battery_uom_name` |
| Recomputo del carrito (omitido) | `odoo/addons/website_sale/models/sale_order.py:L932` | `_recompute_cart()` — no se override-ea |
| Campo nativo del checklist | `enterprise/appointment/models/appointment_type.py:L147` | `message_intro` (Html, `translate=True`, `sanitize_attributes=False`) |
| Donde el core pinta `message_intro` | `enterprise/appointment/views/appointment_templates_appointments.xml:L233` | Al final de la pagina del turno → por eso el tipo del link lo lleva arriba del calendario |
| Template y bloque no editable | `enterprise/appointment/views/appointment_templates_appointments.xml:L75` y `:L92` | `appointment_info` y `o_appointment_info_main` (`o_not_editable`) |
| Intro nativo de la pagina del turno | `enterprise/appointment/views/appointment_templates_appointments.xml:L231-234` | El bloque que se apaga en el tipo del link y cuando se llega desde el checkout (D54) |
| Helper del patron campo-vacio | `odoo/odoo/tools/mail.py:L490` | `is_html_empty()` |
| Base de `_mail_get_companies()` | `odoo/addons/mail/models/models.py:L128-140` | Cae al `default` cuando el modelo no tiene `company_id`; **no** pinta el layout |
| Caller de `_mail_get_companies()` en la notificacion | `odoo/addons/mail/models/mail_thread.py:L2831` | Dentro de `message_notify()`: `record_company_id` |
| El hook que pinta el logo/colores | `odoo/addons/mail/models/mail_thread.py:L3606-3719` | `_notify_by_email_prepare_rendering_context()`; el calculo de `company`/`website_url` en `:L3657-3666` lee `record.company_id` **directo** |
| `sudo()` de la compañia del layout | `odoo/addons/mail/models/mail_thread.py:L3660` | El core tambien la lee con `sudo()` |
| Reglas de lectura de `res.company` | `odoo/odoo/addons/base/security/base_security.xml:L105-125` | Por que el override escribe la compañia con `sudo()` |
| Camino comun de confirmacion Y recordatorio | `odoo/addons/calendar/models/calendar_attendee.py:L124-L196` | `_notify_attendees()` → `message_notify()` sobre el `calendar.event`, una llamada **por asistente** |
| Disparador de la confirmacion (request web) | `enterprise/appointment/models/calendar_attendee.py:L16-L44` | `_send_invitation_emails()` — corre en el `create()` del attendee |
| Disparador del recordatorio (cron) | `odoo/addons/calendar/models/calendar_alarm_manager.py:L182-L202` | `_send_reminder()`: `env.company` es la del usuario tecnico del cron |
| Molde del fallback organizador/creador | `odoo/addons/calendar/controllers/main.py:L66` | `event.user_id and event.user_id.company_id or event.create_uid.company_id` |
| Vinculo cita ↔ pedido | `enterprise/website_appointment_sale/models/sale_order_line.py:L10-11` | `sale.order.line.calendar_event_id` **sin `copy=False`**: "el mas viejo, no cancelado, gana" (D43 y backfill D62) |
| Molde de override de `_notify_by_email_prepare_rendering_context` | `odoo/addons/sale/models/sale_order.py:L1758`, `odoo/addons/project/models/project_task.py:L1506`, `odoo/addons/crm/models/crm_lead.py:L2103` | Llaman a `super()` y pisan claves del dict devuelto |
| Modelo del paso de checkout | `odoo/addons/website_sale/models/website_checkout_step.py:L7` y `:L19` | `website.checkout.step` y `_get_next_checkout_step()`: el paso es **uno solo** (D3/D44) |
| Secuencias de los pasos del core | `odoo/addons/website_sale/data/data.xml:L74` y `:L90` | Address `250` · Payment `999` → en `/shop/installation` hay `partner_shipping_id` |
| Valores de navegacion del checkout | `odoo/addons/website_sale/models/website.py:L981-1012` | `_get_checkout_step_values()`: `current_website_checkout_step_href` (**string**), `previous_website_checkout_step` y `next_website_checkout_step` (**records**), `next_website_checkout_step_href` (string) |
| Layout del checkout | `odoo/addons/website_sale/views/templates.xml:L3776` | `checkout_layout` y `show_navigation_button` |
| Boton principal del wizard | `odoo/addons/website_sale/views/templates.xml:L3432` | `name="website_sale_main_button"` → molde del link del Paso 3 |
| Formulario de direccion del core | `odoo/addons/website_sale/controllers/main.py:L1099-1103` | `/shop/address` con `partner_id`, `address_type` y `**query_params` |
| Vuelta al paso tras guardar/descartar | `odoo/addons/website_sale/controllers/main.py:L1234`, `:L1236` y `:L1184` | `callback or '/shop/checkout'` al guardar y `discard_url` al descartar (D12/D45) |
| Carrito anonimo | `odoo/addons/website_sale/models/sale_order.py:L880` | `_is_anonymous_cart()` |
| `description` de la tarea es Html | `odoo/addons/project/models/project_task.py:L153` | Por eso se escapa con `markupsafe.escape()` y se devuelve `Markup` |
| Paso nativo entre el 400 y el 999 | `odoo/addons/website_sale/data/data.xml:L82-85` y `odoo/addons/website_sale/models/website.py:L959-960` | *Extra Info* (`sequence 500`): el Paso 3 **no siempre** es el pago (D44) |
| URL literal de edicion | `odoo/addons/website_sale/views/templates.xml:L3658` | `/shop/address?partner_id={{...}}&address_type=billing` — forma copiada con `delivery` |
| Titulo de la direccion de entrega | `odoo/addons/website_sale/views/templates.xml:L3489` | `delivery_address_list` |
| Guardado de la direccion desde el frontend | `odoo/addons/portal/controllers/portal.py:L594` y `:L598` | `_parse_form_data()`: la whitelist filtra los campos que llegan en el form (D49) |
| Whitelist base | `odoo/addons/portal/models/res_partner.py:L10-19` | `_get_frontend_writable_fields()` (`@api.model`) |
| Override de la whitelist (**no se implementa**) | `odoo/addons/website_sale/models/res_partner.py:L40` | **Suma** campos; sin `@api.model`, aunque la base si |
| Reset por edicion del partner | `odoo/addons/website_sale/models/res_partner.py:L49` y `:L58` | Molde literal del reset de `installation_address_confirmed` |
| Direccion de entrega del pedido | `odoo/addons/sale/models/sale_order.py:L160` y `:L406` | `partner_shipping_id` y su compute (D45) |
| La tarea de FSM va a la direccion de entrega | `enterprise/industry_fsm_sale/models/sale_order.py:L118` y `:L123` | `_get_sale_order_partner_id()` y `_timesheet_create_task_prepare_values()` fuerzan `partner_shipping_id` |
| Recompute del contacto de la tarea | `enterprise/industry_fsm_sale/models/project_task.py:L237` | `_compute_partner_id` condicionado a `account.group_delivery_invoice_address` (RB32) |
| Vals de la tarea (clave `description`) | `odoo/addons/sale_project/models/sale_order_line.py:L252` y `:L273` | Donde se agregan entre calles + notas (D47) |
| Camino alternativo de creacion de tarea | `odoo/addons/sale_project/models/sale_order_line.py:L285` | `_prepare_task_template_vals` — **no** pasa por nuestro override |
| Formato del resumen de direccion | `odoo/odoo/addons/base/models/res_partner.py:L1196` | `_display_address()` |
| `request.cart` en todo el frontend | `odoo/addons/website_sale/models/ir_http.py:L32` | Se setea en `_frontend_pre_dispatch()` → existe en `/appointment/...`: base de D54 |
| Gate de pago del core | `odoo/addons/website_sale/models/sale_order.py:L907` y `:L914-930` | `_is_cart_ready()` / `_check_cart_is_ready_to_be_paid()` — valida **ademas** carrier y direccion |
| Campos obligatorios de la direccion | `odoo/addons/portal/controllers/portal.py:L318` | `_get_mandatory_delivery_address_fields()` |
| Booker de la cita | `enterprise/appointment/models/appointment_type.py:L1217` | `appointment_booker_id = customer` en los vals de la cita |
| Partners de la cita (empleado primero) | `enterprise/appointment/models/appointment_type.py:L1205` | `partners = staff_user.partner_id \| customer` → por que no `partner_ids[:1]` |
| Alta del contacto del visitante | `enterprise/appointment/controllers/appointment.py:L800-824` | El submit crea un contacto nuevo, nunca busca por email |
| Campo `location` de la cita | `odoo/addons/calendar/models/calendar_event.py:L139` | `location = fields.Char('Location', tracking=True)` — destino de D62 |
| El core llena `location` desde el tipo de cita | `enterprise/appointment/models/appointment_type.py:L1225` | `'location': self.location` en `_prepare_calendar_event_values()` → vacio en los tipos de instalacion; si tiene valor, no se pisa (D62) |
| `location` en la ficha de la cita | `odoo/addons/calendar/views/calendar_views.xml:L152` | Visible sin vistas nuevas |
| `location` en la lista de citas | `odoo/addons/calendar/views/calendar_views.xml:L91` | `optional="show"` |
| `location` en el popover del Gantt de Citas | `enterprise/appointment/views/calendar_event_views.xml:L229-231` | Visible sin vistas nuevas |
| `location` en el `.ics` | `odoo/addons/calendar/models/calendar_event.py:L1614` | `event.add('location')` |
| Re-notificacion solo por cambio de `start` | `odoo/addons/calendar/models/calendar_event.py:L855` | Escribir `location` no reenvia invitaciones |
| Version de la carpeta de migracion | `odoo/odoo/modules/migration.py:L154` | `convert_version()` antepone la serie a `1.14.0` |

**Internos del modulo** (archivo + metodo):

| Que | Donde | Por que importa |
|-----|-------|-----------------|
| Consigna de fotos | `views/website_sale_installation_templates.xml` → template `installation_photos_message` | Llamado desde el Paso 2 del checkout y desde `views/appointment_templates.xml` (formulario de la cita) |
| Encabezado de seccion del link | `views/website_sale_installation_templates.xml` → template `installation_form_section` | Solo se pinta en el camino del link: por eso el aviso de D61 va dentro del bloque |
| Bloques de direccion y fotos del formulario | `views/appointment_templates.xml` → template `appointment_form` | Donde van los avisos de D61 |
| Checklist arriba del calendario | `views/appointment_templates.xml` → template `appointment_info` | Apaga el bloque nativo y agrega el de arriba |
| Campo de la consigna | `models/appointment_type.py` → `installation_photos_message` | Html traducible, vacio = texto por defecto |
| Campo en la pestaña Comunicacion | `views/appointment_type_views.xml` → `page name="messages"` | Donde se configura `installation_photos_message` |
| Opt-in del carrier | `views/delivery_carrier_views.xml` → `group name="delivery_details"` | Mismo grupo para `includes_free_batteries` |
| Paso propio y su ruta | `models/website.py` → `INSTALLATION_STEP_HREF` / `_get_allowed_steps_domain()` | Patron defensivo `getattr(request, "cart", None)` que reusa D54 |
| Ruta POST del paso | `controllers/website_sale_installation_appointment.py` → `shop_installation_submit()` | Ramas de fotos y `confirm_installation_address`; fallback `_get_installation_next_step_href()` |
| Valores del paso | `controllers/website_sale_installation_appointment.py` → `_prepare_installation_values()` | `block_states` y la direccion |
| Submit del formulario de la cita | `controllers/website_sale_installation_appointment.py` → `appointment_form_submit()` | Savepoint alrededor de `_save_appointment_installation_address()` (D58/D62) |
| Tarea de FSM de la cita | `models/calendar_event.py` → `_installation_generate_fsm_task()` / `_installation_task_description()` | Molde del idioma de la compañia que reusa `_installation_fill_location()` |
| Confirmacion del pedido | `models/sale_order.py` → `_action_confirm()` | Fotos + ubicacion + portal despues del `super()` |
| JS de las fotos | `static/src/js/installation_photos.js` → `InstallationPhotos` | `selector = "#shop_installation form[data-installation-photos]"` y `button[name='installation_continue']`: contrato con la plantilla |
| Precedente interno: sync idempotente | `extra-addons/odoo_customization_sunra/website_sale_payment_method_price/models/sale_order.py` → `_apply_payment_price_rule()` | Limpia y aplica, nunca apila; guard de contexto `wspmp_skip_recompute` |
| Precedente interno: flag tecnico | `extra-addons/odoo_customization_sunra/website_sale_payment_method_price/models/sale_order_line.py` → `is_payment_method_discount` | Molde del `help` de `is_free_battery_line` |

## Documentacion afectada

| Archivo | Que se actualiza |
|---------|------------------|
| `README.md` del modulo | **Purga de historia** (hallazgos de `history_lint.py --module`: las comparaciones contra el estado anterior del paso de fotos, de los avisos y de la guia de instalaciones); sumar el **aviso de obligatoriedad** del formulario del link (D61) y la **direccion en la Cita** (`location`, link + checkout + backfill al actualizar, D62), con su gotcha: el correo de confirmacion no la muestra (sale al crear la cita) |
| `static/description/index.html` | Misma purga (el bloque de la lista de facturacion, sin etiqueta de version ni comparacion) y los mismos dos agregados |
| `README.md` del repo (`extra-addons/odoo_customization_sunra/README.md`) | Fila del modulo: version `1.14.0` y una linea con "direccion de instalacion en la Cita" |
| `__manifest__.py` | `version` → `1.14.0`; en `description`, una linea: la direccion de instalacion queda como ubicacion de la Cita |
| `i18n/es_419.po` | Terminos nuevos de D61 y la etiqueta "between streets: %s" de D62 |
| Esta spec | `Version` = `1.14.0`; al cerrar, `Estado` → `implemented` y la fila `Depurado` la escribe `history_lint.py --seal` |

## Plan del cambio

> Cambio en curso: purga de historia del modulo + aviso de obligatoriedad en el formulario del link
> (D61) + direccion de instalacion en la Cita (D62) con backfill. La purga va **primero**, con el
> arbol igual a su base. El repo no tiene `.swarm.conf`: no se agregan tests; los existentes tienen
> que seguir en verde (ver *Edge cases*).

| ID | Descripcion | Depende de | Archivos | Cubre |
|----|-------------|------------|----------|-------|
| **T01** | Purga de historia en comentarios y docstrings del modulo: sin narrativa de cambio ("antes…", "ya no…", fechas de reportes del cliente), sin referencias al tracker, sin referencias a tareas `Txx` de planes pasados; el bloque de 28 lineas sobre `billing_address_list` queda en el porque no evidente (una o dos lineas + `D60`). Conservar los gotchas del core anclados y las referencias `Dnn` | — | `static/src/js/installation_photos.js`, `tests/test_calendar_event_mail_company.py`, `tests/test_free_batteries.py`, `views/appointment_templates.xml`, `views/website_sale_installation_templates.xml`, `views/website_sale_templates.xml`, y lo que reporte `history_lint.py --module` en `models/` y `controllers/` | CA62 |
| **T02** | D61: aviso de obligatoriedad en los bloques de direccion (primera linea del bloque, siempre) y de fotos (inmediatamente arriba del input, solo con `installation_min_photos > 0`, numero por `t-out`), `text-danger` + `fa-exclamation-circle` + `o_not_editable`, dentro de cada bloque para que se vea con y sin secciones. Sin JS ni SCSS nuevo | T01 | `views/appointment_templates.xml` | CA56, CA57 |
| **T03** | D62: `calendar.event._installation_fill_location(address)` (solo citas con `location` vacio, idioma de la compañia reasignando `self`, formato de una linea, no escribe si la linea queda vacia) | T01 | `models/calendar_event.py` | CA58, CA59, CA60 |
| **T04** | D62 link: en `_save_appointment_installation_address()`, primer paso `event.sudo()._installation_fill_location(address_vals)`, antes del guard de `appointment_booker_id` (dentro del savepoint existente del llamador) | T03 | `controllers/website_sale_installation_appointment.py` | CA58, CA60 |
| **T05** | D62 checkout: `sale.order._sync_installation_location()` y su llamada en `_action_confirm()` despues del `super()`, junto a `_sync_installation_photos()` | T03 | `models/sale_order.py` | CA59, CA60 |
| **T06** | Backfill idempotente `migrations/1.14.0/post-migrate.py`: tipos de instalacion (`installation_fsm_project_id` o usados por un carrier, `active_test=False`), citas activas con `location` vacio, fuente = `partner_shipping_id` del pedido (no cancelado, el mas viejo) con calle, si no `appointment_booker_id` con calle; `mail_notrack=True`; log de cuantas completo | T03 | `migrations/1.14.0/post-migrate.py` | CA61 |
| **T07** | i18n es_419: "Required: upload at least" → "Obligatorio: subí al menos"; "photo(s) to confirm the appointment." → "foto(s) para poder confirmar la cita."; "Required: street and number, and town." → "Obligatorio: calle y número, y localidad."; "between streets: %s" → "entre calles: %s". Verificar los `msgid` contra un export real del arch (`trans_export`) para no inventar terminos | T02, T03 | `i18n/es_419.po` | CA56, CA57, CA58 |
| **T08** | Documentacion: purga de historia de `README.md` e `index.html` y agregado de D61/D62 (ver *Documentacion afectada*); fila del modulo en el README del repo | T02, T05, T06 | `README.md`, `static/description/index.html`, `../README.md` | CA62 |
| **T09** | Cierre: `version` del manifest → `1.14.0` (+ linea en `description`), `Version` de la spec igual, `Estado` → `implemented`; `-u` del modulo en la base de desarrollo (corre el backfill); `spec_lint.py` y `history_lint.py --module` sin errores; `history_lint.py --seal <modulo>` | T01, T02, T03, T04, T05, T06, T07, T08 | `__manifest__.py`, `specs/website_sale_installation_appointment.md` | CA56, CA57, CA58, CA59, CA60, CA61, CA62 |
