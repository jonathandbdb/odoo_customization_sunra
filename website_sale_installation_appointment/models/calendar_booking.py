# -*- coding: utf-8 -*-
from odoo import _, models


class CalendarBooking(models.Model):
    _inherit = "calendar.booking"

    def _get_description(self):
        """Aclarar en el pedido que la linea de la reserva es el TURNO, no un segundo cobro.

        El nativo arma la descripcion de la linea con el nombre del tipo de cita
        (`appointment_account_payment/models/calendar_booking.py`), asi que junto al metodo de envio
        "Envio con instalacion" el cliente leia dos lineas que parecian dos instalaciones. La
        instalacion se cobra en el envio; esta linea va en $0 y solo reserva el dia y la hora.
        """
        description = super()._get_description()
        carrier = self.env["delivery.carrier"].sudo().search(
            [("installation_appointment_type_id", "=", self.appointment_type_id.id)], limit=1,
        )
        if carrier:
            description = "%s\n%s" % (description, _(
                "Included in the %(carrier)s shipping method — no extra charge.",
                carrier=carrier.name,
            ))
        return description

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
