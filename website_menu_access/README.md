# website_menu_access

Oculta la app Sitio web del backend a los usuarios internos que no tienen el grupo `website.group_website_restricted_editor` (Sitio web: Editor restringido).

## Objetivo

En el core, el menu raiz `website.menu_website_configuration` es visible para todo usuario interno (`base.group_user`). El modulo lo limita a quienes tienen el permiso de Sitio web.

## Alcance

- Incluye: cambio de los `group_ids` del menu raiz de Sitio web.
- No incluye: modelos, campos, grupos, ACLs ni reglas nuevas. No toca los menus de programas de descuento y lealtad.

## Configuracion (funcional)

1. Ajustes - Usuarios y compañias - Usuarios, abrir el usuario.
2. Dejar el campo "Sitio web" vacio en sus permisos.
3. Guardar y recargar el navegador.

## Gotchas

- Si el usuario tiene Ajustes = Administracion o Ventas = Administrador, sigue viendo la app: esos grupos implican el permiso de Sitio web (core: `website/security/website_security.xml:22` y `website_sale/security/res_groups.xml:24-27`). Lo mismo ocurre con los grupos de gestor de eventos, eLearning y reclutamiento web.
- Los programas de descuento y lealtad no los modifica este modulo; se ocultan quitando Ventas = Administrador (`sale_loyalty/views/sale_loyalty_menus.xml`).

## Seguridad

Sin ACLs ni record rules propias. Aplica a todas las companias por igual (los grupos no dependen de la compañia).

## Dependencias

- `website`

## Mapa de archivos

- `__manifest__.py` — metadatos y dependencia.
- `views/website_menu_access_menus.xml` — redefine `group_ids` de `website.menu_website_configuration`.
- `__init__.py` — `uninstall_hook` que restituye `base.group_user` en el menu.

## Instalacion / actualizacion

```bash
odoo -d <db> -i website_menu_access --stop-after-init
odoo -d <db> -u website_menu_access --stop-after-init
```

(Ejecutar dentro del contenedor Odoo del entorno.)

## Validacion manual

1. Usuario interno sin "Sitio web" y sin Ajustes/Ventas administrador: no ve la app Sitio web.
2. Usuario con "Sitio web" = Editor restringido: la ve.
3. Desinstalar el modulo: todo usuario interno vuelve a verla.

## Licencia

LGPL-3. Desarrollado por Sunra - https://github.com/sunraargsh
