# -*- coding: utf-8 -*-
from odoo import fields, models


class AppointmentType(models.Model):
    _inherit = "appointment.type"

    installation_fsm_project_id = fields.Many2one(
        comodel_name="project.project",
        string="Field Service Project",
        domain="[('is_fsm', '=', True)]",
        help="For appointment types booked WITHOUT going through the eCommerce (the link Nokey "
             "shares when the customer pays outside the website): the visit booked here creates a "
             "task in this Field Service project, so the crew has the job on their planning. Leave "
             "empty for appointment types that already create the task through a sales order.",
    )
    installation_request_photos = fields.Boolean(
        string="Ask for Site Photos",
        help="Show the photo upload in the appointment form: the crew needs to know what they will "
             "find at the installation site.",
    )
    installation_min_photos = fields.Integer(
        string="Minimum Site Photos",
        help="Photos required to book. 0 shows the upload box without blocking the booking.",
    )
    # La consigna de las fotos es texto que el funcional cambia sin avisar (que se tiene que ver,
    # cuantas fotos, con que luz). Va en un campo y no en la plantilla: editar la plantilla desde el
    # editor web crea una copia por sitio que deja de recibir las actualizaciones del modulo.
    # `sanitize_attributes=False` espeja a `message_intro` del core: sin eso el editor pierde los
    # estilos que deja al escribir.
    installation_photos_message = fields.Html(
        string="Site Photos Message",
        translate=True,
        sanitize_attributes=False,
        help="Instructions shown above the photo upload, both in the eCommerce checkout and in the "
             "appointment form of the link shared by Nokey. Leave empty to show the default text of "
             "the module.",
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
