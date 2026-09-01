# website_sale_installment_plans_ux

Ajustes de presentación sobre la leyenda de cuotas que `website_sale_installment_plans` (ADHOC)
publica debajo del precio en la ficha de producto y en la grilla del eCommerce.

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

### No incluye

- No cambia las plantillas QWeb: la ubicación de la leyenda, el ícono de tarjeta y el texto del
  campo **Mensaje** siguen siendo los del módulo de ADHOC.
- No toca el cálculo del importe: el coeficiente de recargo se aplica igual que antes.
- No agrega campos, ni menús, ni configuración.
- No modifica el flujo de pago: la leyenda sigue siendo informativa y el total del carrito no cambia.

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

## Dependencias

- `website_sale_installment_plans` (repo `odoo_l10n_ar`), que a su vez arrastra `card_installment`
  y `website_sale`.

Es una dependencia **entre repos de addons**: este módulo vive en `odoo_customization_sunra` y
depende de uno de `odoo_l10n_ar`. Ambos tienen que estar en el `addons_path`.

## Mapa de archivos

| Archivo | Rol |
|---------|-----|
| `models/account_card_installment.py` | El override de `map_installment_values()` y el helper de moneda |
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

## Limitaciones conocidas

- Los límites del módulo base siguen vigentes: los planes publicados se muestran en **todos** los
  sitios web y sin filtrar por compañía.
- La leyenda es informativa: no agrega el recargo al total del pedido.
- Convive con `website_sale_payment_method_price`, que también inserta información debajo del precio
  (el segundo precio por medio de pago). Los dos bloques se apilan; este módulo no altera esa
  disposición.

## Licencia y autoría

LGPL-3 — Sunra.
