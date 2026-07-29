# odoo_customization_sunra

Repositorio de customizaciones del cliente Sunra sobre Odoo 19 Enterprise. Agrupa los módulos
custom que corren sobre la instancia `sunrasa` (sin localización, sin módulos de terceros salvo los
que se prueben explícitamente).

## Módulos

| Módulo | Resumen |
|--------|---------|
| `sk_customer_product_warranty` | Gestión de garantías de producto por categoría/plantilla/variante y seguimiento por número de serie |
| `base_import_ux` | Mejoras UX del asistente de importación nativo: filas de cabecera a saltear (CSV) y fecha DD-MM-YYYY por defecto en extractos bancarios (caso Mercado Pago) |
| `website_sale_installation_appointment` | eCommerce: método de envío con instalación — agenda la Cita en el checkout, pide fotos del lugar, genera la tarea de Field Service e invita al cliente al portal al confirmar la venta |
| `helpdesk_service_appointment` | Portal de service/reparación de cerraduras instaladas: formulario `/my/service/new` → ticket de Helpdesk → Cita → tarea de Field Service, con estado de garantía informativo |