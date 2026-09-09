# -*- coding: utf-8 -*-
import base64
import logging

from markupsafe import Markup, escape

from odoo import Command, _
from odoo.http import request, route
from odoo.tools.mimetypes import guess_mimetype

from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

# Limites del upload de fotos del formulario de service (el endpoint es auth='user').
MAX_PHOTOS = 10
MAX_PHOTO_SIZE = 10 * 1024 * 1024

# Tipos de direccion validos para "direccion de visita" (fix post-review, m1): sin este filtro,
# commercial.child_ids trae tambien contactos-persona (type='contact', ej. empleados de la
# empresa), que no son direcciones fisicas utilizables por el tecnico.
ADDRESS_PARTNER_TYPES = ("invoice", "delivery", "other")

# Los 7 helpdesk.tag semilla (tipo de problema, D10/D28); ver data/helpdesk_service_appointment_data.xml.
PROBLEM_TAG_XMLIDS = (
    "helpdesk_tag_not_opening",
    "helpdesk_tag_battery_drain",
    "helpdesk_tag_not_closing",
    "helpdesk_tag_battery_corrosion",
    "helpdesk_tag_connectivity",
    "helpdesk_tag_locked_out",
    "helpdesk_tag_other",
)


class HelpdeskServiceAppointmentPortal(CustomerPortal):
    """Formulario de portal /my/service/new (GET/POST): pedido de service/reparacion de una
    cerradura ya instalada, sin pasar por el eCommerce (reemplaza al JotForm "Agendar service
    con Nokey").
    """

    @route("/my/service/new", type="http", auth="user", website=True, methods=["GET"], sitemap=False)
    def portal_service_new(self, **kw):
        partner = request.env.user.partner_id
        values = self._prepare_service_form_values(partner)
        return request.render("helpdesk_service_appointment.portal_service_new", values)

    def _ticket_get_page_view_values(self, ticket, access_token, **kwargs):
        # Bloque Service en /my/ticket/<id>: solo aplica a tickets de un team de Service (para
        # el resto queda en False, y el template no muestra nada de esto). Se compara contra el
        # team que recibiria un pedido nuevo **y** contra el semilla: con varias companias, un
        # ticket viejo pudo nacer en otro team y su bloque tiene que seguir apareciendo (D38).
        values = super()._ticket_get_page_view_values(ticket, access_token, **kwargs)
        service_teams = self._get_service_team() | self._get_service_team_seed()
        values["service_appointment_url"] = (
            ticket._get_service_appointment_url() if ticket.team_id in service_teams else False
        )
        return values

    @route("/my/service/new", type="http", auth="user", website=True, methods=["POST"], sitemap=False)
    def portal_service_new_submit(self, **post):
        partner = request.env.user.partner_id
        commercial = partner.commercial_partner_id or partner
        warnings = []

        problem_tags = self._get_service_problem_tags()
        problem_tag = request.env["helpdesk.tag"]
        problem_tag_id = self._safe_int(post.get("problem_tag_id"))
        if problem_tag_id:
            problem_tag = request.env["helpdesk.tag"].sudo().browse(problem_tag_id)
        if problem_tag not in problem_tags:
            # RB02: el tipo de problema es obligatorio y debe ser uno de los 7 tags semilla.
            warnings.append(_("Please select a valid issue type."))

        service_products = request.env["product.product"]._get_partner_service_products(partner)
        valid_products = {item["product"] for item in service_products}
        product = request.env["product.product"]
        product_id = self._safe_int(post.get("product_id"))
        if product_id:
            candidate = request.env["product.product"].sudo().browse(product_id)
            if candidate not in valid_products:
                # RB03/anti-IDOR (D26): el producto debe estar entre las entregas del partner.
                warnings.append(_("The selected lock does not belong to your account."))
            else:
                product = candidate

        product_note = (post.get("product_note") or "").strip()
        installation_age = post.get("installation_age") or ""
        if not product and not product_note:
            # RB04: fallback "No esta en la lista / No lo se" exige el texto libre del modelo.
            warnings.append(_("Please select your lock, or describe its model if it is not on the list."))

        valid_addresses = commercial | commercial.child_ids.filtered(
            lambda p: p.type in ADDRESS_PARTNER_TYPES
        )
        address = request.env["res.partner"]
        visit_address_id = self._safe_int(post.get("visit_address_id"))
        if visit_address_id:
            candidate_address = request.env["res.partner"].sudo().browse(visit_address_id)
            if candidate_address not in valid_addresses:
                # RB05/anti-IDOR (D26): la direccion debe pertenecer al commercial partner.
                warnings.append(_("The selected visit address is not valid."))
            else:
                address = candidate_address

        if not (post.get("description") or "").strip():
            warnings.append(_("Please describe the issue."))

        if warnings:
            # Fix post-review (M3): ademas de los warnings, se persisten los VALORES tipeados
            # para que el cliente no pierda lo que cargo al rebotar. Solo strings: en rutas
            # type="http" Odoo mergea request.httprequest.files dentro de los params, y un
            # FileStorage en la sesion rompe su serializacion JSON (R1).
            request.session["helpdesk_service_appointment_warnings"] = warnings
            request.session["helpdesk_service_appointment_values"] = {
                key: value for key, value in post.items() if isinstance(value, str)
            }
            return request.redirect("/my/service/new")

        # sudo: el portal no crea helpdesk.ticket (mismo criterio que el form nativo de
        # website_helpdesk); producto y direccion ya se revalidaron contra los datos del
        # propio partner (anti-IDOR, D26).
        ticket = request.env["helpdesk.ticket"].sudo().create({
            "name": _("Service request: %(problem)s", problem=problem_tag.name),
            "team_id": self._get_service_team().id,
            "partner_id": partner.id,
            "tag_ids": [Command.link(problem_tag.id)],
            "description": self._prepare_service_description(post, product_note, installation_age),
            "product_id": product.id,
            "service_visit_address_id": address.id,
        })

        # W5 del review: si el team no es el de la compania de la request (no habia ninguno), el
        # cliente NO va a ver este ticket en su portal. El log del servidor no lo mira nadie: queda
        # como **nota interna** en el chatter, que es donde el agente si lo ve (mismo patron que los
        # avisos de `calendar.event`). Nota interna = no la ve el cliente en el portal.
        if ticket.company_id != request.env.company:
            ticket.message_post(
                body=_(
                    "This request was created in the Service team of %(team_company)s because "
                    "%(request_company)s has no Service team. The customer will NOT see this ticket "
                    "in their portal until a Service team is configured for their company.",
                    team_company=ticket.company_id.display_name,
                    request_company=request.env.company.display_name,
                ),
                subtype_xmlid="mail.mt_note",
            )

        photo_warnings = self._save_service_photos(ticket, request.httprequest.files.getlist("service_photos"))
        if photo_warnings:
            # Aviso al cliente sin abortar el pedido (RB06): el ticket ya lo tiene como
            # follower, asi que queda visible en su historial de comunicacion.
            ticket.message_post(body=Markup("<br/>").join(escape(warning) for warning in photo_warnings))

        # Redirect 303 a la URL derivada de invite.redirect_url (D13): nunca armada a mano.
        return request.redirect(ticket._get_service_appointment_url(), code=303)

    def _prepare_service_form_values(self, partner):
        commercial = partner.commercial_partner_id or partner
        Product = request.env["product.product"]

        products = []
        for item in Product._get_partner_service_products(partner):
            product = item["product"]
            warranty = product._get_service_warranty(item["first_delivery"], item["last_delivery"])
            products.append({"product": product, "warranty_status": warranty["status"]})

        address_ids = commercial | commercial.child_ids.filtered(
            lambda p: p.type in ADDRESS_PARTNER_TYPES
        )
        default_address_id = commercial.address_get(["delivery"]).get("delivery")

        # Fix post-review (M3): rehidratar el formulario con lo que el cliente tipeo si el POST
        # rebota por warnings (nunca se pierde lo cargado, salvo las fotos que no son
        # re-populables por seguridad del navegador).
        form_values = request.session.pop("helpdesk_service_appointment_values", {})
        selected_address_id = self._safe_int(form_values.get("visit_address_id")) or default_address_id
        selected_product_id = self._safe_int(form_values.get("product_id"))
        selected_problem_tag_id = self._safe_int(form_values.get("problem_tag_id"))

        values = self._prepare_portal_layout_values()
        values.update({
            "page_name": "service_new",
            "partner": partner,
            "products": products,
            "address_ids": address_ids,
            "default_address_id": default_address_id,
            "problem_tags": self._get_service_problem_tags(),
            "installation_age_options": self._get_installation_age_options(),
            "max_photos": MAX_PHOTOS,
            "max_photo_size_mb": MAX_PHOTO_SIZE // (1024 * 1024),
            "warnings": request.session.pop("helpdesk_service_appointment_warnings", []),
            "form_values": form_values,
            "selected_address_id": selected_address_id,
            "selected_product_id": selected_product_id,
            "selected_problem_tag_id": selected_problem_tag_id,
        })
        return values

    def _get_service_team_seed(self):
        """Team "Service" semilla del modulo.

        Nace en la compania **del usuario que instala el modulo** (`helpdesk.team.company_id` es
        `required` con `default=env.company`), que en una base multi-compania no tiene por que
        ser la del negocio: por eso no se usa directo, ver `_get_service_team` (D38).

        :return: recordset (sudo) de `helpdesk.team`
        """
        # sudo: el portal no lee helpdesk.team directamente por su cuenta.
        return request.env.ref(
            "helpdesk_service_appointment.helpdesk_team_service", raise_if_not_found=True,
        ).sudo()

    def _get_service_team(self):
        """Team de Service que recibe el pedido: el de la compania de la request (D38).

        El ancla es `request.env.company`, que en una request de website **no** es "la compania
        del usuario": el core la resuelve a la compania del **sitio** si el usuario la tiene
        permitida y, si no, a la propia del usuario (`website/models/ir_http.py`,
        `_frontend_pre_dispatch`).
        Es justo lo que hace falta acá, porque el ticket tiene que nacer en una compania que el
        cliente pueda **ver**: la record rule **global** de helpdesk (`helpdesk_ticket_company_rule`,
        sin `groups`, se ANDea con la del portal) filtra por `company_ids`, asi que un ticket de otra
        compania le queda invisible en `/my/tickets` (y el cliente cree que su pedido se perdio).

        Se prefiere el semilla cuando ya es el de esa compania (instalacion mono-compania: mismo
        comportamiento que antes). Si no, se busca el team de service de la compania. Si esa
        compania no tiene ninguno, se cae al semilla y se loguea: es preferible que el pedido
        entre a un team equivocado —y quede el aviso en el log— que perder el pedido del cliente.

        :return: recordset (sudo) de `helpdesk.team`, siempre con un registro
        """
        seed = self._get_service_team_seed()
        company = request.env.company
        if seed.company_id == company:
            return seed
        # sudo: el portal no lee helpdesk.team. Criterio del "team de service" de una compania:
        # los dos flags que el flujo necesita de verdad — `use_fsm` (la visita es una tarea de
        # Field Service, D1) y `privacy_visibility='portal'` (sin eso la record rule del portal
        # ni le muestra el ticket al cliente, D27). Desempate estable por `id`.
        teams = request.env["helpdesk.team"].sudo().search([
            ("company_id", "=", company.id),
            ("use_fsm", "=", True),
            ("privacy_visibility", "=", "portal"),
        ], order="id")
        if teams:
            # Se prefiere uno con proyecto de Field Service: un team sin `fsm_project_id` agenda la
            # cita pero **no** genera la tarea del tecnico (queda solo una nota en el chatter), asi
            # que entre varios candidatos es el peor. Desempate final estable por `id`.
            team = teams.filtered("fsm_project_id")[:1] or teams[:1]
            if len(teams) > 1:
                # Un misrouteo por ambiguedad es indiagnosticable a posteriori si no queda traza.
                _logger.warning(
                    "helpdesk_service_appointment: la compania %s tiene %s teams de service "
                    "(use_fsm + visibilidad portal): %s. Se usa %s (id %s). Si no es el correcto, "
                    "ajustar las marcas del team en Helpdesk > Configuracion > Equipos.",
                    company.display_name, len(teams), teams.mapped("display_name"),
                    team.display_name, team.id,
                )
            return team
        _logger.warning(
            "helpdesk_service_appointment: la compania %s (%s) no tiene un team de service "
            "(use_fsm + visibilidad portal); el pedido entra al team semilla %s de %s y el "
            "cliente NO va a verlo en su portal. Ver README, Configuracion.",
            company.display_name, company.id, seed.display_name, seed.company_id.display_name,
        )
        return seed

    def _get_service_problem_tags(self):
        """Los 7 helpdesk.tag semilla (tipo de problema, D10/D28)."""
        Tag = request.env["helpdesk.tag"].sudo()
        tags = Tag.browse()
        for xml_id in PROBLEM_TAG_XMLIDS:
            tags |= request.env.ref(
                "helpdesk_service_appointment.%s" % xml_id, raise_if_not_found=True,
            ).sudo()
        return tags

    def _get_installation_age_options(self):
        # Rango de antiguedad de instalacion para el fallback "No esta en la lista / No lo se"
        # (proxy del JotForm, D8). Se arma en el metodo (no a nivel de modulo) para que _()
        # traduzca con el idioma de la request actual.
        return [
            ("lt_6m", _("Less than 6 months")),
            ("6m_1y", _("6 months to 1 year")),
            ("gt_1y", _("More than 1 year")),
        ]

    def _prepare_service_description(self, post, product_note, installation_age):
        """Descripcion HTML del ticket: problema + aclaraciones de direccion + (fallback:
        modelo declarado y antiguedad, D8). Los valores del cliente se escapan: description
        es un campo Html.
        """
        age_labels = dict(self._get_installation_age_options())
        lines = [Markup("<p>%s</p>") % escape((post.get("description") or "").strip())]

        address_notes = (post.get("address_notes") or "").strip()
        if address_notes:
            lines.append(Markup("<p><strong>%s:</strong> %s</p>") % (
                _("Visit address notes"), escape(address_notes),
            ))
        if product_note:
            lines.append(Markup("<p><strong>%s:</strong> %s</p>") % (
                _("Lock model (declared by customer)"), escape(product_note),
            ))
            if installation_age:
                lines.append(Markup("<p><strong>%s:</strong> %s</p>") % (
                    _("Installation age"), escape(age_labels.get(installation_age, installation_age)),
                ))
        return Markup("").join(lines)

    def _save_service_photos(self, ticket, uploads):
        """Guardar las fotos de la falla con los limites endurecidos (D11/RB06): tamaño,
        cantidad y ``guess_mimetype`` del contenido real. Patron endurecido de
        ``website_sale_installation_appointment._save_installation_photos``, pero los adjuntos
        se crean PENDIENTES (``res_model='mail.compose.message'``, ``res_id=0``): el
        ``message_post`` posterior los reasigna al ticket. Crearlos ya apuntando al ticket los
        perderia en silencio: ``mail.thread._process_attachments_for_post`` descarta los
        adjuntos de un usuario portal que no sean pendientes suyos.

        :return: lista de warnings de los archivos rechazados
        :rtype: list
        """
        warnings = []
        attachment_ids = []
        available_slots = MAX_PHOTOS
        for upload in uploads:
            if not upload or not upload.filename:
                continue
            if available_slots <= 0:
                warnings.append(_("You can upload up to %(max_photos)s photos.", max_photos=MAX_PHOTOS))
                break
            content = upload.read()
            if not content:
                continue
            if len(content) > MAX_PHOTO_SIZE:
                warnings.append(_(
                    "The file %(filename)s is too big (maximum %(max_size)s MB).",
                    filename=upload.filename, max_size=MAX_PHOTO_SIZE // (1024 * 1024),
                ))
                continue
            # Se valida el mimetype real del contenido, no el que declara el navegador.
            mimetype = guess_mimetype(content)
            if not mimetype.startswith("image/"):
                warnings.append(_("The file %(filename)s is not an image.", filename=upload.filename))
                continue
            # sudo: la foto la sube el cliente portal, que no crea ir.attachment por si mismo.
            attachment = request.env["ir.attachment"].sudo().create({
                "name": upload.filename,
                "datas": base64.b64encode(content),
                "mimetype": mimetype,
                "res_model": "mail.compose.message",
                "res_id": 0,
            })
            attachment_ids.append(attachment.id)
            available_slots -= 1

        if attachment_ids:
            ticket.message_post(
                body=_("Photos of the reported issue uploaded by the customer."),
                attachment_ids=attachment_ids,
            )
        return warnings

    def _safe_int(self, value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return False

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
