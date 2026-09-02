# website_sale_grid_quantity

Agrega el selector de cantidad con botones de **más** y **menos** en cada tarjeta del listado de la
tienda, para que el cliente elija cuántas unidades quiere sin entrar a la ficha del producto.

Se activa **por sitio web**.

## El problema

En un catálogo de repuestos, un pedido no es un artículo: son 10 o 15 distintos, y de varios de
ellos el concesionario quiere 3, 5 o 20 unidades.

Odoo trae el selector de cantidad en la **ficha del producto** y en el **carrito**, pero en el
listado solo tiene el botón *Agregar al carrito*, que agrega **una** unidad. Para pedir 5 hay que
entrar al producto, cambiar la cantidad, agregar, volver al listado, y repetir por cada artículo.
Con 15 artículos son 15 idas y vueltas.

## Qué hace el módulo

En cada tarjeta del listado, entre el precio y el botón de agregar, aparece:

```
[ − ]  [  1  ]  [ + ]
```

El cliente fija la cantidad ahí mismo y agrega al carrito de una sola vez. El mínimo es 1 (el `−`
no baja de ahí).

### Activarlo

**Ajustes → Sitio Web → Comercio electrónico → «Selector de cantidad en el listado de productos»**

Al ser por sitio web, un sitio B2B de concesionarios lo puede tener prendido y el sitio al
consumidor final apagado, aunque compartan la misma base.

## Cómo funciona

**El módulo no agrega JavaScript.** Solo agrega el markup, porque el core ya trae todo el
comportamiento y lo engancha por selector CSS. Esto es deliberado: es lo que hace que el módulo
sobreviva a una actualización de Odoo sin mantenimiento.

Las tres piezas del core que se reutilizan (`website_sale/static/src/interactions/website_sale.js`):

| Pieza del core | Cómo se aprovecha |
|---|---|
| `static selector = '.oe_website_sale'` | La interacción cubre la página de tienda, listado incluido. |
| `'a.js_add_cart_json': { 't-on-click.prevent': this.onChangeQuantity }` | El manejador de `+`/`−` se enlaza **por selector**, no por posición. Alcanza con que los enlaces tengan esa clase, estén dentro de un `.input-group` y el de restar se llame `remove_one`. |
| `_updateRootProduct(form)` | Lee la cantidad de `input[name="add_qty"]` dentro del form de la tarjeta. El *Agregar al carrito* del listado ya pasa por acá. |

Por eso los nombres `add_qty` y `remove_one` y la clase `js_add_cart_json` **no son decorativos:
son el contrato con el core**. Si una versión futura de Odoo los cambia, el selector deja de
enganchar y los botones dejan de responder (sin error visible) — es lo primero a revisar ante una
actualización.

El contenedor usa la clase propia `o_wsale_grid_quantity` en lugar de la `css_quantity` de la
ficha, para que la lógica de variantes de la página de producto (`variant_mixin`) no pueda alcanzar
este bloque.

## Productos con variantes

Desde la tarjeta no hay combinación elegida, así que el core abre el configurador de producto al
agregar. La cantidad del listado viaja al configurador dentro de `rootProduct`.

## Validación manual

1. Prender el ajuste en el sitio y abrir la tienda.
2. En una tarjeta, tocar `+` tres veces: el número debe pasar a 4.
3. Tocar `−` varias veces: tiene que frenar en 1, no bajar a 0 ni a negativo.
4. Dejarlo en 4 y *Agregar al carrito*: la línea del carrito debe quedar con **cantidad 4**.
5. Probar un producto **con variantes**: al agregar se abre el configurador y la cantidad elegida
   tiene que llegar igual.
6. En el otro sitio web, con el ajuste apagado: el listado debe quedar **idéntico** a antes.
