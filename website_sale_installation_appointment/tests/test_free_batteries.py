# -*- coding: utf-8 -*-
from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFreeBatteries(TransactionCase):
    """ Flujos troncales de "pilas incluidas sin costo" (spec, T11).

    Fixtures deliberadamente livianas: las pilas de los tests que no ejercitan el gate de
    stock son NO storable (`is_storable=False`), asi que website_sale_stock nunca entra en
    juego y no hace falta un warehouse configurado.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env.ref("website.default_website")
        cls.partner = cls.env["res.partner"].create({"name": "Test Free Batteries Customer"})

        cls.battery = cls.env["product.product"].create({
            "name": "Test Battery Pack",
            "type": "consu",
            "is_storable": False,
            "list_price": 6000.0,
        })
        cls.battery_2 = cls.env["product.product"].create({
            "name": "Test Battery Pack 2",
            "type": "consu",
            "is_storable": False,
            "list_price": 3000.0,
        })

        cls.lock = cls.env["product.product"].create({
            "name": "Test Smart Lock",
            "type": "consu",
            "is_storable": False,
            "list_price": 50000.0,
        })
        cls.lock.product_tmpl_id.write({
            "free_battery_product_id": cls.battery.id,
            "free_battery_qty": 1,
        })
        cls.lock_2 = cls.env["product.product"].create({
            "name": "Test Smart Lock 2",
            "type": "consu",
            "is_storable": False,
            "list_price": 60000.0,
        })
        cls.lock_2.product_tmpl_id.write({
            "free_battery_product_id": cls.battery.id,
            "free_battery_qty": 1,
        })

        delivery_product = cls.env["product.product"].create({
            "name": "Test Shipping",
            "type": "service",
        })
        cls.carrier_free = cls.env["delivery.carrier"].create({
            "name": "Test Free Batteries Shipping",
            "delivery_type": "fixed",
            "product_id": delivery_product.id,
            "fixed_price": 0.0,
            "includes_free_batteries": True,
            "is_published": True,
        })
        cls.carrier_normal = cls.env["delivery.carrier"].create({
            "name": "Test Regular Shipping",
            "delivery_type": "fixed",
            "product_id": delivery_product.id,
            "fixed_price": 0.0,
        })

    def _create_order(self, carrier=False, lock=None, qty=1.0):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "website_id": self.website.id,
            "order_line": [Command.create({
                "product_id": (lock or self.lock).id,
                "product_uom_qty": qty,
            })],
        })
        if carrier:
            order.carrier_id = carrier.id
        return order

    def _free_lines(self, order):
        return order.order_line.filtered("is_free_battery_line")

    # === Agregacion / agrupacion / idempotencia (CA14, CA15, CA17) === #

    def test_sync_creates_free_line_grouped_by_battery_product(self):
        """ CA14, CA17: linea a $0, agregada por producto de pila (dos cerraduras -> una linea). """
        order = self._create_order(carrier=self.carrier_free, qty=2)
        order.order_line = [Command.create({
            "product_id": self.lock_2.id,
            "product_uom_qty": 3,
        })]
        order._sync_free_battery_lines()

        free_lines = self._free_lines(order)
        self.assertEqual(len(free_lines), 1)
        self.assertEqual(free_lines.product_id, self.battery)
        self.assertEqual(free_lines.product_uom_qty, 5.0)
        self.assertEqual(free_lines.price_unit, 0.0)

    def test_sync_updates_quantity_without_duplicating(self):
        """ CA15: cambiar la cantidad de la cerradura ajusta la linea, no la duplica. """
        order = self._create_order(carrier=self.carrier_free, qty=1)
        order._sync_free_battery_lines()
        order.order_line.filtered(lambda l: l.product_id == self.lock).product_uom_qty = 3
        order._sync_free_battery_lines()

        free_lines = self._free_lines(order)
        self.assertEqual(len(free_lines), 1)
        self.assertEqual(free_lines.product_uom_qty, 3.0)

    def test_sync_is_idempotent(self):
        """ RB13: correr el sync dos veces seguidas no cambia nada. """
        order = self._create_order(carrier=self.carrier_free, qty=2)
        order._sync_free_battery_lines()
        order._sync_free_battery_lines()

        free_lines = self._free_lines(order)
        self.assertEqual(len(free_lines), 1)
        self.assertEqual(free_lines.product_uom_qty, 2.0)

    def test_sync_toggles_with_carrier_flag(self):
        """ CA16, CA25: sin el flag no se crea nada; al prenderlo aparece, al apagarlo desaparece. """
        order = self._create_order(carrier=self.carrier_normal, qty=1)
        order._sync_free_battery_lines()
        self.assertFalse(self._free_lines(order))

        order.carrier_id = self.carrier_free
        order._sync_free_battery_lines()
        self.assertTrue(self._free_lines(order))

        order.carrier_id = self.carrier_normal
        order._sync_free_battery_lines()
        self.assertFalse(self._free_lines(order))

    # === Idioma de la linea (D28/RB19) === #

    def test_free_line_name_is_translated_for_spanish_customer(self):
        """ La linea gratis es la UNICA constancia para el cliente (D28/RB19: se ve en el
        carrito y en la factura); si el texto queda en ingles anula su unico proposito. Prueba
        que `_prepare_free_battery_line_vals` arma el `name` en el idioma del cliente Y que ese
        texto tiene traduccion cargada en el `.po` del modulo (no solo que el mecanismo de
        `_get_lang()` funciona, sino que el `msgid` no cae al ingles por falta de `msgstr`).
        """
        self.partner.lang = "es_AR"
        order = self._create_order(carrier=self.carrier_free)
        order._sync_free_battery_lines()
        free_line = self._free_lines(order)
        self.assertIn(
            "Incluidas con tu método de envío, sin cargo adicional.",
            free_line.name,
        )

    # === Defensas de precio (CA18, CA19, CA20) === #

    def test_free_line_price_stays_zero_on_forced_recompute(self):
        """ CA18: camino forzado (/shop/payment -> _recompute_prices con force_price_recomputation). """
        order = self._create_order(carrier=self.carrier_free)
        order._sync_free_battery_lines()
        free_line = self._free_lines(order)
        order._recompute_prices()
        self.assertEqual(free_line.price_unit, 0.0)

    def test_free_line_price_stays_zero_on_quantity_change(self):
        """ CA19: camino normal (no forzado) de _compute_price_unit. """
        order = self._create_order(carrier=self.carrier_free, qty=2)
        order._sync_free_battery_lines()
        free_line = self._free_lines(order)
        free_line.product_uom_qty = 4
        self.assertEqual(free_line.price_unit, 0.0)

    def test_free_line_has_no_discount_nor_pricelist_item(self):
        """ CA20: con una tarifa con descuento, la linea gratis no arrastra discount/pricelist_item_id. """
        order = self._create_order(carrier=self.carrier_free)
        # company_id explicito: la base de test es multi-compañia y el default del pricelist
        # no necesariamente coincide con la compañia del pedido (write() con company mismatch
        # tira UserError por check_company).
        pricelist = self.env["product.pricelist"].create({
            "name": "Test Discount Pricelist",
            "company_id": order.company_id.id,
            "item_ids": [Command.create({
                "applied_on": "3_global",
                "compute_price": "percentage",
                "percent_price": 10.0,
            })],
        })
        order.pricelist_id = pricelist
        order._sync_free_battery_lines()
        free_line = self._free_lines(order)

        # El riesgo real (D23/RB12) es la COMBINACION: _recompute_prices() resetea el
        # descuento a 0 y despues _compute_discount lo vuelve a aplicar segun la tarifa; sin
        # el guard de pricelist_item_id=False, este es el paso que lo prendería de nuevo.
        order._recompute_prices()

        self.assertFalse(free_line.pricelist_item_id)
        self.assertEqual(free_line.discount, 0.0)

    # === Alta manual separada / reorder / sellable (CA21, CA22, CA28) === #

    def test_manual_add_of_battery_creates_separate_paid_line(self):
        """ CA21: agregar a mano la misma pila crea una linea separada y paga (D24). """
        order = self._create_order(carrier=self.carrier_free)
        order._sync_free_battery_lines()
        self.assertEqual(len(self._free_lines(order)), 1)

        order._cart_add(self.battery.id, quantity=1)

        battery_lines = order.order_line.filtered(lambda l: l.product_id == self.battery)
        self.assertEqual(len(battery_lines), 2)
        free_battery_line = battery_lines.filtered("is_free_battery_line")
        paid_battery_line = battery_lines - free_battery_line
        self.assertEqual(free_battery_line.price_unit, 0.0)
        self.assertGreater(paid_battery_line.price_unit, 0.0)

    def test_free_line_reorder_not_allowed(self):
        """ CA22: "Volver a pedir" no debe re-agregar la pila. """
        order = self._create_order(carrier=self.carrier_free)
        order._sync_free_battery_lines()
        free_line = self._free_lines(order)
        self.assertFalse(free_line._is_reorder_allowed())

    def test_free_line_is_never_sellable_even_if_published(self):
        """ CA28: publicar la pila no vuelve editable/clickeable la linea gratis (D29). """
        order = self._create_order(carrier=self.carrier_free)
        order._sync_free_battery_lines()
        free_line = self._free_lines(order)
        self.battery.is_published = True
        self.assertFalse(free_line._is_sellable())

    # === Engaches de backend (CA23 a/b/c) === #

    def test_onchange_adds_free_battery_line(self):
        """ CA23(a): pedido armado en el backend trae la pila por el onchange, en memoria.

        `carrier_id` no esta en ninguna vista de formulario estandar de sale.order (el flujo
        real del backend para asignar envio es el boton "Add shipping", cubierto por
        `test_set_delivery_line_adds_free_battery_line`), asi que `Form` no lo precarga en el
        snapshot del onchange (`web/models/models.py`: `cache_values` solo copia los campos de
        `fields_spec`, i.e. los de la vista). Se ejercita el onchange directo sobre un registro
        `.new()` (self es `NewId`), que es exactamente el escenario que D26/T05 describe.
        """
        order_new = self.env["sale.order"].new({
            "partner_id": self.partner.id,
            "carrier_id": self.carrier_free.id,
            "order_line": [Command.create({
                "product_id": self.lock.id,
                "product_uom_qty": 2,
            })],
        })
        order_new._onchange_free_battery_lines()

        free_lines = order_new.order_line.filtered("is_free_battery_line")
        self.assertEqual(len(free_lines), 1)
        self.assertEqual(free_lines.product_uom_qty, 2.0)

    def test_onchange_removes_free_battery_line_via_form(self):
        """ CA23(a) complementario: la rama `Command.delete` del onchange -la que la spec marca
        como "el codigo mas riesgoso"- no tenia cobertura, y el test anterior no probaba el
        trigger real (`@api.onchange("order_line", "carrier_id")`) porque llamaba al metodo
        directo. Acá se arma un pedido que YA tiene `carrier_id` en base y la linea de pilas ya
        materializada (`_sync_free_battery_lines`), se abre un `Form` sobre ese pedido -en
        `models.onchange()` el registro se construye con `origin=self`, asi que `carrier_id`
        (fuera del `fields_spec` de la vista) se sigue leyendo del registro real- y se saca la
        cerradura del o2m: la linea de pilas fantasma tiene que desaparecer sola. Si alguien
        borra el decorador `@api.onchange`, este test cae en rojo (el anterior no lo detectaria).
        """
        order = self._create_order(carrier=self.carrier_free, qty=1)
        order._sync_free_battery_lines()
        self.assertTrue(self._free_lines(order))
        lock_index = next(
            index for index, line in enumerate(order.order_line)
            if line.product_id == self.lock
        )

        with Form(order) as order_form:
            order_form.order_line.remove(index=lock_index)
        order = order_form.save()

        self.assertFalse(self._free_lines(order))

    def test_set_delivery_line_adds_free_battery_line(self):
        """ CA23(b): boton "Add shipping" (choose.delivery.carrier) escribe por write(), sin onchange. """
        order = self._create_order()
        order.set_delivery_line(self.carrier_free, 0.0)
        self.assertEqual(len(self._free_lines(order)), 1)

    def test_action_confirm_syncs_before_confirming(self):
        """ CA23(c): red de seguridad final si nada disparo antes el sync. """
        order = self._create_order(carrier=self.carrier_free)
        self.assertFalse(self._free_lines(order))

        order.action_confirm()

        free_lines = self._free_lines(order)
        self.assertEqual(len(free_lines), 1)
        self.assertEqual(free_lines.price_unit, 0.0)

    # === Auto-curacion (CA24) === #

    def test_cart_update_line_quantity_self_heals_free_line(self):
        """ CA24: intentar borrar la linea gratis por /shop/cart/update la re-sincroniza (D21). """
        order = self._create_order(carrier=self.carrier_free, qty=2)
        order._verify_cart_after_update()
        free_line = self._free_lines(order)
        self.assertTrue(free_line)

        order._cart_update_line_quantity(free_line.id, 0)

        healed_line = self._free_lines(order)
        self.assertTrue(healed_line)
        self.assertEqual(healed_line.product_uom_qty, 2.0)

    # === Constraints de configuracion (CA26) === #

    def test_free_battery_config_constrains(self):
        """ CA26: cantidad negativa, cantidad sin producto, y producto que es su propia pila. """
        with self.assertRaises(ValidationError):
            self.lock.product_tmpl_id.write({"free_battery_qty": -1})
        with self.assertRaises(ValidationError):
            self.lock.product_tmpl_id.write({
                "free_battery_product_id": False,
                "free_battery_qty": 2,
            })
        with self.assertRaises(ValidationError):
            self.lock.product_tmpl_id.write({
                "free_battery_product_id": self.lock.id,
                "free_battery_qty": 1,
            })

    # === Duplicado de pedido (CA31) === #

    def test_copy_order_keeps_a_single_free_line_with_flag(self):
        """ CA31: duplicar el pedido conserva UNA linea a $0 con el flag (D33). """
        order = self._create_order(carrier=self.carrier_free, qty=2)
        order._sync_free_battery_lines()
        self.assertTrue(self._free_lines(order))

        duplicate = order.copy()
        dup_free_lines = self._free_lines(duplicate)
        self.assertEqual(len(dup_free_lines), 1)
        self.assertEqual(dup_free_lines.price_unit, 0.0)
        self.assertTrue(dup_free_lines.is_free_battery_line)

        # El sync ya reconoce la linea duplicada: no crea una segunda.
        duplicate._sync_free_battery_lines()
        self.assertEqual(len(self._free_lines(duplicate)), 1)

    # === Stock (CA32, tripwire del MRO de D34) === #

    def test_free_line_never_blocks_stock_availability(self):
        """ CA32: la linea gratis nunca bloquea el pago por stock (D34), aunque la pila sea
        storable, tenga stock 0 y no permita venta sin stock. """
        limited_battery = self.env["product.product"].create({
            "name": "Test Battery Pack (Limited Stock)",
            "type": "consu",
            "is_storable": True,
            "allow_out_of_stock_order": False,
        })
        self.lock.product_tmpl_id.free_battery_product_id = limited_battery
        order = self._create_order(carrier=self.carrier_free)
        order._sync_free_battery_lines()
        free_line = self._free_lines(order)
        self.assertEqual(free_line.product_id, limited_battery)

        # Sin el override, esta linea (storable, stock 0, sin venta sin stock) devolveria
        # False y el gate de pago tiraria ValidationError.
        self.assertTrue(free_line._check_availability())
        order._check_cart_is_ready_to_be_paid()

    # === Cantidades no positivas (CA33) === #

    def test_negative_quantity_does_not_create_free_line(self):
        """ CA33: una cerradura en cantidad -1 no genera linea de pilas (ni negativa ni en 0). """
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "website_id": self.website.id,
            "carrier_id": self.carrier_free.id,
            "order_line": [Command.create({
                "product_id": self.lock.id,
                "product_uom_qty": -1,
            })],
        })
        order._sync_free_battery_lines()
        self.assertFalse(self._free_lines(order))

    def test_cancelling_quantities_do_not_create_free_line(self):
        """ CA33: +1 y -1 que se cancelan -- si ya habia una linea de pilas, se borra. """
        order = self._create_order(carrier=self.carrier_free, qty=1)
        order._sync_free_battery_lines()
        self.assertTrue(self._free_lines(order))

        order.order_line.filtered(lambda l: l.product_id == self.lock).product_uom_qty = -1
        order._sync_free_battery_lines()
        self.assertFalse(self._free_lines(order))

    # === Multi-compañia (CA34) === #

    def test_battery_from_incompatible_company_is_skipped(self):
        """ CA34: una pila que termina en otra compañia se saltea, sin romper el carrito (D38). """
        other_company = self.env["res.company"].create({"name": "Test Other Company"})
        foreign_battery = self.env["product.product"].create({
            "name": "Test Foreign Battery",
            "type": "consu",
            "is_storable": False,
        })
        self.lock.product_tmpl_id.free_battery_product_id = foreign_battery
        # La pila se configura compatible (compañia compartida) y DESPUES pasa a ser
        # especifica de otra compañia (limpieza multi-compañia habitual): _check_company no
        # se vuelve a disparar sobre la plantilla de la cerradura, asi que la config queda
        # inconsistente en la practica sin que nadie se entere en el momento (D38).
        foreign_battery.company_id = other_company.id

        order = self._create_order(carrier=self.carrier_free)
        order._sync_free_battery_lines()
        self.assertFalse(self._free_lines(order))

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
