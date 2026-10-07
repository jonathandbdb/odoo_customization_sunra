# website_sale_category_boxes

Muestra cada categoría principal del lateral de la tienda web (`/shop`) y del menú móvil de filtros en su propia caja, con los colores y radios del tema de cada sitio web. Se activa por sitio.

## Objetivo y alcance

- Ordenar visualmente el listado de categorías de la tienda sin alterar el comportamiento del core.
- Con el interruptor apagado el sitio se ve igual que el core.
- No agrega modelos, JavaScript ni lógica de negocio. No cambia qué categorías se muestran.

## Funcionamiento

- Una caja por categoría principal: borde sutil, nombre en mayúsculas.
- Hover y caja abierta con el color primario del tema (`$primary`).
- Barra de acento en la categoría actual; chevron visible que rota al desplegar.
- Subcategorías en un panel tenue con guía de jerarquía.
- Foco visible y sin animaciones con `prefers-reduced-motion`.
- Funciona con y sin la opción estándar **Contraer categorías** (Editar - grilla de productos - Estilo), que es la que hace que se desplieguen; se recomienda usarlas juntas.

## Configuración

1. Sitio web - Ajustes - eCommerce, seleccionar el sitio y activar **Category Boxes**.
2. Recomendado: activar **Contraer categorías** en el editor de la tienda.
3. Verificar en `/shop` (escritorio y móvil).

## Detalle técnico

| Elemento | Descripción |
|----------|-------------|
| `website.shop_category_boxes` | Boolean por sitio web (`models/website.py`) |
| `res.config.settings.website_shop_category_boxes` | related a `website_id.shop_category_boxes`, `readonly=False` (`models/res_config_settings.py`) |
| `views/res_config_settings_views.xml` | `<setting>` "Category Boxes" tras `ecommerce_access_setting` |
| `views/website_sale_templates.xml` | Hereda `website_sale.products_categories_list` y agrega `data-category-boxes` al contenedor `wsale_products_categories_list` |
| `static/src/scss/category_boxes.scss` | Todo el diseño, en `web.assets_frontend` |

## Seguridad

Sin grupos, ACLs ni record rules propias. El campo vive en `website`, por lo que aplica por sitio web y es independiente entre compañías.

## Dependencias

`website_sale`.

## Notas de mantenimiento

- No se tocan `class` ni `t-attf-class` del contenedor: las vistas de categorías contraíbles del core dependen de ellas; por eso se marca con un atributo `data-`.
- Los estilos cuelgan de `[data-category-boxes]`.

## Instalación / actualización (Docker)

```
odoo_runtime.sh update <db> website_sale_category_boxes
```

## Validación manual

1. Con el interruptor apagado, `/shop` se ve como el core.
2. Activarlo en un sitio: las categorías aparecen en cajas, también en el menú móvil de filtros.
3. Probar con y sin "Contraer categorías"; hover, categoría actual, foco con teclado.
4. En otro sitio web con el interruptor apagado, no cambia nada.

## Licencia

LGPL-3. Desarrollado por Sunra - https://github.com/sunraargsh
