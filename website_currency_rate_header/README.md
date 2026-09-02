# website_currency_rate_header

Muestra en el **encabezado del sitio web** la cotización vigente de una moneda, expresada en otra.
Por ejemplo: `Tipo de Cambio Oficial: $ 1.480,00`.

Se activa **por sitio web**.

## El problema

En Sunra el catálogo está en **dólares** (la compañía y las listas de precios están en USD) pero se
factura en **pesos**. El concesionario mira precios en dólares y quiere saber con qué cotización
está mirando, porque al momento de facturar el importe en pesos puede variar.

Odoo no muestra la cotización en ningún lugar del sitio.

## Qué hace el módulo

Agrega una línea en el encabezado, con el texto y la moneda que se configuren.

**Ajustes → Sitio Web → General:**

| Campo | Qué es |
|---|---|
| **Cotización en el encabezado** | Prende o apaga la línea en este sitio. |
| **Moneda de la cotización** | La moneda en la que se expresa el importe. |
| **Texto de la cotización** | El texto que va antes del importe. Es **traducible**. Por defecto *Official Exchange Rate:*; en el sitio en español se pone *Tipo de Cambio Oficial:*. |

### La dirección de la cotización

En la semántica de Odoo, `rate` es **cuántas unidades de esa moneda vale una unidad de la moneda de
la compañía**. El campo `rate_string` del backend lo dice literal: `1 USD = 1480.000000 ARS`.

Entonces, con la compañía en **USD** y la moneda de la cotización en **ARS**, se muestran los pesos
por dólar — que es exactamente lo que necesita ver el concesionario. El importe se formatea en la
moneda elegida (ARS), con su símbolo y separadores.

Si la moneda elegida es la misma que la de la compañía no se muestra nada: cotizarla contra sí misma
daría siempre 1.

### De dónde sale el dato

Del tipo de cambio estándar de Odoo (`res.currency`), así que funciona con cualquier origen: carga
manual o sincronización automática. En este workspace lo mantiene el módulo
`l10n_ar_currency_exchange_bna`, que sincroniza la venta del Banco Nación por cron cada hora. El
módulo del encabezado **no depende** de él.

## Cómo funciona

Se engancha en `website.placeholder_header_text_element`, que es un template **vacío** del core que
invocan **todas** las variantes de encabezado (default, hamburger, stretch, vertical, search y
mobile). Es el único punto de extensión estable: si el cliente cambia el estilo de encabezado del
sitio, la cotización sigue apareciendo.

El core usa ese mismo mecanismo en `website.header_text_element`, de donde sale la estructura del
`<li>` y las variables de contexto `_item_class` / `_div_class` que pasan los encabezados.

El cálculo corre con `sudo()` porque la línea se renderiza para el visitante anónimo, que no tiene
acceso de lectura a las cotizaciones (`res.currency.rate`).

## Validación manual

1. Prender la cotización en el sitio, elegir la moneda y escribir el texto.
2. Confirmar que el importe del encabezado coincide con la *Tasa actual* de esa moneda en el
   backend (Contabilidad → Configuración → Monedas).
3. Cambiar el estilo de encabezado del sitio (Ajustes → Sitio Web → Encabezado) y confirmar que la
   cotización **sigue apareciendo**.
4. Cambiar la cotización en el backend (o correr el cron) y confirmar que el encabezado refleja el
   valor nuevo.
5. Elegir como moneda la misma de la compañía: no debe mostrarse nada.
6. En el otro sitio web, con la cotización apagada: el encabezado queda **idéntico** a antes.
