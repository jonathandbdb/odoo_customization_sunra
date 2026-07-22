# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class WarrantyMixin(models.AbstractModel):
    _name = 'warranty.mixin'
    _description = 'Warranty Information Mixin'

    warranty_duration = fields.Integer(
        string='Warranty Duration',
        help='Warranty duration for the product'
    )
    warranty_unit = fields.Selection([
        ('day', 'Day'),
        ('week', 'Week'),
        ('month', 'Month'),
        ('year', 'Year'),
    ], string='Warranty Unit', default='month')
    warranty_start_type = fields.Selection([
        ('first_sale', 'First Sale'),
        ('last_sale', 'Last Sale'),
        ('manufacture', 'Manufacturing'),
    ], string='Warranty Start Date', default='first_sale')

    def _format_warranty_display(self, duration, unit, start_type, source=None):
        """Garanti bilgisini formatlar"""
        if not duration or duration <= 0:
            return False
        
        unit_labels = {
            'day': _('Day') if duration == 1 else _('Days'),
            'week': _('Week') if duration == 1 else _('Weeks'),
            'month': _('Month') if duration == 1 else _('Months'),
            'year': _('Year') if duration == 1 else _('Years'),
        }
        start_type_labels = {
            'first_sale': _('First Sale'),
            'last_sale': _('Last Sale'),
            'manufacture': _('Manufacturing'),
        }
        start_type_label = start_type_labels.get(start_type, start_type)

        unit_label = unit_labels.get(unit, unit)
        if source:
            return f"{duration} {unit_label} - {start_type_label} ({source})"
        return f"{duration} {unit_label} - {start_type_label}"
