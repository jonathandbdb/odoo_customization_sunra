# -*- coding: utf-8 -*-
{
    "name": "website_menu_access",
    "version": "1.0.0",
    "summary": "Oculta la app Sitio web a los usuarios internos sin permisos de sitio web",
    "description": """
Restringe el menu raiz de la app Sitio web del backend.

- El core deja ese menu visible a todo usuario interno; este modulo lo limita a quienes tienen
  el grupo Editor restringido de Sitio web (que implican el Disenador y el Administrador de ajustes,
  y varios grupos de ventas, eventos, eLearning y reclutamiento).
- Un usuario interno sin ese grupo (por ejemplo, Administracion) deja de ver la app.
- No agrega modelos ni campos; al desinstalar restituye el grupo original del core.
    """,
    "category": "Website/Website",
    "author": "Sunra",
    "website": "https://github.com/sunraargsh",
    "license": "LGPL-3",
    "depends": [
        "website",
    ],
    "data": [
        "views/website_menu_access_menus.xml",
    ],
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
