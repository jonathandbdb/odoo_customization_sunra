# website_sale_variant_code

Mostrar en el eCommerce el **código interno de la variante que el cliente está mirando**, en lugar de
una leyenda fija con los códigos de todas las variantes.

- **Versión**: 1.0.0
- **Licencia**: LGPL-3
- **Depende de**: `website_sale`

## El problema

Los repuestos se publican como un producto con variantes: *Guardabarro - V8 Mini* tiene la variante
**Delantero** (`V8M-070`) y la variante **Trasero** (`V8M-071`), cada una con su referencia interna
bien cargada en Odoo.

Pero la página web mostraba una leyenda escrita a mano en la descripción del producto:

```
Guardabarro - V8 Mini
Cod: V8M-070 | Cod: V8M-071
```

Los dos códigos juntos, sin importar cuál variante estuviera seleccionada, y también en el carrito.
El cliente no sabía cuál de los dos estaba comprando.

Esa leyenda era **texto plano cargado a mano** en dos campos del producto (`description_ecommerce` y
`description_sale`), no un dato calculado, así que:

- no cambiaba al elegir una variante (es la misma cadena para todas);
- envejecía mal — al relevar la base, **22 de 198 productos ya tenían el código equivocado**: 21
  multi-variante mostraban solo uno de sus dos códigos, y uno mono-variante apuntaba a otro código;
- se filtraba a todo lo que consume esos campos: el feed de Google Merchant, el `og:description` al
  compartir el producto, los presupuestos y los mails.

## Qué hace el módulo

| Dónde | Antes | Ahora |
|---|---|---|
| Página de producto | `Cod: V8M-070 \| Cod: V8M-071` fijo | `Cod: V8M-070`, y cambia al tocar *Trasero* |
| Carrito | la misma leyenda con los dos códigos | el código de la variante de esa línea |

El texto se muestra como `Ref:` en inglés y **`Cod:` en español** (`i18n/es_AR.po`), para conservar
la estética que ya tenía el sitio.

### Cómo funciona

La página de producto se renderiza para la **plantilla**, no para la variante — por eso el código no
podía "seguir" a la selección sin ayuda. El módulo cierra ese hueco en tres puntos:

1. **Backend** (`models/product_template.py`) — `_get_additionnal_combination_info` agrega
   `default_code` al payload de `/website_sale/get_combination_info`, que es lo único que sabe qué
   variante quedó elegida.
2. **Frontend** (`static/src/js/website_sale_variant_code.js`) — extiende `_onChangeCombination` de
   la interacción `WebsiteSale` para escribir ese valor en el DOM. El core actualiza precio, imagen,
   etiquetas y disponibilidad, pero no la referencia interna.
3. **Templates** (`views/website_sale_variant_code_templates.xml`) — el valor inicial de la página
   sale de `product_variant` (la variante de la combinación preseleccionada, que el controller ya
   resuelve). En el carrito no hace falta JS: la línea ya apunta a una variante concreta.

## Limpieza de las leyendas manuales

Instalar el módulo **no borra nada**. La limpieza es un paso aparte y explícito, porque toca datos
de producción.

Sin ella el resultado sería peor que antes: el módulo *agrega* el código correcto pero la leyenda
vieja sigue en la descripción, y quedarían las dos, contradiciéndose.

```python
# Dry run: informa qué haría, sin escribir (default)
env['product.template']._clean_manual_code_descriptions()

# Aplicar
env['product.template']._clean_manual_code_descriptions(dry_run=False)
env.cr.commit()
```

El método:

- borra **solo** lo que reconoce como leyenda (líneas que empiezan con `Cod:` / `Cod.:`);
- si el campo tiene contenido real además de la leyenda, en HTML **no lo toca** y lo reporta en
  `skipped` para revisión manual — no reescribe HTML a ciegas;
- **loguea el valor previo de cada campo** antes de borrarlo (`[variant_code]` en el log del
  servidor): es la copia auditable de lo que se sacó;
- es **idempotente**: correrlo dos veces no cambia nada la segunda vez;
- recorre **todos los idiomas instalados**, porque el campo es traducible y la leyenda podía estar
  cargada en uno solo.

> ⚠️ **El carrito ya armado no se limpia solo.** Al agregar un producto al carrito, Odoo copia
> `description_sale` dentro de `sale.order.line.name`
> (`product.product.get_product_multiline_description_sale`). Los pedidos que ya existían conservan
> la leyenda vieja congelada en el nombre de la línea. Los nuevos salen limpios.

### Estado relevado (staging, 2026-09-01)

| | Cantidad |
|---|---|
| Productos activos con la leyenda manual | 198 |
| — de ellos, multi-variante (el caso que confunde) | 23 |
| Campos que limpia el datafix (2 por producto) | 396 |
| Campos con contenido real a preservar | 0 |
| Productos cuya leyenda ya estaba equivocada | 22 |

El único producto mono-variante con el código mal es
**Manillar Completo Del/Tra - V8 Mini** (`product.template` id 421): la leyenda decía `V8M-122` y la
variante tiene `V8M-126`. Después del datafix va a mostrar `V8M-126`. **Conviene que la funcional
confirme cuál de los dos es el correcto** — si el bueno era `V8M-122`, hay que corregir la
referencia interna de la variante, que es de donde sale el dato ahora.

## Validación manual

1. Abrir un repuesto con dos variantes (ej. *Guardabarro - V8 Mini*) en la tienda.
2. Con **Delantero** seleccionado tiene que decir `Cod: V8M-070`; al tocar **Trasero**, cambia a
   `Cod: V8M-071` sin recargar la página.
3. Agregar al carrito y verificar que la línea muestre el código de la variante elegida, uno solo.
4. Abrir un producto **sin** variantes y sin referencia interna: no debe aparecer ninguna leyenda
   vacía.
