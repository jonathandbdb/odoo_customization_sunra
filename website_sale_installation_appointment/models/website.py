# -*- coding: utf-8 -*-
from odoo import models
from odoo.fields import Domain
from odoo.http import request

# Ruta del paso de checkout que agrega este modulo (tambien la usan los hooks del __init__).
INSTALLATION_STEP_HREF = "/shop/installation"


class Website(models.Model):
    _inherit = "website"

    def _get_allowed_steps_domain(self):
        # El paso "Instalacion" es condicional: participa del checkout solo si el metodo de envio
        # elegido exige instalacion. Al filtrarlo del dominio, el core lo saltea solo al calcular el
        # paso siguiente/anterior y no lo dibuja en el wizard (envio normal -> no existe).
        domain = super()._get_allowed_steps_domain()
        cart = getattr(request, "cart", None) if request else None
        if not cart or not cart._is_installation_required():
            return Domain.AND([domain, [("step_href", "!=", INSTALLATION_STEP_HREF)]])
        return domain

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
