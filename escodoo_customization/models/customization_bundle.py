# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import re

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .compiler import (
    MODIFIER_KEYS,
    STRUCTURE_TYPES,
    SUPPORTED_ANCHOR_KINDS,
    arch_tree,
    ensure_field_name,
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
    company_id = fields.Many2one("res.company", ondelete="set null")
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
        self.ensure_one()
        operations = self.operation_ids.filtered(
            lambda o: o.state in ("draft", "broken")
        ).sorted("sequence")
        for operation in operations:
            operation.action_apply()
        return True

    def action_reapply(self):
        """Recompile every non-archived operation."""
        self.ensure_one()
        operations = self.operation_ids.filtered(
            lambda o: o.state != "archived"
        ).sorted("sequence")
        for operation in operations:
            operation.action_apply()
        return True

    def action_health_check(self):
        """Re-resolve anchors without creating fields or views."""
        self.ensure_one()
        operations = self.operation_ids.filtered(
            lambda o: o.state not in ("archived", "draft")
        ).sorted("sequence")
        for operation in operations:
            operation.action_health_check()
        return True

    def action_export(self):
        """Open a dialog with the generated zip ready to download."""
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
        payload, apply. ``view_type`` may be form, list or search.
        Pages without a technical name are anchored with ``anchor_string``.
        """
        self._check_ui_access()
        params = params or {}
        bundle = self.browse(params.get("bundle_id"))
        if not bundle.exists():
            raise UserError(self.env._("Select a customization bundle first."))
        action = params.get("action")
        if action not in UI_ACTIONS:
            raise UserError(self.env._("Unknown customization action '%s'.") % action)
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
                    self.env._("Click a field, page, group or button to set the anchor.")
                )
            anchor_string = (
                source_unnamed_page_string(view, raw_string, tag=anchor_kind)
                or raw_string
            )
        if action == "set_widget" and anchor_kind != "field":
            raise UserError(self.env._("Widgets can only be set on fields."))
        if action in ("add_after", "place_after") and anchor_kind == "button":
            raise UserError(
                self.env._("Place a field on a page or after another field.")
            )
        if action in STRUCTURE_TYPES:
            if (params.get("view_type") or "form") != "form":
                raise UserError(
                    self.env._("Pages and groups can only be added on forms.")
                )
            if anchor_kind == "button":
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
                    self.env._(
                        "Group '%s' has no XML ID and cannot be used in a view."
                    )
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
    ):
        """Create a place_field operation and optionally compile it."""
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
            "payload": {"field_name": field_name},
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

    def _check_ui_access(self):
        if not self.env.user.has_group(
            "escodoo_customization.group_customization_manager"
        ):
            raise AccessError(
                self.env._("Only customization managers can edit forms in place.")
            )

    def unlink(self):
        # Cascade at SQL level would skip operation.unlink() and leak generated
        # views/fields. Unlink operations through the ORM first.
        self.mapped("operation_ids").unlink()
        return super().unlink()
