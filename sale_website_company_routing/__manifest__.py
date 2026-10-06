# -*- coding: utf-8 -*-
{
    "name": "sale_website_company_routing",
    "version": "1.0.0",
    "summary": "Ruteo de lineas de pedido entre compañias al confirmar y stock web por compañia",
    "description": """
En una base multi-compañia, un sitio web pertenece a una sola compañia y el carrito se crea siempre
en ella. Este modulo permite que un producto lo venda y despache otra compañia, y que la web muestre
el stock de la compañia que realmente lo tiene.

- Cada producto (o su categoria, con herencia por la categoria padre) declara la compañia que lo
  vende y despacha. Cada linea del pedido muestra esa compañia y se puede cambiar a mano.
- Al confirmar el pedido, las lineas de otra compañia se mueven a un pedido nuevo en esa compañia,
  confirmado y vinculado al original, con la lista de precios del cliente en la compañia destino y
  el precio convertido a su moneda con la cotizacion de esa compañia.
- El envio y el metodo de envio viajan con lo ruteado. Los descuentos globales (cupones y
  promociones automaticos, y los de modulos que enganchen los hooks) se recalculan en cada pedido.
- Cada producto (o su categoria) declara de que compañias se toma el stock que muestra el
  eCommerce: disponibilidad, tope del carrito y semaforo de stock.
- Sin configurar, el comportamiento es identico al core.
    """,
    "category": "Sales/Sales",
    "author": "Sunra",
    "website": "https://github.com/sunraargsh",
    "license": "LGPL-3",
    "depends": [
        "sale_stock",
        "website_sale_stock",
        "website_sale_collect",
        "sale_loyalty",
    ],
    "data": [
        "views/product_category_views.xml",
        "views/product_template_views.xml",
        "views/sale_order_views.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
