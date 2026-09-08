# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.addons.mail.tests.common import MailCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestCalendarEventMailBranding(MailCommon):
    """ Marca del correo de una cita de instalacion (D43, Plane #38).

    `MailCommon` ya deja armadas dos compañias (`company_admin`, la del usuario que corre el
    test/cron, y `company_2`, con su propio usuario `user_employee_c2`), ideales para probar el
    fix sin fixtures propias.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Con `email`: el destinatario del test no se filtra hoy por falta de mail, pero sin el, un
        # endurecimiento futuro del core dejaria el fallo disfrazado de "no se genero el mail" en
        # vez de "el branding esta mal".
        cls.order_partner = cls.env["res.partner"].create({
            "name": "Test Mail Branding Customer",
            "email": "branding.customer@example.com",
        })
        cls.product = cls.env["product.product"].create({"name": "Test Installation Product"})
        # Fecha relativa (no hardcodeada): solo importa que sea futura, `stop > now` es lo unico
        # que verifica `_send_reminder` para elegir a que citas les manda el recordatorio.
        start = fields.Datetime.now() + timedelta(days=1)
        cls.event = cls.env["calendar.event"].create({
            "name": "Test Installation Appointment",
            "start": start,
            "stop": start + timedelta(hours=1),
            "partner_ids": [(4, cls.order_partner.id)],
        })

    def test_mail_get_companies_order_wins(self):
        """ La compañia del pedido que origino la cita gana, aunque el `default` sea otra. """
        order = self.env["sale.order"].create({
            "partner_id": self.order_partner.id,
            "company_id": self.company_2.id,
        })
        self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": self.product.id,
            "calendar_event_id": self.event.id,
        })
        companies = self.event._mail_get_companies(default=self.company_admin)
        self.assertEqual(companies[self.event.id], self.company_2)

    def test_mail_get_companies_organizer_fallback_without_order(self):
        """ Sin pedido asociado (cita por link compartido), gana la compañia del organizador. """
        self.event.user_id = self.user_employee_c2  # pertenece a `company_2`
        companies = self.event._mail_get_companies(default=self.company_admin)
        self.assertEqual(companies[self.event.id], self.company_2)

    def test_mail_get_companies_falls_back_to_create_uid_without_order_or_organizer(self):
        """ Rama 3: ni pedido ni organizador -> compania de quien creo la cita (molde del propio
        core para citas, `odoo/addons/calendar/controllers/main.py:L66`), antes que el `default`
        que reciba el llamador. El `create_uid` de la cita es OdooBot (el `setUpClass` corre con
        `SUPERUSER_ID`), cuya compañia es la misma `main_company` que `company_admin` — de ahi el
        valor esperado.
        """
        self.event.user_id = False
        companies = self.event._mail_get_companies(default=self.company_2)
        self.assertEqual(companies[self.event.id], self.company_admin)

    def test_notification_layout_uses_order_company_branding(self):
        """ CA38 — el test que habria cachado el bug real: el override que importa no es el
        resolvedor de compañia sino `_notify_by_email_prepare_rendering_context()`, que es quien
        pinta el layout. Se renderiza la notificacion de verdad (mismo camino que usa
        `_notify_attendees`, confirmacion Y recordatorio) y se verifica que el layout use el
        nombre (y por ende el logo/colores) de la compañia del pedido, no la del usuario que
        dispara la notificacion.
        """
        order = self.env["sale.order"].create({
            "partner_id": self.order_partner.id,
            "company_id": self.company_2.id,
        })
        self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": self.product.id,
            "calendar_event_id": self.event.id,
        })
        with self.mock_mail_gateway():
            self.event.with_context(no_document=True).sudo().message_notify(
                body="Test notification body",
                subject="Test notification subject",
                partner_ids=self.order_partner.ids,
                email_layout_xmlid="mail.mail_notification_light",
                force_send=False,
            )
        mails = self._new_mails.filtered(
            lambda mail: mail.model == "calendar.event" and mail.res_id == self.event.id
        )
        self.assertTrue(mails, "No se genero el mail.mail: revisar la config de notificacion del test.")
        body_html = mails[-1].body_html
        self.assertIn(self.company_2.name, body_html)
        self.assertNotIn(self.company_admin.name, body_html)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
