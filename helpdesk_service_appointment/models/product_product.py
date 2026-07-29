# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

# Mapeo unidad -> kwarg de relativedelta. Debe seguir el MISMO criterio que
# sk_customer_product_warranty/models/stock_move_line.py para no divergir del calculo de
# garantia que ya usa el resto del sistema (unidad desconocida -> sin garantia calculable).
WARRANTY_UNIT_TO_RELATIVEDELTA_KWARG = {
    "day": "days",
    "week": "weeks",
    "month": "months",
    "year": "years",
}


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _get_partner_service_products(self, partner):
        """Cerraduras entregadas al commercial partner (y sus contactos), con primera y ultima
        fecha de entrega, para armar "sus cerraduras" en el portal de service y para revalidar
        el ``product_id`` del POST (anti-IDOR, D25/D26 de la spec).

        :param partner: res.partner del usuario logueado
        :return: lista de dicts ``{'product': product.product (sudo), 'first_delivery': date,
            'last_delivery': date}``, uno por producto (dedupe de unidades), ordenada por nombre
        :rtype: list
        """
        if not partner:
            return []
        commercial = partner.commercial_partner_id or partner

        # sudo: el portal no lee movimientos de stock; se leen solo agregados (producto +
        # fechas min/max) del propio commercial partner. No es una copia del nativo
        # _compute_suitable_product_ids (helpdesk_stock): ese tambien suma ventas confirmadas
        # sin entregar, que aca no sirven porque la garantia necesita una entrega real (D25).
        groups = self.env["stock.move.line"].sudo()._read_group(
            domain=[
                ("state", "=", "done"),
                ("picking_code", "=", "outgoing"),
                ("picking_id.partner_id", "child_of", commercial.id),
                ("picking_id.is_replacement", "=", False),
            ],
            groupby=["product_id"],
            aggregates=["date:min", "date:max"],
        )

        items = []
        for product, date_min, date_max in groups:
            if not product:
                continue
            items.append({
                "product": product,
                # Los agregados date:min/date:max son Datetime en UTC: se normalizan a la tz
                # del usuario para que una entrega de noche no se lea como el dia siguiente.
                "first_delivery": fields.Datetime.context_timestamp(self, date_min).date() if date_min else False,
                "last_delivery": fields.Datetime.context_timestamp(self, date_max).date() if date_max else False,
            })
        items.sort(key=lambda item: item["product"].display_name)
        return items

    def _get_service_warranty(self, first_delivery=None, last_delivery=None, lot=None):
        """Estado de garantia efectivo de una unidad entregada, sin depender de numeros de
        serie (D20 de la spec): nunca lanza excepcion, un producto mal configurado devuelve
        ``unknown`` (D23).

        :param first_delivery: fecha (Date) de la primera entrega al partner
        :param last_delivery: fecha (Date) de la ultima entrega al partner
        :param lot: stock.lot opcional; si trae warranty_expiry_date, esa fecha gana sobre el
            calculo por entregas (D22)
        :return: dict ``{'status': 'valid'|'expired'|'unknown', 'expiry_date': Date|False,
            'delivery_date': Date|False}``
        :rtype: dict
        """
        self.ensure_one()
        result = {"status": "unknown", "expiry_date": False, "delivery_date": False}

        if lot and lot.warranty_expiry_date:
            # El lote es el dato mas especifico: su fecha gana sobre el calculo por entregas.
            expiry = lot.warranty_expiry_date
        else:
            duration, unit, start_type, dummy_source = self._get_warranty_info()
            if not duration or duration <= 0 or not unit:
                # Producto sin garantia configurada (o warranty_tracking apagado, D23).
                return result
            if start_type == "manufacture":
                # Sin numero de serie no conocemos la fecha de fabricacion: usar la entrega
                # como proxy informaria mas garantia de la real (D21).
                return result
            base_date = last_delivery if start_type == "last_sale" else first_delivery
            if not base_date:
                return result
            relativedelta_kwarg = WARRANTY_UNIT_TO_RELATIVEDELTA_KWARG.get(unit)
            if not relativedelta_kwarg:
                return result
            expiry = base_date + relativedelta(**{relativedelta_kwarg: duration})
            result["delivery_date"] = base_date

        result["expiry_date"] = expiry
        result["status"] = "valid" if expiry >= fields.Date.context_today(self) else "expired"
        return result

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
