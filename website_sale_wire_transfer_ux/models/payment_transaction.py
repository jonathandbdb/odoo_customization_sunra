# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import _, models


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _get_wire_transfer_mail_block(self):
        """
        Armar el bloque de datos de transferencia que va en el mail de orden pendiente.

        Se resuelve todo en Python (y no en el cuerpo de la plantilla de correo) por dos razones:
        el bloque que se inserta en la plantilla del core queda en **una sola linea** y no depende
        del idioma, asi que sirve igual para todos los idiomas activos; y las etiquetas se traducen
        con `_()` en el idioma del destinatario, que es el que la plantilla pone en el contexto al
        renderizar.

        No usa `ensure_one()` a proposito: `ai` (Enterprise) valida los `mail.template` al
        guardarlos **renderizandolos** (`enterprise/ai/models/mail_template.py`), y en esa pasada la
        transaccion puede venir vacia. Un metodo llamado desde el cuerpo de un mail no puede
        levantar excepciones: devuelve vacio y listo.

        :return: el bloque HTML, o vacio si la transaccion no es una transferencia pendiente
        :rtype: Markup
        """
        if len(self) != 1:
            return Markup()
        provider = self.provider_id.sudo()
        if (
            self.state != "pending"
            or provider.code != "custom"
            or provider.custom_mode != "wire_transfer"
        ):
            return Markup()
        parts = [Markup("<br/>"), provider.pending_msg or Markup()]
        cbu_account = provider._get_wire_transfer_cbu_account()
        if cbu_account:
            parts.append(Markup("<br/><b>%s</b> %s") % (_("CBU:"), cbu_account.acc_number))
        # La Comunicacion es la referencia del pedido (lo que el cliente pone en la transferencia),
        # distinta de la referencia de la transaccion que ya imprime el mail del core.
        reference = self.sale_order_ids[:1].reference
        if reference:
            parts.append(Markup("<br/><b>%s</b> %s") % (_("Communication:"), reference))
        return Markup("").join(parts)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
