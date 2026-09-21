{
    "name": "Windows Access Manager",
    "version": "19.0.1.0.0",
    "summary": "Manage groups + members across AD, local Windows, SSAS and PBIRS via the Windows Access Management API",
    "category": "Extra Tools",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/ir.model.access.csv",
        "views/win_access_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "win_access/static/src/pbirs_tree.js",
            "win_access/static/src/pbirs_tree.xml",
        ],
    },
    "application": True,
    "installable": True,
}
