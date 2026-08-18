# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Web Customizer",
    "version": "18.0.1.0.0",
    "summary": "Upgrade-safe UI customization, exportable as a real addon",
    "category": "Tools",
    "license": "AGPL-3",
    "author": "Escodoo",
    "website": "https://github.com/Escodoo/web-customizer",
    "development_status": "Beta",
    "maintainers": ["marcelsavegnago"],
    "depends": ["web"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/customization_bundle_data.xml",
        "views/customization_operation_views.xml",
        "views/customization_bundle_views.xml",
        "views/menu.xml",
        "wizards/customization_export_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "web_customizer/static/src/**/*",
            # PivotRenderer is only defined in the lazy bundle, so importing it
            # from assets_backend would leave the whole bundle unresolved.
            ("remove", "web_customizer/static/src/customization_pivot_patch.js"),
        ],
        "web.assets_backend_lazy": [
            "web_customizer/static/src/customization_pivot_patch.js",
        ],
        "web.assets_unit_tests": [
            "web_customizer/static/tests/customization_patches.test.js",
        ],
        "web.assets_tests": [
            "web_customizer/static/tests/tours/**/*",
        ],
    },
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
}
