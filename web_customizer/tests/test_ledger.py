# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import CustomizationCase


@tagged("post_install", "-at_install")
class TestCustomizationLedger(CustomizationCase):
    def test_install_creates_sandbox_bundle(self):
        bundle = self.env.ref("web_customizer.bundle_sandbox")
        self.assertEqual(bundle.code, "sandbox")
        self.assertFalse(bundle.operation_ids)
        self.assertEqual(bundle.state, "draft")

    def test_bundle_code_constraint(self):
        with self.assertRaises(ValidationError):
            self._create_bundle(code="Invalid-Code")
        with self.assertRaises(ValidationError):
            self._create_bundle(code="1starts_with_digit")

    def test_add_field_name_double_underscore(self):
        bundle = self._create_bundle(code="client_underscore")
        with self.assertRaises(ValidationError):
            self.env["customization.operation"].create(
                {
                    "bundle_id": bundle.id,
                    "type": "add_field",
                    "model_id": self.partner_model.id,
                    "payload": {
                        "ttype": "char",
                        "string": "Bad",
                        "name": "x_cust_foo__bar",
                    },
                }
            )

    def test_add_field_requires_ttype(self):
        bundle = self._create_bundle(code="client_nottype")
        with self.assertRaises(ValidationError):
            self.env["customization.operation"].create(
                {
                    "bundle_id": bundle.id,
                    "type": "add_field",
                    "model_id": self.partner_model.id,
                    "payload": {"string": "No type"},
                }
            )

    def test_place_field_requires_view_and_anchor(self):
        bundle = self._create_bundle(code="client_place")
        with self.assertRaises(ValidationError):
            self.env["customization.operation"].create(
                {
                    "bundle_id": bundle.id,
                    "type": "place_field",
                    "model_id": self.partner_model.id,
                    "payload": {"field_name": "email"},
                }
            )

    def test_bundle_unlink_removes_generated_artifacts(self):
        bundle = self._create_bundle(
            code="client_unlink",
            operations=[
                Command.create(
                    {
                        "type": "add_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "payload": {
                            "ttype": "char",
                            "string": "Site Reference",
                            "name": "x_cust_unlink_ref",
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
                        "payload": {"field_name": "x_cust_unlink_ref"},
                    }
                ),
            ],
        )
        bundle.action_apply()
        field = self.env["ir.model.fields"]._get("res.partner", "x_cust_unlink_ref")
        self.assertTrue(field)
        view = bundle.operation_ids.filtered("generated_view_id").generated_view_id
        self.assertTrue(view)
        view_id, field_id = view.id, field.id
        bundle.unlink()
        self.assertFalse(self.env["ir.ui.view"].browse(view_id).exists())
        self.assertFalse(self.env["ir.model.fields"].browse(field_id).exists())

    def test_payload_ui_fields_sync_from_payload(self):
        bundle = self._create_bundle(code="client_payload_ui")
        operation = self.env["customization.operation"].create(
            {
                "bundle_id": bundle.id,
                "type": "add_field",
                "model_id": self.partner_model.id,
                "payload": {
                    "ttype": "char",
                    "string": "Site Reference",
                    "name": "x_cust_site_ref",
                    "help": "Internal site code.",
                },
            }
        )
        self.assertEqual(operation.payload_ttype, "char")
        self.assertEqual(operation.payload_string, "Site Reference")
        self.assertEqual(operation.payload_name, "x_cust_site_ref")
        self.assertEqual(operation.payload_help, "Internal site code.")
        self.assertIn('"ttype": "char"', operation.payload_json)

    def test_payload_ui_fields_write_back_to_payload(self):
        bundle = self._create_bundle(code="client_payload_write")
        operation = self.env["customization.operation"].create(
            {
                "bundle_id": bundle.id,
                "type": "place_field",
                "model_id": self.partner_model.id,
                "view_id": self.form_view.id,
                "view_type": "form",
                "anchor_name": "email",
                "payload": {"field_name": "phone"},
            }
        )
        operation.payload_field_name = "website"
        self.assertEqual(operation.payload.get("field_name"), "website")
        operation.write({"payload_field_name": "comment"})
        self.assertEqual(operation.payload.get("field_name"), "comment")

    def test_payload_ui_create_writes_json(self):
        bundle = self._create_bundle(code="client_payload_create")
        operation = self.env["customization.operation"].create(
            {
                "bundle_id": bundle.id,
                "type": "add_field",
                "model_id": self.partner_model.id,
                "payload_ttype": "char",
                "payload_string": "From UI",
                "payload_name": "x_cust_from_ui",
            }
        )
        self.assertEqual(operation.payload.get("ttype"), "char")
        self.assertEqual(operation.payload.get("string"), "From UI")
        self.assertEqual(operation.payload.get("name"), "x_cust_from_ui")
