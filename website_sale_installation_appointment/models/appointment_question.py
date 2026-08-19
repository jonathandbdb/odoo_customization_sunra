# -*- coding: utf-8 -*-
import re

import stdnum.ar

from odoo import _, fields, models

# Expresiones para los formatos numericos. Se aceptan espacios y separadores tipicos y se validan
# los digitos: el objetivo es que no entre texto libre ("cuatro coma cinco", "no se"), no imponer
# una notacion.
INTEGER_RE = re.compile(r"^\s*\d{1,6}\s*$")
DECIMAL_RE = re.compile(r"^\s*\d{1,5}([.,]\d{1,2})?\s*$")


class AppointmentQuestion(models.Model):
    _inherit = "appointment.question"

    answer_format = fields.Selection(
        selection=[
            ("free", "Free text"),
            ("integer", "Whole number"),
            ("decimal", "Number"),
            ("phone", "Phone number"),
            ("identification", "ID number (DNI / CUIT)"),
        ],
        string="Answer Format",
        default="free",
        required=True,
        help="Checks what the customer types before booking. Free text accepts anything; the other "
             "formats reject answers that are not a valid number, phone or ID.",
    )

    installation_measure_guide = fields.Boolean(
        string="Show Measuring Guide",
        help="Show the door measuring diagrams (A and B) right before this question in the "
             "appointment form. Tick it on the door thickness question: the customer sees what to "
             "measure exactly where the answer is asked, in every path that uses this question.",
    )

    def _effective_answer_format(self):
        """Formato real a aplicar: una pregunta de tipo Telefono valida como telefono aunque no se
        haya tocado el formato (es lo que el funcional espera al elegir ese tipo de campo).

        :rtype: str
        """
        self.ensure_one()
        if self.answer_format == "free" and self.question_type == "phone":
            return "phone"
        return self.answer_format

    def _answer_input_attrs(self):
        """Atributos HTML del input segun el formato, para que el navegador ya frene el error.

        El formulario nativo llama a ``reportValidity()`` antes de enviar, asi que un ``pattern``
        alcanza para que el cliente vea el problema en el campo (sin perder lo que cargo).

        :return: dict de atributos (``type``, ``inputmode``, ``pattern``, ``maxlength``, ``title``)
        :rtype: dict
        """
        answer_format = self._effective_answer_format()
        if answer_format == "integer":
            return {"type": "text", "inputmode": "numeric", "pattern": r"\d{1,6}", "maxlength": "6",
                    "title": _("Enter a whole number, digits only.")}
        if answer_format == "decimal":
            return {"type": "text", "inputmode": "decimal", "pattern": r"\d{1,5}([.,]\d{1,2})?",
                    "maxlength": "8", "title": _("Enter a number, for example 4 or 4,5.")}
        if answer_format == "phone":
            return {"type": "tel", "inputmode": "tel", "pattern": r"[\d\s()+.-]{8,20}", "maxlength": "20",
                    "title": _("Enter a valid phone number, digits only.")}
        if answer_format == "identification":
            return {"type": "text", "inputmode": "numeric", "pattern": r"[\d.\s-]{7,13}", "maxlength": "13",
                    "title": _("Enter a valid DNI (8 digits) or CUIT (11 digits).")}
        # El nativo emite type="phone"/"char", que NO existen en HTML y el navegador trata como
        # texto libre; se normaliza a "text" para no arrastrar ese error.
        return {"type": "text"}

    def _validate_answer(self, value):
        """Validar del lado del servidor lo que el cliente escribio.

        :param value: respuesta cargada
        :type value: str
        :return: mensaje de error, o False si la respuesta es valida
        :rtype: str | bool
        """
        answer_format = self._effective_answer_format()
        value = (value or "").strip()
        if not value or answer_format == "free":
            return False
        if answer_format == "integer" and not INTEGER_RE.match(value):
            return _('"%(question)s": enter a whole number.', question=self.name)
        if answer_format == "decimal" and not DECIMAL_RE.match(value):
            return _('"%(question)s": enter a number, for example 4 or 4,5.', question=self.name)
        if answer_format == "phone" and len(re.sub(r"\D", "", value)) < 8:
            return _('"%(question)s": enter a valid phone number.', question=self.name)
        if answer_format == "identification":
            digits = re.sub(r"\D", "", value)
            # Mismo criterio que la localizacion (stdnum): 11 digitos = CUIT/CUIL con digito
            # verificador, 7-8 = DNI.
            module = stdnum.ar.cuit if len(digits) == 11 else stdnum.ar.dni
            if not module.is_valid(digits):
                return _('"%(question)s": the ID number is not valid.', question=self.name)
        return False

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
