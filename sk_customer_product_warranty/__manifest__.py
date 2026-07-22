{
    'name': "Customer Warranty",
    'summary': "Product warranty management and serial number-based warranty tracking.",
    'description': """
Product Warranty Module for Customers
==============================
""",
    'author': "Salih Kalender",
    'website': "https://github.com/SalihKalender28",
    'category': 'Inventory/Inventory',
    'version': '19.0.1.0.0',
    'depends': ['product', 'stock'],
    'data': [
        'views/product_views.xml',
        'views/product_category_views.xml',
        'views/stock_lot_views.xml',
    ],
    'images': [
        'static/description/icon.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

