# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import ast
import io
import zipfile

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.escodoo_customization.models.exporter import (
    export_bundle_files,
    export_bundle_zip,
)

from .common import CustomizationCase


@tagged("post_install", "-at_install")
class TestCustomizationExport(CustomizationCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.model.data"].create(
            {
                "name": "tester_partner_form",
                "module": "escodoo_customization",
                "model": "ir.ui.view",
                "res_id": cls.form_view.id,
                "noupdate": True,
            }
        )

    def _applied_bundle(self, code="client_export"):
        bundle = self._create_bundle(
            code=code,
            operations=[
                Command.create(
                    {
                        "type": "add_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "payload": {
                            "ttype": "char",
                            "string": "Site Reference",
                            "name": "x_esc_export_ref",
                            "help": "Exported site code.",
                        },
                    }
                ),
                Command.create(
                    {
                        "type": "place_field",
                        "sequence": 20,
                        "model_id": self.partner_model.id,
                        "view_id": self.form_view.id,
                        "view_type": "form",
                        "anchor_name": "email",
                        "position": "after",
                        "payload": {"field_name": "x_esc_export_ref"},
                    }
                ),
            ],
        )
        bundle.action_apply()
        return bundle

    def test_export_zip_contains_installable_addon(self):
        bundle = self._applied_bundle()
        zip_bytes, filename = export_bundle_zip(bundle)
        self.assertEqual(filename, "client_export.zip")
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = set(zf.namelist())
            self.assertIn("client_export/__manifest__.py", names)
            self.assertIn("client_export/__init__.py", names)
            self.assertIn("client_export/data/ir_model_fields.xml", names)
            self.assertIn("client_export/views/inherited_views.xml", names)
            manifest_src = zf.read("client_export/__manifest__.py").decode()
            manifest = ast.literal_eval(
                "\n".join(
                    line
                    for line in manifest_src.splitlines()
                    if line and not line.startswith("#")
                )
            )
            fields_xml = zf.read("client_export/data/ir_model_fields.xml").decode()
            views_xml = zf.read("client_export/views/inherited_views.xml").decode()
        self.assertEqual(manifest["name"], "Test bundle")
        self.assertIn("base", manifest["depends"])
        self.assertIn("x_esc_export_ref", fields_xml)
        self.assertIn("Site Reference", fields_xml)
        self.assertIn("base.model_res_partner", fields_xml)
        self.assertIn('<field name="state">manual</field>', fields_xml)
        self.assertIn("escodoo_customization.tester_partner_form", views_xml)
        self.assertIn('name="x_esc_export_ref"', views_xml)
        self.assertIn('position="after"', views_xml)

    def test_export_skips_broken_operations(self):
        bundle = self._applied_bundle(code="client_export_broken")
        self.env["customization.operation"].create(
            {
                "bundle_id": bundle.id,
                "type": "place_field",
                "sequence": 90,
                "model_id": self.partner_model.id,
                "view_id": self.form_view.id,
                "view_type": "form",
                "anchor_name": "missing_anchor",
                "position": "after",
                "payload": {"field_name": "phone"},
            }
        )
        bundle.action_apply()
        broken = bundle.operation_ids.filtered(lambda o: o.state == "broken")
        self.assertTrue(broken)
        files = export_bundle_files(bundle)
        views_xml = files["views/inherited_views.xml"]
        self.assertNotIn("missing_anchor", views_xml)
        self.assertIn("x_esc_export_ref", views_xml)

    def test_export_without_applied_operations_raises(self):
        bundle = self._create_bundle(code="client_export_empty")
        with self.assertRaises(UserError):
            export_bundle_zip(bundle)

    def test_export_wizard_builds_attachment(self):
        bundle = self._applied_bundle(code="client_export_wizard")
        wizard = (
            self.env["customization.export.wizard"]
            .with_context(default_bundle_id=bundle.id)
            .create({})
        )
        self.assertTrue(wizard.data)
        self.assertEqual(wizard.filename, "client_export_wizard.zip")
