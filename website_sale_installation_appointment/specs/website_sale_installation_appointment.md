# Spec de modulo: website_sale_installation_appointment

| Campo | Valor |
|-------|-------|
| **Modulo** | `website_sale_installation_appointment` |
| **Version** | `1.8.0` (== `version` del `__manifest__.py`, formato `x.x.x`) |
| **Serie Odoo** | `19` (informativa) |
| **Estado** | `verified` |
| **Actualizado** | `2026-09-04` |

> Cliente: **Miluan SRL / Nokey** (eCommerce de cerraduras inteligentes, `nokey.odoo.com`).
> Repo: `extra-addons/sunrasa/odoo_customization_sunra`. Licencia LGPL-3, autor Sunra.
> `depends`: `website_sale`, `delivery`, `website_appointment_sale`, `sale_project`.
>
> **Nota de version**: el modulo esta en `1.8.0` — la feature de pilas incluidas se suma sobre
> el `1.7.0` del otro dev (textos del cliente configurables desde el tipo de cita, commit
> `e5526ae`). El `version` del manifest y la `Version` de esta spec estan sincronizados.

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
| D3 | ¿Como aparece/desaparece el paso "Instalacion" del checkout? | Filtrando el dominio de pasos (`website._get_allowed_steps_domain()`), no con vistas condicionales: el core calcula solo el paso siguiente/anterior. |
| D4 | ¿Que valida el upload publico de fotos? | Mimetype **real del contenido** (no el declarado), 10 MB por archivo, 10 fotos por pedido. Minimo configurable por carrier (`installation_min_photos`; 0 = opcional). |
| D5 | ¿Se puede pagar sin agendar / sin fotos? | No: gate en `_check_cart_is_ready_to_be_paid()` + `_get_shop_payment_errors()`, y `shop_payment()` redirige al paso en vez de mostrar el error. |
| D6 | ¿Donde ve la cuadrilla las fotos? | Se copian al chatter de la **Cita** y de la **tarea de FSM** despues de `super()._action_confirm()`. |
| D7 | ¿El cliente de una instalacion recibe portal? | Si, **incondicional** para pedidos con `installation_required`, via el `portal.wizard` nativo. Idempotente (usuario activo o archivado → no-op con nota en el chatter). Nunca rompe la confirmacion (savepoint + log). |
| D8 | ¿Y las citas agendadas FUERA del eCommerce (link compartido)? | `appointment.type.installation_fsm_project_id` → la tarea de FSM la crea este modulo en `calendar.event.create()`, y se sincroniza al reprogramar/cancelar/desarchivar. |
| D9 | ¿Como se evita que el cliente escriba cualquier cosa en el formulario de la cita? | Campo propio `appointment.question.answer_format` (libre/entero/numero/telefono/documento): emite `type`/`inputmode`/`pattern` reales y **revalida en el servidor**. |
| D10 | ¿Donde se muestran los diagramas de medidas? | Dentro del bucle de preguntas, justo antes de la pregunta marcada con `appointment.question.installation_measure_guide` (un solo lugar sirve para los dos caminos). |
| D11 | ¿Una sola instalacion por pedido? | Si: reagendar reemplaza la reserva anterior (`_remove_previous_installation_bookings`). |
| D12 | ¿Nombre de la empresa en el checkout? | Se saca `#company_name_div` heredando `website_sale.address_form_fields` (NO desactivando `address_b2b`, que se lleva la Responsabilidad de ARCA de `l10n_ar`). |
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
| D31 | ¿Como se avisa en el checkout que las pilas van incluidas? | Con **dos cambios separables**: (a) el `<li>` historico de las pilas recibe `t-if="not order.carrier_id.includes_free_batteries"` **como atributo** —no se toca su **texto**, asi que el `msgid` traducido queda intacto—, para que el default del modulo no siga pidiendo pilas que van gratis; y (b) el **aviso nuevo** va en un bloque propio **fuera** del par `t-if`/`t-else` (D41), para que se vea tambien cuando el funcional cargo `message_intro`. El argumento de la "rama muerta" aplica **al aviso** (por eso va afuera), **no** al `<li>`: condicionarlo sigue siendo necesario porque el `t-else` es lo que ve todo tipo de cita con `message_intro` vacio. |
| D32 | ¿Sobre que estados actua la sincronizacion? | `[ASUNCION]` Solo `draft`/`sent`. En un pedido confirmado, ajustar/borrar lineas es trabajo del backoffice (y chocaria con `_unlink_except_confirmed`). |
| D33 | ¿El flag se copia al duplicar el pedido? | **Si**: `is_free_battery_line` va **sin `copy=`** (default `True`). El molde correcto es `is_delivery` del core, que tampoco lo declara (`odoo/addons/delivery/models/sale_order_line.py:L9`). Con `copy=False` el duplicado quedaria con la linea a $0 **sin el flag** → el primer recompute la llevaria a precio de tarifa y el sync, al no reconocerla, **crearia una segunda linea gratis** (doble cantidad de pilas, la mitad facturada). ⚠️ El `copy=False` de `is_payment_method_discount` del modulo hermano **NO es el molde**: esa linea es un descuento atado al medio de pago que se re-elige en el checkout; esta es una linea de producto que se entrega. No unificar los dos flags. |
| D34 | ¿Que pasa con el control de stock del eCommerce? | Se override-ea `_check_availability()` → `True` para la linea gratis. `website_sale_stock` es `auto_install` y esta **instalado** en la base: su `_check_cart_is_ready_to_be_paid` tira `ValidationError` si una linea storable sin *Sell when Out-of-Stock* supera el stock libre. Con *Pilas AA* (tmpl 411) ya en `allow_out_of_stock_order = false` y **stock 0**, el cliente quedaria **sin poder pagar** por un producto que no eligio y que no puede borrar (D20/D21 lo auto-curan): checkout muerto. No se resuelve "por configuracion" — los datos reales ya contradicen ese requisito. **Por que el override no queda sombreado**: `website_sale_stock` **no** esta en nuestro `depends` (agregarlo arrastraria `stock`: footprint peor), pero el orden de carga es `(phase, depth, order_name)` con `depth` = camino mas largo a `base` (`odoo/odoo/modules/module_graph.py:L175`, `:L225`): dependemos de `website_appointment_sale` → `website_sale`, asi que `depth(nuestro) >= depth(website_sale)+2` mientras `depth(website_sale_stock) = depth(website_sale)+1` → **cargamos despues y ganamos el MRO**. ⚠️ Riesgo latente: si un cambio de `depends` empata la profundidad, el desempate es alfabetico (`website_sale_installation_appointment` < `website_sale_stock`) y quedariamos **primeros**, con el override convertido en **codigo muerto** y el checkout muerto en silencio. **CA32 en T11 es el tripwire** de esa regresion. |
| D35 | ¿El `name` de la linea nombra el metodo de envio? | **No.** Se usa un texto sin el nombre del carrier (*"Included with your shipping method — no extra charge."*) para no tener estado que sincronizar: el sync solo escribe `product_uom_qty`, asi que al pasar a **otro** envio que tambien incluye pilas (el futuro que pide D13) el nombre horneado quedaria mintiendo en el carrito **y en la factura**. Ademas la descripcion se arma en el **idioma del cliente**. |
| D36 | ¿El sync puede tocar lineas ya facturadas o entregadas? | **No**: se excluyen del `write` y del `unlink` las lineas con `qty_invoiced` o `qty_delivered` distintos de 0. `state in ('draft','sent')` **no** implica "nada facturado": un pedido facturado que el backoffice devuelve a presupuesto ("Set to Quotation") vuelve a `draft` con `qty_invoiced != 0`, y `_check_line_unlink` solo bloquea en `state == 'sale'`. Mismo criterio que `_remove_delivery_line` del core. |
| D37 | ¿Que engaches cubren el backend? | Tres, complementarios: el `@api.onchange` (carga interactiva), **`set_delivery_line()`** (el boton **Add shipping** → wizard `choose.delivery.carrier` escribe por `write`, los onchange **no** corren) y `action_confirm()` (red final). `_set_delivery_method()` **no se reemplaza**: es el unico que cubre el camino de **quitar** el envio, donde `set_delivery_line` no se llama. |
| D38 | ¿Y si la pila configurada es de otra compañia? | `free_battery_product_id` lleva `check_company=True` + domain de compañia (la base tiene 2 compañias), y el agregado **saltea** el producto incompatible en vez de romper. `product_id` de `sale.order.line` es `check_company=True` y el `sudo()` del sync **no** exime de `_check_company`: sin esto, una mala configuracion daria **error 500 en cada request del carrito** del visitante publico. |
| D39 | ¿Cantidades no positivas? | Solo se acumulan lineas con `product_uom_qty > 0`, y los `needs` que quedan en `<= 0` se descartan (caen en `to_unlink`). Un pedido con la cerradura en `-1` (nota de credito preparada como pedido negativo) generaria una linea de pilas **negativa** → `stock_delivery` crearia un movimiento de **devolucion** de pilas que el cliente nunca entrego; y `+1 / -1` dejaria una linea en 0 en el carrito y en el PDF. |
| D41 | ¿Donde se pinta el aviso de "pilas incluidas"? | **Fuera** del par `t-if`/`t-else` del checklist, como bloque propio inmediatamente despues, condicionado **solo** a `order.carrier_id.includes_free_batteries`. Rationale: la logica **condicional a datos** tiene que vivir en la plantilla —un campo de texto configurable no puede expresar una condicion—, mientras los textos **estaticos** del cliente van en campos (criterio de D42). **Los dos criterios conviven**: prosa estatica → campo; texto que depende del estado del pedido → plantilla. |
| D42 | ¿Por que los textos del cliente van en campos y no en las plantillas? *(current-state, decision del commit `e5526ae`)* | Porque **editar una plantilla desde el editor web crea una copia COW por sitio que deja de recibir las actualizaciones del modulo**: asi se vacio la guia de fotos en produccion, en los dos flujos, sin que ningun deploy la arreglara. El checklist sale del campo **nativo** `message_intro` y la consigna de fotos del campo nuevo `installation_photos_message`; vacios → el texto por defecto del modulo. Van **por tipo de cita** a proposito: el del eCommerce cobra online y el del link cobra el dia del turno, asi que las condiciones difieren. |
| D40 | ¿La cantidad convierte UoM de la **cerradura**? | `[ASUNCION]` **No**: `free_battery_qty * line.product_uom_qty` se toma tal cual, porque hoy las cerraduras se venden en **Units**. Si mañana una se vende en "Caja de 6", 1 caja pediria 1 paquete en vez de 6. Fix conocido de una linea: `line.product_uom_id._compute_quantity(line.product_uom_qty, line.product_id.uom_id)` (molde: `odoo/addons/delivery/models/sale_order_line.py:L24`). Las cerraduras **dentro de un combo** si aportan pilas (deseable), pero configurar pilas en la plantilla del combo **y** en el item las contaria dos veces. |

## Alcance

### Incluye

**Envio con instalacion (existente)**
- Opt-in por metodo de envio (tipo de cita + fotos minimas) y campos espejo en el pedido.
- Paso de checkout condicional `/shop/installation` (checklist, agenda, guia y subida de fotos).
- Gate de pago (sin cita o sin fotos no se paga) con redireccion al paso.
- Copia de las fotos a la Cita y a la tarea de FSM; titulo estable de la tarea.
- Invitacion automatica al portal al confirmar.
- Formato de respuesta validado en las preguntas de cita (cliente + servidor) y guia de medidas junto a la pregunta.
- **Textos del cliente configurables por tipo de cita** (D42): checklist "antes de agendar" desde el campo nativo `message_intro` y consigna de las fotos desde `installation_photos_message`, con el texto por defecto del modulo como respaldo, en los dos caminos; y en el tipo de cita del link, el checklist se sube arriba del calendario.
- Camino sin eCommerce: cita por link compartido → tarea de FSM creada/sincronizada por el modulo.
- Paso de checkout como dato por website (`post_init_hook` / `uninstall_hook`).

**Pilas incluidas sin costo (feature del *Plan del cambio en curso*)**
- Configuracion por producto (`free_battery_product_id`, `free_battery_qty` en la UoM del producto de pila) y opt-in por metodo de envio (`includes_free_batteries`).
- Generacion automatica, agregada por producto de pila, de la linea de pedido en **$0**, sincronizada de forma idempotente en el carrito web, en el backend (onchange) y al confirmar.
- Defensa del precio 0 y del descuento 0 en todos los caminos de recomputo del core.
- Linea visible pero no editable en el carrito, con auto-curacion si el cliente la manipula por el endpoint.
- Texto del checkout condicional (pilas incluidas vs. pilas a cargo del cliente).
- Suite inicial de tests de los flujos troncales de esta feature.

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
- **Tocar `migrations/1.3.0/`**: ver *Notas de implementacion* (deuda conocida, declarada fuera de alcance por el usuario).

## Modelos

### Nuevos

No aplica: el modulo no define modelos propios, solo extiende modelos de `odoo/` y `enterprise/`.

### Extendidos

| Modelo | `_inherit` | Que se agrega |
|--------|-----------|--------------|
| `delivery.carrier` | `delivery.carrier` | Opt-in de instalacion (tipo de cita + fotos minimas) y **opt-in de pilas incluidas** (`includes_free_batteries`) + constrains de configuracion |
| `product.template` | `product.template` | **Configuracion de pilas del producto** (`free_battery_product_id`, `free_battery_qty`) + constrain de configuracion |
| `sale.order` | `sale.order` | Campos espejo de la instalacion, gate de pago, copia de fotos, invitacion al portal; **agregacion y sincronizacion de las lineas de pilas** + engaches de carrito/backend/confirmacion |
| `sale.order.line` | `sale.order.line` | Deteccion de la linea de la reserva y titulo de la tarea de FSM; **flag `is_free_battery_line`** y las 5 defensas de precio/edicion |
| `appointment.type` | `appointment.type` | Proyecto de FSM para citas fuera del eCommerce, pedido de fotos y minimo, y **consigna de las fotos configurable** (`installation_photos_message`) |
| `appointment.question` | `appointment.question` | Formato de respuesta validado y marca de la guia de medidas |
| `calendar.booking` | `calendar.booking` | Aclaracion en la descripcion de la linea ("incluido en el metodo de envio") |
| `calendar.event` | `calendar.event` | Tarea de FSM de la cita agendada fuera del eCommerce + sincronizacion y fotos |
| `website` | `website` | Paso de checkout condicional |

**Controllers** (`controllers/website_sale_installation_appointment.py`): `WebsiteSaleInstallation(WebsiteSale)`
(paso del checkout + overrides de pago) y `AppointmentInstallation(WebsiteAppointmentSale)` (validacion de
respuestas, fotos y vuelta al paso). No cambian con esta feature.

## Campos

| Modelo | Campo | Tipo | String | Requerido | Default | Restricciones |
|--------|-------|------|--------|-----------|---------|--------------|
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

### Existentes (no cambian con esta feature)

#### `sale.order`
- `_compute_installation_required()` — `@api.depends('carrier_id.installation_appointment_type_id')`; `installation_required = bool(tipo de cita del carrier)`.
- `_compute_installation_booking_id()` / `_compute_installation_event_id()` — primera reserva / primera cita de las lineas cuyo `appointment_type_id` es el del carrier.
- `_compute_installation_photo_count()` — `len(installation_photo_ids)`.
- `_is_installation_required()` — `any(...)` sobre el recordset (lo usan controllers y templates).
- `_is_installation_scheduled()` — `bool(booking or event)`.
- `_get_installation_errors()` — lista de mensajes: falta agendar / faltan N fotos. Devuelve `[]` si el pedido no requiere instalacion.
- `_check_cart_is_ready_to_be_paid()` — **override**: `ValidationError` con los errores de instalacion antes del `super()`.
- `_action_confirm()` — **override**: `super()` primero (el nativo crea Cita y tarea) y despues `_sync_installation_photos()` + `_grant_portal_access_after_installation_sale()`. **No se toca en esta feature** (ver D27).
- `_sync_installation_photos()` / `_post_installation_photos(target)` — copian las fotos al chatter de la Cita y de las tareas (`sudo`, adjuntos copiados sin dueño).
- `_grant_portal_access_after_installation_sale()` — invitacion nativa al portal, idempotente, aislada en `savepoint`, con nota en el chatter ante cualquier problema.

#### `sale.order.line`
- `_is_installation_booking_line()` — la linea es la reserva de la instalacion del carrier del pedido.
- `_timesheet_create_task_prepare_values(project)` — **override** de `sale_project`: `name = "<pedido> - <tipo de cita>"`.

#### `delivery.carrier`
- `_check_installation_appointment_type()` — `@api.constrains`: el tipo de cita debe tener paso de pago + producto, y ese producto generar tarea o tener precio.
- `_check_installation_min_photos()` — `@api.constrains`: `>= 0`.

#### `appointment.question`
- `_effective_answer_format()`, `_answer_input_attrs()`, `_validate_answer(value)` — formato efectivo, atributos HTML reales y validacion de servidor (entero/decimal/telefono/DNI-CUIT via `stdnum.ar`).

#### `calendar.event`
- `create()` / `write()` — **overrides**: generan la tarea de FSM de las citas con `installation_fsm_project_id` (aislado en savepoint) y la mantienen en linea al reprogramar/cancelar/desarchivar.
- `_installation_generate_fsm_task()`, `_installation_cancel_task()`, `_installation_restore_task()`, `_installation_post_photos(attachments)`.

#### `calendar.booking`
- `_get_description()` — **override**: agrega "Included in the … shipping method — no extra charge." a la descripcion de la linea de la reserva.

#### `website`
- `_get_allowed_steps_domain()` — **override**: saca `/shop/installation` del dominio cuando el carrito no requiere instalacion.

#### Controllers
- `shop_installation()` / `shop_installation_submit()` / `shop_installation_photo_remove()` — paso del checkout y endpoints publicos de fotos.
- `shop_payment()` / `_get_shop_payment_errors(order)` — **overrides**: redireccion al paso y errores de pago.
- `appointment_type_id_form()` / `appointment_form_submit()` / `_get_customer_partner()` / `_redirect_to_payment()` — **overrides** del flujo de citas (errores de formato, fotos, partner del carrito, vuelta al paso).
- `create_installation_photos(uploads, available_slots, res_model, res_id)` — helper compartido de validacion/creacion de adjuntos.

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

## Vistas

### `delivery.carrier` form (`view_delivery_carrier_form`, hereda `delivery.view_delivery_carrier_form`)
- Dentro del grupo `name="delivery_details"`: `installation_appointment_type_id`, `installation_min_photos` (`invisible="not installation_appointment_type_id"`) y **`includes_free_batteries`** (nuevo, mismo grupo — es donde el funcional ya configura este metodo de envio).

### `product.template` form (`product_template_view_form`, hereda `product.product_template_form_view`) — **nueva vista**
- Dentro del grupo `name="upsell"` ("Upsell & Cross-Sell") de la pestaña **Sales** (`odoo/addons/product/views/product_views.xml:L143`), junto a `optional_product_ids` (`odoo/addons/sale/views/product_template_views.xml:L12`) y `accessory_product_ids` (`odoo/addons/website_sale/views/product_views.xml:L169`):
  - `free_battery_product_id`, con `domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]"` (misma forma que el vecino `optional_product_ids`, `odoo/addons/sale/views/product_template_views.xml:L16`; la auto-referencia la cubre el constrain, no el domain, porque el campo apunta a `product.product` y el `id` del form es el del template).
  - `free_battery_qty`, seguido de **`free_battery_uom_name`** (`readonly`): la UoM real del producto de pila queda **a la derecha del numero**, para que `1` se lea como "un paquete de 4" y nunca como "una pila" (D15, riesgo funcional #1). **Mecanismo unico**: es un campo related del modelo, no un label estatico ni un `t` auxiliar. **Implementacion real** (correccion post-review sobre la spec original, que decia `nolabel="1"` en un solo `<field>`): `<label for="free_battery_qty" invisible="not free_battery_product_id"/>` + `<div class="o_row" invisible="not free_battery_product_id"><field name="free_battery_qty"/><field name="free_battery_uom_name" readonly="1" class="oe_inline"/></div>` — el patron canonico de Odoo para pegar una UoM al numero (molde: `is_storable`/`qty_available` + `uom_name` en `odoo/addons/stock/views/product_views.xml:L182-199`), mejor que la alternativa literal de la spec.

### `sale.order` form (`view_order_form`, hereda `sale.view_order_form`)
- `installation_required` invisible (para las condiciones), y pestaña **Installation** (`invisible="not installation_required"`) con tipo de cita, reserva, cita y las fotos (`widget="many2many_binary"`).
- La linea de pilas **no** agrega nada a esta vista: es una linea de pedido normal con el flag tecnico oculto.

### `appointment.type` form / `appointment.question` form y list
- Tirador de `sequence` y `answer_format` en la lista de preguntas del tipo de cita; `installation_fsm_project_id`, `installation_request_photos`, `installation_min_photos` en `group name="right_details"`.
- `installation_photos_message` en la pestaña **Comunicacion** (`page name="messages"`), despues de `message_confirmation` y con su separador: es donde el funcional ya entra a editar los mensajes del cliente. **Sin `invisible`**: el tipo del eCommerce pide las fotos en el paso del checkout (tiene `installation_request_photos` apagado) y necesita el texto igual.
- `answer_format` (oculto para `select`/`radio`/`checkbox`) e `installation_measure_guide` en la ficha de la pregunta, y en su lista.

### Templates del checkout / carrito
- `installation` (`/shop/installation`): encabezado; **checklist** con el par `t-if="not is_html_empty(appointment_type.message_intro)"` (campo **nativo**, editable en linea) / `t-else` con el checklist por defecto del modulo, que es donde vive el `<li>` historico de las pilas; avisos/errores; tarjeta **1. Pick the day and time**; tarjeta **2. Upload photos of the site** (con `installation_photos_message` y `installation_photo_examples`); y navegacion.
  **Cambio de esta feature (D31 + D41), dos partes**:
  1. Al `<li>` historico de las pilas (`:L122`) se le agrega **`t-if="not order.carrier_id.includes_free_batteries"`** como **atributo**: si el envio las incluye, ese punto del checklist por defecto no se pinta (si no, el cliente lee "necesitas 4 u 8 pilas" y dos centimetros mas abajo que van incluidas → compra pilas que ya le mandan gratis y el diferencial comercial se lee como un error de la tienda). `order` esta en scope: el controller lo pasa explicito (`extra-addons/sunrasa/odoo_customization_sunra/website_sale_installation_appointment/controllers/website_sale_installation_appointment.py:L179`).
  2. El **aviso** ("las pilas van incluidas sin cargo") va en un **bloque propio con `t-if="order.carrier_id.includes_free_batteries"`**, ubicado **despues del cierre del `<div t-else="">`** — nunca entre el `t-if` y el `t-else` (ahi QWeb rompe al cargar la vista). Asi se ve **tambien** cuando el funcional cargo `message_intro` y el `t-else` no se pinta (D41).
  - El div del aviso lleva **`o_not_editable`** en su clase: es texto plano en una pagina editable y, si alguien lo toca desde el editor web, Odoo crea la **copia COW por sitio** del template `installation` y el aviso queda congelado/borrado para ese sitio sin que ningun deploy lo reponga — exactamente el incidente que narra D42. Precedente: `odoo/addons/website_sale_stock/views/website_sale_stock_templates.xml:L15`.
  - Conviene que el aviso sea **un solo nodo de texto** (no `<h6>` + `<p>`): asi el `.po` recibe **exactamente una** entrada nueva.
  ⚠️ **El `msgid` del `<li>` no cambia**: agregar un atributo no altera su nodo de texto (la extraccion de `arch_db` solo saltea `script`/`style`/`title`, `odoo/odoo/tools/translate.py:L59`), asi que la entrada de `i18n/es_419.po:L546` queda intacta y el `.po` solo **suma** la del aviso.
- `installation_photos_message`: template del commit `e5526ae`, con el patron `t-if="not is_html_empty(...)"` / `t-else` (texto por defecto del modulo), llamado con `t-call` desde los **dos** caminos — el paso del checkout y el formulario de la cita del link.
- `installation_measure_guide` / `installation_photo_examples`: templates reutilizables llamados con `t-call` desde el paso y desde el formulario de la cita.
- `appointment_form` (hereda `appointment.appointment_form`): errores de formato, `enctype` multipart, guia de medidas junto a la pregunta marcada, input de fotos (con `installation_photos_message` arriba) e inputs con `type`/`pattern` reales.
- `appointment_info` (hereda `appointment.appointment_info`): en el tipo de cita **del link** (`installation_fsm_project_id`) el checklist de `message_intro` **sube arriba del calendario** y se apaga el bloque nativo del final, para que se lea antes de elegir el turno. El bloque nuevo va **fuera** de `o_appointment_info_main` (que es `o_not_editable`) para que el `t-field` siga siendo editable en linea.
- `address_form_fields` / `delivery_address_list`: sin "Nombre de la empresa"; titulo "Installation address" cuando el pedido requiere instalacion.
- **Nuevo en `views/website_sale_templates.xml`**: heredar `website_sale.cart_lines` para ocultar el **boton Eliminar** de la linea gratis, en los dos nodos (los dos tienen `name=` estable, y la variable del bucle es `line` — `odoo/addons/website_sale/views/templates.xml:L2880`):
  - desktop: `//div[@name='o_wsale_cart_line_button_container']//a[hasclass('js_delete_product')]` → `t-if="not line.is_free_battery_line"` (`:L2954`)
  - mobile: `//div[@name='o_wsale_cart_line_button_container_mobile']//button[hasclass('js_delete_product')]` → `t-if="not line.is_free_battery_line"` (`:L2974`)
  - ⚠️ **No** ocultar los contenedores completos: el de desktop tambien contiene el selector de cantidad cuando la linea es de combo.
  - El **selector de cantidad** y el **link al producto** no necesitan xpath: los cubre `_is_sellable()`.

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

**Pilas incluidas (feature en curso)**
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
20. **RB20**: El checklist del paso de instalacion dice que las pilas **van incluidas** cuando el metodo de envio las incluye, y mantiene el texto historico ("necesitas 4 u 8 pilas el dia de la instalacion") cuando no.
21. **RB21**: **Duplicar** un pedido con pilas gratis produce **una sola** linea de pilas, a 0 y con el flag puesto (el flag se copia — D33).
22. **RB22**: La linea gratis **nunca** bloquea el pago por stock, aunque el producto de pila tenga *Sell when Out-of-Stock* apagado y stock 0 (D34).
23. **RB23**: El sync **no** toca lineas de pilas con cantidad facturada o entregada distinta de 0 (D36), y **no** genera lineas con cantidad `<= 0` (D39).
24. **RB24**: Una pila configurada en una compañia incompatible con el pedido **se saltea**: no se crea la linea y el carrito **no se rompe** (D38).

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
- **`message_intro` que contradice el aviso** (config, no codigo): si el funcional deja en `message_intro` el punto "tenes que tener 4 u 8 pilas" y el carrier **incluye** las pilas, el cliente lee las dos cosas: el checklist configurado pidiendoselas y el aviso diciendo que van incluidas. El aviso **no puede** saber que dice el texto libre del campo; se resuelve como **requisito de configuracion** (T12 lo documenta): con carrier que incluye pilas, ese punto sale de `message_intro`.
- **`invoice_policy` del producto de pila**: con `'order'` (lo que ya tienen 411/412) la linea llega a la factura, que es la razon de ser de D28. Si alguien lo pasa a `'delivery'` con stock 0, la linea no se facturaria.
- **Multi-compañia / multi-sitio**: la configuracion es por producto y por metodo de envio, que ya son registros por compañia/sitio; el modulo no agrega logica de compañia propia.

## Criterios de aceptacion

> `CA01`–`CA13` y `CA35`–`CA36`: comportamiento **ya implementado** del modulo (current-state; el plan
> en curso no los vuelve a cubrir — `CA35`/`CA36` vienen del commit `e5526ae` de otro dev).
> `CA14`–`CA34` y `CA37`: feature de **pilas incluidas** (los cubre el plan del cambio, salvo `CA30`).
> `CA37` queda fuera de orden numerico porque `CA35`/`CA36` entraron con el rebase sobre `e5526ae`.

**Envio con instalacion (existente)**
- [ ] **CA01**: Carrito con un producto etiquetado como instalable → el metodo *Envio con instalacion* aparece en el checkout.
- [ ] **CA02**: Elegir ese metodo → el paso *Instalacion* aparece en el wizard, con checklist, agenda y guia de fotos.
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

**Textos configurables (current-state, commit `e5526ae` — sin tarea en el plan)**
- [ ] **CA35**: Cargar `message_intro` en el tipo de cita → ese texto reemplaza al checklist por defecto en el paso del checkout y (en el tipo del link) se ve **arriba del calendario**, no al final; vaciarlo → vuelve el checklist por defecto del modulo.
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
  ⚠️ **Como validarlo**: con la configuracion real (tmpl 411 storable, *Sell when Out-of-Stock* apagado, **stock 0**) el alta **no crea ninguna linea** y sale el warning nativo *"… has not been added to your cart since it is not available"* — `website_sale_stock._verify_updated_quantity` (`odoo/addons/website_sale_stock/models/sale_order.py:L22`) calcula `free_qty = 0` y `_get_cart_qty` (`:L102`) **cuenta tambien nuestra linea gratis** (`_get_common_product_lines`, `:L120`, no filtra el flag) → `allowed_line_qty <= 0`, y `_cart_find_product_line` nunca entra en juego. Eso es comportamiento **nativo y correcto** (no se vende lo que no hay), ajeno a esta feature: **CA21 y su test en T11 se validan con stock cargado o con *Sell when Out-of-Stock* activado**.
- [ ] **CA22**: "Volver a pedir" un pedido que tenia pilas gratis → la pila **no** se re-agrega al carrito nuevo.
- [ ] **CA23**: Armar el pedido en el **backend** (sin eCommerce): (a) al cargar lineas y metodo de envio a mano, la linea de pilas aparece por el onchange; (b) asignando el envio con el boton **Add shipping** (wizard `choose.delivery.carrier`, que escribe por `write` y **no** dispara onchange), la linea aparece igual — de modo que el **presupuesto en PDF ya la incluye**; (c) si ninguno de los dos se disparo, al confirmar queda sincronizada.
- [ ] **CA24**: Borrar la linea gratis (o cambiarle la cantidad) por `/shop/cart/update` con su `line_id` real → queda **re-creada/ajustada en el mismo request**.
- [ ] **CA25**: Cerradura **sin** pilas configuradas, o carrier sin el flag → **no** se crea ninguna linea (no-op), y las lineas gratis previas se limpian.
- [ ] **CA26**: Configuracion invalida (producto sin cantidad, cantidad sin producto, cantidad negativa, producto que es su propia pila) → `ValidationError` al guardar el producto.
- [ ] **CA27**: En el carrito, la linea gratis **se ve** pero no ofrece selector de cantidad editable, ni link al producto, ni boton **Eliminar** (desktop y mobile).
- [ ] **CA28**: **Publicar** el producto de pila (`is_published = True`) **no** habilita el selector de cantidad ni el link de la linea gratis (regresion que previene el override de `_is_sellable()`).
- [ ] **CA29**: En el paso `/shop/installation`, con un carrier que incluye pilas se ve el **aviso de pilas incluidas**, y con uno que no, no se ve. El aviso aparece **tambien cuando `message_intro` esta cargado** (o sea, cuando el checklist por defecto del modulo no se renderiza) — ese es justo el caso que el diseño anterior fallaba.
- [ ] **CA37**: Con `message_intro` **vacio** —o cargado pero **sin traducir al idioma del visitante**— y un carrier que incluye pilas, el `<li>` historico ("You'll need 4 or 8 AA/AAA batteries…") **NO se muestra**: no puede convivir con el aviso de que van incluidas. ⚠️ Verificar **en ingles y en un tipo de cita nuevo**: `is_html_empty()` evalua el **idioma activo**, y en la base el tipo 1 tiene `message_intro` con `en_US: ""` pero `es_AR` cargado (el tipo 3 en NULL), asi que un QA manual **solo en es_AR pasaria en verde con el defecto puesto**. El `msgid` de la traduccion no cambia (agregar un atributo no altera el nodo de texto).
- [ ] **CA30**: La **factura** del pedido muestra la linea de pilas a 0, con la descripcion que aclara que va incluida (requiere `invoice_policy = 'order'` en el producto de pila — ya es el caso en los tmpl 411/412). **Sin tarea propia en el plan**: no necesita codigo nuevo, es consecuencia de D28 + esa configuracion; se verifica a mano.
- [ ] **CA31**: **Duplicar** un pedido que tiene la linea de pilas gratis → el duplicado queda con **UNA** linea de pilas, a **$0** y **con el flag**; al confirmarlo no se crea una segunda ni se cobra ninguna.
- [ ] **CA32**: Producto de pila con *Sell when Out-of-Stock* **apagado** y **stock 0** (configuracion real de tmpl 411) → el carrito **se puede pagar**: `_check_cart_is_ready_to_be_paid` no tira `ValidationError` por la linea gratis.
- [ ] **CA33**: Pedido con la cerradura en cantidad **`-1`** o con `+1` y `-1` que se cancelan → **no** se crea linea de pilas negativa ni en 0 (y si habia una, se borra).
- [ ] **CA34**: Cerradura de una compañia con una pila configurada en **otra** compañia → el carrito **no rompe** (sin `UserError`/500): la pila se saltea y no se crea la linea.

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
| Precedente interno: sync idempotente | `extra-addons/sunrasa/odoo_customization_sunra/website_sale_payment_method_price/models/sale_order.py:L110` | `_apply_payment_price_rule()` — limpia y aplica, nunca apila; `sudo()` comentado; guard de contexto `wspmp_skip_recompute` (`:L146`) |
| Precedente interno: flag tecnico | `extra-addons/sunrasa/odoo_customization_sunra/website_sale_payment_method_price/models/sale_order_line.py:L8` | `is_payment_method_discount` — molde del `help` de `is_free_battery_line` ("without guessing by product") |
| Campo nativo del checklist | `enterprise/appointment/models/appointment_type.py:L147` | `message_intro` (Html, `translate=True`, `sanitize_attributes=False`) — el que usa el modulo para el checklist configurable (D42) |
| Donde el core pinta `message_intro` | `enterprise/appointment/views/appointment_templates_appointments.xml:L233` | Al final de la pagina del turno, bajo "Descripcion" → por eso el modulo lo sube arriba del calendario |
| Template y bloque no editable | `enterprise/appointment/views/appointment_templates_appointments.xml:L75` y `:L92` | `appointment_info` y `o_appointment_info_main` (`o_not_editable`): el bloque nuevo va **fuera** para seguir siendo editable en linea |
| Helper del patron campo-vacio | `odoo/odoo/tools/mail.py:L490` | `is_html_empty()` — el `t-if`/`t-else` de los textos configurables |
| Traduccion existente (intacta) | `extra-addons/sunrasa/odoo_customization_sunra/website_sale_installation_appointment/i18n/es_419.po:L547` | El `msgid` del `<li>` de las pilas (con su `\n` + 28 espacios) **no se modifica**: el aviso nuevo es una entrada aparte |
| Par `t-if`/`t-else` del checklist | `extra-addons/sunrasa/odoo_customization_sunra/website_sale_installation_appointment/views/website_sale_installation_templates.xml:L117` | El aviso de pilas va **despues** de este bloque, fuera del par (D41) |
| El `<li>` historico que NO se toca | `extra-addons/sunrasa/odoo_customization_sunra/website_sale_installation_appointment/views/website_sale_installation_templates.xml:L123` | Vive dentro del `t-else` → solo se pinta si `message_intro` esta vacio: rama muerta para el aviso |
| Template de la consigna de fotos | `extra-addons/sunrasa/odoo_customization_sunra/website_sale_installation_appointment/views/website_sale_installation_templates.xml:L41` | `installation_photos_message` (current-state), llamado desde `:L183` y desde `views/appointment_templates.xml:L37` |
| Campo nuevo del otro dev | `extra-addons/sunrasa/odoo_customization_sunra/website_sale_installation_appointment/models/appointment_type.py:L31` | `installation_photos_message` — Html traducible, vacio = texto por defecto |
| Checklist arriba del calendario | `extra-addons/sunrasa/odoo_customization_sunra/website_sale_installation_appointment/views/appointment_templates.xml:L72` | Override `appointment_info`: apaga el bloque nativo (`:L78`) y agrega el de arriba (`:L82`) |
| Campo en la pestaña Comunicacion | `extra-addons/sunrasa/odoo_customization_sunra/website_sale_installation_appointment/views/appointment_type_views.xml:L33` | Donde se configura `installation_photos_message` |
| Donde cuelga el opt-in del carrier | `extra-addons/sunrasa/odoo_customization_sunra/website_sale_installation_appointment/views/delivery_carrier_views.xml:L9` | `group name="delivery_details"` — mismo grupo para `includes_free_batteries` |

## Documentacion afectada

| Archivo | Accion | Que reflejar |
|---------|--------|-------------|
| `website_sale_installation_appointment/README.md` | actualizar | (a) **corregir el drift de version**: la linea 7 dice "Versión: 1.2.0" (el commit `e5526ae` agrego secciones pero no la toco) y el modulo va a `1.8.0`; (b) tabla de campos: `includes_free_batteries`, `free_battery_product_id`, `free_battery_qty`, `is_free_battery_line`; (c) seccion nueva "Pilas incluidas sin costo" (configuracion en el producto **en la UoM del producto de pila**, opt-in del metodo de envio, linea a 0 agregada por producto, linea visible pero no editable, aparece en la factura); (d) *Configuracion*: paso para configurar las pilas, **requisito `invoice_policy = 'order'`** en el producto de pila (con `'delivery'` + stock 0 la linea no se facturaria y se perderia la constancia de entrega que justifica D28) y aviso de aprovisionar stock; (e) *Gotchas*: la UoM ("1 = un paquete de 4"), que publicar la pila no la vuelve editable, y que la linea gratis **no** bloquea el pago aunque la pila tenga *Sell when Out-of-Stock* apagado con stock 0, y que **`message_intro` no debe repetir el punto de las pilas** cuando el carrier las incluye (si no, el cliente lee dos cosas opuestas); (f) *Validacion manual*: los pasos de CA14–CA30 |
| `website_sale_installation_appointment/static/description/index.html` | actualizar | Funcionalidad visible nueva: "las pilas van incluidas sin cargo cuando el envio las incluye" + como se configura |
| `odoo_customization_sunra/README.md` (raiz del repo) | actualizar | Sumar "pilas incluidas sin cargo" al resumen de la fila del modulo en el indice |
| `website_sale_installation_appointment/specs/website_sale_installation_appointment.md` | actualizar | Esta spec: `Estado` → `implemented` y `Version` sincronizada con el manifest (`1.8.0`) al cerrar T12 |

## Plan del cambio (completado)

> **Solo la feature de pilas incluidas** (el resto del modulo ya estaba implementado y solo se
> describe como current-state). Las 12 tareas (T01..T12) se ejecutaron en orden y estan
> **cerradas**: T01..T10 codigo, T11 tests (20/20 en verde), T12 documentacion + version. Se deja
> la tabla como registro de lo hecho (archivos, dependencias y CA cubiertos).

| Tarea | Descripcion | Depende de | Archivos | Cubre |
|-------|-------------|------------|----------|-------|
| **T01** | `product.template`: campos `free_battery_product_id` (M2o `product.product`, `ondelete="restrict"`, **`check_company=True`** + domain de compañia), `free_battery_qty` (Integer, default 0) con `string`/`help` que dejan **inequivoca la UoM** (D15) y `free_battery_uom_name` (Char related, readonly), + `_check_free_battery_config` (`@api.constrains`) | — | `models/product_template.py` (nuevo), `models/__init__.py` | CA26, CA34 |
| **T02** | `delivery.carrier`: campo `includes_free_batteries` (Boolean, default False) con `help` explicito | — | `models/delivery_carrier.py` | CA25 |
| **T03** | `sale.order.line`: flag tecnico `is_free_battery_line` (Boolean, default False, **sin `copy=`** → copiable, D33), con el `help` del molde del modulo hermano (pero NO su `copy=False`) | — | `models/sale_order_line.py` | CA21, CA31 |
| **T04** | `sale.order`: `_get_free_battery_needs()` (agregado por producto de pila; excluye `is_downpayment`/`_is_global_discount()`, saltea `product_uom_qty <= 0` y compañias incompatibles) + `_prepare_free_battery_line_vals()` (texto **sin** el carrier, en el idioma del cliente) + `_sync_free_battery_lines()` (idempotente, `sudo()`, guard defensivo `wsia_skip_battery_sync`, solo `draft`/`sent`, **sin tocar lineas facturadas/entregadas**) | T01, T02, T03 | `models/sale_order.py` | CA14, CA17, CA25, CA33, CA34 |
| **T05** | `sale.order`: engaches — overrides de `_verify_cart_after_update()`, `_set_delivery_method()` y **`set_delivery_line()`** (boton *Add shipping* del backoffice), `@api.onchange('order_line', 'carrier_id')` llamado `_onchange_free_battery_lines` (sync **en memoria** con `Command.*`; NO usar el nombre `_onchange_order_line`, pisaria el del core) y override **nuevo** de `action_confirm()` (sync antes del `super()`; NO tocar el `_action_confirm()` existente) | T04 | `models/sale_order.py` | CA15, CA16, CA23, CA24 |
| **T06** | `sale.order.line`: defensas — `_get_display_price()`, `_compute_pricelist_item_id()`, `_check_validity()`, `_is_reorder_allowed()`, `_is_sellable()` y **`_check_availability()`** (override de `website_sale_stock`, D34) | T03 | `models/sale_order_line.py` | CA18, CA19, CA20, CA22, CA27, CA28, CA32 |
| **T07** | `sale.order._cart_find_product_line()`: filtrar las lineas gratis del resultado del `super()` | T03 | `models/sale_order.py` | CA21 |
| **T08** | Vistas de configuracion: vista nueva de `product.template` (grupo `upsell` de la pestaña Sales, con la **UoM visible** al lado de la cantidad) y `includes_free_batteries` en `group name="delivery_details"` del carrier | T01, T02 | `views/product_template_views.xml` (nuevo), `views/delivery_carrier_views.xml`, `__manifest__.py` | CA14, CA25, CA26 |
| **T09** | Carrito: xpath sobre `website_sale.cart_lines` para ocultar el boton **Eliminar** de la linea gratis en desktop y mobile (`t-if="not line.is_free_battery_line"` sobre los dos nodos `js_delete_product`; **no** ocultar los contenedores) | T03, T06 | `views/website_sale_templates.xml` | CA27 |
| **T10** | Paso del checkout, **dos partes**: (a) `t-if="not order.carrier_id.includes_free_batteries"` **como atributo** del `<li>` historico de las pilas (su **texto no se toca** → `msgid` intacto); (b) **bloque nuevo** con el aviso de pilas incluidas, con clase **`o_not_editable`**, ubicado **despues del cierre del `<div t-else="">`** (nunca entre el `t-if` y el `t-else`: QWeb rompe al cargar) y condicionado solo a `includes_free_batteries` (D31 + D41). Aviso en **un solo nodo de texto** → el `.po` **suma una** entrada nueva con su `msgstr` es_419, sin modificar ninguna existente | T02 | `views/website_sale_installation_templates.xml`, `i18n/es_419.po` | CA29, CA37 |
| **T11** | Suite de tests de los **flujos troncales de pilas** (sin matriz exhaustiva): agregacion y agrupacion, idempotencia del sync, cambio de cantidad y de carrier, precio 0 en el camino forzado y en el normal (**combinados**: `_recompute_prices()` con una tarifa de descuento real, no cada uno por separado), `discount == 0` / `pricelist_item_id == False`, alta manual separada, `_is_reorder_allowed`, `_is_sellable` con el producto **publicado**, los tres engaches de backend (onchange, `set_delivery_line`, `action_confirm`), auto-curacion via `_cart_update_line_quantity`, constrains de configuracion, duplicado de pedido, cantidades no positivas (`-1`, y `+1`/`-1` que se cancelan en el tiempo), multi-compañia, y que el `name` de la linea sale traducido para un cliente es_AR (no solo que `_get_lang()` corre, sino que el `.po` tiene el `msgstr` cargado). **El camino onchange quedo con DOS tests, no uno** (correccion post-review, ver *Notas de implementacion*): `test_onchange_adds_free_battery_line` ejercita la rama `Command.create` llamando `_onchange_free_battery_lines()` directo sobre un `.new()` (no via `Form`: `carrier_id` no esta en ninguna vista backend de `sale.order`, asi que `Form` no lo agrega a su `fields_spec` y el trigger real nunca se prueba con ese atajo); `test_onchange_removes_free_battery_line_via_form` cubre la rama **`Command.delete`** (la mas riesgosa) **a traves del trigger real** `@api.onchange`, abriendo un `Form` sobre un pedido que YA tiene `carrier_id` persistido (en `models.onchange()` el registro se arma con `origin=self`, asi que un campo fuera del `fields_spec` de la vista se sigue leyendo del registro real) y sacando la cerradura del o2m. ⚠️ **Dos cuidados de configuracion en los datos del test**: el de CA21 (alta manual) necesita el producto de pila **con stock** o con *Sell when Out-of-Stock* activado, si no lo rechaza `website_sale_stock` antes de llegar a nuestro codigo; y **CA32 es el tripwire del MRO de D34** (si algun dia el override queda sombreado, este test es el que avisa) | T04..T07 | `tests/__init__.py` (nuevo), `tests/test_free_batteries.py` (nuevo) | CA14, CA15, CA16, CA17, CA18, CA19, CA20, CA21, CA22, CA23, CA24, CA25, CA26, CA28, CA31, CA32, CA33, CA34 |
| **T12** | **Cierre**: doc (README del modulo con el **drift `1.2.0` → `1.8.0`** corregido —la linea 7 sigue sin actualizarse, el commit `e5526ae` no la toco—, `index.html`, fila del README del repo; incluye los **requisitos de configuracion**: `invoice_policy = 'order'` en el producto de pila, aprovisionar stock —tambien porque una linea de un producto sin stock **apaga el mail de carrito abandonado**—, la lectura de la UoM y **sacar el punto de las pilas de `message_intro`** cuando el carrier las incluye) + bump `version` del manifest `1.7.0` → **`1.8.0`** + `Estado` de esta spec a `implemented` con la `Version` sincronizada | T01..T11 | `README.md`, `static/description/index.html`, `../README.md`, `__manifest__.py`, `specs/website_sale_installation_appointment.md` | — (anti-drift + version sync) |

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
  y editar otra cosa (ej. `order_line`): ahi el onchange sigue viendo el carrier real. T11 usa las
  dos variantes: `.new()` + llamada directa al metodo para la rama `Command.create` (mas simple,
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
  tests por repo no aplica; T11 esta en el plan porque el usuario lo pidio explicitamente y el modulo
  no tenia `tests/`. Alcance acotado a los flujos troncales **de esta feature** (no se especifican
  tests del modulo preexistente). `TransactionCase` alcanza para todo lo de modelo (incluido
  `_cart_update_line_quantity`, que solo necesita el pedido con `website_id`); si algun helper del
  carrito exigiera `request`, usar `HttpCase` + `MockRequest` de `odoo.addons.website.tools`.
- **Dos mecanismos de texto que conviven** (D41 + D42): la **prosa estatica** del cliente va en campos del tipo de cita (`message_intro`, `installation_photos_message`) porque editar la plantilla desde el editor web crea una copia COW por sitio que se congela; el **texto que depende del estado del pedido** (aviso de pilas, condicionado a `includes_free_batteries`) va en la plantilla, porque un campo de texto no puede expresar una condicion. Criterio a aplicar en los proximos textos del modulo.
- **Rebase sobre `e5526ae`**: ese commit (textos configurables, otro dev) **no toca** `models/sale_order.py`, `models/sale_order_line.py`, `models/delivery_carrier.py` ni `views/website_sale_templates.xml`, asi que de las 12 tareas del plan **solo T10 cambio de diseño** (el `<li>` objetivo quedo dentro de un `t-else` que solo se pinta si `message_intro` esta vacio). Ninguna otra tarea colisiona.
- **Interacciones con modulos vecinos, verificadas como INERTES** (no re-investigar):
  - **`website_sale_payment_method_price`** (modulo hermano, mismo repo): la linea de pilas contribuye **0** al total, asi que no mueve el descuento por medio de pago; y la linea de descuento global que ese modulo genera queda **fuera** de `_compute_price_unit` por `_is_global_discount()` (`odoo/addons/sale/models/sale_order_line.py:L601`), asi que nuestro `_get_display_price()` no la toca. **El orden de los overrides no importa.**
  - **Linea del booking de `website_appointment_sale`**: filtros disjuntos (`calendar_booking_ids` vs `is_free_battery_line`), y su propio `_cart_find_product_line` devuelve un recordset **vacio** cuando viene `calendar_booking_id`, con lo que nuestro `.filtered()` encadenado es un no-op.
- **Correccion sobre el metodo del peso**: `_get_invalid_delivery_weight_lines` **si** tiene llamadores de produccion, pero **solo** en las integraciones de carriers de terceros de enterprise (`delivery_dhl_rest`, `delivery_ups_rest`, `delivery_usps_rest`, `delivery_sendcloud`, `delivery_bpost`, `delivery_easypost` + legacy). Con el carrier `fixed` del cliente ninguno corre; la omision del override de peso sigue siendo correcta, pero el motivo es "ningun llamador **alcanzable en esta configuracion**", no "ningun llamador".
- **Naming deliberado**: el onchange se llama `_onchange_free_battery_lines`, no `_onchange_order_line`, porque ese nombre pisaria el onchange de combos del core (`odoo/addons/sale/models/sale_order.py:L936`). Desviacion consciente de la convencion `_onchange_<campo>` de `AGENTS.md`.
- **El guard `wsia_skip_battery_sync` es defensivo**: hoy **no hay** ningun camino de recursion real; se deja por simetria con el modulo hermano y para que un engache futuro no se muerda la cola.
- **`state` de la spec**: al cerrar T12 pasa a `implemented`; @reviewer/@testing la dejan `verified`.
