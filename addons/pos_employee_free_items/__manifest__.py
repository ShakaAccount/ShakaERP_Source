{
    "name": "POS Employee Free Items",
    "version": "19.0.3.0.0",
    "summary": "Allow POS employees to claim a limited number of free catalogue items each day.",
    "category": "Point of Sale",
    "depends": [
        "point_of_sale",
        "pos_hr",
        "auth_totp",
        "hr"
    ],
    "data": [
        "security/pos_free_item_security.xml",
        "security/ir.model.access.csv",
        "views/free_item_catalog_views.xml",
        "views/employee_free_allowance_views.xml",
        "views/pos_config_views.xml",
        "views/pos_order_views.xml",
        "data/pos_free_item_demo.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_employee_free_items/static/src/js/pos_free_items.js",
            "pos_employee_free_items/static/src/xml/pos_screen_templates.xml",
        ]
    },
    "author": "ShakaERP",
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False
}
