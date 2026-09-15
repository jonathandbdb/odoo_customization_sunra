# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.http import request


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
             "find at the installation site. It is NOT needed for the appointment type used by the "
             "eCommerce checkout: that path already asks for the photos in its own step, and this "
             "module hides the upload there so the customer is not asked twice.",
    )
    installation_request_address = fields.Boolean(
        string="Ask for the Installation Address",
        help="Show the address block in the appointment form. Tick it on the appointment types "
             "booked WITHOUT going through the eCommerce (the link Nokey shares): there is no "
             "delivery address behind them, so without this the crew gets a task with no place to "
             "go. The eCommerce checkout already has the address and never shows this block.",
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

    def _is_installation_link_form(self):
        """ Whether this is the standalone booking form Nokey shares as a link (D59).

        Marks the form the customer fills WITHOUT going through the eCommerce: the one that asks
        for everything (contact, door, address, photos) and therefore needs to be organised in
        sections. The checkout path only confirms the slot and keeps the plain native layout.

        `installation_fsm_project_id` is already the marker of "booked outside the eCommerce" (D8),
        so it is reused here instead of inventing a second flag.

        :rtype: bool
        """
        self.ensure_one()
        return bool(self.installation_fsm_project_id) and not self._is_installation_checkout_source()

    def _is_installation_asking_photos(self):
        """ Whether the appointment form itself must ask for the site photos (D57).

        Never on the checkout path: the installation step of the checkout already asks for them
        (and stores them on the order), so showing the upload again in the appointment form makes
        the customer load the same photos twice and only the checkout ones count. The gate is in
        code and not only in the configuration on purpose: the same appointment type can be used by
        both paths, and then no configuration can tell them apart.

        :rtype: bool
        """
        self.ensure_one()
        return self.installation_request_photos and not self._is_installation_checkout_source()

    def _is_installation_asking_address(self):
        """ Whether the appointment form must ask for the installation address (D58).

        Same criterion as the photos: on the checkout path the address is the delivery address of
        the order and is confirmed in Step 1, so the block is never shown there.

        :rtype: bool
        """
        self.ensure_one()
        return self.installation_request_address and not self._is_installation_checkout_source()

    def _is_installation_checkout_source(self):
        """ Whether the visitor reached the appointment page FROM the checkout (D54).

        Used so the checkout path does not repeat the intro the customer already read in Step 2
        of the installation step. Based on `request.cart` (not a URL parameter): between the
        "Schedule" button and the appointment form the core navigates on its own
        (`/appointment/<id>` -> `/appointment/<id>/info?...`), so a parameter of our own would be
        lost along the way.

        :rtype: bool
        """
        self.ensure_one()
        # Mismo patron defensivo que website._get_allowed_steps_domain(): tambien puede correr
        # fuera de un request web (ej. un cron o un test).
        cart = getattr(request, "cart", None) if request else None
        return bool(cart) and cart._is_installation_required() and cart.installation_appointment_type_id == self

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
