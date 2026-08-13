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
