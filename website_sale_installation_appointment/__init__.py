# -*- coding: utf-8 -*-
from . import models
from . import controllers

from .models.website import INSTALLATION_STEP_HREF


def post_init_hook(env):
    # Los pasos del checkout son registros por website: el core copia los pasos genericos
    # (website_id vacio) cuando se crea un website, asi que los websites que ya existian no
    # reciben el paso nuevo solos. Lo replicamos aca, publicado.
    generic_step = env.ref(
        "website_sale_installation_appointment.checkout_step_installation",
        raise_if_not_found=False,
    )
    if not generic_step:
        return
    for website in env["website"].search([]):
        if not website._get_checkout_step(INSTALLATION_STEP_HREF):
            generic_step.copy({"website_id": website.id, "is_published": True})


def uninstall_hook(env):
    # Las copias por website no las borra el desinstalador (no tienen XML ID), y quedarian
    # apuntando a una ruta inexistente.
    env["website.checkout.step"].sudo().search([
        ("step_href", "=", INSTALLATION_STEP_HREF),
    ]).unlink()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
