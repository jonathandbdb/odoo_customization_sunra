# -*- coding: utf-8 -*-
from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _is_installation_booking_line(self):
        """ Whether this line is the installation booked from the checkout.

        :rtype: bool
        """
        self.ensure_one()
        appointment_type = self.order_id.carrier_id.installation_appointment_type_id
        if not appointment_type:
            return False
        line_types = self.calendar_booking_ids.appointment_type_id | self.calendar_event_id.appointment_type_id
        return appointment_type in line_types

    def _timesheet_create_task_prepare_values(self, project):
        """ Override of `sale_project`: give the installation task a stable title.

        The line name of a booking is the booking description (appointment type + dates), and
        `sale_project` drops its first line when it matches the product name, leaving the task
        titled with the dates only. The crew reads this title on the Field Service board, so we
        keep it predictable: "<order> - <appointment type>".
        """
        values = super()._timesheet_create_task_prepare_values(project)
        if self._is_installation_booking_line():
            appointment_type = self.order_id.carrier_id.installation_appointment_type_id
            values["name"] = "%s - %s" % (self.order_id.name or "", appointment_type.name)
        return values

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
