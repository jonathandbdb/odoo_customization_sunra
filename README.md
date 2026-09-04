# odoo_customization_sunra

Repositorio de customizaciones del cliente Sunra sobre Odoo 19 Enterprise. Agrupa los módulos
custom que corren sobre la instancia `sunrasa` (sin localización, sin módulos de terceros salvo los
que se prueben explícitamente).

## Módulos

| Módulo | Resumen |
|--------|---------|
| `sk_customer_product_warranty` | Gestión de garantías de producto por categoría/plantilla/variante y seguimiento por número de serie |
| `base_import_ux` | Mejoras UX del asistente de importación nativo: filas de cabecera a saltear (CSV) y fecha DD-MM-YYYY por defecto en extractos bancarios (caso Mercado Pago) |
| `website_sale_installation_appointment` | eCommerce: método de envío con instalación — agenda la Cita en el checkout, pide fotos del lugar, genera la tarea de Field Service e invita al cliente al portal al confirmar la venta; y pilas incluidas sin cargo cuando el método de envío las incluye |
| `helpdesk_service_appointment` | Portal de service/reparación de cerraduras instaladas: formulario `/my/service/new` → ticket de Helpdesk → Cita → tarea de Field Service, con estado de garantía informativo |
| `sunra_mrp_component_serials` | Trazabilidad de motor/batería(s)/controlador contra el número de serie del chasis: traslado automático kit → bicicleta armada en la orden de fabricación e impresión sin intervención manual en remito y factura |
| `website_sale_payment_method_price` | eCommerce: descuento o recargo por medio de pago y por sitio — segundo precio en la grilla, la ficha y el carrito ("con TRANSFERENCIA"), y el descuento real con su IVA al elegir el medio en el checkout |
| `website_sale_variant_code` | eCommerce: muestra el código interno de la variante elegida (y no el de todas) en la página de producto y en el carrito, oculta por sitio la descripción de venta en el carrito donde repetía ese código, más la limpieza de las leyendas `Cod: ...` cargadas a mano en las descripciones |
| `website_sale_installment_plans_ux` | eCommerce: ajusta la leyenda de cuotas de `website_sale_installment_plans` — saca el total entre paréntesis y formatea el importe con la moneda del sitio (`En 6 cuotas de $ 58.823,53`) |
| `website_sale_wire_transfer_ux` | eCommerce: botón **Copiar CBU** y link **Cambiar medio de pago** en la confirmación cuando el pago queda pendiente por transferencia (el CBU sale de la cuenta bancaria de la compañía, no del texto del mensaje), más los datos de la transferencia en el mail de orden pendiente |
| `website_sale_grid_quantity` | eCommerce: botones de más y menos con la cantidad en cada tarjeta del listado, para cargar varias unidades sin entrar al producto — se activa por sitio y no agrega JavaScript propio (reusa el manejador del core) |
| `website_sale_stock_level_indicator` | eCommerce: semáforo de stock (sin stock / poco stock / stock normal / stock alto) en el listado y en la ficha, con niveles configurables por sitio en texto, color y cantidad, y la cantidad de niveles que haga falta |
| `website_currency_rate_header` | Sitio web: muestra la cotización vigente de una moneda en el encabezado (`Tipo de Cambio Oficial: $ 1.480,00`), por sitio — para catálogos con precios en dólares que se facturan en pesos |
