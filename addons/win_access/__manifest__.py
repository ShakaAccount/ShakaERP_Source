{
    "name": "Windows Access Manager",
    "version": "19.0.1.0.0",
    "summary": "Manage groups + members across AD, local Windows, SSAS and PBIRS via the Windows Access Management API",
    "category": "Extra Tools",
    "license": "LGPL-3",
    "depends": ["base", "web", "entity"],
    "external_dependencies": {"python": ["requests", "pymssql"]},
    "data": [
        "security/ir.model.access.csv",
        "views/win_access_views.xml",
        "views/bi_user_access_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "win_access/static/src/win_access.scss",
            "win_access/static/src/pbirs_tree.js",
            "win_access/static/src/pbirs_tree.xml",
            "win_access/static/src/sync_panel.js",
            "win_access/static/src/sync_panel.xml",
            "win_access/static/src/member_list.js",
            "win_access/static/src/member_list.xml",
        ],
    },
    "application": True,
    "installable": True,
}
