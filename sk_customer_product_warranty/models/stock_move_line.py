# -*- coding: utf-8 -*-
from odoo import models, fields, api
from dateutil.relativedelta import relativedelta


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'


    def _action_done(self):
        """Teslimat yapılırken lot'a garanti tarihi yaz"""
        res = super()._action_done()

        for move_line in self:
            # Sadece müşteriye gidenler-gelenler ve üretimden çıkanlar
            if not (move_line.lot_id and move_line.product_id.tracking == 'serial' and move_line.product_id.warranty_tracking):
                continue

            # Sadece ilgili hareketleri işle
            is_from_customer = move_line.location_id.usage == 'customer'
            is_to_customer = move_line.location_dest_id.usage == 'customer'
            is_from_production = move_line.location_id.usage == 'production'

            if not (is_from_customer or is_to_customer or is_from_production):
                continue

            product = move_line.product_id
            lot = move_line.lot_id
            duration, unit, start_type, source = product._get_warranty_info()

            if is_from_customer:
                # Müşteriden müşteriye gidene dokunma, last_sale bizim yaptığımız last_sale
                if is_to_customer:
                    continue
                # müşteriden gelen iade durumu
                elif start_type == 'last_sale' and lot.warranty_expiry_date:
                    lot.warranty_expiry_date = False
                continue

            # Üretimden çıkan ve üretim garantisi olmayanlar (müşteriye gitmemek şartıyla geçilir)
            if is_from_production and start_type != 'manufacture' and not is_to_customer:
                continue

            # İlk satış + mevcut garanti varsa dokunma
            if lot.warranty_expiry_date and start_type == 'first_sale':
                continue

            # Üretim garantisi + müşteriye giden + üretimden çıkmayan
            if start_type == 'manufacture' and is_to_customer and not is_from_production:
                continue

            # Garanti hesapla ve ata
            if duration and duration > 0 and unit:
                # Garanti başlangıç tarihini belirle
                base_date = move_line.date or fields.Datetime.now()

                if unit == 'day':
                    expiry_date = base_date + relativedelta(days=duration)
                elif unit == 'week':
                    expiry_date = base_date + relativedelta(weeks=duration)
                elif unit == 'month':
                    expiry_date = base_date + relativedelta(months=duration)
                elif unit == 'year':
                    expiry_date = base_date + relativedelta(years=duration)
                else:
                    continue

                lot.warranty_expiry_date = expiry_date.date()
        return res