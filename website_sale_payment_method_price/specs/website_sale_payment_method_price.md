# Spec de modulo: website_sale_payment_method_price

| Campo | Valor |
|-------|-------|
| **Modulo** | `website_sale_payment_method_price` |
| **Version** | `1.3.1` (== `version` del `__manifest__.py`, formato `x.x.x`) |
| **Serie Odoo** | `19` (informativa) |
| **Estado** | `implemented` (1.0.2 quedo `verified`; 1.2.0 = rediseno del bloque de precio, implementado y revisado el 11-09-2026; **1.3.0** = segunda maqueta del bloque de precio, la que eligio el cliente el 14-09-2026: un precio por renglon con su pill y la linea "Ahorras $X" en verde. Implementado el 14-09-2026 (T01..T06) y verificado en el navegador por el orquestador sobre la base local con la paleta real de produccion —ficha y tarjeta, con y sin precio de referencia, y cambio de variante—. Queda `implemented` hasta la pasada de @reviewer. **1.3.1** = ajuste de la clienta del 15-09-2026 sobre el precio sin impuestos nacionales, ver D27) |
| **Actualizado** | `2026-09-15` |

## Objetivo

Permitir un **descuento o recargo por medio de pago** en el eCommerce, con dos entregables:

1. **Vidriera**: el precio con cada medio de pago configurado se publica en un **bloque de precio
   propio** (recuadro con el precio de lista tachado, el porcentaje en un pill y el precio del medio
   como protagonista — D17), en la grilla del shop, en la ficha del producto y como fila extra debajo
   del Total del carrito.
2. **Cobro**: al elegir ese medio en el checkout, el descuento se aplica **de verdad** al pedido como
   linea con su IVA, de modo que el total cobrado coincida con el precio publicado.

Motivo: Nokey vende hoy en Tiendanube, donde esa funcion es nativa y el 15 % por transferencia es el
argumento de venta principal del sitio (verificado sobre 22 productos de `www.nokey.com.ar`). Odoo 19
no tiene equivalente: los `fees` de `payment.provider` existieron hasta la v15 y fueron eliminados, y
el precio del carrito se calcula antes de que el cliente elija como pagar.

## Decisiones vigentes

| # | Decision | Valor vigente |
|---|----------|---------------|
| D1 | ¿Donde vive la configuracion? | En **`payment.method`** (pestana "Website"), NO en `payment.provider`. Lo fuerza el requerimiento del cliente: transferencia lleva descuento y tarjeta no, pero **ambas cuelgan del mismo proveedor** cuando el medio es Mercado Pago (`mercado_pago_wallet` vs `card`). A nivel proveedor no se pueden separar. |
| D2 | Granularidad | **Una linea por (medio, sitio)** en un modelo hijo, no un m2m de sitios con un porcentaje unico: soporta otro porcentaje en otro sitio sin rediseñar. |
| D3 | ¿Medios de pago en la lista de precios? | **No.** Decision explicita del dev: las lineas por sitio son la unica fuente, para que no se solapen dos configuraciones que pueden contradecirse. |
| D4 | Semantica del redondeo | Espeja `product.pricelist.item.price_round`: multiplo, `float_round` al mas cercano, aplicado **despues** del porcentaje. En 0 no redondea. |
| D5 | Base del calculo en la vidriera | Sobre el precio **ya mostrado** (post `_apply_taxes_to_price`, con o sin IVA segun `website.show_line_subtotals_tax_selection`). Verificado contra el sitio real: 664.936,10 es con IVA y 565.195,69 es el 85 % de ese numero, no del neto. |
| D6 | ¿Como se materializa el ajuste en el pedido? | Reusando `sale.order.discount` con `discount_type='amount'` (importe fijo) → `account.tax._prepare_global_discount_lines`, que parte el importe por combinacion de impuestos. **No** se reimplementa la matematica del IVA. |
| D7 | ¿Importe fijo o porcentaje? | **Importe fijo.** Con porcentaje el total no coincidiria con los precios redondeados que promete la vidriera, que es justamente el punto. El objetivo se calcula igual que en el sitio (por precio unitario) y el ajuste es la diferencia. Ademas `_reduce_base_lines_to_target_amount` interpreta el importe fijo como **total con impuestos**, la misma base que muestra el sitio. |
| D8 | ¿Por que medio se busca la regla? | Por **`primary_payment_method_id`**. En el checkout el radio es siempre el primario (`card`), pero el proveedor **reescribe** `payment_method_id` con la marca real (`visa`) al procesar el feedback. Buscar por el medio tal cual llega perderia la configuracion. |
| D9 | ¿Como se sincroniza el medio preseleccionado? | En el servidor, dentro de `_get_shop_payment_values`, espejando la condicion del core (`/home/leandro/projects/nexit/19.0/odoo/addons/payment/views/payment_form_templates.xml:L38`), y **solo si el pedido no tiene ya una regla**. Si la tiene es porque el cliente eligio un medio, y quitarsela pelearia contra esa eleccion en cada recarga. |
| D10 | ¿Por que se recarga el paso de pago? | El importe se lee del `dataset` del formulario en el `setup()` de la interaccion (`/home/leandro/projects/nexit/19.0/odoo/addons/payment/static/src/interactions/payment_form.js:L23`), asi que un refresh parcial dejaria un numero viejo. Atajo deliberado; la seleccion del radio se conserva con el parametro `wspmp_pm`. |
| D15 | ¿Como se restaura la seleccion tras la recarga? | Marcando `radio.checked` **antes** de `super.willStart()`, sin disparar eventos: el `willStart` del core, al encontrar un radio marcado, despliega el formulario inline y habilita el boton (`/home/leandro/projects/nexit/19.0/odoo/addons/payment/static/src/interactions/payment_form.js:L36`). **No** con `radio.click()`: los listeners de `dynamicContent` se enganchan recien cuando `willStart` resuelve (`/home/leandro/projects/nexit/19.0/odoo/addons/web/static/src/public/colibri.js:L51`), asi que el `change` no lo escucha nadie y el boton de pagar queda deshabilitado. **Consecuencia**: el `_prepareInlineForm` del proveedor pasa a correr dentro del `willStart` (en Mercado Pago eso es cargar el SDK y montar el brick de tarjeta, `/home/leandro/projects/nexit/19.0/odoo/addons/payment_mercado_pago/static/src/interactions/payment_form.js:L33`), y por eso la seccion colapsada se despliega **antes** del super: el brick tiene que montar en un contenedor visible. Como todo esto corre antes que el core, la restauracion va **blindada** (`try/catch` + el id validado como numerico): un throw nuestro dejaria al framework sin enganchar ningun listener y reproduciria el mismo boton trabado. |
| D11 | ¿Donde se cuelga el JS de la ficha? | En **`WebsiteSale.prototype`**, no en `VariantMixin`: el core copia el mixin al prototipo con `Object.assign` (`/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/static/src/interactions/website_sale.js:L651`), asi que un `patch()` sobre el mixin llega tarde. Comprobado en vivo: la primera version parcheaba el mixin y no repintaba. |
| D12 | ¿Reserva de stock al pagar por transferencia? | **Como lo hace Odoo** (pedido en presupuesto, sin reserva). Decision explicita de la cliente → sin desarrollo. |
| D13 | Convivencia con otras promociones | El ajuste **se suma** a lo que haya (decision comercial de la cliente). El objetivo se calcula sobre el precio final de cada linea, ya con sus descuentos. |
| D14 | ¿Se publican precios de medios no disponibles? | No. Se descartan reglas de medios archivados y de proveedores deshabilitados, sin publicar, de otra compania o restringidos a otro sitio. |
| D16 | ¿Que pasa con el residual sin impuestos de un descuento? | **No forma base descontable.** El reparto por grupo (D6) deja un renglon sin impuestos cuando el pedido tiene una porcion sin IVA; si esa porcion es el **residual de otro descuento**, el reparto se realimenta y los descuentos quedan partidos en dos para siempre (reproducido con el cupon 5000OFF + el 15 % de transferencia: 4 renglones que no se consolidan ni sacando el disparador). Se excluyen esas lineas via `_get_no_effect_on_threshold_lines`, el mismo hook que usa `sale_loyalty_delivery` para las lineas de envio. Una porcion sin IVA **real** (un producto sin impuestos) sigue partiendo el descuento, que es lo correcto: no se puede revertir un IVA que no existe. El campo `reward_id` se consulta en blando para no depender de `sale_loyalty`. |
| D17 | Orden y contenido del bloque de precio (**reemplazada por D25 en 1.3.0**) | **Maqueta aprobada por la cliente el 11-09-2026** (vigente hasta 1.2.0; el orden y los pills los redefine D25, lo demas sigue valiendo). De arriba a abajo: (1) precio sin impuestos nacionales, chico y gris, **fuera** del recuadro; (2) dentro de un recuadro fino (`border 1.5px #bbb`, `radius 12px`), el precio de lista **tachado** + un pill de marca `#A3EA24` con el porcentaje (`-15% OFF`); (3) el precio con el medio de pago **en grande**, protagonista; (4) la etiqueta `pagando con <medio>`; (5) la linea de cuotas en un renglon. Aplica a la **ficha** y a la **grilla**. Este modulo pasa a ser el **unico dueno del orden** de los precios en esas dos superficies. El color de marca `#A3EA24` va **hardcodeado en el SCSS**: decision consciente, no se parametriza (ni campo de configuracion ni variable publica del tema); si algun dia cambia la identidad de marca, se cambia el SCSS. |
| D18 | ¿Como queda arriba el precio sin impuestos nacionales, sin tocar la localizacion AR? | **No se mueve ni se edita** el `<small>` que publica `l10n_ar_website_sale` (es obligatorio por normativa y nunca se elimina). El recuadro se agrega **al final** del bloque de precio del core y las herencias de este modulo declaran `priority="18"`, asi que se aplican **despues** de las de la AR (`priority` 16, el default): el `<small>` que la AR ya agrega al final del bloque queda **arriba** del recuadro por orden de aplicacion, sin tocarlo. Se **descarto** `position="move"` sobre ese `<small>`: obligaria a declarar `l10n_ar_website_sale` en `depends` (un locator que no matchea **aborta** la combinacion de la vista) y no gana determinismo, porque mover tambien exige que la AR se haya aplicado antes. **Como se ancla**: el recuadro entra con `position="inside"` sobre el div padre del bloque (`//div[@name='product_price']` en la ficha, `//div[hasclass('product_price')]` en la grilla) y queda como **ultimo hijo**; cualquier ancla `after`/`before` sobre un hijo intermedio (como la de 1.1.0, que colgaba de `//div[@name='product_price_container']` con `after`) invierte el orden y deja el `<small>` de la AR **abajo** del recuadro, rompiendo CA20. La cadena que lo sostiene: la AR inyecta su `<small>` con `//div[1]` sin `position` (⇒ `inside`, al final) en `l10n_ar_website_sale/views/templates.xml:5`; el `priority` declarado en `<template>` se escribe de verdad en `ir.ui.view.priority` (`convert.py:508`), el default es 16 (`ir_ui_view.py:148`) y la combinacion resuelve `ORDER BY v.priority, v.id` (`ir_ui_view.py:758`). |
| D19 | ¿Que precio se tacha y de donde sale el pill? | Se tacha el precio que **el core ya publica** (`oe_price` en la ficha, `price_reduce` en la grilla): frente al del medio de pago es el "precio de lista". Se consigue **moviendo el nodo del core** dentro del recuadro y tachandolo por CSS — no se duplica el importe ni se recalcula nada (el core ya trae `price`/`list_price` y `price_reduce`/`base_price`). El pill muestra el porcentaje de la **primera regla visible** (por `sequence`) y **solo** si es `price_type='discount'`. |
| D20 | ¿Como se arma la etiqueta del medio? | String nuevo `_("paying with")` + el nombre del medio en `<b>`, **sin** `text-transform: uppercase` (se saca el de `payment_method_price.scss`). Se mandan **prefijo y nombre por separado** (dos nodos en la vista y en el JS) para no meter HTML dentro de un string traducible ni `innerHTML` en el repintado de variantes. El nombre del medio es dato de la DB. |
| D21 | ¿Como entran las cuotas al recuadro? | Este modulo **no toca** las cuotas: expone un **contenedor estable** `div[@name='wspmp_box']` con un **slot vacio** `div[@name='wspmp_installments']` dentro del recuadro (ficha y grilla). **El contrato es el atributo `name`, no la clase**: el recuadro lleva clases condicionales (`o_wspmp_box_active` / `o_wspmp_discounted`) que en la grilla solo pueden venir por `t-attf-class`, y `hasclass()` lee **solo** el atributo estatico `class` (`ir_ui_view.py:83`), asi que `//div[hasclass('o_wspmp_box')]` **no matchearia** y abortaria la combinacion de la vista con `ValueError` (`template_inheritance.py:343`). Las clases `o_wspmp_box` / `o_wspmp_installments` se conservan para el CSS y el JS —repetidas **dentro** del `t-attf-class`, porque en el render el atributo dinamico pisa al estatico (`ir_qweb.py:1946`)— pero **todos los xpath, los nuestros y los del puente, van por `name`** (es la convencion del core, cf. `div[name='product_price_container']`). El modulo puente `website_sale_installment_plans_ux` (tarea aparte, 1.0.0 -> 1.1.0, sin spec) mueve ahi el `div.installment-plans` que inyecta ADHOC (`website_sale_installment_plans`), con `position="move"` y `priority="20"` (despues de este modulo), y **tiene que declarar `website_sale_payment_method_price` en `depends`**: hoy declara solo `website_sale_installment_plans` (`extra-addons/odoo_customization_sunra/website_sale_installment_plans_ux/__manifest__.py:20`) y no tiene `views/`; el slot es su destino y un locator sin destino rompe la vista. Esto se documenta aca porque el puente no tiene spec propia. **Renombrar el contenedor, el slot o su `name` rompe el puente**: son contrato. |
| D22 | ¿Tarjetas de la grilla de igual altura? | Si, y se resuelve con **CSS de este modulo**, porque la variacion de altura la introduce hoy este bloque: la tarjeta ocupa el alto de su celda y el bloque precio+CTA se pega al pie (`margin-top: auto` sobre `.o_wsale_product_sub`). No se toca el core ni el tema; el selector exacto se ajusta verificando en el navegador. **Ojo con `display: contents`**: `.o_wsale_product_sub` declara `display: var(--o-wsale-card-sub-display, flex)` (`product_tile.scss:289`) y el propio core anota que **puede** caer en `contents` segun el tema (`product_tile.scss:186`); con `contents` ese nodo no genera caja y un `margin-top: auto` sobre el **no hace nada** — el anclaje al pie va entonces sobre el precio y el CTA, que pasan a ser hijos flex directos de `.o_wsale_product_information` (`product_tile.scss:169`). El CSS **cubre los dos casos**; T06 verifica primero cual usa el tema de Nokey y lo deja anotado. **Estado real del sitio (copia COW, verificado en la base local — copia de produccion del 09-09-2026)**: el sitio Nokey (`website_id=1`) tiene una **copia por sitio** de `website_sale.products_item` (`ir.ui.view` 19099, `arch_updated=true`, editada a mano desde el editor web el 07-08-2026; el arch lleva el comentario «centrar precio 7-08-2026») que **ya centra el bloque**: `.o_wsale_product_information` con `text-center` y `.o_wsale_product_sub` de `justify-content-between gap-2` a `justify-content-center flex-column align-items-center gap-2`. Se **asume ese estado** (en el sitio `.o_wsale_product_sub` es `flex-column` centrado) y el **SCSS de este modulo pasa a ser dueno del centrado del bloque de precio** —replica la intencion de esa edicion a mano— para que la copia COW se pueda **restablecer a la generica** y el layout quede versionado en el repo. El restablecimiento de las dos copias COW se ejecuta **en produccion dentro de Plane #68**, no en este modulo. **Fix post-review (11-09-2026)**: las 4 reglas de este punto (`.o_wsale_product_sub`/`.o_wsale_product_information`, sin colgar de `.o_wspmp_box*`) iban sueltas, sin scope y sin especificidad para ganarle al core: medido en el navegador, en Sunra (`website_id=3`, sin la copia COW de Nokey) el `text-align: center` se filtraba a un sitio ajeno, y las 3 reglas de `.o_wsale_product_sub` eran **inertes** en los dos sitios porque el core las declara con especificidad 0-2-0 (`.oe_product_cart .o_wsale_product_sub { ... }`, `product_tile.scss`) contra nuestras reglas sueltas de 0-1-0; el apilado que se veia en Nokey salia solo del tema (la variable CSS) mas las utilidades Bootstrap `!important` de la copia COW, no de este modulo — la garantia de este punto (D22) **no se cumplia**. Corregido con scope `:has(.o_wspmp_box_active)` (para que solo actuen con el recuadro activo, igual que el resto del modulo, CA19) y prefijo `.oe_product_cart` (sube la especificidad a 0-3-0, le gana al core sin `!important`). **Segunda vuelta de la medicion**: con las 4 clases de la COW removidas por JS (simulando el restablecimiento a la generica, Plane #68), `flex-direction`/`align-items` quedaban corregidos por la sola especificidad, pero `justify-content` NO — el template generico trae `justify-content-between` como utilidad de Bootstrap **directo en el markup** (`product_tile_templates.xml:186`), y esa utilidad es `!important`: ninguna especificidad la vence. Se agrego `!important` **solo** a esa propiedad (mismo criterio que D19 con `justify-content: flex-start !important` en la ficha). Verificado con Playwright sobre las dos superficies (base local), quitando TODAS las clases que agrega la COW (`flex-column align-items-center justify-content-center gap-2` de `.o_wsale_product_sub`, `text-center` de `.o_wsale_product_information`) para simular la restauracion real: en Nokey el bloque queda apilado y centrado (`column` / `center` / `center` / `center`) sostenido **solo** por el CSS de este modulo; en Sunra (`website_id=3`, sin regla de precio configurada, 0 de 21 tarjetas con `.o_wspmp_box_active`) `.o_wsale_product_information` sigue en `start` (nunca `center`) y `.o_wsale_product_sub` en `row`: no hay filtracion a ese sitio. La verificacion **visual** del layout tras el restablecimiento real de la copia COW de Nokey sigue en produccion, dentro de Plane #68. |
| D23 | ¿Que se rediseña en el carrito? | La fila por medio debajo del Total adopta la **etiqueta nueva** y el **pill**, con el importe destacado. **No** lleva recuadro ni slot de cuotas: la tabla de totales ya tiene su propio marco y las cuotas no se publican ahi. `[ASUNCION]` — la maqueta aprobada cubre ficha y grilla; si la cliente quiere el recuadro tambien en el carrito, el cambio es esta fila. |
| D24 | ¿Que NO se arregla por codigo? | (a) Los **centavos** de los precios de lista son dato de la lista de precios: no se fuerza un redondeo por codigo, se **recomienda a la cliente** corregir la lista. (b) El **nombre del medio** ("Efectivo/Transferencia") es dato de la DB: se **recomienda renombrarlo** a "Efectivo o transferencia". (c) El **"Ref"** de la ficha es de `website_sale_variant_code`, tarea aparte. |
| D25 | Bloque de precio, 2da maqueta (1.3.0) | **Maqueta elegida por el cliente el 14-09-2026** (reemplaza el orden de D17). De arriba a abajo, dentro del recuadro: (1) el precio de **referencia** tachado —el que ya publica el core: el precio de lista cuando hay descuento de lista de precios, o el **precio comparativo** (`compare_list_price`) cuando no— con un pill **neutro** al lado con su porcentaje (`-22%`); (2) el precio **actual** del core tachado, con el pill **verde de marca** del medio de pago (`-15% OFF`) al lado; (3) el precio con el medio de pago **en grande**; (4) **`Ahorras $X` en verde**, la diferencia entre el precio de referencia (o el actual, si no hay referencia) y el precio con el medio; (5) `pagando con <medio>`; (6) el slot de cuotas. **Un precio por renglon**, cada uno con su pill al lado: para eso la herencia **envuelve** cada nodo del core en un `div.o_wspmp_line` con `position="replace"` + `$0`, sin duplicar el importe (se mantiene D19). **Ojo con `$0`**: la herencia lo busca con `.//*[text()='$0']` (`template_inheritance.py:163`), asi que tiene que ser el **primer nodo de texto del envoltorio, literal** (un salto de linea antes y sale impreso en la pagina), y el nodo original se **anexa al final** — el pill queda primero en el DOM y el orden visual lo pone el SCSS (`order`). El pill del medio de pago conserva el `#A3EA24` hardcodeado (D17); el de referencia es gris neutro para no competir con el. El verde de `Ahorras` **no** es `#A3EA24` (sobre blanco no llega al contraste minimo como color de texto) sino `#3c7300`, el mismo tono oscurecido. **Dato, no codigo**: hoy ningun producto de Nokey tiene precio comparativo ni descuento de lista de precios visible (medido sobre la copia de produccion), asi que el primer renglon **no se ve** hasta que el cliente cargue "Precio comparativo" en la ficha del producto o un descuento porcentual en la lista. |
| D26 | ¿Alineacion del bloque? | **Ficha a la izquierda, tarjeta centrada.** La tarjeta del listado ya venia centrada (D22, replicando la edicion a mano del sitio) y los renglones nuevos se centran con ella para que el bloque se lea como una sola pieza; la ficha sigue alineada a la izquierda, como la maqueta. En la tarjeta, ademas, el pill y el precio tachado bajan de tamano: a 390 px la grilla son 2 columnas y la tarjeta queda en ~173 px utiles, donde con los tamanos de la ficha el pill no entra en el mismo renglon (medido en el navegador). |
| D27 | ¿Donde va el precio sin impuestos nacionales? | **Debajo de los precios de venta, y chico** (pedido de la clienta el 15-09-2026: *"el precio sin impuestos tendria que estar abajo del resto de los precios ya que es solo para ARCA"*; estaba entre el nombre del producto y el recuadro). **Reemplaza a D17(1) y a CA20 en cuanto a la posicion**; lo demas de D18 sigue igual: el nodo de `l10n_ar_website_sale` **no se toca ni se mueve por herencia** —eso obligaria a declarar ese modulo en `depends` y un locator sin destino aborta la vista—, se reordena por **CSS**: el contenedor pasa a `flex-direction: column` y el `<small>` se manda al final con `order: 1`. Con el recuadro activo ese contenedor tiene exactamente dos hijos (el `<small>` y el recuadro), asi que es el reordenamiento minimo. Tres detalles que costaron una vuelta cada uno, medidos en el navegador: (a) el `display: flex` necesita `!important` en las dos superficies —la ficha trae `d-inline-block` de Bootstrap y la tarjeta resuelve el display por custom property del tema—; (b) el selector tiene que incluir **`.o_l10n_ar_product_price`**, porque en la tarjeta `l10n_ar_website_sale` agrega esa clase por `t-attf-class` sobre un `class` **estatico** del core y en el render el atributo dinamico **pisa** al estatico (`ir_qweb.py:1946`): el div final queda **sin** `product_price`; (c) el contenedor necesita `align-self: stretch` o toma el ancho de su contenido (173 px contra 154 del padre) y el importe sale cortado. |

## Alcance

### Incluye
- Modelo `payment.method.website.price` con tipo, porcentaje, alcance, redondeo y visibilidad, unico
  por (medio, sitio), y su pestana "Website" en el formulario del medio de pago.
- Bloque de precio rediseñado (D17) en la grilla del shop y en la ficha del producto: recuadro con el
  precio de lista tachado, pill con el porcentaje, el precio del medio de pago como protagonista y la
  etiqueta `pagando con <medio>`, con repintado JS al cambiar de variante; y fila por medio debajo del
  Total del carrito/checkout (D23).
- Slot estable para la linea de cuotas dentro del recuadro, con el **contrato de locator por atributo
  `name`** (`div[@name='wspmp_box']` / `div[@name='wspmp_installments']`, D21), y CSS de la grilla para
  que las tarjetas queden de igual altura con el bloque precio+CTA al pie (D22).
- Aplicacion real del ajuste al pedido en el checkout, con su IVA repartido por grupo de impuesto.
- Caida del ajuste al cambiar de medio y recalculo al cambiar el carrito.
- Revalidacion al crear la transaccion, para no cobrar nunca un importe distinto al mostrado.
- Traduccion `es_AR` de las cadenas visibles (incluida la etiqueta `con <medio>`).
- Documentacion (`README.md` + `static/description/index.html`) y fila en el README raiz del repo.

### NO incluye
- **Campo de medios de pago en la lista de precios** (D3).
- **Exclusion por producto o categoria**: el alcance es el sitio. Si se publica algo que no deba
  llevar descuento, hoy no hay donde excluirlo.
- **Minimos de compra ni topes de descuento** (la cliente los descarto).
- **Cambios en la reserva de stock** ni en el circuito de acreditacion de la transferencia (D12).
- **Habilitar `mercado_pago_wallet`**: existe en el catalogo del core pero nace inactivo y el modulo
  de MP activa solo tarjetas. Es configuracion + verificacion en staging, no codigo.
- **Las cuotas**: ni el calculo ni el texto (los ponen ADHOC `website_sale_installment_plans` y el
  puente `website_sale_installment_plans_ux`). Este modulo solo expone el slot adonde el puente las
  mueve (D21).
- **El precio sin impuestos nacionales**: lo publica `l10n_ar_website_sale`, es obligatorio por
  normativa y no se edita, no se mueve y no se elimina (D18).
- **El "Ref" de la ficha** (`website_sale_variant_code`), **los centavos de los precios de lista** y el
  **nombre del medio de pago**: dato o tarea aparte (D24).
- Modificar core/enterprise: todo es `_inherit`, `t-inherit` y `patch()`.

## Modelos

### Nuevos

| Modelo | _description | Para que |
|--------|--------------|----------|
| `payment.method.website.price` | Payment Method Website Price | Una linea de precio por medio de pago y sitio web |

### Extendidos

| Modelo | Que se agrega |
|--------|--------------|
| `payment.method` | `website_price_ids` + `_get_website_price_rule(website)` |
| `product.template` | `_get_payment_method_price_vals()` + overrides de `_get_sales_prices` y `_get_additionnal_combination_info` |
| `sale.order` | `payment_price_rule_id`, calculo y aplicacion del ajuste, override de `_recompute_cart` |
| `sale.order.line` | `is_payment_method_discount` |

## Campos

### `payment.method.website.price`

| Campo | Tipo | Notas |
|-------|------|-------|
| `payment_method_id` | Many2one `payment.method` | required, `ondelete='cascade'`, index |
| `website_id` | Many2one `website` | required, `ondelete='cascade'` |
| `sequence` | Integer | default 10, orden de los precios extra |
| `price_type` | Selection `discount`/`surcharge` | required, default `discount` |
| `percentage` | Float `(16,2)` | required, default 0; constraint 0..100 |
| `applies_to` | Selection `product`/`delivery`/`all` | required, default `product` |
| `price_round` | Float | constraint >= 0; help espeja el del core |
| `show_on_website` | Boolean | default True |

Constraint SQL: `UNIQUE(payment_method_id, website_id)`.

### Otros

| Modelo | Campo | Tipo | Notas |
|--------|-------|------|-------|
| `payment.method` | `website_price_ids` | One2many | inverso `payment_method_id` |
| `sale.order` | `payment_price_rule_id` | Many2one | `copy=False`, `readonly=True` |
| `sale.order.line` | `is_payment_method_discount` | Boolean | `copy=False`, tecnico |

## Metodos

### `PaymentMethodWebsitePrice._apply_to_price(self, price)`
Unico lugar donde se calcula el precio ajustado. Signo por `price_type`, luego
`float_round(price, precision_rounding=price_round)` si hay redondeo. Espeja
`product.pricelist.item._compute_price` (rama `formula`).

### `PaymentMethodWebsitePrice._get_website_rules(self, website, only_visible=False)`
Reglas vigentes del sitio: descarta porcentaje 0, medios archivados y medios sin proveedor usable
(via `_is_payment_method_available`).

### `PaymentMethod._get_website_price_rule(self, website)`
Resuelve la regla **subiendo al metodo primario** (D8).

### `PaymentMethodWebsitePrice._get_percentage_label(self)`
Porcentaje de la regla como texto para el pill: sin decimales cuando es entero (`15`), con el separador
del idioma (`formatLang`) cuando no lo es. Unico lugar donde se formatea el porcentaje.

### `ProductTemplate._get_payment_method_price_vals(self, website, price, rules=None, reference_price=None)`
Devuelve `[{name, label, price, price_formatted, price_type, badge, saving_label}]`, en el orden de `sequence` de las
reglas. `label` es el **prefijo** traducible (`_("paying with")`) y `name` el nombre del medio: viajan
**separados** para que la vista y el JS los compongan como `prefijo` + `<b>nombre</b>` sin meter HTML
dentro de un string traducible ni `innerHTML` en el repintado (D20). `badge` es el texto del pill
(`-15% OFF`, armado con `_()` sobre `_get_percentage_label()`) y solo viaja si la regla es
`price_type='discount'`; si no, `False` (D19). `price_formatted` viaja porque el JS de variantes no debe
re-resolver la moneda ni su precision. Descarta reglas con `applies_to='delivery'` (no afectan el precio
del producto). Desde 1.3.0 recibe ademas `reference_price` (el precio tachado que el core publica arriba)
y devuelve `saving_label`: el string `_("You save %(amount)s")` **ya armado y formateado** (D25), para que
el JS lo repinte con `textContent` sin componer HTML ni re-resolver la moneda; `False` si no hay ahorro.

### `ProductTemplate._get_payment_method_reference_badge(self, website, price, reference_price)`
Texto del pill **neutro** que acompana al precio tachado de referencia (`-22%`), o `False` si no hay
descuento que mostrar (D25). El redondeo del porcentaje se hace aca y no en QWeb. Viaja como
`payment_method_reference_badge` en `combination_info` (ficha) y en `template_price_vals` (grilla), y el JS
de variantes lo repinta igual que el pill del medio de pago.

### `SaleOrder._get_payment_method_price_totals(self)`
Los mismos campos que el helper del producto (`label`, `name`, `price`, `price_formatted`, `price_type`,
`badge`) pero sobre el total del pedido: una fila por medio debajo del Total, y solo mientras el pedido no
tenga ya una regla aplicada. `price_type` viaja tambien aca para que la fila del carrito decida pill y
destacado sin volver a resolver la regla (D23). Desde 1.3.0 la firma **ya no es identica** a la del helper
del producto: el del producto suma `saving_label`, que el carrito no publica (D23 no lleva ahorro: la tabla
de totales ya tiene su propio marco y el ahorro se lee en la vidriera).

### `SaleOrder._get_payment_price_amount(self, rule)`
Importe del ajuste **con impuestos**. Redondea por precio unitario en la base que muestra el sitio y
devuelve la diferencia contra el subtotal base; si el sitio muestra sin impuestos, escala por la
relacion bruto/neto del propio pedido.

### `SaleOrder._apply_payment_price_rule(self, rule)` / `_remove_payment_price_rule(self)`
Idempotente: limpia lo aplicado y vuelve a crear via `sale.order.discount`. Marca las lineas nuevas
con `is_payment_method_discount` y les agrega el nombre del medio.

### `SaleOrder._get_residual_discount_lines(self)`
Lineas de descuento (propias o recompensas de `sale_loyalty`) que quedaron **sin impuestos**: el residual del reparto por
grupo. Criterio: sin `tax_ids` y con `is_payment_method_discount` o `reward_id` (D16).

### `SaleOrder._get_no_effect_on_threshold_lines(self)` (override)
Suma esas lineas a las que `sale_loyalty` ya excluye, para que no cuenten ni como base descontable ni para los minimos de
compra de los programas. `super()` se resuelve con `getattr`: sin `sale_loyalty` instalado el hook no existe y nadie lo llama.

### `SaleOrder._recompute_cart(self)` (override)
Reajusta el descuento cuando cambia el carrito, con guarda de contexto `wspmp_skip_recompute`.

### Controllers
- `WebsiteSalePaymentMethodPrice.shop_payment_method_price` — `POST /shop/payment/method_price`.
  Opera **solo** sobre `request.cart`. Devuelve `{'reload': bool}`.
- `PaymentPortal._get_shop_payment_values` (override) — sincroniza el medio preseleccionado (D9).
- `PaymentPortal.shop_payment_transaction` (override) — revalida el ajuste contra el medio real.

## Assets y JS

| Archivo | Que hace |
|---------|----------|
| `static/src/js/payment_method_price.js` | `patch(WebsiteSale.prototype)` → `_onChangeCombination` repinta el recuadro: recrea las filas de `.o_wspmp_prices` (importe + prefijo + nombre en `<b>`), actualiza el texto del pill y togglea `o_wspmp_box_active` / `o_wspmp_discounted`. **Tiene que espejar el template**: si cambia el markup del recuadro, cambia aca (no re-resuelve moneda ni porcentaje, los recibe ya formateados del servidor). **Restriccion**: el `replaceChildren()` se hace **solo** sobre `.o_wspmp_prices`; sobre `o_wspmp_box` (y sobre el slot de cuotas) **unicamente se togglean clases**. Con el `move`, el `span.oe_price` del core vive **dentro** del recuadro y lo repinta `super._onChangeCombination()` (`variant_mixin.js:346`), que corre primero: vaciar el recuadro entero borraria el precio del core (y, con el puente instalado, la linea de cuotas) |
| `static/src/js/payment_form_price.js` | `patch(PaymentForm.prototype)` → `selectPaymentOption` llama la ruta y recarga; `willStart` re-marca el radio desde `wspmp_pm` **antes del super** (D15) via `_wspmpRestoreSelectedOption` |
| `static/src/scss/payment_method_price.scss` | Estilo del bloque (D17): recuadro `1.5px #bbb` / `radius 12px`, pill `#A3EA24`, precio del medio como protagonista, tachado y achicado del precio del core movido, etiqueta **sin** mayusculas forzadas y sin corte ni desborde a 360 px (`@include media-breakpoint-down(md)`), y tarjetas de la grilla de igual altura con el bloque precio+CTA al pie (D22). El recuadro es `display: contents` por defecto (D19/CA19: sin decoracion, el precio del core no cambia de tamano ni posicion) y pasa a `display: flex; flex-direction: column` con `.o_wspmp_box_active`: el `move` (T02/T03) agrega el precio de lista **antes del slot** (`position="before"` sobre `wspmp_installments`, no `inside` de `wspmp_box`), asi que ya queda antes en el DOM y `order: -1` solo lo reafirma visualmente cuando el recuadro esta activo (con el recuadro en `display: contents`, sin reglas visibles, `order` no aplica: el orden real depende del DOM, CA19). En la **grilla** ademas fija `width: 100%` / `flex-basis: 100%` para no depender de `--o-wsale-card-price-display`, que `.product_price` declara **sin fallback** (`product_tile.scss:298`; por eso la AR usa `d-block` en su `<small>`) y el tema puede dejar en `inline`; en la **ficha** normaliza el ancho del contenedor movido y fuerza `justify-content: flex-start !important` (el nodo del core trae `justify-content-end` como utilidad Bootstrap, que ya es `!important`, `templates.xml:2701`) para alinear el precio de lista a la izquierda, junto con el protagonista (maqueta aprobada). El `<small>` de `l10n_ar_website_sale` (D18, fuera del recuadro) se estiliza chico y gris por CSS (`[name='product_price'] > small`), sin tocarlo. **Los selectores nunca usan `aria-label`**: es un atributo traducible (igual que en los xpath, D21) y en render sale traducido (`"Precio de venta"` en es_AR): un selector CSS por el string en ingles no matchea (sin error, simplemente no aplica) — se usa la clase estatica `fw-bold` del span de `price_reduce` y el `del` hijo directo del recuadro |

Todos en `web.assets_frontend`.

## Vistas

| XML ID | Hereda | Que agrega |
|--------|--------|-----------|
| `payment_method_form` | `payment.payment_method_form` | Pestana "Website" con la lista editable de `website_price_ids` |
| `product_price` | `website_sale.product_price` (`priority="18"`) | **Dos operaciones separadas** (el `move` no puede ir anidado dentro del markup nuevo): **(a)** `<xpath expr="//div[@name='product_price']" position="inside">` agrega `div[@name='wspmp_box']` (clase `o_wspmp_box` + las condicionales por `t-attf-class`) con el pill, las filas de precio por medio con su etiqueta y el slot vacio `div[@name='wspmp_installments']`; **(b)** `<xpath expr="//div[@name='wspmp_installments']" position="before"><xpath expr="//div[@name='product_price_container']" position="move"/></xpath>`, con el `move` como **hijo directo** del spec y **sin contenido** (fila del precio de lista tachado). El destino es **`before` del slot**, no `inside` del recuadro: asi el precio de lista queda antes en el DOM (badge -> precios -> precio de lista -> slot) incluso con el recuadro en `display: contents` (sin reglas visibles, CA19), donde `order: -1` no tiene efecto. Ancla `inside` sobre `//div[@name='product_price']` (`templates.xml:2697`) ⇒ el recuadro queda **ultimo hijo** (D18); **reemplaza** el ancla de 1.1.0 (`views/website_sale_templates.xml:10`, `//div[@name='product_price_container']` + `after`). **1.3.0** suma **dos operaciones mas, despues del `move`** (asi los nodos quedan detras del `t-set` del recuadro y las variables estan en contexto): `position="replace"` + `$0` sobre `//span[@name='product_list_price']`, sobre `//del[@name='product_price_strikethrough']` y sobre `//span[hasclass('oe_price')]`, para envolver cada precio del core en su `div.o_wspmp_line` con el pill que le corresponde (D25) |
| `products_item` | `website_sale.products_item` (`priority="18"`) | Lo mismo en la tarjeta del listado, en **tres operaciones**: **(a)** `<xpath expr="//div[hasclass('product_price')]" position="inside">` agrega el mismo `div[@name='wspmp_box']` con pill, filas y slot (aca `hasclass` **si** es valido: la clase es estatica del core, `product_tile_templates.xml:191`); **(b)** `move` de `//div[hasclass('product_price')]//span[hasclass('fw-bold')]` (el span de `price_reduce`) **antes** del slot (`<xpath expr="//div[@name='wspmp_installments']" position="before">`) — **no** por `@aria-label`: es un atributo traducible y la herencia de vistas lo rechaza como selector (`ir_ui_view.py:412`, ParseError, verificado al implementar); **(c)** `move` de `t[name='product_base_price']`, misma ancla `before`. Los dos `move` son operaciones **independientes**, cada uno hijo directo de su propio `<xpath expr="//div[@name='wspmp_installments']" position="before">` y sin contenido; en el DOM final quedan en el orden precios -> precio de lista tachado -> precio actual -> slot. **1.3.0**: los dos `move` se hacen **primero** (base_price antes que `fw-bold`, para que el tachado quede arriba) y recien despues se envuelve cada uno con `position="replace"` + `$0` en su `div.o_wspmp_line` + pill (D25) |
| `total` | `website_sale.total` | Fila por medio debajo del Total, con la etiqueta nueva y **un pill por fila** (sin recuadro, D23) |

> **Contrato de locators (D21).** El recuadro y el slot se localizan **siempre por atributo `name`** (`div[@name='wspmp_box']`, `div[@name='wspmp_installments']`), nunca por `hasclass()`: el recuadro lleva clases condicionales por `t-attf-class` y `hasclass()` solo lee el atributo estatico `class` (`ir_ui_view.py:83`), con lo que el xpath no matchearia y la combinacion de la vista abortaria con `ValueError` (`template_inheritance.py:343`). Las clases se repiten **dentro** del `t-attf-class` porque en el render el atributo dinamico pisa al estatico (`ir_qweb.py:1946`).
> **`position="move"` solo se procesa como hijo directo del spec** (`template_inheritance.py:45`): anidado dentro del `<div>` nuevo es un **no-op silencioso** (el `<xpath>` queda literal en el arch) y, si el `move` lleva hijos, `extract` tira `ValueError` (`template_inheritance.py:137`). Por eso cada `move` va en su propia operacion, vacio.

## Seguridad

`payment.method.website.price`: lectura para `base.group_user`; lectura/escritura/creacion/borrado
para `base.group_system`. La lectura desde el frontend publico va por `sudo()` (es configuracion, no
hay dato de terceros). No hacen falta record rules: el filtro real es `website_id`.

## Reglas de negocio

1. Una regla con porcentaje 0 no tiene efecto y no se publica.
2. `applies_to` solo afecta al checkout; la vidriera muestra siempre el precio del producto.
3. El ajuste del pedido es unico: al reaplicar se borra el anterior, nunca se apila.
4. Al cambiar de medio de pago el ajuste se cae.
5. Al cambiar el carrito el ajuste se recalcula.
6. Si el ajuste no corresponde al medio con el que se paga, se corrige y el core pide refrescar.
7. Nunca se cobra un importe distinto al que se mostro.
8. El recuadro solo se **decora** (borde, pill, tachado del precio del core) cuando hay al menos un
   precio por medio de pago visible; si no hay reglas visibles o el producto no tiene precio, el
   precio del core se ve como siempre.
9. En la **ficha y la grilla** (donde hay un solo recuadro) el pill lleva el porcentaje de la
   **primera** regla visible (por `sequence`) y solo si es un descuento; con recargo no hay pill ni
   tachado (el precio del medio es el mas caro). En el **carrito** no hay recuadro y cada fila lleva
   **su propio** pill, con el porcentaje de su regla (D23).
10. Este modulo no publica ni formatea las cuotas: expone el slot `div[@name='wspmp_installments']` y
    el modulo puente las mueve ahi (D21).
11. El precio sin impuestos nacionales de la localizacion AR no se edita, no se mueve y no se
    elimina: queda arriba del recuadro por orden de aplicacion de las vistas (D18).

## Edge cases

| Caso | Comportamiento |
|------|----------------|
| Un solo medio de pago (el core lo preselecciona) | El servidor aplica el ajuste antes de renderizar: no hay recarga extra ni error de importe |
| Varios medios, ninguno preseleccionado | Se muestra el total de lista mas la fila "con &lt;medio&gt;"; el ajuste se aplica al elegir |
| El cliente recarga el paso de pago con un ajuste aplicado | El ajuste se conserva (D9); el radio se re-marca via `wspmp_pm` y el core despliega el formulario inline y habilita el boton (D15) |
| El medio elegido cae en la lista colapsada de "otros medios" (hay tokens guardados) | Al restaurar la seleccion se despliega la lista y se oculta el boton de expandir, para no dejar marcado un medio invisible |
| Pago con token guardado | El medio se resuelve desde `token.payment_method_id` |
| Producto con precio 0 / `prevent_zero_price_sale` | No se publican precios por medio de pago |
| Carrito con solo linea de envio y `applies_to='product'` | Ajuste 0, no se crea linea |
| Impuestos mixtos (21 % y 10,5 %) | El total cierra exacto; puede haber centavos de diferencia en el reparto entre grupos |
| El pedido ya arrastra un residual de descuento sin impuestos | Se ignora como base: el descuento vuelve a un solo renglon en el siguiente recalculo (D16) |
| Medio archivado o proveedor deshabilitado | La regla no se publica ni se aplica |
| No hay ninguna regla visible para el sitio | El recuadro no se decora ni tacha nada: se ve el precio del core tal cual (el contenedor existe igual, porque la estructura la fija la herencia de la vista, no el dato) |
| Mas de una regla visible | Una fila de precio + etiqueta por regla; el pill es el de la **primera** (por `sequence`). Hoy Nokey tiene una sola regla (Efectivo/Transferencia, 15 %) |
| Regla de tipo recargo | Hay precio y etiqueta, pero **no** pill ni tachado |
| El producto ya tiene descuento de lista de precios | Conviven el tachado del core (`oe_default_price` / `base_price`, que el core ya mostraba) y el tachado del precio del medio: dos precios tachados. Es correcto, aunque cargado; no se oculta ninguno para no perder informacion del core |
| `l10n_ar_website_sale` no instalado (sitio no AR) | No hay precio sin impuestos nacionales y no pasa nada: este modulo no lo referencia en ningun xpath (D18) |
| El sitio tiene una **copia por sitio (COW)** del template heredado | La herencia se aplica **sobre la copia del sitio y en el idioma del sitio (`es_AR`)**, no sobre la vista generica: el `-i`/`-u` pasa igual y un locator que no matchea recien se ve al **renderizar el sitio**. Verificado en la base local (copia de produccion del 09-09-2026): `website_sale.products_item` tiene la copia 19099 (`website_id=1`, `arch_updated=true`) editada a mano, y **todos** los locators de la grilla existen en su arch `es_AR` (`div.product_price`, `span[hasclass('fw-bold')]`, `t[@name='product_base_price']`, `.o_wsale_product_sub`, `.o_wsale_product_information`). T09 valida sobre la vista del sitio, no sobre la generica |
| El modulo puente de cuotas no esta instalado | El slot `div[@name='wspmp_installments']` queda vacio (no se ve) y las cuotas se siguen viendo donde las pone ADHOC |
| Producto con `prevent_zero_price_sale` (o precio 0) **con el puente de cuotas instalado** | La linea de cuotas se **oculta junto con** el bloque de precio. Es consecuencia de D21: hoy el `div.installment-plans` de ADHOC es **hermano** de `div[name='product_price']` (se inyecta antes de `#product_unavailable`, `extra-addons/odoo_l10n_ar/website_sale_installment_plans/views/website_templates.xml:4`, y ese nodo esta fuera del bloque de precio, `templates.xml:2747`), asi que sobrevive al `d-none`; movido al slot pasa a ser **descendiente** y hereda el `d-none` que el core pone en `div[name='product_price']` (`templates.xml:2699`). Es el comportamiento deseado (sin precio publicable no se publican cuotas), queda anotado para que no se lea como bug del puente |

## Criterios de aceptacion

| # | Criterio | Estado |
|---|----------|--------|
| **CA01** | La pestana Website permite cargar una linea por sitio con los 6 campos | OK |
| **CA02** | `_apply_to_price(664936.10)` con 15 % da 565.195,685; con redondeo 100 da 565.200,00; con 1000 da 565.000,00 | OK |
| **CA03** | Con `price_type='surcharge'` el signo se invierte | OK |
| **CA04** | El porcentaje fuera de 0..100 se rechaza | OK |
| **CA05** | La regla se resuelve desde una marca (`visa`) hacia el primario (`card`) | OK |
| **CA06** | En la **grilla**, la tarjeta muestra de arriba a abajo: el precio sin impuestos nacionales, y dentro del recuadro el precio de lista tachado con el pill `-15% OFF`, el precio del medio en grande y `pagando con **Efectivo/Transferencia**` | OK |
| **CA07** | En la **ficha** del producto, el mismo bloque y el mismo orden que CA06, **en el layout de ficha activo en Nokey**: el core llama `website_sale.product_price` desde dos layouts excluyentes (el normal, `templates.xml:2082`, y la caja de CTA `#o_wsale_cta_wrapper`, `templates.xml:2391`), y T09 verifica cual esta activo y valida ahi | OK |
| **CA08** | Al cambiar de variante se repintan desde el servidor el precio del medio, el pill y la decoracion del recuadro, con el mismo markup que renderiza el template | OK |
| **CA09** | El carrito/checkout muestra debajo del Total una fila por medio con el importe destacado, `pagando con **<medio>**` y el pill (sin recuadro, D23) | OK |
| **CA10** | Con un solo medio, el paso de pago ya se dibuja con el descuento aplicado y su linea de IVA | OK |
| **CA11** | Con varios medios, elegir el del descuento aplica el ajuste y conserva la seleccion | OK |
| **CA12** | Cambiar a otro medio quita el descuento y devuelve el total de lista | OK |
| **CA13** | Cambiar cantidades recalcula el ajuste (15 % del nuevo total) | OK |
| **CA14** | El total cobrado coincide con el precio publicado en la vidriera | OK |
| **CA15** | Las cadenas visibles salen en castellano (`pagando con <medio>`, `-15% OFF`) | OK |
| **CA17** | Un `wspmp_pm` invalido o inexistente no rompe el paso de pago: la pagina arranca normal y el medio se puede elegir a mano | OK |
| **CA16** | Tras la recarga por cambio de medio, el boton de pagar queda habilitado y el formulario inline del medio (p. ej. la tarjeta de Mercado Pago) se despliega, sin volver a tocar el radio | OK (reproducido y verificado en el navegador local, 4-sep-2026) |
| **CA18** | La etiqueta del medio se ve en minusculas (sin `text-transform`) y a 360 px de ancho no se corta, no se trunca con puntos suspensivos y no desborda el recuadro, ni en ficha ni en grilla | OK |
| **CA19** | Sin reglas visibles (o con el producto sin precio) el recuadro **no se decora**: sin borde, sin pill y sin tachado del precio del core, y el precio del core se ve con **su tamaño y su posicion originales** (el contenedor existe igual: la estructura la fija la herencia de la vista, no el dato) | OK |
| **CA20** | El precio sin impuestos nacionales de `l10n_ar_website_sale` se sigue publicando —desde 1.3.1 **debajo** del recuadro y mas chico (D27)— en ficha y grilla, y se sigue repintando al cambiar de variante | OK |
| **CA21** | El recuadro expone `div[@name='wspmp_box']` con el slot `div[@name='wspmp_installments']` en ficha y grilla, y el modulo puente puede mover ahi `div.installment-plans` con un xpath **por `name`** + `position="move"` + `priority="20"` sin tocar este modulo | OK |
| **CA22** | En la grilla, las tarjetas de una misma fila quedan de igual altura y el bloque precio+CTA queda alineado al pie | OK |
| **CA23** | Con `price_type='surcharge'` se muestran precio y etiqueta pero **no** hay pill ni tachado del precio del core | OK |
| **CA24** | Con una regla de descuento visible, el bloque muestra **un precio por renglon**: el de referencia tachado con su pill neutro, el actual tachado con el pill del medio, el precio del medio en grande y `Ahorras $X` en verde (D25) | OK |
| **CA25** | Sin precio de referencia (ni comparativo ni descuento de lista) **no** se pinta el renglon de arriba: no queda un renglon vacio ni un pill suelto | OK |
| **CA26** | A 390 px, en la tarjeta del listado (2 columnas, ~173 px utiles) el precio tachado y su pill entran en el **mismo renglon** | OK |
| **CA27** | El precio sin impuestos nacionales se ve **debajo** del recuadro y en cuerpo chico, en ficha y en tarjeta; en la tarjeta (154 px utiles) la linea **rompe** y no se corta por la derecha | OK |

## Referencias al core

> Anclajes `path:L#` verificados sobre el checkout de v19 (`/home/leandro/projects/nexit/19.0`).
> Rutas absolutas porque en este workspace el core no vive bajo el root del enjambre.

| Que | Anclaje (`path:L#`) | Por que importa |
|-----|---------------------|-----------------|
| Modelo del medio de pago | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/models/payment_method.py:L12` | No tiene `company_id` ni `website_id`: es catalogo global, de ahi la linea por sitio (D2). |
| Form del medio de pago | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/views/payment_method_views.xml:L4` | Tiene `<sheet>` + `<notebook>`: la pestana Website cuelga por herencia. |
| Accion del medio de pago | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/views/payment_method_views.xml:L133` | Filtra `is_primary = True`: la pestana solo se ve en primarios. |
| Datos del catalogo | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/data/payment_method_data.xml:L2` | `noupdate="1"`: la configuracion sobre esos registros sobrevive los upgrades. |
| Reescritura del medio con la marca real | `/home/leandro/projects/nexit/19.0/odoo/addons/payment_mercado_pago/models/payment_transaction.py:L230` | Fundamenta D8: la transaccion puede terminar en `visa`, no en `card`. |
| Medio primario derivado | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/models/payment_transaction.py:L47` | Campo a usar para resolver la regla (compute en L142). |
| Preseleccion del radio | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/views/payment_form_templates.xml:L38` | Condicion que espeja el sync del servidor (D9). |
| Interaccion del formulario de pago | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/static/src/interactions/payment_form.js:L23` | El importe se lee del `dataset` en el setup: fundamenta la recarga (D10). |
| Handler del radio | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/static/src/interactions/payment_form.js:L55` | `selectPaymentOption`, el metodo que se parchea. |
| `willStart` del formulario de pago | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/static/src/interactions/payment_form.js:L36` | Si encuentra un radio marcado despliega el inline form y habilita el boton: es el camino que usa la restauracion (D15). |
| Inline form de Mercado Pago | `/home/leandro/projects/nexit/19.0/odoo/addons/payment_mercado_pago/static/src/interactions/payment_form.js:L33` | `_prepareInlineForm` lee el radio marcado del `document` y monta el brick: exige que la restauracion ocurra antes del super (D15). |
| Arranque de una Interaction | `/home/leandro/projects/nexit/19.0/odoo/addons/web/static/src/public/colibri.js:L51` | Los listeners se enganchan **despues** de `willStart`: fundamenta D15. |
| Colapso de la lista de medios | `/home/leandro/projects/nexit/19.0/odoo/addons/payment/views/payment_form_templates.xml:L91` | `#o_payment_methods` nace `collapse` cuando hay tokens. |
| Chequeo de importe al crear la transaccion | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/controllers/payment.py:L64` | Aborta si el form y `amount_total` difieren: es el candado que obliga al flujo. |
| Precio de la grilla | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/models/product_template.py:L389` | Hook de la vidriera en el listado. |
| Precio de la ficha | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/models/product_template.py:L584` | `_get_additionnal_combination_info`, marcado por el core como punto de override. |
| Impuestos del precio del sitio | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/models/product_template.py:L693` | `_apply_taxes_to_price`: fundamenta D5. |
| Config de IVA del sitio | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/models/website.py:L70` | `show_line_subtotals_tax_selection`. |
| jsonrpc de variantes | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/controllers/variant.py:L8` | Descarta claves (L33): `payment_method_prices` sobrevive. |
| Mixin copiado al prototipo | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/static/src/interactions/website_sale.js:L651` | `Object.assign`: fundamenta D11. |
| Repintado de precios en JS | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/static/src/js/variant_mixin.js:L269` | `_onChangeCombination`; patron a copiar en L346. |
| Template de precio de la ficha | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/templates.xml:L2696` | `website_sale.product_price`. |
| Template de la tarjeta | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/product_tile_templates.xml:L186` | Bloque de precio del listado. |
| Template de totales | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/templates.xml:L4085` | `website_sale.total`, fila por medio debajo del Total. |
| Descuento global (wizard) | `/home/leandro/projects/nexit/19.0/odoo/addons/sale/wizard/sale_order_discount.py:L147` | `_prepare_global_discount_lines`: reparto por combinacion de impuestos (D6). |
| Reparto del importe fijo | `/home/leandro/projects/nexit/19.0/odoo/addons/account/models/account_tax.py:L3659` | El importe fijo se compara contra `total_excluded + tax_amount`: es total CON impuestos (D7). |
| Base descontable de las recompensas | `/home/leandro/projects/nexit/19.0/odoo/addons/sale_loyalty/models/sale_order.py:L339` | Resta `_get_no_effect_on_threshold_lines()`: el hook que usa D16. |
| Un renglon por grupo de impuesto | `/home/leandro/projects/nexit/19.0/odoo/addons/sale_loyalty/models/sale_order.py:L637` | El cupon arma una linea por clave de `discountable_per_tax` (D16). |
| Precedente del mismo hook | `/home/leandro/projects/nexit/19.0/odoo/addons/sale_loyalty_delivery/models/sale_order.py:L22` | El core excluye asi las lineas de envio. |
| Redondeo de listas de precios | `/home/leandro/projects/nexit/19.0/odoo/addons/product/models/product_pricelist_item.py:L126` | Semantica de `price_round` que se espeja (D4). |
| Orden del calculo | `/home/leandro/projects/nexit/19.0/odoo/addons/product/models/product_pricelist_item.py:L606` | descuento -> redondeo -> recargo. |
| Linea de envio | `/home/leandro/projects/nexit/19.0/odoo/addons/delivery/models/sale_order_line.py:L9` | `is_delivery`, usado por `applies_to`. |
| Recompute del carrito | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/models/sale_order.py:L932` | `_recompute_cart`, hook del reajuste. |
| Bloque de precio de la ficha | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/templates.xml:2697` | `div[name='product_price']`: el padre donde el recuadro entra `inside` (y queda **ultimo hijo**); es tambien el `//div[1]` que usa la AR (D18). |
| `d-none` del bloque de precio | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/templates.xml:2699` | `t-attf-class` con `d-none` si `prevent_zero_price_sale`, sobre un padre `d-inline-block`: todo lo que viva adentro del bloque desaparece con el (edge case de las cuotas). |
| Ficha: layout normal | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/templates.xml:2082` | `t-call` de `website_sale.product_price` cuando **no** esta activa `website_sale.cta_wrapper_boxed`. |
| Ficha: layout caja de CTA | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/templates.xml:2391` | El otro `t-call`, dentro de `#o_wsale_cta_wrapper`: son excluyentes y T09 valida el que este activo (CA07). |
| Nodo hermano del bloque | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/templates.xml:2747` | `#product_unavailable` esta **fuera** de `div[name='product_price']`: por eso las cuotas de ADHOC hoy sobreviven al `d-none` y, movidas al slot, ya no. |
| Contenedor de precio de la ficha | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/templates.xml:2701` | `div[name='product_price_container']`: el nodo que se **mueve** dentro del recuadro (D19); trae `justify-content-end` y clases de tamaño propias (`/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/templates.xml:2703`) que el CSS del recuadro normaliza. |
| Precio de la ficha (nodo) | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/templates.xml:2705` | `span.oe_price` con `combination_info['price']`: el precio que se tacha. No se duplica. |
| Precio de lista de la ficha | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/templates.xml:2709` | `span.oe_default_price` con `combination_info['list_price']`, gateado por `has_discounted_price`: viaja movido con su contenedor. |
| Precio comparativo de la ficha | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/templates.xml:2717` | `del[name='product_price_strikethrough']` con `compare_list_price`: idem. |
| Bloque de precio de la tarjeta | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/product_tile_templates.xml:191` | `div.product_price`: el contenedor donde se agrega el recuadro en la grilla. |
| Precio de la tarjeta (nodo) | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/product_tile_templates.xml:192` | El `span` con `price_reduce` (`aria-label="Sale price"`, `class="mb-0 fw-bold"`): no tiene `name`, y `aria-label` **no sirve** como selector de herencia (es un atributo traducible, `TRANSLATED_ATTRS` en `odoo/tools/translate.py:75`; la validacion de vistas lo rechaza con `ValueError` — "View inheritance may not use attribute 'aria-label' as a selector", `ir_ui_view.py:412` — y aborta la carga con `ParseError`, verificado al ejecutar T03). El `move` usa la clase propia: `//div[hasclass('product_price')]//span[hasclass('fw-bold')]`, unica dentro del bloque de precio combinado. |
| Precio base de la tarjeta | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/product_tile_templates.xml:199` | `t[name='product_base_price']` con `base_price`: el tachado que el core ya trae, se mueve con el precio. |
| Repintado de precios del core | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/static/src/js/variant_mixin.js:346` | Busca `.oe_price` / `.oe_default_price` **dentro de `parent`**: mover el nodo a otro lugar del mismo contenedor no lo rompe. |
| Fila del Total del carrito | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/templates.xml:4140` | `tr[name='o_order_total']`, ancla de la fila por medio (D23). |
| Alto de la tarjeta | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/views/product_tile_templates.xml:118` | `div.o_wsale_product_information` ya es `flex-grow-1`: el CSS de D22 solo tiene que pegar `o_wsale_product_sub` al pie. |
| Layout de la tarjeta | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/static/src/scss/product_tile.scss:289` | `.o_wsale_product_sub`: `display: var(--o-wsale-card-sub-display, flex)` (row, `align-items: end`) con precio y CTA: el bloque que se ancla abajo. |
| `o_wsale_product_sub` puede ser `contents` | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/static/src/scss/product_tile.scss:186` | Lo anota el propio core: con `display: contents` ese nodo no genera caja y `margin-top: auto` sobre el **no hace nada** (D22). |
| Hijos flex de la tarjeta | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/static/src/scss/product_tile.scss:169` | `.o_wsale_product_information` es `display: flex` en columna: con `contents`, precio y CTA pasan a ser **sus** hijos directos y ahi va el anclaje al pie (D22). |
| `display` del bloque de precio de la tarjeta | `/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/static/src/scss/product_tile.scss:298` | `.product_price` usa `var(--o-wsale-card-price-display)` **sin fallback** (por eso la AR pone `d-block` en su `<small>`): el recuadro fija su propio layout. |
| `position="move"` | `/home/leandro/projects/nexit/19.0/odoo/odoo/tools/template_inheritance.py:45` | El nodo se **extrae** del arbol y se reinserta (no se copia: no hay precio duplicado), pero el `move` se procesa **solo como hijo directo** del spec: anidado mas adentro del markup nuevo queda como XML literal en el arch, sin error. |
| `move` con contenido | `/home/leandro/projects/nexit/19.0/odoo/odoo/tools/template_inheritance.py:137` | `extract` tira `ValueError` si el spec del `move` tiene hijos: el `<xpath ... position="move"/>` va **vacio**. |
| Locator que no matchea | `/home/leandro/projects/nexit/19.0/odoo/odoo/tools/template_inheritance.py:343` | `ValueError`: xpathear un nodo de un modulo que podria no estar instalado **rompe** la vista. Funda D18 (no se toca el `<small>` de la AR). |
| Orden de las vistas heredadas | `/home/leandro/projects/nexit/19.0/odoo/odoo/addons/base/models/ir_ui_view.py:758` | `ORDER BY v.priority, v.id`: por eso `priority="18"` garantiza aplicar despues de la AR (D18). |
| Prioridad por defecto | `/home/leandro/projects/nexit/19.0/odoo/odoo/addons/base/models/ir_ui_view.py:148` | `priority` default 16: el que traen la AR y ADHOC. |
| `priority` en el tag `<template>` | `/home/leandro/projects/nexit/19.0/odoo/odoo/tools/convert.py:508` | El atributo se escribe de verdad en `ir.ui.view.priority`: `priority="18"` no es decorativo (D18). |
| `class` vs `t-attf-class` en el render | `/home/leandro/projects/nexit/19.0/odoo/odoo/addons/base/models/ir_qweb.py:1946` | Los `t-attf-*` se compilan **despues** de los atributos estaticos y pisan el mismo nombre: el token de clase hay que repetirlo dentro del `t-attf-class` (D21). |
| `hasclass()` en los xpath | `/home/leandro/projects/nexit/19.0/odoo/odoo/addons/base/models/ir_ui_view.py:83` | Lee **solo** el atributo estatico `class`: sirve para el `div.product_price` de la grilla (clase estatica del core) y **no** para el recuadro, que lleva `t-attf-class` (D21). |
| Precio sin impuestos nacionales (ficha) | `/home/leandro/projects/nexit/19.0/odoo/addons/l10n_ar_website_sale/views/templates.xml:5` | El `<small>` "Precio s/Imp. Nac.:" que la AR **agrega al final** del bloque de precio (xpath `//div[1]`, position `inside` por defecto): por eso queda arriba del recuadro sin moverlo (D18). |
| Precio sin impuestos nacionales (grilla) | `/home/leandro/projects/nexit/19.0/odoo/addons/l10n_ar_website_sale/views/templates.xml:25` | Idem en la tarjeta, dentro de `div.product_price`. |
| Repintado del precio s/Imp. Nac. | `/home/leandro/projects/nexit/19.0/odoo/addons/l10n_ar_website_sale/static/src/interactions/website_sale.js:10` | Otro `patch` de `_onChangeCombination` que busca `.o_l10n_ar_price_tax_excluded` dentro de `parent`: no se pisa con el nuestro (CA20). |
| La AR es `auto_install` | `/home/leandro/projects/nexit/19.0/odoo/addons/l10n_ar_website_sale/__manifest__.py:23` | Se instala sola con `l10n_ar` + `website_sale`: no hace falta (ni conviene) declararla en `depends`. |
| Cuotas ADHOC en la ficha | `extra-addons/odoo_l10n_ar/website_sale_installment_plans/views/website_templates.xml:4` | `div.installment-plans` insertado antes de `#product_unavailable` (hermano del bloque de precio): el nodo que mueve el puente al slot (D21). |
| Cuotas ADHOC en la grilla | `extra-addons/odoo_l10n_ar/website_sale_installment_plans/views/website_templates.xml:21` | Idem dentro de `div.product_price`. |
| `depends` del puente | `extra-addons/odoo_customization_sunra/website_sale_installment_plans_ux/__manifest__.py:20` | Hoy solo declara `website_sale_installment_plans` y no tiene `views/`: su tarea 1.1.0 tiene que sumar `website_sale_payment_method_price` (D21). |
| Ancla del bloque en 1.1.0 (a reemplazar) | `views/website_sale_templates.xml:10` | Hoy cuelga de `//div[@name='product_price_container']` con `position="after"`: con el recuadro eso dejaria el `<small>` de la AR abajo (D18). |

## Documentacion afectada

| Archivo | Que se actualiza |
|---------|------------------|
| `README.md` del modulo | Version `1.3.0`; la seccion *La vidriera* describe los 7 renglones de la maqueta nueva y aclara que el renglon de referencia **depende de un dato** (Precio comparativo / descuento de lista), no de codigo; la nota de "los pills viven siempre en el DOM" distingue ficha (siempre, con `d-none`) de grilla (`t-if`); *Validacion manual* suma el paso del precio comparativo y el corte a 390 px |
| `static/description/index.html` | Blurb, tabla de funcionalidades y ejemplo con la maqueta nueva (renglones, `Ahorras`), y la nota tecnica suma el `position="replace"` + `$0` al lado del `move` |
| `README.md` del repo | Fila del modulo con la descripcion nueva del recuadro |
| `__manifest__.py` | `version` `1.3.0`; `summary` y `description` con la maqueta nueva |
| Esta spec | D25/D26, CA24–CA26, la firma de `_get_payment_method_price_vals()`, el helper nuevo `_get_payment_method_reference_badge()`, la tabla de Vistas y el plan T01–T07 |

## Plan del cambio en curso

> **1.3.1 (15-09-2026)** — ajuste de la clienta sobre el precio sin impuestos nacionales (D27). El
> plan de 1.3.0 (T01..T07, segunda maqueta del bloque) esta cerrado y no se repite aca.

| Tarea | Descripcion | Depende de | Archivos | Cubre | Estado |
|-------|-------------|-----------|----------|-------|--------|
| **T01** | SCSS: el contenedor del precio pasa a columna (`display: flex !important` + `align-self: stretch`) y el `<small>` de la AR va al final con `order: 1`, mas chico y gris. El selector cubre `.product_price` **y** `.o_l10n_ar_product_price` (en la tarjeta el core pierde la clase estatica, ver D27). Padding lateral del recuadro de la tarjeta a 0.5rem para recuperar los 11 px que necesita el renglon del precio tachado con su pill | — | `static/src/scss/payment_method_price.scss` | CA20, CA27 | hecho |
| **T02** | Bump del manifest a 1.3.1, sync de la `Version` de la spec y doc (README + index.html) | T01 | `__manifest__.py`, `specs/...md`, `README.md`, `static/description/index.html` | — | hecho |
| **T03** | Verificacion en el navegador a 390 px, ficha y tarjeta, midiendo que el `<small>` quede **debajo** del recuadro y que no se corte | T01 | — | CA20, CA27 | hecho |

## Notas de implementacion

- **Minimal footprint**: no se reimplementa nada que el core ya haga. El reparto del descuento por
  grupo de impuesto, el redondeo, el formateo de moneda y la deteccion de medios compatibles son
  todos del core; el modulo aporta la configuracion, el calculo del objetivo y el pegamento.
- **Atajo deliberado (D10)**: recargar el paso de pago completo en vez de re-renderizar el fragmento.
  La alternativa es reconstruir a mano el contexto de pago del formulario, mucho mas fragil por poco
  beneficio.
- **Tercera trampa, encontrada en produccion (4-sep-2026)**: la restauracion de la seleccion se hacia
  con `radio.click()` **despues** del `super.willStart()`. Como los listeners de la interaccion se
  enganchan recien cuando `willStart` resuelve, ese click no ejecutaba `selectPaymentOption`: el radio
  quedaba marcado pero el boton de pagar deshabilitado y el formulario de tarjeta sin montar. El
  cliente lo vivia como "el boton de pagar queda trabado"; se destrababa eligiendo otro medio y
  volviendo (ese segundo click si tiene listener). Corregido en 1.0.1 (D15).
- **Riesgos conocidos anotados en la review de 1.0.1 (no corregidos, con su porque)**:
  - `wspmp_pm` lleva solo el id, sin el tipo de opcion. Un `payment.token` con el mismo id
    numerico que el medio elegido restauraria el radio equivocado (los tokens se renderizan
    primero). Verificado el 4-sep-2026 en PROD: `payment_token` esta **vacio** (0 filas), asi que
    hoy no puede pasar; si algun dia se guardan tarjetas, mandar tipo+id en el parametro.
  - Si el SDK de Mercado Pago no carga (adblock, caida del CDN), el `willStart` del core rechaza
    y el formulario queda inerte en vez de degradar solo ese medio. Es el mismo comportamiento
    que el core tiene cuando hay un solo medio de pago; sin alternativa dentro del alcance.
- **Dos trampas encontradas en vivo, no por lectura**: el patch del mixin que no tenia efecto (D11) y
  la pelea entre el sync del servidor y la eleccion del cliente (D9). Las dos aparecieron probando en
  el navegador, no revisando codigo: cualquier cambio en esta zona se valida en el sitio, no solo en
  el shell.
- **Tests automaticos**: `odoo_customization_sunra` no tiene `.swarm.conf`, asi que rige el default
  del repo (no se escriben tests salvo pedido). Los candidatos naturales, si se piden, son
  `_apply_to_price` (signo y redondeo) y `_get_payment_price_amount` (bases con y sin impuestos).
- **Rediseño 1.2.0 — minimal footprint**: el bloque **no recalcula ni duplica** ningun precio. La
  grilla ya trae `price_reduce` y `base_price`, y la ficha `price` y `list_price`: el recuadro se arma
  **moviendo** los nodos que el core ya renderiza (`position="move"`) y decorandolos por CSS. Lo unico
  que se agrega al dato es el texto del pill y el nombre del medio.
- **Especificidad CSS, sin `!important`**: el precio del core viene con clases de tamaño del core
  (`h5` en la ficha, `fw-bold` en la tarjeta). Los selectores del recuadro
  (`.o_wspmp_box_active [name='product_price_container']`, `.o_wspmp_box_active .oe_price`) tienen dos
  componentes y le ganan a una clase suelta: alcanza para achicar y tachar sin forzar nada. El tachado
  cuelga ademas de `.o_wspmp_discounted`, que no se pone con recargo (CA23).
- **Locators: `name` para los xpath, clases para CSS/JS**: el recuadro y el slot se ubican por atributo
  `name` porque `hasclass()` no ve las clases dinamicas (D21); las clases siguen existiendo (y se repiten
  dentro del `t-attf-class`) porque el CSS y el JS si las leen del DOM ya renderizado.
- **Lo que hay que mirar en el navegador y no se ve leyendo** (el precedente de este modulo son dos
  trampas encontradas en vivo): (a) que el `<small>` de la AR realmente quede arriba del recuadro con
  `priority="18"` — el orden final lo resuelve la combinacion de vistas, no el archivo; (b) que el
  repintado del core (`/home/leandro/projects/nexit/19.0/odoo/addons/website_sale/static/src/js/variant_mixin.js:346`) siga encontrando `.oe_price` despues del `move`; (c) que
  el CSS de igual altura (D22) no pelee con los custom properties `--o-wsale-card-*` del tema.
- **Vistas editadas a mano desde el editor web (copias COW del sitio)** — verificado en la base local (copia de
  produccion del 09-09-2026). El sitio Nokey (`website_id=1`) tiene copias por sitio
  (`ir_ui_view.website_id=1`, `arch_updated=true`) de dos templates que este modulo hereda o toca:
  - `website_sale.products_item` (vista **19099**, editada el 07-08-2026; el arch lleva el comentario
    «centrar precio 7-08-2026»): `.o_wsale_product_information` con `text-center` y `.o_wsale_product_sub` de
    `justify-content-between gap-2` a `justify-content-center flex-column align-items-center gap-2`.
  - `website_sale.delivery_method` (vista **19910**, 02-09-2026): el badge de precio quedo como texto fijo
    «Gratis» en `es_AR`. Lo resolvio el modulo `website_sale_delivery_price_label` —no es de esta spec—; se cita
    como **evidencia del patron**: en este sitio se edito mas de un template desde el editor.

  Consecuencias para este modulo: **(1)** la herencia de vistas se aplica **sobre la copia por sitio y en el
  idioma del sitio (`es_AR`)**, no sobre la generica — el `-i`/`-u` pasa igual y el error aparece solo al
  renderizar el sitio; **(2)** todos los locators de la grilla tienen que existir en el arch `es_AR` de la copia
  19099 — **verificado**: `div.product_price`, `span[hasclass('fw-bold')]`, `t[@name='product_base_price']`,
  `.o_wsale_product_sub` y `.o_wsale_product_information` estan; **(3)** D22/T06: se asume que en el sitio
  `.o_wsale_product_sub` es `flex-column` centrado y el SCSS del modulo es **dueno del centrado** del bloque de
  precio, para que la copia COW se pueda restablecer a la generica y el layout quede versionado (el
  restablecimiento de las dos copias corre **en produccion, dentro de Plane #68**, no en este modulo);
  **(4)** T09 valida **sobre la vista del sitio** (`website_id=1`, `lang=es_AR`), nunca sobre la generica;
  **(5)** al instalar/actualizar, Odoo crea automaticamente copias por sitio de **nuestras** vistas heredadas,
  colgadas de la COW (`arch_updated=false`, se propagan en cada `-u`): es el comportamiento esperado, no es un
  problema.
- **Riesgo conocido del orden de vistas**: D18 se apoya en que `l10n_ar_website_sale` y ADHOC usan la
  `priority` por defecto (16). Si alguna subiera de 18, el `<small>` de la AR o la linea de cuotas
  quedarian **debajo** del recuadro. Es visual, no rompe nada, y se corrige subiendo nuestra
  `priority`.
- **Implementado 11-09-2026 (1.2.0)** — ajustes tecnicos sobre lo planeado en T02/T03/T05, en dos
  rondas, sin cambiar ninguna decision (D1..D24) ni el contrato de locators (D21):
  - **`aria-label` no sirve como selector de herencia.** Es un atributo traducible
    (`TRANSLATED_ATTRS`, `odoo/tools/translate.py:75`) y Odoo 19 lo rechaza con `ValueError` ("View
    inheritance may not use attribute 'aria-label' as a selector", `ir_ui_view.py:412`), que aborta
    la carga del modulo con `ParseError`. El `move` de T03(b) usa en cambio
    `//div[hasclass('product_price')]//span[hasclass('fw-bold')]` (la clase `fw-bold` del propio
    span, unica dentro del bloque de precio combinado). Verificado con `-u`: sin este cambio el
    modulo no instala.
  - **La misma trampa en CSS y JS, encontrada en la verificacion visual (2da ronda, 11-09-2026).**
    A diferencia del xpath, un selector CSS por `aria-label` **no tira error**: simplemente no
    matchea nunca, porque en render el atributo sale traducido (`aria-label="Precio de venta"` en
    es_AR, no el string en ingles del arch fuente). Sintoma en la grilla: el precio de lista
    quedaba **sin tachar y al final** del recuadro (ni `order: -1` ni `text-decoration` aplicaban).
    Corregido: los selectores de `payment_method_price.scss` van por `span.fw-bold` / `del` (hijo
    directo del recuadro) y el comentario de `payment_method_price.js` ya no menciona
    `[aria-label]`.
  - **El recuadro usa `display: contents` / `display: flex`, no `display: block`.** El `move`
    agrega el precio de lista tachado **antes del slot** (T02/T03, ver el punto siguiente); dentro
    del recuadro activo hace falta reordenarlo visualmente al frente con `order: -1` — una
    propiedad que solo aplica a items flex/grid, no a `display: block`. El recuadro es
    `display: contents` por defecto (transparente para el layout: satisface CA19 sin CSS
    adicional) y `display: flex; flex-direction: column` bajo `.o_wspmp_box_active`, con
    `width: 100%` en la grilla para no depender de `--o-wsale-card-price-display`. El pill se
    renderiza **siempre** en el DOM (oculto con `d-none` si no aplica) para que el JS de T07 solo
    tenga que togglear clases/texto sobre el, nunca crearlo ni destruirlo, igual que sobre
    `o_wspmp_box` y el slot.
  - **El `move` cambio de destino: `before` del slot, no `inside` del recuadro (2da ronda).** Con
    `position="inside"` sobre `wspmp_box`, el precio de lista quedaba **despues** del slot en el
    DOM; en el estado **inactivo** (`display: contents`, sin reglas visibles, CA19) `order: -1` no
    tiene ningun efecto, asi que las cuotas de ADHOC (que el puente ya movio al slot) aparecian
    **arriba** del precio del core — un cambio de posicion real respecto del original, no solo
    cosmetico con el recuadro activo. Corregido: T02(b)/T03(b)/T03(c) apuntan a
    `<xpath expr="//div[@name='wspmp_installments']" position="before">` (el `move` sigue siendo
    hijo directo y vacio: `add_stripped_items_before` procesa `before` igual que `inside`). DOM
    resultante, verificado por `odoo shell` (COW 19099 y `product_price`/`products_item`
    genericas): badge -> precios -> precio de lista (ficha) / precio actual + precio de lista
    tachado (grilla) -> slot, en **ambos** estados (activo e inactivo).
  - **Alineacion del precio de lista en la ficha (2da ronda).** El nodo movido
    (`product_price_container`) trae `justify-content-end` del core como utilidad de Bootstrap
    (`templates.xml:2701`), que Bootstrap declara con `!important`: el `justify-content: flex-start`
    original (sin `!important`) no le ganaba (medido: `flex-end` computado). Corregido con el propio
    `!important`, comentado en el SCSS con el porque (unica excepcion a "sin `!important`" del
    resto del modulo, justificada).
  - **El `<small>` de impuestos nacionales (D18) se ve chico y gris (2da ronda).** Medido en la
    ficha: 16px/700 (el tema no lo achica ahi, a diferencia de la grilla). D18 prohibe mover o
    editar ese nodo; se lo estiliza por CSS, acotado a `[name='product_price'] > small` (el atributo
    `name` solo existe en el wrapper de la ficha, asi que no afecta la grilla).
  - **T06 (igual altura de la grilla)**: no se hizo verificacion visual en navegador en esta pasada
    (la paleta local es la de Sunra y no sirve para juzgar, y la verificacion visual queda para el
    orquestador). El SCSS cubre **los dos casos** que anota el propio core (`flex` y `display:
    contents` de `.o_wsale_product_sub`, `product_tile.scss:186/289`): cual usa el tema de Nokey se
    confirma en esa pasada visual, sin que haga falta tocar el CSS.

- **Ronda de correcciones post-review (11-09-2026), sin cambiar ninguna decision** — 3 IMPORTANTES
  y varios MENORES de la revision de @reviewer sobre 1.2.0 (Plane #63), cerrados en la misma tarea:
  - **I1 (la mas importante)**: ver el fix documentado en D22 arriba — el CSS de igual altura de la
    grilla no tenia scope ni especificidad para cumplir esa decision (medido: se filtraba a Sunra y
    era inerte frente al core en los dos sitios). Corregido con `:has(.o_wspmp_box_active)` +
    prefijo `.oe_product_cart`; ademas `justify-content` necesito su propio `!important` porque el
    template generico trae `justify-content-between` (utilidad Bootstrap, `!important`) directo en
    el markup. Verificado con Playwright simulando el restablecimiento completo de la copia COW.
  - **M1**: `_order` de `payment.method.website.price` paso de `payment_method_id, sequence, id` a
    `sequence, payment_method_id, id` (la spec y RB09 dicen que el orden es por `sequence`).
  - **M2**: los dos renglones de esta spec que todavia citaban `span[@aria-label='Sale price']`
    como locator vigente/verificado se corrigieron a `span[hasclass('fw-bold')]` (el real desde
    T03, ver Notas de implementacion arriba).
  - **M3**: `[name='product_price'] > small` matcheaba tambien el `tax_disclaimer` del core
    (hermano directo dentro del mismo wrapper) y se aplicaba siempre, incluso sin ninguna regla
    visible (rompia CA19: cambiaba de tamano/peso aun con `show_on_website=false`). Acotado a
    `:has(.o_wspmp_box_active)` y, dentro de ese estado, solo al `<small>` de la AR (distinguido
    por el span propio `.o_l10n_ar_price_tax_excluded`, que el `tax_disclaimer` del core no trae).
  - **M4**: `controllers/website_sale_payment_method_price.py` no guardaba el `int()` de `token_id`
    ni de `payment_method_id`: un valor no numerico desde el cliente (la ruta es publica) tiraba
    `ValueError` sin capturar -> 500. Envuelto en `try/except (TypeError, ValueError)`, devolviendo
    el mismo vacio (`None` / recordset vacio) que ya usaba cada funcion.
  - **M5**: la clase `o_wspmp_box_pdp` (recuadro de la ficha) no se usaba en ningun selector de
    CSS ni de JS; se saco de la vista (`views/website_sale_templates.xml`).
  - **M9**: `ProductTemplate._get_sales_prices` ejecutaba el `search` de reglas del sitio aunque
    `self` (los templates a procesar) estuviera vacio. El corte temprano por `self` vacio se movio
    antes del `search`.
  - M7 y M8, y el ajuste de `index.html` (etiqueta de 1.1.0 dada de baja en T08) y del README raiz
    del repo, son correcciones de **documentacion** (de este modulo y de
    `website_sale_installment_plans_ux` / `website_sale_variant_code`) sin cambios de codigo en
    `website_sale_payment_method_price`.
