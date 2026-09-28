# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import UserError


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def unlink(self):
        # Antes del super() (D64): despues del borrado la relacion ya no tiene la foto y no hay
        # forma de saber que tarea la tenia. El borrado desde el chatter llega hasta aca sin pasar
        # por ProjectTask.write() (odoo/addons/mail/controllers/attachment.py:L108), asi que ese
        # gate no alcanza a frenarlo.
        tasks = self.env["project.task"].sudo().with_context(active_test=False).search([
            ("installation_photo_ids", "in", self.ids),
            ("state", "=", "1_done"),
            ("project_id.is_fsm", "=", True),
            ("project_id.installation_require_photos", "=", True),
        ])
        # sudo() solo para leer: quien borra el adjunto puede no tener acceso a la tarea (el
        # borrado desde el chatter corre con sudo() y se valida por propiedad del adjunto, no por
        # la tarea). No se escribe nada con sudo(); el super().unlink() corre con el entorno de
        # quien llama.
        if any(not (task.installation_photo_ids - self) for task in tasks):
            raise UserError(_(
                "You cannot delete the last photo of the installed lock of a task that is "
                "already done."
            ))
        return super().unlink()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
