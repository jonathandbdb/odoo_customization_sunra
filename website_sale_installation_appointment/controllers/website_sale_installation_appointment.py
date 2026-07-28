# -*- coding: utf-8 -*-
import base64

from odoo import Command, _
from odoo.http import request, route
from odoo.tools import format_datetime
from odoo.tools.mimetypes import guess_mimetype

from odoo.addons.website_appointment_sale.controllers.appointment import WebsiteAppointmentSale
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.website_sale_installation_appointment.models.website import INSTALLATION_STEP_HREF

# Limites del upload publico de fotos (el endpoint es auth="public").
MAX_PHOTOS = 10
MAX_PHOTO_SIZE = 10 * 1024 * 1024


class WebsiteSaleInstallation(WebsiteSale):

    # === CHECKOUT FLOW - INSTALLATION STEP === #

    @route(
        [INSTALLATION_STEP_HREF], type="http", auth="public", website=True, sitemap=False,
    )
    def shop_installation(self, **post):
        order_sudo = request.cart
        redirection = self._check_cart(order_sudo)
        if redirection:
            return redirection
        if not order_sudo._is_installation_required():
            return request.redirect("/shop/payment")

        return request.render(
            "website_sale_installation_appointment.installation",
            self._prepare_installation_values(order_sudo),
        )

    @route(
        [INSTALLATION_STEP_HREF + "/submit"], type="http", auth="public", website=True,
        methods=["POST"], sitemap=False,
    )
    def shop_installation_submit(self, **post):
        order_sudo = request.cart
        redirection = self._check_cart(order_sudo)
        if redirection:
            return redirection
        if not order_sudo._is_installation_required():
            return request.redirect("/shop/payment")

        warnings = self._save_installation_photos(
            order_sudo, request.httprequest.files.getlist("installation_photos")
        )
        if warnings:
            request.session["installation_warnings"] = warnings
            return request.redirect(INSTALLATION_STEP_HREF)
        if order_sudo._get_installation_errors():
            # Falta algo (cita o fotos): se vuelve al paso, que ya muestra el detalle.
            return request.redirect(INSTALLATION_STEP_HREF)

        return request.redirect(self._get_installation_next_step_href())

    @route(
        [INSTALLATION_STEP_HREF + "/photo/<int:attachment_id>/remove"], type="http",
        auth="public", website=True, methods=["POST"], sitemap=False,
    )
    def shop_installation_photo_remove(self, attachment_id, **post):
        order_sudo = request.cart
        redirection = self._check_cart(order_sudo)
        if redirection:
            return redirection

        # Solo se puede borrar una foto que pertenezca al carrito en curso; el sudo es porque el
        # cliente del eCommerce (public/portal) no tiene permiso de unlink sobre ir.attachment.
        photo = order_sudo.installation_photo_ids.filtered(lambda att: att.id == attachment_id)
        if photo:
            photo.sudo().unlink()
        return request.redirect(INSTALLATION_STEP_HREF)

    # === OVERRIDES === #

    def _get_shop_payment_errors(self, order):
        """ Override of `website_sale`: block the payment while the installation is incomplete. """
        errors = super()._get_shop_payment_errors(order)
        installation_errors = order._get_installation_errors()
        if installation_errors:
            errors.append((
                _("Your installation is not scheduled yet."),
                "\n".join(installation_errors),
            ))
        return errors

    # === TOOLS === #

    def _prepare_installation_values(self, order_sudo):
        """ Rendering values of the installation step.

        :param order_sudo: the current cart (sudo)
        :return: dict of values for the template
        :rtype: dict
        """
        values = {
            "website_sale_order": order_sudo,
            "order": order_sudo,
            "errors": order_sudo._get_installation_errors(),
            "warnings": request.session.pop("installation_warnings", []),
            "appointment_type": order_sudo.installation_appointment_type_id,
            "installation_slot_label": self._get_installation_slot_label(order_sudo),
            "installation_photos": self._get_installation_photos(order_sudo),
            "max_photos": MAX_PHOTOS,
            "show_navigation_button": False,
        }
        values.update(request.website._get_checkout_step_values())
        return values

    def _get_installation_slot_label(self, order_sudo):
        """ Human readable date and time of the booked installation, in the customer timezone.

        :return: the formatted slot, or an empty string if nothing is booked yet
        :rtype: str
        """
        booking = order_sudo.installation_booking_id
        event = order_sudo.installation_event_id
        start = booking.start or event.start
        if not start:
            return ""
        timezone = (
            request.session.get("timezone")
            or order_sudo.installation_appointment_type_id.appointment_tz
        )
        return format_datetime(request.env, start, tz=timezone, dt_format="short")

    def _get_installation_photos(self, order_sudo):
        """ Photos already uploaded, with a tokenized URL so the customer can review them.

        :return: list of dicts (id, name, url)
        :rtype: list
        """
        photos = []
        # sudo: el cliente no lee ir.attachment; se le da acceso solo a SUS fotos via access_token.
        for photo in order_sudo.installation_photo_ids.sudo():
            access_token = photo.access_token or photo.generate_access_token()[0]
            photos.append({
                "id": photo.id,
                "name": photo.name,
                "url": "/web/image/%s?access_token=%s" % (photo.id, access_token),
            })
        return photos

    def _save_installation_photos(self, order_sudo, uploads):
        """ Store the uploaded photos as attachments linked to the order.

        :param order_sudo: the current cart (sudo)
        :param uploads: list of werkzeug FileStorage
        :return: list of warnings for the rejected files
        :rtype: list
        """
        warnings = []
        available_slots = MAX_PHOTOS - order_sudo.installation_photo_count
        for upload in uploads:
            if not upload or not upload.filename:
                continue
            if available_slots <= 0:
                warnings.append(_(
                    "You can upload up to %(max_photos)s photos.", max_photos=MAX_PHOTOS,
                ))
                break
            content = upload.read()
            if not content:
                continue
            if len(content) > MAX_PHOTO_SIZE:
                warnings.append(_(
                    "The file %(filename)s is too big (maximum %(max_size)s MB).",
                    filename=upload.filename,
                    max_size=MAX_PHOTO_SIZE // (1024 * 1024),
                ))
                continue
            # Se valida el mimetype real del contenido, no el que declara el navegador.
            mimetype = guess_mimetype(content)
            if not mimetype.startswith("image/"):
                warnings.append(_(
                    "The file %(filename)s is not an image.", filename=upload.filename,
                ))
                continue
            # sudo: la foto la sube el cliente del eCommerce, que no crea ir.attachment por si mismo.
            # Ya se validaron tipo, tamaño y cantidad antes de llegar aca.
            attachment = request.env["ir.attachment"].sudo().create({
                "name": upload.filename,
                "datas": base64.b64encode(content),
                "mimetype": mimetype,
                "res_model": order_sudo._name,
                "res_id": order_sudo.id,
            })
            order_sudo.installation_photo_ids = [Command.link(attachment.id)]
            available_slots -= 1
        return warnings

    def _get_installation_next_step_href(self):
        """ Href of the checkout step following the installation one.

        :rtype: str
        """
        website = request.website
        step = website._get_checkout_step(INSTALLATION_STEP_HREF)
        next_step = step._get_next_checkout_step(website._get_allowed_steps_domain()) if step else None
        return next_step.step_href if next_step else "/shop/payment"


class AppointmentInstallation(WebsiteAppointmentSale):

    def _redirect_to_payment(self, calendar_booking):
        """ Override of `website_appointment_sale`: when the booking is the installation of the
            current cart, go back to the installation step of the checkout (the native flow returns
            to the address step, which would hide the photo upload). """
        appointment_type = calendar_booking.appointment_type_id
        response = super()._redirect_to_payment(calendar_booking)
        # Si el slot ya no estaba disponible, el metodo nativo borra la reserva y redirige al error.
        if not calendar_booking.exists() or not calendar_booking.order_line_id:
            return response
        order_sudo = request.cart
        if order_sudo and order_sudo.installation_appointment_type_id == appointment_type:
            self._remove_previous_installation_bookings(order_sudo, calendar_booking)
            return request.redirect(INSTALLATION_STEP_HREF)
        return response

    def _remove_previous_installation_bookings(self, order_sudo, calendar_booking):
        """ Keep a single installation booking in the cart.

        Rescheduling means booking again, and the native flow adds one cart line per booking. The
        previous lines (with their bookings) are dropped so the customer does not end up paying two
        installations.

        :param order_sudo: the current cart (sudo)
        :param calendar_booking: the booking just made, to be kept
        """
        appointment_type = order_sudo.installation_appointment_type_id
        previous_lines = order_sudo.order_line.filtered(
            lambda line: line.calendar_booking_ids
            and appointment_type in line.calendar_booking_ids.appointment_type_id
            and calendar_booking not in line.calendar_booking_ids
        )
        previous_lines.unlink()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
