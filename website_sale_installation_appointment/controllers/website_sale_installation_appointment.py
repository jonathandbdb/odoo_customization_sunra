# -*- coding: utf-8 -*-
import base64
import re
from urllib.parse import urlencode

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



def create_installation_photos(uploads, available_slots, res_model=False, res_id=0):
    """Crear los adjuntos de las fotos del lugar, validando tipo, tamano y cantidad.

    Compartida por el paso del checkout y por el formulario de la cita (link que comparte Nokey):
    en los dos casos sube fotos un usuario publico, asi que se valida el mimetype del CONTENIDO
    real y no lo que declara el navegador.

    :param uploads: lista de werkzeug FileStorage
    :param available_slots: cuantas fotos mas se aceptan
    :param res_model: modelo al que se atan (por defecto quedan pendientes, para message_post)
    :param res_id: id del registro
    :return: (ir.attachment creados, lista de avisos)
    :rtype: tuple
    """
    warnings = []
    attachments = request.env["ir.attachment"].sudo()
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
        # Se valida el mimetype real del contenido, no el que declara el navegador. Las fotos HEIC
        # del iPhone caen aca: se avisa con el nombre del archivo para que el cliente sepa cual.
        mimetype = guess_mimetype(content)
        if not mimetype.startswith("image/"):
            warnings.append(_(
                "The file %(filename)s is not an image we can read. If it comes from an iPhone, "
                "send it as JPG.", filename=upload.filename,
            ))
            continue
        attachments |= request.env["ir.attachment"].sudo().create({
            "name": upload.filename,
            "datas": base64.b64encode(content),
            "mimetype": mimetype,
            "res_model": res_model or "mail.compose.message",
            "res_id": res_id,
        })
        available_slots -= 1
    return attachments, warnings


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

        remove_photo_id = post.get("remove_photo_id")
        if remove_photo_id:
            return self.shop_installation_photo_remove(int(remove_photo_id))

        warnings = self._save_installation_photos(
            order_sudo, request.httprequest.files.getlist("installation_photos")
        )
        if warnings:
            request.session["installation_warnings"] = warnings
            return request.redirect(INSTALLATION_STEP_HREF)
        if post.get("stay_on_step") or order_sudo._get_installation_errors():
            # Subida de fotos desde el propio input (stay_on_step) o falta algo (cita o fotos):
            # se vuelve al paso, que ya muestra el detalle y las fotos cargadas.
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

    def shop_payment(self, **post):
        """ Override of `website_sale`: send the customer to the installation step if it is still
            incomplete.

        The "next step" link of the delivery step is rendered before the customer picks a delivery
        method, so it points to the payment page even when the chosen method requires an
        installation. Redirecting here keeps the flow going through the installation step instead of
        showing an error on the payment page.
        """
        order_sudo = request.cart
        if order_sudo and order_sudo._is_installation_required() and order_sudo._get_installation_errors():
            return request.redirect(INSTALLATION_STEP_HREF)
        return super().shop_payment(**post)

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
            "min_photos": order_sudo.carrier_id.installation_min_photos,
            "photo_count": order_sudo.installation_photo_count,
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
        attachments, warnings = create_installation_photos(
            uploads,
            MAX_PHOTOS - order_sudo.installation_photo_count,
            res_model=order_sudo._name,
            res_id=order_sudo.id,
        )
        for attachment in attachments:
            order_sudo.installation_photo_ids = [Command.link(attachment.id)]
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

    def appointment_type_id_form(self, appointment_type_id, date_time, duration, **kwargs):
        """ Override of `appointment`: surface the answer format errors of the previous attempt. """
        response = super().appointment_type_id_form(appointment_type_id, date_time, duration, **kwargs)
        if hasattr(response, "qcontext"):
            response.qcontext["installation_answer_errors"] = request.session.pop(
                "installation_answer_errors", [],
            )
        return response

    def appointment_form_submit(self, appointment_type_id, datetime_str, duration_str, name, email,
                                staff_user_id=None, available_resource_ids=None, asked_capacity=1,
                                guest_emails_str=None, **kwargs):
        """ Override of `appointment`: check the answers before booking the slot.

        Red de seguridad del `pattern` que ya frena en el navegador: si el cliente entra sin JS (o
        manda el POST a mano), las respuestas se validan igual y vuelve al formulario con el
        detalle en vez de quedar una cita con datos inservibles para el instalador.
        """
        appointment_type = request.env["appointment.type"].sudo().browse(int(appointment_type_id)).exists()
        errors = []
        for question in appointment_type.question_ids:
            key = "question_%s" % question.id
            if key not in kwargs:
                continue
            error = question._validate_answer(kwargs.get(key))
            if error:
                errors.append(error)
        # Fotos del lugar: solo en los tipos de cita que las piden (el link que comparte Nokey).
        photos = request.env["ir.attachment"].sudo()
        if appointment_type.installation_request_photos:
            uploads = request.httprequest.files.getlist("installation_photos")
            photos, photo_warnings = create_installation_photos(uploads, MAX_PHOTOS)
            errors.extend(photo_warnings)
            missing = appointment_type.installation_min_photos - len(photos)
            if missing > 0:
                errors.append(_(
                    "Please upload at least %(min_photos)s photo(s) of the installation site.",
                    min_photos=appointment_type.installation_min_photos,
                ))

        if errors:
            photos.unlink()
            request.session["installation_answer_errors"] = errors
            return request.redirect("/appointment/%s/info?%s" % (
                appointment_type.id, self._get_installation_info_query(
                    datetime_str, duration_str, staff_user_id, available_resource_ids,
                    asked_capacity, **kwargs,
                ),
            ))

        response = super().appointment_form_submit(
            appointment_type_id, datetime_str, duration_str, name, email,
            staff_user_id=staff_user_id, available_resource_ids=available_resource_ids,
            asked_capacity=asked_capacity, guest_emails_str=guest_emails_str, **kwargs,
        )
        if photos:
            event = self._get_submitted_appointment_event(response)
            if event:
                event._installation_post_photos(photos)
            else:
                photos.unlink()
        return response

    def _get_submitted_appointment_event(self, response):
        """ Recover the event just created by the native submit.

        El nativo redirige a ``/calendar/view/<access_token>``: se toma el token de ahi en vez de
        adivinar cual es la cita recien creada.

        :param response: respuesta del submit nativo
        :return: calendar.event (sudo) o un recordset vacio
        """
        location = response.headers.get("Location", "") if hasattr(response, "headers") else ""
        match = re.search(r"/calendar/view/([0-9a-f-]+)", location)
        if not match:
            return request.env["calendar.event"].sudo()
        return request.env["calendar.event"].sudo().search(
            [("access_token", "=", match.group(1))], limit=1,
        )

    def _get_installation_info_query(self, datetime_str, duration_str, staff_user_id,
                                     available_resource_ids, asked_capacity, **kwargs):
        """ Query string to render the appointment form again on the same slot.

        :rtype: str
        """
        params = {"date_time": datetime_str, "duration": duration_str, "asked_capacity": asked_capacity}
        if staff_user_id:
            params["staff_user_id"] = staff_user_id
        if available_resource_ids:
            params["available_resource_ids"] = available_resource_ids
        for key in ("allday", "resource_selected_id", "filter_appointment_type_ids",
                    "filter_staff_user_ids", "filter_resource_ids", "invite_token"):
            if kwargs.get(key):
                params[key] = kwargs[key]
        return urlencode(params)

    def _get_customer_partner(self):
        """ Override of `appointment`: fall back to the cart customer for guest checkouts.

        El nativo solo devuelve el partner del **usuario logueado**, asi que a un invitado que ya
        cargo sus datos en el paso de Direccion el formulario de la cita le vuelve a pedir nombre y
        mail; y al enviarlo, como el partner viene vacio, crea un contacto NUEVO sin buscar por
        email (`appointment/controllers/appointment.py`, `appointment_form_submit`) -> el mismo
        cliente quedaba duplicado en Contactos. Con el partner del carrito el formulario llega
        prellenado y se reutiliza ese contacto.
        """
        partner = super()._get_customer_partner()
        if partner:
            return partner
        order_sudo = request.cart
        if order_sudo and not order_sudo._is_anonymous_cart():
            return order_sudo.partner_id
        return partner

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
