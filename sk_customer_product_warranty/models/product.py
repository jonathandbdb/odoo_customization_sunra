# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = ['product.template', 'warranty.mixin']

    warranty_tracking = fields.Boolean(
        string='Warranty Tracking',
        help='Enable warranty tracking for this product'
    )
    warranty_type = fields.Selection([
        ('category', 'Use Category Warranty'),
        ('custom', 'Custom Warranty'),
    ], string='Warranty Type', default='category')
    
    effective_warranty = fields.Char(
        string='Effective Warranty',
        compute='_compute_effective_warranty',
        store=False
    )

    @api.depends('warranty_tracking', 'warranty_type', 'warranty_start_type', 'warranty_duration', 'warranty_unit', 'categ_id.warranty_duration', 'categ_id.warranty_unit', 'categ_id.warranty_start_type')
    def _compute_effective_warranty(self):
        for rec in self:
            if not rec.warranty_tracking:
                rec.effective_warranty = False
                continue
            
            duration, unit, start_type, source = rec._get_warranty_info()
            if duration and duration > 0:
                rec.effective_warranty = rec._format_warranty_display(duration, unit, start_type, source)
            else:
                rec.effective_warranty = False

    def _get_warranty_info(self):
        """Ürün veya kategori garantisini döndürür (duration, unit, start_type, source)"""
        self.ensure_one()
        
        if not self.warranty_tracking:
            return (0, None, None, None)
        
        if self.warranty_type == 'custom' and self.warranty_duration and self.warranty_duration > 0:
            return (self.warranty_duration, self.warranty_unit or 'month', self.warranty_start_type or 'first_sale', 'Template')
        elif self.warranty_type == 'category' and self.categ_id and self.categ_id.warranty_duration and self.categ_id.warranty_duration > 0:
            return (self.categ_id.warranty_duration, self.categ_id.warranty_unit or 'month', self.categ_id.warranty_start_type or 'first_sale', 'Category')
        
        return (0, None, None, None)

    def _prepare_variant_values(self, combination):
        values = super()._prepare_variant_values(combination)
        values['warranty_tracking'] = self.warranty_tracking
        return values


class ProductProduct(models.Model):
    _inherit = ['product.product', 'warranty.mixin']

    warranty_tracking = fields.Boolean(
        string='Warranty Tracking',
        help='Enable warranty tracking for this variant'
    )
    warranty_type = fields.Selection([
        ('category', 'Use Category Warranty'),
        ('template', 'Use Template Warranty'),
        ('custom', 'Custom Warranty'),
    ], string='Warranty Type', default='template')
    effective_warranty = fields.Char(
        string='Effective Warranty',
        compute='_compute_effective_warranty',
        store=False
    )

    @api.depends('warranty_tracking', 'warranty_type', 'warranty_duration', 'warranty_unit', 'warranty_start_type',
                 'product_tmpl_id.warranty_tracking', 'product_tmpl_id.warranty_type', 'product_tmpl_id.warranty_start_type',
                 'product_tmpl_id.warranty_duration', 'product_tmpl_id.warranty_unit',
                 'product_tmpl_id.categ_id.warranty_duration', 'product_tmpl_id.categ_id.warranty_unit', 'product_tmpl_id.categ_id.warranty_start_type')
    def _compute_effective_warranty(self):
        for rec in self:
            if not rec.warranty_tracking:
                rec.effective_warranty = False
                continue
            
            duration, unit, start_type, source = rec._get_warranty_info()
            if duration and duration > 0:
                rec.effective_warranty = rec._format_warranty_display(duration, unit, start_type, source)
            else:
                rec.effective_warranty = False

    def _get_warranty_info(self):
        """Varyant, template veya kategori garantisini döndürür (duration, unit, start_type, source)"""
        self.ensure_one()
        
        if not self.warranty_tracking:
            return (0, None, None, None)
        
        if self.warranty_type == 'custom' and self.warranty_duration and self.warranty_duration > 0:
            return (self.warranty_duration, self.warranty_unit or 'month', self.warranty_start_type or 'first_sale', 'Variant')
        elif self.warranty_type == 'template':
            tmpl = self.product_tmpl_id
            if tmpl.warranty_tracking:
                if tmpl.warranty_type == 'custom' and tmpl.warranty_duration and tmpl.warranty_duration > 0:
                    return (tmpl.warranty_duration, tmpl.warranty_unit or 'month', tmpl.warranty_start_type or 'first_sale', 'Template')
                elif tmpl.warranty_type == 'category' and tmpl.categ_id and tmpl.categ_id.warranty_duration and tmpl.categ_id.warranty_duration > 0:
                    return (tmpl.categ_id.warranty_duration, tmpl.categ_id.warranty_unit or 'month', tmpl.categ_id.warranty_start_type or 'first_sale', 'Category')
        elif self.warranty_type == 'category' and self.product_tmpl_id.categ_id and self.product_tmpl_id.categ_id.warranty_duration and self.product_tmpl_id.categ_id.warranty_duration > 0:
            return (self.product_tmpl_id.categ_id.warranty_duration, self.product_tmpl_id.categ_id.warranty_unit or 'month', self.product_tmpl_id.categ_id.warranty_start_type or 'first_sale', 'Category')
        
        return (0, None, None, None)

