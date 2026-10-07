# -*- coding: utf-8 -*-
from odoo import Command


def uninstall_hook(env):
    # El menu raiz de Sitio web vuelve a quedar visible a todo usuario interno, como en el core
    menu = env.ref("website.menu_website_configuration", raise_if_not_found=False)
    if menu:
        menu.group_ids = [Command.set([env.ref("base.group_user").id])]

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
