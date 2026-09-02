# website_sale_stock_level_indicator

Muestra un cartel con el **nivel de stock** de cada producto en el listado de la tienda y en la
ficha: *sin stock*, *poco stock*, *stock normal*, *stock alto*.

Los niveles se configuran **por sitio web**: el texto, el color y la cantidad a partir de la cual
aplica cada uno. La cantidad de niveles es libre.

## El problema

El comprador de repuestos necesita saber, de un vistazo y sin abrir cada producto, si hay
disponibilidad. Un número exacto de unidades no sirve —es información interna y cambia todo el
tiempo—, pero un semáforo sí.

Odoo trae solo **dos estados** (`website_sale_stock`): un cartel rojo *Sin existencias* y un cartel
amarillo cuando la cantidad baja de un umbral. Y en el **listado no muestra nada**: hay que entrar
al producto para saber si hay.

## Qué hace el módulo

### Configuración

**Ajustes → Sitio Web → Comercio electrónico → «Indicador de nivel de stock»**

Al prenderlo aparece la lista de niveles del sitio. Una línea por nivel:

| Campo | Qué es |
|---|---|
| **Desde cantidad** | El nivel aplica cuando la disponibilidad llega a este número y no llega al siguiente. |
| **Etiqueta** | El texto del cartel. Es **traducible**: se puede poner *Poco stock*, *Pocas unidades*, *Últimas unidades* o lo que use el negocio. |
| **Color** | Una de las clases contextuales de Bootstrap (rojo, naranja, verde, celeste, azul, gris, negro), para que el cartel herede el tema del sitio. |
| **Color personalizado** | Opcional. Un color CSS libre (ej. `#B4E933`) para un color de marca que no esté en la lista. Si está cargado, gana sobre el anterior. |

Configuración de ejemplo, que es la que se usa en Sunra:

| Desde cantidad | Etiqueta | Color |
|---|---|---|
| 0 | Sin stock | rojo |
| 1 | Poco stock | naranja |
| 11 | Stock normal | celeste |
| 101 | Stock alto | verde |

### Resolución

Gana el nivel de **mayor «desde cantidad» que la disponibilidad alcanza**. Con la tabla de arriba:
`0` → *Sin stock*, `7` → *Poco stock*, `50` → *Stock normal*, `500` → *Stock alto*.

Un solo número por nivel, en lugar de un par mínimo/máximo, hace imposible por construcción que
queden huecos o rangos solapados. Y como la cantidad de niveles es libre, más adelante se puede
agregar un quinto (por ejemplo *Por ingresar*, para productos con orden de compra pendiente) sin
tocar código.

### Dónde aparece

- **Listado de la tienda**: arriba del título de la tarjeta. Describe la variante que la tarjeta ya
  está mostrando, que es la que su botón agrega al carrito — no un agregado de todas las variantes,
  que sería engañoso.
- **Ficha de producto**: debajo del título, y **cambia al elegir otra variante** sin recargar.

### Qué no lleva cartel

- Los productos **no almacenables** (servicios, consumibles): no tienen disponibilidad que medir.
  Es el mismo criterio del core.
- Cualquier producto, si el sitio tiene el indicador apagado o no tiene niveles configurados. En
  ese caso el comportamiento del core queda intacto.

## Cómo funciona

### La disponibilidad se mide con el depósito del sitio

Se usa `website._get_product_available_qty()`, el mismo helper que el resto del eCommerce, que
resuelve `free_qty` en el depósito configurado en el sitio (`website.warehouse_id`). Con dos sitios
web en la misma base y depósitos distintos, cada uno mira el suyo.

El stock negativo (sobreventa) se pisa en cero: para el que compra es simplemente sin stock.

### El listado resuelve las cantidades en una sola consulta

`product.template` **no tiene** `free_qty` en Odoo 19 (solo `product.product`), y el helper del core
recibe un registro suelto. Llamarlo por tarjeta hace N+1: cada `with_context()` sobre un registro
abre su propio bucket de caché y rompe el prefetch, así que una grilla de repuestos terminaría
haciendo una consulta por producto.

Por eso `website._get_variant_stock_level()` recibe además **todas** las variantes que se están
renderizando —el diccionario `product_variants` que ya arma el controller de la tienda— y resuelve
la página entera de una vez; las tarjetas siguientes salen de caché.

### La ficha sigue a la variante elegida

La página de producto se renderiza para la **plantilla**, así que el único lugar donde se sabe qué
variante quedó seleccionada es el payload de `/website_sale/get_combination_info`. El módulo le
agrega `stock_level_name`, `stock_level_class` y `stock_level_style`, y un parche de
`_onChangeCombination` repinta el cartel.

El cartel va debajo del título y **no** dentro del `div.availability_messages` del core: ese
contenedor lo reescribe entero el JS de disponibilidad de `website_sale_stock` y borraría el nodo.

## Validación manual

1. Prender el indicador en el sitio y cargar los cuatro niveles de la tabla de ejemplo.
2. Poner en un producto cantidades de 0, 5, 50 y 500 y confirmar que el cartel pasa por *Sin
   stock*, *Poco stock*, *Stock normal* y *Stock alto*.
3. Cambiarle el texto a un nivel (ej. *Poco stock* → *Pocas unidades*) y confirmar que el cartel lo
   refleja.
4. Abrir un producto con variantes y cambiar de variante: el cartel tiene que cambiar sin recargar.
5. Abrir un **servicio**: no debe aparecer ningún cartel.
6. Configurar depósitos distintos en cada sitio web y confirmar que cada uno mira el suyo.
7. En el otro sitio web, con el indicador apagado: el listado y la ficha quedan **idénticos** a
   antes.
