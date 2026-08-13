# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Escodoo Customization",
    "version": "18.0.1.0.0",
    "summary": "Upgrade-safe UI customization ledger with semantic view anchors",
    "category": "Tools",
    "license": "AGPL-3",
    "author": "Escodoo",
    "website": "https://github.com/Escodoo/escodoo-customization",
    "development_status": "Beta",
    "maintainers": ["marcelsavegnago"],
    "depends": ["base"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/customization_operation_views.xml",
        "views/customization_bundle_views.xml",
        "views/menu.xml",
    ],
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
}
