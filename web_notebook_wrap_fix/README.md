# web_notebook_wrap_fix

Parche de CSS temporal para una regresión del core de Odoo 19 que rompe el corte de línea dentro
del contenido de las pestañas (notebook) del backend.

## Objetivo de negocio

El commit de core `7d26b3444f61` ("[FIX] web: adjust SCSS for vertical notebook", `odoo/odoo#279098`,
task-5933892), mergeado a la serie `19.0` el 04/09/2026, movió la regla `white-space: nowrap` de
`.o_notebook .nav-item` (que aplicaba solo a las solapas del notebook) a `.o_notebook.horizontal`
(el notebook completo). Como `white-space` es una propiedad que se hereda, esto propaga `nowrap` a
**todo el contenido** de cada pestaña, no solo a sus solapas.

Consecuencia visible: en cualquier pestaña que combine elementos inline (ej. botones) con un widget
`inline-block` (ej. una lista one2many/many2many), el widget deja de poder bajar a su propio
renglón — queda pegado al lado de los botones y se desborda a la derecha, con scroll horizontal y
columnas fuera de pantalla.

El caso que disparó el fix es la pestaña "Deudas" del formulario de pagos del módulo ADHOC
vendorizado `account_payment_pro` (Nokey/Sunra, producción): los botones de la pestaña empujan la
lista de facturas pendientes fuera de la vista, ocultando columnas como "Saldo residual" y "Monto".
La regresión es genérica del backend (no específica de ese módulo): afecta a cualquier pestaña con
esa misma mezcla de contenido.

`web_notebook_wrap_fix` restaura el comportamiento previo con un único bloque SCSS que apunta a
`.o_notebook.horizontal > .o_notebook_content` (3 clases contra las 2 del selector del core) para
devolverle `white-space: normal` al contenido de la pestaña, ganando por especificidad sin usar
`!important` ni depender del orden de concatenación del bundle. Las solapas (`.nav-item`) no se
tocan: siguen heredando el `nowrap` del core, que es justamente lo que esa regla buscaba.

## Alcance

### Incluye
- Una regla CSS/SCSS que devuelve `white-space: normal` al contenido de la pestaña
  (`.o_notebook.horizontal > .o_notebook_content`) sin tocar la regla de las solapas.
- Carga automática (`auto_install: True`): se instala solo en cualquier base con `web` instalado,
  sin acción manual, incluido el deploy a Odoo.sh.

### No incluye
- Ningún cambio de modelos, vistas, seguridad, wizards ni datos: es exclusivamente un asset CSS.
- No modifica `account_payment_pro` ni ningún otro módulo funcional: el fix actúa a nivel del
  framework `web` (componente notebook), agnóstico de qué módulo dispare el síntoma.
- No es una solución permanente: es un parche de compatibilidad mientras la regresión siga presente
  en el core instalado.

## Modelos y vistas

Ninguno. El módulo no define modelos, vistas, seguridad, wizards, reportes ni scheduled actions: es
un único archivo `static/src/scss/notebook_wrap.scss` cargado en el bundle `web.assets_backend`.

## Dependencias

- `web` (core) — único módulo del que depende (`depends: ["web"]`); el fix aplica al framework de
  notebooks del backend, no a un módulo funcional puntual.
- Sin dependencias de terceros ni de Enterprise.

## Mapa de archivos principales

```
web_notebook_wrap_fix/
    __manifest__.py                       # depends=["web"], auto_install=True, asset en web.assets_backend
    static/src/scss/
        notebook_wrap.scss                 # única regla del parche
    static/description/
        index.html                         # esta documentación
```

## Instalación / actualización (Docker)

Al ser `auto_install: True`, el módulo se instala solo en cuanto está presente en el `addons_path`
(no hace falta `-i` manual) en cualquier base que tenga `web` instalado — incluido el deploy a
Odoo.sh. Para forzarlo manualmente en el entorno local (contenedor `nokey-odoo-1`, base `nokey`):

```bash
cd /home/leandro/PersonalProject/Nokey && docker compose stop odoo

docker compose run --rm --no-deps odoo python3 /home/bo/odoo/odoo-bin \
    -c /etc/odoo/odoo.conf -d nokey -i web_notebook_wrap_fix --stop-after-init

docker compose up -d odoo
```

Tras instalar/actualizar, refrescar los assets del navegador (recarga forzada) para descartar el
bundle CSS viejo.

## Validación manual

1. Instalar/actualizar el módulo (ver arriba) y refrescar los assets del navegador.
2. Abrir un pago (o cualquier formulario con notebook) cuya pestaña combine botones y una lista
   x2many — ej. la pestaña "Deudas" en `account_payment_pro`.
3. Confirmar que los botones quedan arriba, en su propio renglón, y la lista ocupa el ancho completo
   de la pestaña sin scroll horizontal, con todas las columnas visibles (ej. "Saldo residual",
   "Monto").
4. Confirmar que las solapas del notebook (los títulos "Deudas", etc.) siguen sin cortar línea (no
   deben verse partidas en dos renglones).

## Notas de mantenimiento

- Este módulo es un **parche temporal**, no una feature: existe solo mientras la regresión siga
  presente en el core de la serie `19.0` instalada.
- **Cuándo retirarlo**: cuando Odoo publique un fix upstream de la regresión introducida por
  `7d26b3444f61` (`odoo/odoo#279098`, task-5933892) — o cuando se actualice a una versión de core
  donde ya esté corregida — desinstalar `web_notebook_wrap_fix` y eliminar la carpeta del módulo
  del repo.
- No acumular más reglas en este módulo: si aparece una regresión de CSS distinta, documentarla en
  un módulo de parche separado (o evaluar si conviene reabrir este con alcance ampliado) en vez de
  mezclar causas raíz distintas bajo el mismo nombre.

## Licencia y autoría

- **Autor**: Sunra — https://github.com/sunraargsh
- **Licencia**: LGPL-3
