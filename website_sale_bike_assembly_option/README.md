# website_sale_bike_assembly_option

Selector **Armada / En caja** en la ficha web de cada vehículo que se vende en caja (bicicletas,
motos, monopatines), de cualquier compañía: con "En caja" el carrito recibe el **kit** al mismo
precio que el vehículo armado. El selector aparece en todo vehículo cuya lista de materiales tenga
el tilde de traslado de piezas y un kit con número de serie como único componente.

| | |
|---|---|
| **Versión** | 1.0.0 |
| **Depende de** | `sale_website_company_routing`, `sunra_mrp_component_serials` |
| **Repos/entornos** | `odoo_customization_sunra`, rama `develop_19.0` |
| **Spec SDD** | `specs/website_sale_bike_assembly_option.md` |

## Para qué sirve

Cada bici existe como producto armado (publicado) y como kit en caja (no publicado) con el mismo
número de chasis, unidos por la LdM de fabricación marcada con `sunra_pull_kit_components`. El
concesionario elige cómo la recibe sin que el kit se publique como producto aparte.

## Cómo funciona

- **Kit**: de la LdM activa de tipo normal con el tilde, el **único** componente serializado
  aplicable a la variante. Ninguno o varios: la bici no ofrece la opción. La LdM se busca sin filtrar
  por compañía (la fabrica otra) y en `sudo()` solo para leerla.
- **Selector**: se ve si alguna variante de la plantilla tiene kit, aunque no tenga atributos.
  Por defecto "Armada".
- **"En caja"**: el servidor cambia la bici por su kit en `sale.order._cart_add` (nunca se acepta un
  kit pedido por el navegador) y descarta los atributos de la bici. El kit no necesita estar publicado.
- **Precio**: la línea del kit toma regla, precio y descuento de la bici armada en la lista de precios
  del sitio, en cada recálculo. El kit conserva **sus propios impuestos**.
- **Carrito**: el kit se fusiona solo con el mismo kit de la misma bici y enlaza a la ficha de la bici.
  El tope lo da el stock web del kit; si el kit no tiene compañías de stock web propias, las de su bici
  (igual que la ficha), no el almacén del sitio.
- **Disponibilidad de la armada**: stock libre de la armada **más** el de su kit (toda caja puede
  armarse sobre pedido), solo para bicis con compañías de stock web (`sale_website_company_routing`). Un kit sin compañías
  de stock web propias usa las de su bici.
- **Compañía**: sin configuración propia, el kit se vende por la compañía de la bici; al confirmar
  se mueve al pedido derivado conservando `assembled_product_id`.
- **Backoffice**: columna opcional oculta "Assembled Vehicle" en las líneas del pedido.

## Requisitos de configuración

- LdM de la bici con el tilde de kit y un único componente con seguimiento por número de serie.
- Kit con **compañía vacía**, y con los **mismos impuestos de venta** que la bici (si difieren, el
  total del kit difiere del de la bici).

## Límites

- Doble conteo: la armada cuenta los kits libres y "En caja" también; un carrito con ambos de la
  misma bici puede superar los kits físicos.
- Sin selector en la grilla, el agregado rápido ni los opcionales: agregan la armada.
- La opción solo afecta al producto principal (no a opcionales ni combos).

## Detalle técnico

- Extiende `product.product`, `product.template`, `sale.order`, `sale.order.line` y `website`.
  Campo nuevo `sale.order.line.assembled_product_id`. Sin ACLs nuevas.
- JS: patch de `WebsiteSale._updateRootProduct` (agrega `bike_assembly_option` si el radio existe) y
  de las props de los configuradores. Sin controller propio.
- Idioma: UI en inglés, traducción en `i18n/es_419.po`.
