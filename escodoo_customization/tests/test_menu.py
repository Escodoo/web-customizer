# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.escodoo_customization.hooks import uninstall_hook

from .common import CustomizationCase


@tagged("post_install", "-at_install")
class TestCustomizationMenu(CustomizationCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_menu = cls.env["ir.ui.menu"].create(
            {
                "name": "Customization Test Menu",
                "parent_id": cls.env.ref("base.menu_administration").id,
            }
        )
        cls.env["ir.model.data"].create(
            {
                "name": "tester_menu",
                "module": "escodoo_customization",
                "model": "ir.ui.menu",
                "res_id": cls.test_menu.id,
                "noupdate": True,
            }
        )
        cls.menu_xmlid = "escodoo_customization.tester_menu"

    def test_hide_menu_deactivates_and_restores(self):
        bundle = self._create_bundle(
            code="client_menu_hide",
            operations=[
                Command.create(
                    {
                        "type": "hide_menu",
                        "sequence": 10,
                        "menu_id": self.test_menu.id,
                        "anchor_kind": "menu",
                        "anchor_name": self.menu_xmlid,
                        "payload": {},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        self.assertFalse(self.test_menu.active)
        bundle.operation_ids.unlink()
        self.assertTrue(self.test_menu.active)

    def test_rename_menu(self):
        original = self.test_menu.name
        bundle = self._create_bundle(
            code="client_menu_rename",
            operations=[
                Command.create(
                    {
                        "type": "set_menu_string",
                        "sequence": 10,
                        "menu_id": self.test_menu.id,
                        "anchor_kind": "menu",
                        "anchor_name": self.menu_xmlid,
                        "payload": {"string": "People"},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(self.test_menu.name, "People")
        bundle.operation_ids.unlink()
        self.assertEqual(self.test_menu.name, original)

    def test_set_menu_groups(self):
        bundle = self._create_bundle(
            code="client_menu_groups",
            operations=[
                Command.create(
                    {
                        "type": "set_menu_groups",
                        "sequence": 10,
                        "menu_id": self.test_menu.id,
                        "anchor_kind": "menu",
                        "anchor_name": self.menu_xmlid,
                        "payload": {"groups": "base.group_system"},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(
            self.test_menu.groups_id.ids,
            [self.env.ref("base.group_system").id],
        )

    def test_create_from_ui_hide_menu(self):
        bundle = self._create_bundle(code="client_ui_menu")
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "hide",
                "anchor_kind": "menu",
                "menu_id": self.test_menu.id,
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        self.assertFalse(self.test_menu.active)
        hide = bundle.operation_ids
        self.assertEqual(hide.type, "hide_menu")
        self.assertEqual(hide.anchor_name, self.menu_xmlid)

    def test_create_from_ui_menu_without_xmlid_raises(self):
        menu = self.env["ir.ui.menu"].create(
            {
                "name": "No XML ID",
                "parent_id": self.env.ref("base.menu_administration").id,
            }
        )
        bundle = self._create_bundle(code="client_ui_menu_noxml")
        with self.assertRaises(UserError):
            self.env["customization.bundle"].create_from_ui(
                {
                    "bundle_id": bundle.id,
                    "action": "hide",
                    "anchor_kind": "menu",
                    "menu_id": menu.id,
                    "apply": True,
                }
            )

    def test_uninstall_hook_restores_menu(self):
        bundle = self._create_bundle(
            code="client_menu_uninstall",
            operations=[
                Command.create(
                    {
                        "type": "hide_menu",
                        "sequence": 10,
                        "menu_id": self.test_menu.id,
                        "anchor_kind": "menu",
                        "anchor_name": self.menu_xmlid,
                        "payload": {},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertFalse(self.test_menu.active)
        uninstall_hook(self.env)
        self.assertTrue(self.test_menu.active)

    def _partner_action_xmlid(self):
        return "base.action_partner_form"

    def test_add_menu_sibling(self):
        bundle = self._create_bundle(
            code="client_add_menu",
            operations=[
                Command.create(
                    {
                        "type": "add_menu",
                        "sequence": 10,
                        "menu_id": self.test_menu.id,
                        "anchor_kind": "menu",
                        "anchor_name": self.menu_xmlid,
                        "position": "after",
                        "payload": {
                            "string": "People",
                            "action_xmlid": self._partner_action_xmlid(),
                            "name": "menu_people",
                        },
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        created = bundle.operation_ids.generated_menu_id
        self.assertTrue(created.exists())
        self.assertEqual(created.name, "People")
        self.assertEqual(created.parent_id, self.test_menu.parent_id)
        self.assertGreater(created.sequence, self.test_menu.sequence)
        action = self.env.ref(self._partner_action_xmlid())
        self.assertEqual(created.action, action)
        created_id = created.id
        bundle.operation_ids.unlink()
        self.assertFalse(self.env["ir.ui.menu"].browse(created_id).exists())

    def test_add_submenu(self):
        bundle = self._create_bundle(
            code="client_add_submenu",
            operations=[
                Command.create(
                    {
                        "type": "add_menu",
                        "sequence": 10,
                        "menu_id": self.test_menu.id,
                        "anchor_kind": "menu",
                        "anchor_name": self.menu_xmlid,
                        "position": "inside",
                        "payload": {
                            "string": "People Child",
                            "action_xmlid": self._partner_action_xmlid(),
                        },
                    }
                ),
            ],
        )
        bundle.action_apply()
        created = bundle.operation_ids.generated_menu_id
        self.assertEqual(created.parent_id, self.test_menu)
        self.assertEqual(created.name, "People Child")

    def test_create_from_ui_add_menu(self):
        bundle = self._create_bundle(code="client_ui_add_menu")
        action = self.env.ref(self._partner_action_xmlid())
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "add_menu",
                "anchor_kind": "menu",
                "menu_id": self.test_menu.id,
                "payload": {
                    "string": "From UI",
                    "action_id": action.id,
                    "name": "menu_from_ui",
                },
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        operation = bundle.operation_ids
        self.assertEqual(operation.type, "add_menu")
        self.assertEqual(operation.position, "after")
        created = operation.generated_menu_id
        self.assertEqual(created.name, "From UI")
        self.assertEqual(created.parent_id, self.test_menu.parent_id)

    def test_create_from_ui_add_submenu(self):
        bundle = self._create_bundle(code="client_ui_add_submenu")
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "add_submenu",
                "anchor_kind": "menu",
                "menu_id": self.test_menu.id,
                "payload": {
                    "string": "Child From UI",
                    "action_xmlid": self._partner_action_xmlid(),
                },
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        operation = bundle.operation_ids
        self.assertEqual(operation.position, "inside")
        self.assertEqual(operation.generated_menu_id.parent_id, self.test_menu)

    def test_create_from_ui_add_menu_without_action_raises(self):
        bundle = self._create_bundle(code="client_ui_add_menu_noact")
        with self.assertRaises(UserError):
            self.env["customization.bundle"].create_from_ui(
                {
                    "bundle_id": bundle.id,
                    "action": "add_menu",
                    "anchor_kind": "menu",
                    "menu_id": self.test_menu.id,
                    "payload": {"string": "No Action"},
                    "apply": True,
                }
            )

    def test_uninstall_hook_removes_generated_menu(self):
        bundle = self._create_bundle(
            code="client_add_menu_uninstall",
            operations=[
                Command.create(
                    {
                        "type": "add_menu",
                        "sequence": 10,
                        "menu_id": self.test_menu.id,
                        "anchor_kind": "menu",
                        "anchor_name": self.menu_xmlid,
                        "position": "after",
                        "payload": {
                            "string": "Uninstall Me",
                            "action_xmlid": self._partner_action_xmlid(),
                        },
                    }
                ),
            ],
        )
        bundle.action_apply()
        menu_id = bundle.operation_ids.generated_menu_id.id
        uninstall_hook(self.env)
        self.assertFalse(self.env["ir.ui.menu"].browse(menu_id).exists())
