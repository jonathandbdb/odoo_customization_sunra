# -*- coding: utf-8 -*-
import base64

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestInstallationTask(TransactionCase):
    """ Resultado de la instalacion en la tarea de Field Service (spec D63/D64, RB37..RB39). """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project_with_tilde = cls.env["project.project"].create({
            "name": "Test FSM Project (Require Photos)",
            "is_fsm": True,
            "company_id": cls.env.company.id,
            "installation_require_photos": True,
        })
        cls.project_without_tilde = cls.env["project.project"].create({
            "name": "Test FSM Project (No Photo Requirement)",
            "is_fsm": True,
            "company_id": cls.env.company.id,
            "installation_require_photos": False,
        })

    def _create_task(self, project):
        return self.env["project.task"].create({
            "name": "Test Installation Task",
            "project_id": project.id,
        })

    def _create_photo(self, task):
        return self.env["ir.attachment"].create({
            "name": "installed_lock.jpg",
            "datas": base64.b64encode(b"fake image content"),
            "res_model": "project.task",
            "res_id": task.id,
        })

    # === Gate de fotos (RB37/RB38, CA64 a CA67) === #

    def test_mark_as_done_without_photos_raises_on_project_with_tilde(self):
        """ CA64: el widget de estado (write() directo de `state`) sin foto -> UserError, sin
        cambiar el estado. """
        task = self._create_task(self.project_with_tilde)
        with self.assertRaises(UserError):
            task.write({"state": "1_done"})
        # super().write() ya dejo "1_done" en cache; sin ningun query posterior en este camino
        # nada lo flushea a la base, asi que descartar el pendiente (flush=False) y releer alcanza
        # para ver el valor real, sin necesitar un savepoint real.
        task.invalidate_recordset(flush=False)
        self.assertNotEqual(task.state, "1_done")

    def test_action_fsm_validate_without_photos_raises(self):
        """ CA64: el boton *Mark as done* (`action_fsm_validate()`) sin foto -> UserError. """
        task = self._create_task(self.project_with_tilde)
        with self.assertRaises(UserError):
            task.action_fsm_validate()
        task.invalidate_recordset(flush=False)
        self.assertNotEqual(task.state, "1_done")

    def test_action_fsm_validate_with_photo_succeeds(self):
        """ CA65: con al menos una foto, el boton *Mark as done* cierra la tarea. """
        task = self._create_task(self.project_with_tilde)
        photo = self._create_photo(task)
        task.write({"installation_photo_ids": [Command.set(photo.ids)]})
        task.action_fsm_validate()
        self.assertEqual(task.state, "1_done")

    def test_mark_as_done_with_photo_succeeds(self):
        """ CA65: con al menos una foto (subida en el mismo guardado), la tarea cierra. """
        task = self._create_task(self.project_with_tilde)
        photo = self._create_photo(task)
        task.write({"installation_photo_ids": [Command.set(photo.ids)], "state": "1_done"})
        self.assertEqual(task.state, "1_done")

    def test_cancel_without_photos_succeeds(self):
        """ CA66: cancelar (1_canceled) no exige fotos. """
        task = self._create_task(self.project_with_tilde)
        task.write({"state": "1_canceled"})
        self.assertEqual(task.state, "1_canceled")

    def test_project_without_tilde_allows_done_without_photos(self):
        """ CA67: sin el tilde del proyecto, la tarea se marca como hecha sin fotos. """
        task = self._create_task(self.project_without_tilde)
        task.write({"state": "1_done"})
        self.assertEqual(task.state, "1_done")

    def test_write_removing_last_photo_of_done_task_raises(self):
        """ CA73: quitarle por write() la ultima foto a una tarea ya hecha -> UserError. """
        task = self._create_task(self.project_with_tilde)
        photo = self._create_photo(task)
        task.write({"installation_photo_ids": [Command.set(photo.ids)], "state": "1_done"})
        with self.assertRaises(UserError):
            task.write({"installation_photo_ids": [Command.clear()]})

    # === Bloqueo del borrado del adjunto (D64, RB37, CA74) === #

    def test_unlink_last_photo_of_done_task_raises(self):
        """ CA74: borrar desde el chatter la ultima foto de una tarea hecha -> UserError, la
        foto sigue en la pagina Installation. """
        task = self._create_task(self.project_with_tilde)
        photo = self._create_photo(task)
        task.write({"installation_photo_ids": [Command.set(photo.ids)], "state": "1_done"})
        with self.assertRaises(UserError):
            photo.unlink()
        self.assertTrue(photo.exists())
        self.assertIn(photo, task.installation_photo_ids)

    def test_unlink_photo_with_another_remaining_succeeds(self):
        """ CA74: con dos fotos, borrar una desde el chatter deja la otra. """
        task = self._create_task(self.project_with_tilde)
        photo_a = self._create_photo(task)
        photo_b = self._create_photo(task)
        task.write({
            "installation_photo_ids": [Command.set((photo_a + photo_b).ids)],
            "state": "1_done",
        })
        photo_a.unlink()
        self.assertFalse(photo_a.exists())
        self.assertEqual(task.installation_photo_ids, photo_b)

    def test_unlink_last_photo_of_cancelled_task_succeeds(self):
        """ CA74: con la tarea cancelada, borrar la unica foto esta permitido. """
        task = self._create_task(self.project_with_tilde)
        photo = self._create_photo(task)
        task.write({"installation_photo_ids": [Command.set(photo.ids)], "state": "1_canceled"})
        photo.unlink()
        self.assertFalse(photo.exists())

    # === Precarga de modelos instalados (RB39, CA68) === #

    def test_installation_task_preloads_ecommerce_products(self):
        """ CA68/CA73: la tarea nace con los productos consu del pedido, sin la linea de envio
        (probado con un envio `consu` con `is_delivery = True`, para que la exclusion la pruebe
        `is_delivery` y no el `type`), sin las pilas gratis y sin el servicio de la reserva. """
        booking_product = self.env["product.product"].create({
            "name": "Test Installation Booking Service",
            "type": "service",
            "service_tracking": "task_global_project",
            "project_id": self.project_with_tilde.id,
        })
        appointment_type = self.env["appointment.type"].create({
            "name": "Test Installation Appointment Type",
            "has_payment_step": True,
            "product_id": booking_product.id,
        })
        shipping_product = self.env["product.product"].create({
            "name": "Test Shipping Product", "type": "consu", "is_storable": False,
        })
        carrier = self.env["delivery.carrier"].create({
            "name": "Test Installation Shipping",
            "delivery_type": "fixed",
            "product_id": shipping_product.id,
            "fixed_price": 0.0,
            "installation_appointment_type_id": appointment_type.id,
        })
        event = self.env["calendar.event"].create({
            "name": "Test Installation Visit",
            "appointment_type_id": appointment_type.id,
        })
        lock = self.env["product.product"].create({
            "name": "Test Smart Lock", "type": "consu", "is_storable": False,
        })
        battery = self.env["product.product"].create({
            "name": "Test Battery", "type": "consu", "is_storable": False,
        })
        partner = self.env["res.partner"].create({"name": "Test Installation Customer"})

        order = self.env["sale.order"].create({
            "partner_id": partner.id,
            "carrier_id": carrier.id,
            "order_line": [
                Command.create({"product_id": lock.id, "product_uom_qty": 1}),
                Command.create({
                    "product_id": battery.id,
                    "product_uom_qty": 1,
                    "is_free_battery_line": True,
                }),
                Command.create({
                    "product_id": shipping_product.id,
                    "product_uom_qty": 1,
                    "is_delivery": True,
                }),
                Command.create({
                    "product_id": booking_product.id,
                    "product_uom_qty": 1,
                    "calendar_event_id": event.id,
                }),
            ],
        })
        booking_line = order.order_line.filtered(lambda line: line.calendar_event_id == event)

        values = booking_line._timesheet_create_task_prepare_values(self.project_with_tilde)

        self.assertEqual(values.get("installation_product_ids"), [Command.set(lock.ids)])

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
