{
    "name": "Jalali (Persian) Calendar Support",
    "version": "19.0.1.0.0",
    "summary": "System-wide Jalali date display for forms, lists, calendar, search and reports",
    "category": "Localization",
    "author": "Your Company",
    "license": "LGPL-3",
    "depends": ["web", "base"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_users_views.xml",
    ],
    "assets": {
        "web._assets_core": [
            "jalali_date/static/src/js/jalali_utils.js",
            "jalali_date/static/src/js/datetime_picker_patch.js",
        ],
        "web.assets_backend": [
            "jalali_date/static/src/css/jalali_date.css",
            "jalali_date/static/src/js/jalali_utils.js",
            "jalali_date/static/src/js/date_datetime_field_patch.js",
            "jalali_date/static/src/js/datetime_picker_patch.js",
            "jalali_date/static/src/js/search_panel_patch.js",
            "jalali_date/static/src/js/calendar_view_patch.js",
            "jalali_date/static/src/xml/datetime_field_template_patch.xml",
            "jalali_date/static/src/xml/datetime_picker_template_patch.xml",
        ],
    },
    "installable": True,
    "application": False,
}
