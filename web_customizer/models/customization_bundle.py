# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import re

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..hooks import health_check_on_upgrade
from .compiler import (
    AGGREGATE_VIEW_TYPES,
    MODIFIER_KEYS,
    STRUCTURE_TYPES,
    SUPPORTED_ANCHOR_KINDS,
    arch_tree,
    ensure_field_name,
    ensure_menu_xmlid_name,
    list_anchor_candidates,
    resolve_related_field,
    slugify_field_suffix,
    source_unnamed_page_string,
)

UI_ACTIONS = (
    "add_after",
    "place_after",
    "hide",
    "rename",
    "set_widget",
    "set_groups",
    "set_modifier",
    "add_page",
    "add_group",
    "add_menu",
    "add_submenu",
    "move_menu",
    "move_as_submenu",
)


class CustomizationBundle(models.Model):
    _name = "customization.bundle"
    _description = "Customization Bundle"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char(
        required=True,
        help="Technical slug used later as the exported addon name "
        "(for example client_acme).",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("applied", "Applied"),
            ("needs_reapply", "Needs Re-apply"),
        ],
        compute="_compute_state",
        store=True,
    )
    company_id = fields.Many2one(
        "res.company",
        ondelete="set null",
        help="Optional tag to filter this bundle. Compiled fields, views "
        "and menus stay global; they are not scoped by company.",
    )
    operation_ids = fields.One2many(
        "customization.operation",
        "bundle_id",
        string="Operations",
    )
    operation_count = fields.Integer(compute="_compute_broken_count")
    broken_count = fields.Integer(compute="_compute_broken_count")

    _sql_constraints = [  # noqa: RUF012
        ("code_unique", "UNIQUE(code)", "The bundle code must be unique."),
    ]

    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if not rec.code or not re.match(r"^[a-z][a-z0-9_]*$", rec.code):
                raise ValidationError(
                    self.env._(
                        "Bundle code must start with a letter and contain only "
                        "lowercase letters, digits and underscores."
                    )
                )

    @api.depends("operation_ids.state")
    def _compute_state(self):
        for rec in self:
            ops = rec.operation_ids.filtered(lambda o: o.state != "archived")
            if not ops or all(o.state == "draft" for o in ops):
                rec.state = "draft"
            elif any(o.state == "broken" for o in ops):
                rec.state = "needs_reapply"
            elif all(o.state == "applied" for o in ops):
                rec.state = "applied"
            else:
                rec.state = "needs_reapply"

    @api.depends("operation_ids.state")
    def _compute_broken_count(self):
        for rec in self:
            rec.operation_count = len(rec.operation_ids)
            rec.broken_count = len(
                rec.operation_ids.filtered(lambda o: o.state == "broken")
            )

    def action_apply(self):
        """Compile draft and broken operations, in sequence."""
        self._check_manager_access()
        self.ensure_one()
        operations = self.operation_ids.filtered(
            lambda o: o.state in ("draft", "broken")
        ).sorted("sequence")
        operations._apply()
        return True

    def action_reapply(self):
        """Recompile every non-archived operation."""
        self._check_manager_access()
        self.ensure_one()
        operations = self.operation_ids.filtered(
            lambda o: o.state != "archived"
        ).sorted("sequence")
        operations._apply()
        return True

    def action_health_check(self):
        """Re-resolve anchors and rewrite inherits whose anchors are back."""
        self._check_manager_access()
        return self._health_check()

    def _health_check(self):
        """Re-resolve anchors. Used by the UI and by the upgrade hook."""
        for bundle in self:
            operations = bundle.operation_ids.filtered(
                lambda o: o.state not in ("archived", "draft")
            ).sorted("sequence")
            operations._health_check()
        return True

    def _register_hook(self):
        super()._register_hook()
        if self.env.registry.updated_modules:
            health_check_on_upgrade(self.env)

    def action_export(self):
        """Open a dialog with the generated zip ready to download."""
        self._check_manager_access()
        self.ensure_one()
        wizard = self.env["customization.export.wizard"]._create_from_bundle(self)
        return {
            "name": self.env._("Export Addon"),
            "type": "ir.actions.act_window",
            "res_model": "customization.export.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    @api.model
    def get_ui_context(
        self, view_id, anchor_name, anchor_kind="field", anchor_string=False
    ):
        """Return bundles and whether the semantic anchor is unique on the view."""
        self._check_ui_access()
        view = self.env["ir.ui.view"].browse(view_id)
        kind = anchor_kind or "field"
        name = (anchor_name or "").strip()
        title = (anchor_string or "").strip()
        candidates = []
        if view.exists() and (name or title):
            if title and not name:
                title = source_unnamed_page_string(view, title)
            tree = arch_tree(view.with_context(lang=None))
            candidates = list_anchor_candidates(tree, name, kind, title)
        count = len(candidates)
        bundles = self.search_read(
            [],
            ["name", "code", "state"],
            order="write_date desc, id desc",
            limit=80,
        )
        return {
            "bundles": bundles,
            "anchor_count": count,
            "anchor_unique": count == 1,
            "anchor_kind": kind,
            "candidates": candidates,
        }

    @api.model
    def create_from_ui(self, params):
        """Create (and optionally apply) operations from the in-place UI.

        ``params`` keys: bundle_id, action, model, view_id, view_type,
        anchor_name, anchor_kind, anchor_string, anchor_index, anchor_page,
        payload, apply. ``view_type`` may be form, list, search or kanban.
        Pages without a technical name are anchored with ``anchor_string``.
        Menus pass ``anchor_kind='menu'`` and ``menu_id`` instead of a view.
        ``add_menu`` / ``add_submenu`` create a sibling or child menu.
        ``move_menu`` / ``move_as_submenu`` reparent an existing menu.
        """
        self._check_ui_access()
        params = params or {}
        bundle = self.browse(params.get("bundle_id"))
        if not bundle.exists():
            raise UserError(self.env._("Select a customization bundle first."))
        action = params.get("action")
        if action not in UI_ACTIONS:
            raise UserError(self.env._("Unknown customization action '%s'.") % action)
        if (params.get("anchor_kind") or "") == "menu":
            return self._create_menu_from_ui(bundle, action, params)
        return self._create_view_from_ui(bundle, action, params)

    def _create_view_from_ui(self, bundle, action, params):
        model_name = params.get("model")
        model = self.env["ir.model"]._get(model_name) if model_name else False
        if not model:
            raise UserError(self.env._("A model is required."))
        view = self.env["ir.ui.view"].browse(params.get("view_id"))
        if not view.exists():
            raise UserError(self.env._("The target view is missing."))
        anchor_kind = params.get("anchor_kind") or "field"
        if anchor_kind not in SUPPORTED_ANCHOR_KINDS:
            raise UserError(
                self.env._("Anchor kind '%s' is not supported.") % anchor_kind
            )
        anchor_name = (params.get("anchor_name") or "").strip() or False
        raw_string = (params.get("anchor_string") or "").strip()
        anchor_string = False
        if not anchor_name:
            if anchor_kind not in ("page", "group") or not raw_string:
                raise UserError(
                    self.env._(
                        "Click a field, page, group or button to set the anchor."
                    )
                )
            anchor_string = (
                source_unnamed_page_string(view, raw_string, tag=anchor_kind)
                or raw_string
            )
        if action == "set_widget" and anchor_kind != "field":
            raise UserError(self.env._("Widgets can only be set on fields."))
        if action != "hide" and anchor_kind == "progressbar":
            raise UserError(self.env._("A progressbar can only be hidden."))
        if action in ("add_after", "place_after") and anchor_kind in (
            "button",
            "progressbar",
        ):
            raise UserError(
                self.env._("Place a field on a page or after another field.")
            )
        if action in STRUCTURE_TYPES:
            if (params.get("view_type") or "form") != "form":
                raise UserError(
                    self.env._("Pages and groups can only be added on forms.")
                )
            if anchor_kind in ("button", "progressbar"):
                raise UserError(
                    self.env._("Place a page or group on a field, page or group.")
                )
        view_type = params.get("view_type") or "form"
        payload = dict(params.get("payload") or {})
        apply = params.get("apply", True)
        sequence = max(bundle.operation_ids.mapped("sequence") or [0]) + 10
        place_position = "inside" if anchor_kind in ("page", "group") else "after"
        occurrence, anchor_page = self._ui_anchor_qualifier(params)
        if action == "add_after":
            operations = self._ui_action_add_after(
                bundle,
                sequence,
                model,
                model_name,
                view,
                view_type,
                anchor_name,
                payload,
                apply,
                anchor_kind=anchor_kind,
                position=place_position,
                occurrence=occurrence,
                anchor_page=anchor_page,
                anchor_string=anchor_string,
            )
        elif action == "place_after":
            field_name = self._ui_existing_field_name(
                model_name, payload.get("field_name"), anchor_name
            )
            operations = self._ui_place_field(
                bundle,
                sequence,
                model,
                view,
                view_type,
                anchor_name,
                field_name,
                apply,
                anchor_kind=anchor_kind,
                position=place_position,
                occurrence=occurrence,
                anchor_page=anchor_page,
                anchor_string=anchor_string,
                field_type=payload.get("field_type"),
            )
        elif action in STRUCTURE_TYPES:
            operations = self._ui_action_add_structure(
                bundle,
                sequence,
                action,
                model,
                view,
                view_type,
                anchor_name,
                payload,
                apply,
                anchor_kind=anchor_kind,
                occurrence=occurrence,
                anchor_page=anchor_page,
                anchor_string=anchor_string,
            )
        else:
            operations = self._ui_action_on_anchor(
                bundle,
                sequence,
                action,
                model,
                view,
                view_type,
                anchor_name,
                payload,
                apply,
                anchor_kind=anchor_kind,
                occurrence=occurrence,
                anchor_page=anchor_page,
                anchor_string=anchor_string,
            )
        return self._ui_result(bundle, operations, apply)

    def _ui_result(self, bundle, operations, apply):
        broken = operations.filtered(lambda o: o.state == "broken")
        return {
            "operation_ids": operations.ids,
            "state": bundle.state,
            "broken": [
                {"id": op.id, "name": op.name, "reason": op.broken_reason or ""}
                for op in broken
            ],
            "reload": bool(operations.ids) and not broken.ids and apply,
        }

    def _create_menu_from_ui(self, bundle, action, params):
        """Create a hide/rename/groups/add/move operation for a navbar menu."""
        menu_actions = (
            "hide",
            "rename",
            "set_groups",
            "add_menu",
            "add_submenu",
            "move_menu",
            "move_as_submenu",
        )
        if action not in menu_actions:
            raise UserError(
                self.env._(
                    "Menus can only be hidden, renamed, restricted, added or moved."
                )
            )
        menu = self.env["ir.ui.menu"].browse(params.get("menu_id"))
        if not menu.exists():
            raise UserError(self.env._("The target menu is missing."))
        xmlid = menu.get_external_id().get(menu.id)
        if not xmlid:
            raise UserError(
                self.env._("Menu '%s' has no XML ID and cannot be customized.")
                % menu.display_name
            )
        payload = dict(params.get("payload") or {})
        apply = params.get("apply", True)
        sequence = max(bundle.operation_ids.mapped("sequence") or [0]) + 10
        vals = {
            "bundle_id": bundle.id,
            "sequence": sequence,
            "menu_id": menu.id,
            "anchor_kind": "menu",
            "anchor_name": xmlid,
        }
        if action in ("add_menu", "add_submenu"):
            return self._ui_action_add_menu(bundle, vals, action, payload, apply, xmlid)
        if action in ("move_menu", "move_as_submenu"):
            return self._ui_action_move_menu(
                bundle, vals, action, payload, apply, xmlid
            )
        if action == "hide":
            vals.update({"type": "hide_menu", "payload": {"xmlid": xmlid}})
        elif action == "rename":
            string = (payload.get("string") or "").strip()
            if not string:
                raise UserError(self.env._("A new label is required."))
            vals.update(
                {
                    "type": "set_menu_string",
                    "payload": {"string": string, "xmlid": xmlid},
                }
            )
        else:
            groups = self._ui_groups_xmlids(payload)
            vals.update(
                {
                    "type": "set_menu_groups",
                    "payload": {"groups": groups, "xmlid": xmlid},
                }
            )
        operation = self.env["customization.operation"].create(vals)
        if apply:
            operation.action_apply()
        return self._ui_result(bundle, operation, apply)

    def _ui_action_add_menu(self, bundle, vals, action, payload, apply, xmlid):
        """Create an add_menu sibling (after) or child (inside) of the anchor."""
        string = (payload.get("string") or "").strip()
        if not string:
            raise UserError(self.env._("A label is required."))
        action_xmlid = self._ui_action_xmlid(payload)
        name = (payload.get("name") or "").strip()
        if name:
            name = ensure_menu_xmlid_name(name)
        position = "inside" if action == "add_submenu" else "after"
        menu_payload = {
            "string": string,
            "action_xmlid": action_xmlid,
            "xmlid": xmlid,
        }
        if name:
            menu_payload["name"] = name
        vals.update(
            {
                "type": "add_menu",
                "position": position,
                "payload": menu_payload,
            }
        )
        operation = self.env["customization.operation"].create(vals)
        if apply:
            operation.action_apply()
        return self._ui_result(bundle, operation, apply)

    def _ui_action_move_menu(self, bundle, vals, action, payload, apply, xmlid):
        """Move the clicked menu after or inside another menu."""
        target_xmlid = self._ui_menu_xmlid(payload, exclude_id=vals["menu_id"])
        position = "inside" if action == "move_as_submenu" else "after"
        vals.update(
            {
                "type": "move_menu",
                "position": position,
                "payload": {"target_xmlid": target_xmlid, "xmlid": xmlid},
            }
        )
        operation = self.env["customization.operation"].create(vals)
        if apply:
            operation.action_apply()
        return self._ui_result(bundle, operation, apply)

    def _ui_menu_xmlid(self, payload, exclude_id=False):
        """Return a menu XML ID from xmlid or record id."""
        target_xmlid = (payload.get("target_xmlid") or "").strip()
        if target_xmlid:
            try:
                menu = self.env.ref(target_xmlid)
            except ValueError as err:
                raise UserError(
                    self.env._("Menu '%s' is missing.") % target_xmlid
                ) from err
            if menu._name != "ir.ui.menu":
                raise UserError(
                    self.env._("Destination '%s' is not a menu.") % target_xmlid
                )
            if exclude_id and menu.id == exclude_id:
                raise UserError(
                    self.env._("Choose a different menu as the destination.")
                )
            return target_xmlid
        target_id = payload.get("target_menu_id")
        if not target_id:
            raise UserError(self.env._("Select a destination menu with an XML ID."))
        menu = self.env["ir.ui.menu"].browse(int(target_id))
        if not menu.exists():
            raise UserError(self.env._("The destination menu is missing."))
        if exclude_id and menu.id == exclude_id:
            raise UserError(self.env._("Choose a different menu as the destination."))
        xmlid = menu.get_external_id().get(menu.id)
        if not xmlid:
            raise UserError(
                self.env._("Menu '%s' has no XML ID and cannot be used.")
                % menu.display_name
            )
        return xmlid

    def _ui_action_xmlid(self, payload):
        """Return a window-action XML ID from xmlid or record id."""
        action_xmlid = (payload.get("action_xmlid") or "").strip()
        if action_xmlid:
            try:
                action = self.env.ref(action_xmlid)
            except ValueError as err:
                raise UserError(
                    self.env._("Action '%s' is missing.") % action_xmlid
                ) from err
            if action._name != "ir.actions.act_window":
                raise UserError(self.env._("Select a window action with an XML ID."))
            return action_xmlid
        action_id = payload.get("action_id")
        if not action_id:
            raise UserError(self.env._("Select a window action with an XML ID."))
        action = self.env["ir.actions.act_window"].browse(int(action_id))
        if not action.exists():
            raise UserError(self.env._("The window action is missing."))
        xmlid = action.get_external_id().get(action.id)
        if not xmlid:
            raise UserError(
                self.env._("Action '%s' has no XML ID and cannot be used.")
                % action.display_name
            )
        return xmlid

    def _ui_action_add_after(
        self,
        bundle,
        sequence,
        model,
        model_name,
        view,
        view_type,
        anchor_name,
        payload,
        apply,
        anchor_kind="field",
        position="after",
        occurrence=0,
        anchor_page=False,
        anchor_string=False,
    ):
        """Create add_field plus place_field after/inside the clicked anchor."""
        # The aggregate role belongs to the placement, not to the field itself.
        field_type = payload.pop("field_type", False)
        if not payload.get("ttype") and not payload.get("related"):
            raise UserError(self.env._("A field type or a related path is required."))
        if payload.get("related") and not payload.get("ttype"):
            dest = resolve_related_field(self.env, model_name, payload["related"])
            payload["ttype"] = dest.ttype
            if dest.relation:
                payload["relation"] = dest.relation
        requested = payload.get("name") or slugify_field_suffix(
            payload.get("string") or (payload.get("related") or "").split(".")[-1]
        )
        field_name = ensure_field_name(requested)
        payload["name"] = field_name
        add_op = self.env["customization.operation"].create(
            {
                "bundle_id": bundle.id,
                "sequence": sequence,
                "type": "add_field",
                "model_id": model.id,
                "payload": payload,
            }
        )
        if apply:
            add_op.action_apply()
            field_name = (add_op.payload or {}).get("name") or field_name
        place_op = self._ui_place_field(
            bundle,
            sequence + 10,
            model,
            view,
            view_type,
            anchor_name,
            field_name,
            apply,
            anchor_kind=anchor_kind,
            position=position,
            occurrence=occurrence,
            anchor_page=anchor_page,
            anchor_string=anchor_string,
            field_type=field_type,
        )
        return add_op | place_op

    def _ui_action_add_structure(
        self,
        bundle,
        sequence,
        action,
        model,
        view,
        view_type,
        anchor_name,
        payload,
        apply,
        anchor_kind="field",
        occurrence=0,
        anchor_page=False,
        anchor_string=False,
    ):
        """Create an add_page or add_group operation on the clicked anchor."""
        string = (payload.get("string") or "").strip()
        if not string:
            raise UserError(self.env._("A label is required."))
        requested = payload.get("name") or slugify_field_suffix(string)
        name = ensure_field_name(requested)
        position = (
            "inside" if action == "add_group" and anchor_kind == "page" else "after"
        )
        vals = {
            "bundle_id": bundle.id,
            "sequence": sequence,
            "type": action,
            "model_id": model.id,
            "view_id": view.id,
            "view_type": view_type,
            "anchor_kind": anchor_kind,
            "anchor_name": anchor_name,
            "position": position,
            "payload": {"string": string, "name": name},
        }
        vals.update(self._ui_anchor_extra(occurrence, anchor_page, anchor_string))
        operation = self.env["customization.operation"].create(vals)
        if apply:
            operation.action_apply()
        return operation

    def _ui_action_on_anchor(
        self,
        bundle,
        sequence,
        action,
        model,
        view,
        view_type,
        anchor_name,
        payload,
        apply,
        anchor_kind="field",
        occurrence=0,
        anchor_page=False,
        anchor_string=False,
    ):
        """Create a hide/rename/widget/groups/modifier operation on the anchor."""
        vals = {
            "bundle_id": bundle.id,
            "sequence": sequence,
            "model_id": model.id,
            "view_id": view.id,
            "view_type": view_type,
            "anchor_kind": anchor_kind,
            "anchor_name": anchor_name,
        }
        vals.update(self._ui_anchor_extra(occurrence, anchor_page, anchor_string))
        if action == "hide":
            vals.update({"type": "hide_field", "payload": {}})
        elif action == "rename":
            string = (payload.get("string") or "").strip()
            if not string:
                raise UserError(self.env._("A new label is required."))
            vals.update(
                {
                    "type": "set_string",
                    "position": "attributes",
                    "payload": {"string": string},
                }
            )
        elif action == "set_widget":
            widget = (payload.get("widget") or "").strip()
            if not widget:
                raise UserError(self.env._("A widget name is required."))
            vals.update(
                {
                    "type": "set_widget",
                    "position": "attributes",
                    "payload": {"widget": widget},
                }
            )
        elif action == "set_groups":
            groups = self._ui_groups_xmlids(payload)
            vals.update(
                {
                    "type": "set_groups",
                    "position": "attributes",
                    "payload": {"groups": groups},
                }
            )
        else:
            modifiers = self._ui_modifiers_payload(payload.get("modifiers") or {})
            if not modifiers:
                raise UserError(self.env._("Set at least one modifier."))
            vals.update(
                {
                    "type": "set_modifier",
                    "position": "attributes",
                    "payload": {"modifiers": modifiers},
                }
            )
        operation = self.env["customization.operation"].create(vals)
        if apply:
            operation.action_apply()
        return operation

    def _ui_groups_xmlids(self, payload):
        """Return comma-separated group XML IDs from names or record ids."""
        xmlids = (payload.get("groups") or "").strip()
        raw_ids = payload.get("group_ids") or []
        if xmlids and not raw_ids:
            return xmlids
        ids = []
        for value in raw_ids:
            try:
                ids.append(int(value))
            except (TypeError, ValueError) as err:
                raise UserError(self.env._("Invalid group id '%s'.") % value) from err
        if not ids:
            raise UserError(self.env._("Select at least one group."))
        groups = self.env["res.groups"].browse(ids).exists()
        if len(groups) != len(set(ids)):
            raise UserError(self.env._("One of the selected groups does not exist."))
        xmlid_map = groups.get_external_id()
        resolved = []
        for group in groups:
            xmlid = xmlid_map.get(group.id)
            if not xmlid:
                raise UserError(
                    self.env._("Group '%s' has no XML ID and cannot be used in a view.")
                    % group.display_name
                )
            resolved.append(xmlid)
        return ",".join(resolved)

    def _ui_modifiers_payload(self, modifiers):
        """Keep only known modifier keys with a non-empty expression."""
        cleaned = {}
        for key in MODIFIER_KEYS:
            value = modifiers.get(key)
            if value is True:
                cleaned[key] = "True"
            elif value not in (None, False, ""):
                cleaned[key] = str(value).strip()
        return {key: value for key, value in cleaned.items() if value}

    def _ui_existing_field_name(self, model_name, field_name, anchor_name):
        """Return a field that already exists on ``model_name``."""
        field_name = (field_name or "").strip()
        if not field_name:
            raise UserError(self.env._("Select an existing field to place."))
        field = self.env["ir.model.fields"]._get(model_name, field_name)
        if not field:
            raise UserError(
                self.env._(
                    "Field '%s' does not exist on %s.",
                    field_name,
                    model_name,
                )
            )
        if field_name == anchor_name:
            raise UserError(
                self.env._("Choose a field other than the one you clicked.")
            )
        return field.name

    def _ui_place_field(
        self,
        bundle,
        sequence,
        model,
        view,
        view_type,
        anchor_name,
        field_name,
        apply,
        anchor_kind="field",
        position="after",
        occurrence=0,
        anchor_page=False,
        anchor_string=False,
        field_type=False,
    ):
        """Create a place_field operation and optionally compile it."""
        payload = {"field_name": field_name}
        if view_type in AGGREGATE_VIEW_TYPES:
            # The in-place UI only ever anchors on a measure, so that is the
            # role a placed field takes unless the caller asked for another.
            payload["field_type"] = field_type or "measure"
        vals = {
            "bundle_id": bundle.id,
            "sequence": sequence,
            "type": "place_field",
            "model_id": model.id,
            "view_id": view.id,
            "view_type": view_type,
            "anchor_kind": anchor_kind,
            "anchor_name": anchor_name,
            "position": position,
            "payload": payload,
        }
        vals.update(self._ui_anchor_extra(occurrence, anchor_page, anchor_string))
        operation = self.env["customization.operation"].create(vals)
        if apply:
            operation.action_apply()
        return operation

    def _ui_anchor_qualifier(self, params):
        """Return (anchor_occurrence, anchor_page) from UI params.

        The UI sends a 0-based ``anchor_index``; the ledger stores a 1-based
        occurrence so 0 can mean "the name must be unique".
        """
        if "anchor_index" not in params or params.get("anchor_index") in (None, ""):
            occurrence = 0
        else:
            occurrence = int(params.get("anchor_index")) + 1
        page = (params.get("anchor_page") or "").strip() or False
        return occurrence, page

    def _ui_anchor_extra(self, anchor_occurrence, anchor_page, anchor_string=False):
        """Fields that qualify an otherwise ambiguous semantic anchor."""
        extra = {}
        if anchor_occurrence:
            extra["anchor_occurrence"] = anchor_occurrence
        if anchor_page:
            extra["anchor_page"] = anchor_page
        if anchor_string:
            extra["anchor_string"] = anchor_string
        return extra

    @api.model
    def _check_manager_access(self, message=None):
        if not self.env.user.has_group("web_customizer.group_customization_manager"):
            raise AccessError(
                message
                or self.env._("Only customization managers can change customizations.")
            )

    def _check_ui_access(self):
        self._check_manager_access(
            self.env._("Only customization managers can edit forms in place.")
        )

    def unlink(self):
        self._check_manager_access()
        # Cascade at SQL level would skip operation.unlink() and leak generated
        # views/fields. Unlink operations through the ORM first.
        self.mapped("operation_ids").unlink()
        return super().unlink()
