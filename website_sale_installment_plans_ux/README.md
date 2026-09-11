# website_sale_installment_plans_ux

Ajustes de presentación sobre la leyenda de cuotas que `website_sale_installment_plans` (ADHOC)
publica debajo del precio en la ficha de producto y en la grilla del eCommerce. Desde 1.1.0
depende de `website_sale_payment_method_price` (dependencia dura) y, además, **mueve** esa
leyenda dentro del recuadro de precio de ese módulo.

| | |
|---|---|
| **Versión** | 1.1.0 |
| **Depende de** | `website_sale_installment_plans` (repo `odoo_l10n_ar`), `website_sale_payment_method_price` |
| **Repos/entornos** | `odoo_customization_sunra`, rama `develop_19.0` |

## Objetivo de negocio

La leyenda que trae el módulo de ADHOC se ve así:

```
En 6 cuotas de $58823.53 (Total $352941.18)   11% de recargo
```

Dos cosas molestaban en el sitio de Nokey:

1. **El total sobra.** El precio total ya está arriba, en grande; repetirlo entre paréntesis en cada
   línea de cuotas ensucia la tarjeta del producto.
2. **Los importes no respetan el formato argentino.** Salen sin separador de miles y con punto
   decimal (`$58823.53`), justo al lado de un precio que Odoo muestra bien (`$ 352.940,18`).

Con este módulo la misma línea queda:

```
En 6 cuotas de $ 58.823,53   11% de recargo
```

## Alcance

### Incluye

- Reescritura del texto de la leyenda (`description`) que consumen la ficha y la grilla.
- Formateo del importe de la cuota con la moneda del sitio web, usando el formateo nativo de Odoo
  (`formatLang`), de modo que acompaña el idioma y la moneda configurados.
- La cantidad de cuotas se toma del campo **Divisor**.
- Desde 1.1.0, con `website_sale_payment_method_price` como dependencia dura, **mueve** el
  `div.installment-plans` que ADHOC inyecta (antes suelto, debajo del precio) dentro del slot
  `div[@name='wspmp_installments']` del recuadro de precio de ese módulo, tanto en la ficha como en
  la grilla. Es puro reacomodo visual (`position="move"`): no se toca el cálculo ni el texto de la
  leyenda.

### No incluye

- No cambia el texto de la leyenda ni el ícono de tarjeta: el texto del campo **Mensaje** sigue
  siendo el del módulo de ADHOC.
- No toca el cálculo del importe: el coeficiente de recargo se aplica igual que antes.
- No agrega campos, ni menús, ni configuración.
- No modifica el flujo de pago: la leyenda sigue siendo informativa y el total del carrito no cambia.

### Edge case: producto sin precio publicable

Si el producto tiene `prevent_zero_price_sale` (o precio 0) **y** `website_sale_payment_method_price`
está instalado, la leyenda de cuotas queda **oculta junto con** el bloque de precio: el slot pasa a
ser descendiente de `div[name='product_price']`/`div.product_price`, que el core oculta con
`d-none` en ese caso. Antes de esta versión (o sin ese módulo instalado) la leyenda es **hermana**
del bloque de precio y sobrevive al `d-none`. Es el comportamiento deseado (sin precio publicable no
se publican cuotas), documentado en la spec del módulo de precios por medio de pago (D21, Edge
cases), no un bug de este puente.

## Cómo funciona

Un único override de `map_installment_values()` sobre `account.card.installment`, que es el método
por el que pasan **los dos** lugares donde se muestran las cuotas (la ficha resuelve por
`_get_combination_info()` y la grilla por `_get_card_installments_for_shop()`, y ambas terminan en
`_get_installment_plans()`). Llama al `super()` y sólo reemplaza la clave `description`.

La moneda para formatear sale de `_get_installment_currency()`: la del sitio web cuando estamos en
una request del frontend, y la de la compañía actual en cualquier otro caso (por ejemplo, si algún
proceso de backend llama al método).

### Por qué el divisor y no el plan

`account.card.installment` tiene dos campos numéricos parecidos:

| Campo | Etiqueta en la UI | Significado |
|-------|-------------------|-------------|
| `divisor` | Divisor | En cuántas cuotas se divide el total |
| `installment` | Plan de Cuotas | Identificador del plan para informar a sistemas de cobro |

El módulo de ADHOC arma la leyenda con `installment`, lo que hace que un plan de 6 cuotas cuyo
identificador sea `16` se publique como *"En 16 cuotas de..."*. Acá se usa `divisor`, que es el campo
que representa la cantidad real de cuotas, y el problema desaparece: ya no hace falta cargar los dos
campos con el mismo número en los planes publicados.

### El movimiento dentro del recuadro de precio (1.1.0)

Dos templates QWeb (`views/website_templates.xml`), uno para la ficha (hereda
`website_sale.product_price`) y otro para la grilla (hereda `website_sale.products_item`), con
`priority="20"` — se aplican **después** del recuadro de `website_sale_payment_method_price`
(`priority="18"`), que es quien crea el slot vacío. Cada uno hace un único
`<xpath expr="//div[@name='wspmp_installments']" position="inside">` con adentro un
`<xpath expr="//div[hasclass('installment-plans')]" position="move"/>`: el `div.installment-plans`
de ADHOC (clase estática, locator válido) se **mueve**, no se duplica. En la grilla ese `div`
arrastra su propio `t-set` de `installment_plans`, que sigue resolviendo bien porque `product` y
`template_price_vals` siguen en scope (mover el nodo no lo saca del `t-call` que los define).

El locator del slot es **siempre por el atributo `name`** (`div[@name='wspmp_installments']`), nunca
por clase: es el contrato que fija la spec de `website_sale_payment_method_price` (D21). Renombrar
ese slot en el módulo de precios rompe este puente.

## Dependencias

- `website_sale_installment_plans` (repo `odoo_l10n_ar`), que a su vez arrastra `card_installment`
  y `website_sale`.
- `website_sale_payment_method_price` (repo `odoo_customization_sunra`, desde 1.1.0): sin este
  módulo no existiría el slot `wspmp_installments`, y el `move` no tendría destino.

Es una dependencia **entre repos de addons**: este módulo vive en `odoo_customization_sunra` y
depende de uno de `odoo_l10n_ar` además de uno propio. Los tres tienen que estar en el `addons_path`.

## Mapa de archivos

| Archivo | Rol |
|---------|-----|
| `models/account_card_installment.py` | El override de `map_installment_values()` y el helper de moneda |
| `views/website_templates.xml` | Mueve la leyenda de cuotas dentro del recuadro de precio (ficha y grilla) |
| `i18n/es.po` | Traducción al español de las dos frases de la leyenda |

> Las frases llevan el comentario `#. odoo-python` en el `.po`: sin ese marcador Odoo no las toma
> como traducciones de código y la leyenda sale en inglés.

## Instalación / actualización

```bash
# Instalar por primera vez
docker exec <contenedor> odoo -c /etc/odoo/odoo.conf -d <base> -i website_sale_installment_plans_ux --stop-after-init

# Actualizar tras un cambio de código o de traducciones
docker exec <contenedor> odoo -c /etc/odoo/odoo.conf -d <base> -u website_sale_installment_plans_ux --stop-after-init
```

## Validación manual

1. Cargar en una tarjeta (**Contabilidad → Pagos → Tarjetas**) un plan con **Divisor** 6,
   **Coeficiente** 1,11 y **Publicado en website** tildado.
2. Abrir el sitio sin iniciar sesión y entrar a un producto publicado.
3. La línea debajo del precio tiene que decir `En 6 cuotas de $ <importe con puntos>`, sin el total
   entre paréntesis.
4. Verificar que el importe usa el mismo formato que el precio de arriba (separador de miles y coma
   decimal).
5. Repetir el chequeo en la grilla del shop: la línea es la misma.
6. Con `website_sale_payment_method_price` instalado y configurada su regla, verificar que la línea
   de cuotas queda **dentro** del recuadro de precio (debajo del precio del medio de pago), tanto en
   la ficha como en la grilla.
7. Con un producto sin precio publicable (`prevent_zero_price_sale`), verificar que la línea de
   cuotas queda oculta junto con el recuadro (edge case documentado arriba).

## Limitaciones conocidas

- Los límites del módulo base siguen vigentes: los planes publicados se muestran en **todos** los
  sitios web y sin filtrar por compañía.
- La leyenda es informativa: no agrega el recargo al total del pedido.
- Desde 1.1.0 depende de `website_sale_payment_method_price`: sin él no compone (el slot de destino
  del `move` no existe).

## Licencia y autoría

LGPL-3 — Sunra.
