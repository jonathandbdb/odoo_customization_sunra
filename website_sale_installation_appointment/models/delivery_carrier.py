# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Trackings de servicio que hacen que el producto de la cita genere tarea (Field Service /
# Proyecto). El puente nativo appointment_account_payment crea la reserva solo si el producto
# genera tarea o tiene precio de lista.
TASK_SERVICE_TRACKINGS = ("task_in_project", "project_only", "task_global_project")


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    installation_appointment_type_id = fields.Many2one(
        comodel_name="appointment.type",
        string="Installation Appointment Type",
        ondelete="restrict",
        help="If set, this delivery method includes an installation: the customer must schedule a "
             "date and time (and upload photos of the installation site) before paying. Leave empty "
             "for regular delivery methods.",
    )
    installation_min_photos = fields.Integer(
        string="Minimum Installation Photos",
        default=1,
        help="Minimum amount of photos of the installation site the customer must upload before "
             "paying. Set to 0 to make photos optional.",
    )
    includes_free_batteries = fields.Boolean(
        string="Includes Free Batteries",
        default=False,
        help="Adds the batteries configured on the products in the cart at $0, because their "
             "cost is already covered by this shipping method. Do not repeat the request for "
             "batteries in the appointment type's checklist message if it applies.",
    )

    @api.constrains("installation_appointment_type_id")
    def _check_installation_appointment_type(self):
        # El flujo nativo (appointment_account_payment -> website_appointment_sale) solo crea la
        # reserva (calendar.booking) que se agrega al carrito si el tipo de cita tiene paso de pago
        # y un producto que genere linea de pedido. Sin eso, la cita se crearia suelta al reservar y
        # nunca quedaria atada al pedido: preferimos frenar la mala configuracion aca.
        for carrier in self.filtered("installation_appointment_type_id"):
            appointment_type = carrier.installation_appointment_type_id
            product = appointment_type.product_id
            if not appointment_type.has_payment_step or not product:
                raise ValidationError(_(
                    "The appointment type %(appointment_type)s cannot be used for installations: it "
                    "must have a payment step and a booking product, otherwise the appointment "
                    "cannot be linked to the eCommerce order.",
                    appointment_type=appointment_type.display_name,
                ))
            if product.service_tracking not in TASK_SERVICE_TRACKINGS and not product.lst_price:
                raise ValidationError(_(
                    "The product %(product)s of the appointment type %(appointment_type)s must "
                    "either create a task in a project or have a sales price, otherwise no booking "
                    "is created when the customer schedules the installation.",
                    product=product.display_name,
                    appointment_type=appointment_type.display_name,
                ))

    @api.constrains("installation_min_photos")
    def _check_installation_min_photos(self):
        for carrier in self:
            if carrier.installation_min_photos < 0:
                raise ValidationError(_("The minimum amount of installation photos cannot be negative."))

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
