# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .compiler import (
    ATTRIBUTE_TYPES,
    MENU_TYPES,
    MENU_WRITE_TYPES,
    PLACEMENT_TYPES,
    STRUCTURE_TYPES,
    AnchorError,
    _deactivate_generated_view,
    apply_operation,
    ensure_field_name,
    ensure_menu_xmlid_name,
    health_check_operation,
    menu_write_conflict_message,
    menu_write_conflicts,
    place_field_conflict_message,
    place_field_conflicts,
    restore_menu_operation,
    view_write_conflict_message,
    view_write_conflicts,
)

TTYPE_SELECTION = [
    ("char", "Char"),
    ("text", "Text"),
    ("integer", "Integer"),
    ("float", "Float"),
    ("boolean", "Boolean"),
    ("date", "Date"),
    ("datetime", "Datetime"),
    ("selection", "Selection"),
    ("many2one", "Many2one"),
    ("many2many", "Many2many"),
    ("binary", "Binary"),
    ("monetary", "Monetary"),
]
PAYLOAD_UI_FIELDS = (
    "payload_ttype",
    "payload_string",
    "payload_name",
    "payload_help",
    "payload_required",
    "payload_relation",
    "payload_related",
    "payload_store",
    "payload_selection",
    "payload_currency_field",
    "payload_field_name",
    "payload_field_type",
    "payload_domain",
    "payload_group_by",
    "payload_optional",
    "payload_widget",
    "payload_groups",
    "payload_mod_invisible",
    "payload_mod_readonly",
    "payload_mod_required",
    "payload_mod_column_invisible",
    "payload_action_xmlid",
    "payload_target_xmlid",
)


class CustomizationOperation(models.Model):
    _name = "customization.operation"
    _description = "Customization Operation"
    _order = "bundle_id, sequence, id"

    bundle_id = fields.Many2one(
        "customization.bundle",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(compute="_compute_name", store=True)
    type = fields.Selection(
        selection=[
            ("add_field", "Add Field"),
            ("place_field", "Place Field"),
            ("move_field", "Move Field"),
            ("add_page", "Add Page"),
            ("add_group", "Add Group"),
            ("add_filter", "Add Filter"),
            ("set_string", "Set Label"),
            ("set_widget", "Set Widget"),
            ("set_groups", "Set Groups"),
            ("set_modifier", "Set Modifier"),
            ("set_optional", "Set Optional Column"),
            ("hide_field", "Hide Field"),
            ("hide_menu", "Hide Menu"),
            ("set_menu_string", "Set Menu Label"),
            ("set_menu_groups", "Set Menu Groups"),
            ("add_menu", "Add Menu"),
            ("move_menu", "Move Menu"),
        ],
        required=True,
        default="place_field",
    )
    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        ondelete="cascade",
        index=True,
    )
    model = fields.Char(
        related="model_id.model",
        store=True,
        index=True,
        string="Model Name",
    )
    view_id = fields.Many2one("ir.ui.view", ondelete="set null", index=True)
    menu_id = fields.Many2one("ir.ui.menu", ondelete="set null", index=True)
    view_type = fields.Selection(
        selection=[
            ("form", "Form"),
            ("list", "List"),
            ("search", "Search"),
            ("kanban", "Kanban"),
            ("pivot", "Pivot"),
            ("graph", "Graph"),
        ],
        default="form",
    )
    anchor_kind = fields.Selection(
        selection=[
            ("field", "Field"),
            ("page", "Page"),
            ("button", "Button"),
            ("group", "Group"),
            ("progressbar", "Progressbar"),
            ("filter", "Filter"),
            ("menu", "Menu"),
            ("xpath", "XPath"),
        ],
        default="field",
        required=True,
    )
    anchor_name = fields.Char(
        help="Semantic anchor, for example the field name partner_id."
    )
    anchor_string = fields.Char(
        help="Untranslated page or group title when the node has no name.",
    )
    anchor_occurrence = fields.Integer(
        default=0,
        help="1-based occurrence when the name is not unique. "
        "0 means the name must be unique.",
    )
    anchor_page = fields.Char(
        help="Parent notebook page name, used to disambiguate the anchor.",
    )
    position = fields.Selection(
        selection=[
            ("before", "Before"),
            ("after", "After"),
            ("inside", "Inside"),
            ("replace", "Replace"),
            ("attributes", "Attributes"),
        ],
        default="after",
    )
    payload = fields.Json()
    payload_json = fields.Text(
        compute="_compute_payload_json",
        string="Raw JSON",
    )
    payload_ttype = fields.Selection(
        selection=TTYPE_SELECTION,
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Field Type",
        help="Changing the type and clicking Re-apply deletes values "
        "already stored in this field.",
    )
    payload_string = fields.Char(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Label",
    )
    payload_name = fields.Char(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Technical Name",
        help="Must start with x_cust_. Leave empty to slugify from the label.",
    )
    payload_help = fields.Text(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Help",
    )
    payload_required = fields.Boolean(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Required",
    )
    payload_relation = fields.Char(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Relation Model",
        help="Technical model name, for example res.partner.",
    )
    payload_related = fields.Char(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Related Path",
        help="Dotted path to an existing field, for example parent_id.email.",
    )
    payload_store = fields.Boolean(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Store Related",
        help="Store the related value in the database. Leave off for a "
        "computed-only related field.",
    )
    payload_selection = fields.Text(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Selection Options",
        help="One option per line as value:Label.",
    )
    payload_currency_field = fields.Char(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Currency Field",
    )
    payload_field_name = fields.Char(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Field To Place",
    )
    payload_field_type = fields.Selection(
        selection=[
            ("measure", "Measure"),
            ("row", "Row Grouping"),
            ("col", "Column Grouping"),
            ("groupby", "Grouping"),
        ],
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Aggregate Role",
        help="Role of the field on a pivot or graph view. Pivot accepts "
        "measure, row and col; graph accepts measure and grouping.",
    )
    payload_domain = fields.Char(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Filter Domain",
        help="Odoo domain, for example [('active', '=', True)].",
    )
    payload_group_by = fields.Char(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Group By Field",
        help="Field name to group by. Leave the domain empty when set.",
    )
    payload_optional = fields.Selection(
        selection=[
            ("show", "Shown by default"),
            ("hide", "Hidden by default"),
        ],
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Optional Column",
        help="Put the column in the list column picker instead of pinning it.",
    )
    payload_widget = fields.Char(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Widget",
    )
    payload_groups = fields.Char(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Groups",
        help="Comma-separated XML IDs, for example base.group_user.",
    )
    payload_mod_invisible = fields.Char(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Invisible",
    )
    payload_mod_readonly = fields.Char(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Readonly",
    )
    payload_mod_required = fields.Char(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Required Expr",
    )
    payload_mod_column_invisible = fields.Char(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Column Invisible",
    )
    payload_action_xmlid = fields.Char(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Window Action",
        help="XML ID of the window action, for example base.action_partner_form.",
    )
    payload_target_xmlid = fields.Char(
        compute="_compute_payload_ui",
        inverse="_inverse_payload_ui",
        string="Destination Menu",
        help="XML ID of the destination menu, for example base.menu_administration.",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("applied", "Applied"),
            ("broken", "Broken"),
            ("archived", "Archived"),
        ],
        default="draft",
        required=True,
    )
    broken_reason = fields.Text()
    generated_view_id = fields.Many2one("ir.ui.view", ondelete="set null", copy=False)
    generated_field_id = fields.Many2one(
        "ir.model.fields", ondelete="set null", copy=False
    )
    generated_menu_id = fields.Many2one("ir.ui.menu", ondelete="set null", copy=False)

    @api.depends(
        "type", "anchor_name", "anchor_string", "payload", "model_id", "menu_id"
    )
    def _compute_name(self):
        for rec in self:
            payload = rec.payload or {}
            anchor = rec.anchor_name or rec.anchor_string or "?"
            if rec.type == "add_field":
                label = payload.get("string") or payload.get("name") or rec.model
                rec.name = f"Add field {label}"
            elif rec.type == "place_field":
                rec.name = (
                    f"Place {payload.get('field_name') or '?'} "
                    f"{rec.position or 'after'} {anchor}"
                )
            elif rec.type == "move_field":
                rec.name = (
                    f"Move {payload.get('field_name') or '?'} "
                    f"{rec.position or 'after'} {anchor}"
                )
            elif rec.type == "add_page":
                rec.name = (
                    f"Add page {payload.get('string') or payload.get('name') or '?'}"
                )
            elif rec.type == "add_group":
                rec.name = (
                    f"Add group {payload.get('string') or payload.get('name') or '?'}"
                )
            elif rec.type == "hide_field":
                rec.name = f"Hide {anchor}"
            elif rec.type == "hide_menu":
                rec.name = f"Hide menu {rec.menu_id.display_name or anchor}"
            elif rec.type == "set_menu_string":
                rec.name = f"Rename menu {rec.menu_id.display_name or anchor}"
            elif rec.type == "set_menu_groups":
                rec.name = f"Restrict menu {rec.menu_id.display_name or anchor}"
            elif rec.type == "add_menu":
                rec.name = (
                    f"Add menu {payload.get('string') or '?'} "
                    f"{rec.position or 'after'} {rec.menu_id.display_name or anchor}"
                )
            elif rec.type == "move_menu":
                rec.name = (
                    f"Move menu {rec.menu_id.display_name or anchor} "
                    f"{rec.position or 'after'} {payload.get('target_xmlid') or '?'}"
                )
            else:
                rec.name = f"{rec.type} on {anchor}"

    @api.depends("payload")
    def _compute_payload_json(self):
        for rec in self:
            rec.payload_json = (
                json.dumps(rec.payload, indent=2, sort_keys=True) if rec.payload else ""
            )

    @api.depends("payload")
    def _compute_payload_ui(self):
        for rec in self:
            payload = rec.payload or {}
            modifiers = payload.get("modifiers") or {}
            rec.payload_ttype = payload.get("ttype") or False
            rec.payload_string = payload.get("string") or False
            rec.payload_name = payload.get("name") or False
            rec.payload_help = payload.get("help") or False
            rec.payload_required = bool(payload.get("required"))
            rec.payload_relation = payload.get("relation") or False
            rec.payload_related = payload.get("related") or False
            rec.payload_store = bool(payload.get("store"))
            rec.payload_selection = self._selection_to_text(payload.get("selection"))
            rec.payload_currency_field = payload.get("currency_field") or False
            rec.payload_field_name = payload.get("field_name") or False
            rec.payload_field_type = payload.get("field_type") or False
            rec.payload_domain = payload.get("domain") or False
            rec.payload_group_by = payload.get("group_by") or False
            rec.payload_optional = payload.get("optional") or False
            rec.payload_widget = payload.get("widget") or False
            rec.payload_groups = payload.get("groups") or False
            rec.payload_mod_invisible = modifiers.get("invisible") or False
            rec.payload_mod_readonly = modifiers.get("readonly") or False
            rec.payload_mod_required = modifiers.get("required") or False
            rec.payload_mod_column_invisible = (
                modifiers.get("column_invisible") or False
            )
            rec.payload_action_xmlid = payload.get("action_xmlid") or False
            rec.payload_target_xmlid = payload.get("target_xmlid") or False

    def _inverse_payload_ui(self):
        for rec in self:
            rec.payload = rec._payload_from_ui()

    def _payload_from_ui(self):
        self.ensure_one()
        ui = {name: self[name] for name in PAYLOAD_UI_FIELDS}
        return self._apply_ui_to_payload(self.payload, self.type, ui) or False

    @api.model
    def _apply_add_field_payload_ui(self, payload, ui):
        if "payload_ttype" in ui:
            self._set_payload_key(payload, "ttype", ui["payload_ttype"])
        if "payload_string" in ui:
            self._set_payload_key(payload, "string", ui["payload_string"])
        if "payload_name" in ui:
            self._set_payload_key(payload, "name", ui["payload_name"])
        if "payload_help" in ui:
            self._set_payload_key(payload, "help", ui["payload_help"])
        if "payload_required" in ui:
            if ui["payload_required"]:
                payload["required"] = True
            else:
                payload.pop("required", None)
        ttype = payload.get("ttype")
        if ttype in ("many2one", "many2many"):
            if "payload_relation" in ui:
                self._set_payload_key(payload, "relation", ui["payload_relation"])
        elif "payload_ttype" in ui:
            payload.pop("relation", None)
        if "payload_related" in ui:
            self._set_payload_key(payload, "related", ui["payload_related"])
        if "payload_store" in ui:
            if ui["payload_store"]:
                payload["store"] = True
            else:
                payload.pop("store", None)
        self._apply_add_field_type_extras(payload, ui)

    @api.model
    def _apply_add_field_type_extras(self, payload, ui):
        """Selection options and currency field for add_field payloads."""
        if "payload_selection" in ui:
            selection = self._selection_from_text(ui["payload_selection"])
            if selection:
                payload["selection"] = selection
            else:
                payload.pop("selection", None)
        if "payload_currency_field" in ui:
            self._set_payload_key(
                payload, "currency_field", ui["payload_currency_field"]
            )

    @staticmethod
    def _selection_to_text(selection):
        if not selection:
            return False
        lines = []
        for item in selection:
            if isinstance(item, list | tuple) and len(item) >= 2:
                lines.append(f"{item[0]}:{item[1]}")
            elif isinstance(item, list | tuple) and item:
                lines.append(str(item[0]))
        return "\n".join(lines) or False

    @staticmethod
    def _selection_from_text(text):
        options = []
        for raw_line in (text or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if ":" in line:
                value, label = line.split(":", 1)
            elif "," in line:
                value, label = line.split(",", 1)
            else:
                value, label = line, line
            value = value.strip()
            label = label.strip() or value
            if value:
                options.append([value, label])
        return options

    @api.model
    def _apply_ui_to_payload(self, payload, op_type, ui):
        payload = dict(payload or {})
        if op_type == "add_field":
            self._apply_add_field_payload_ui(payload, ui)
        elif op_type in PLACEMENT_TYPES:
            if "payload_field_name" in ui:
                self._set_payload_key(payload, "field_name", ui["payload_field_name"])
            if "payload_field_type" in ui:
                self._set_payload_key(payload, "field_type", ui["payload_field_type"])
        elif op_type in STRUCTURE_TYPES + ("set_string", "set_menu_string", "add_menu"):
            self._apply_label_payload_ui(payload, op_type, ui)
        elif op_type == "move_menu":
            if "payload_target_xmlid" in ui:
                self._set_payload_key(
                    payload, "target_xmlid", ui["payload_target_xmlid"]
                )
        elif op_type == "set_widget":
            if "payload_widget" in ui:
                self._set_payload_key(payload, "widget", ui["payload_widget"])
        elif op_type == "set_optional":
            if "payload_optional" in ui:
                self._set_payload_key(payload, "optional", ui["payload_optional"])
        elif op_type == "add_filter":
            self._apply_filter_payload_ui(payload, ui)
        elif op_type in ("set_groups", "set_menu_groups"):
            if "payload_groups" in ui:
                self._set_payload_key(payload, "groups", ui["payload_groups"])
        elif op_type == "set_modifier":
            self._apply_modifier_payload_ui(payload, ui)
        return payload

    @api.model
    def _apply_label_payload_ui(self, payload, op_type, ui):
        if "payload_string" in ui:
            self._set_payload_key(payload, "string", ui["payload_string"])
        if op_type in STRUCTURE_TYPES + ("add_menu",) and "payload_name" in ui:
            self._set_payload_key(payload, "name", ui["payload_name"])
        if op_type == "add_menu" and "payload_action_xmlid" in ui:
            self._set_payload_key(payload, "action_xmlid", ui["payload_action_xmlid"])

    @api.model
    def _apply_filter_payload_ui(self, payload, ui):
        if "payload_string" in ui:
            self._set_payload_key(payload, "string", ui["payload_string"])
        if "payload_name" in ui:
            self._set_payload_key(payload, "name", ui["payload_name"])
        if "payload_domain" in ui:
            self._set_payload_key(payload, "domain", ui["payload_domain"])
        if "payload_group_by" in ui:
            self._set_payload_key(payload, "group_by", ui["payload_group_by"])

    @api.model
    def _apply_modifier_payload_ui(self, payload, ui):
        modifiers = dict(payload.get("modifiers") or {})
        mapping = (
            ("payload_mod_invisible", "invisible"),
            ("payload_mod_readonly", "readonly"),
            ("payload_mod_required", "required"),
            ("payload_mod_column_invisible", "column_invisible"),
        )
        for ui_name, key in mapping:
            if ui_name in ui:
                self._set_payload_key(modifiers, key, ui[ui_name])
        if modifiers:
            payload["modifiers"] = modifiers
        else:
            payload.pop("modifiers", None)

    @api.model
    def _vals_with_payload_ui(self, vals, current_payload=None, op_type=None):
        ui = {name: vals[name] for name in PAYLOAD_UI_FIELDS if name in vals}
        if not ui:
            return vals
        vals = dict(vals)
        payload = self._apply_ui_to_payload(
            vals.get("payload") or current_payload,
            vals.get("type") or op_type,
            ui,
        )
        vals["payload"] = payload or False
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._vals_with_payload_ui(vals) for vals in vals_list]
        return super().create(vals_list)

    @staticmethod
    def _set_payload_key(payload, key, value):
        if value:
            payload[key] = value
        else:
            payload.pop(key, None)

    @api.constrains(
        "type",
        "view_id",
        "menu_id",
        "anchor_name",
        "anchor_string",
        "anchor_kind",
        "anchor_occurrence",
        "anchor_page",
        "payload",
        "model_id",
        "state",
    )
    def _check_operation(self):
        for rec in self:
            rec._check_one_operation()

    def _check_one_operation(self):
        self.ensure_one()
        if self.type == "add_field":
            self._check_add_field_operation()
        elif self.type in MENU_TYPES:
            self._check_menu_operation()
        elif self.type in PLACEMENT_TYPES + ATTRIBUTE_TYPES + STRUCTURE_TYPES:
            self._check_view_operation()

    def _check_add_field_operation(self):
        payload = self.payload or {}
        if not self.model_id:
            raise ValidationError(self.env._("A model is required to add a field."))
        if not payload.get("ttype") and not payload.get("related"):
            raise ValidationError(
                self.env._("add_field requires a field type or a related path.")
            )
        if payload.get("name"):
            ensure_field_name(payload["name"])

    def _check_menu_operation(self):
        if not self.menu_id:
            raise ValidationError(self.env._("A menu is required."))
        if self.type == "add_menu" and (self.payload or {}).get("name"):
            ensure_menu_xmlid_name(self.payload["name"])
        if self.state in ("draft", "applied"):
            other = menu_write_conflicts(self)
            if other:
                raise ValidationError(menu_write_conflict_message(self, other))

    def _check_view_operation(self):
        if not self.view_id:
            raise ValidationError(
                self.env._("A target view is required for this operation.")
            )
        if not self.anchor_name and not (
            self.anchor_kind in ("page", "group") and self.anchor_string
        ):
            raise ValidationError(self.env._("An anchor name or title is required."))
        if self.type in STRUCTURE_TYPES and (self.payload or {}).get("name"):
            ensure_field_name(self.payload["name"])
        if self.state not in ("draft", "applied"):
            return
        if self.type in ATTRIBUTE_TYPES:
            other = view_write_conflicts(self)
            if other:
                raise ValidationError(view_write_conflict_message(self, other))
        elif self.type in PLACEMENT_TYPES:
            other = place_field_conflicts(self)
            if other:
                raise ValidationError(place_field_conflict_message(self, other))

    def _mark_broken(self, reason):
        self.ensure_one()
        _deactivate_generated_view(self)
        self.write({"state": "broken", "broken_reason": reason})

    def _mark_applied(self):
        self.ensure_one()
        self.write({"state": "applied", "broken_reason": False})

    def action_apply(self):
        """Compile this operation. Anchor failures become broken, not silent."""
        self.env["customization.bundle"]._check_manager_access()
        return self._apply()

    def _apply(self):
        """Compile without an extra ACL check (bundle actions already checked)."""
        for operation in self:
            if operation.state == "archived":
                continue
            try:
                apply_operation(operation)
            except (AnchorError, UserError, ValidationError, ValueError) as err:
                reason = getattr(err, "reason", None) or str(err)
                operation._mark_broken(reason)
            else:
                operation._mark_applied()
        return True

    def action_health_check(self):
        """Re-resolve anchors; heal broken ops whose anchors are valid again."""
        self.env["customization.bundle"]._check_manager_access()
        return self._health_check()

    def _health_check(self):
        """Re-resolve anchors. Used by the UI and by the upgrade hook.

        A restored anchor is not enough on its own: the inherit was
        deactivated (or is stale). Recompile the operation so the
        consultant does not have to click Re-apply.
        """
        for operation in self:
            if operation.state in ("archived", "draft"):
                continue
            if operation.type == "add_field":
                if operation.generated_field_id:
                    operation._mark_applied()
                continue
            ok, reason = health_check_operation(operation)
            if ok:
                if operation.state == "broken":
                    operation._apply()
                else:
                    operation._mark_applied()
            else:
                operation._mark_broken(reason)
        return True

    def unlink(self):
        self.env["customization.bundle"]._check_manager_access()
        menu_ops = self.filtered(lambda rec: rec.type in MENU_WRITE_TYPES).sorted(
            "sequence", reverse=True
        )
        for operation in menu_ops:
            restore_menu_operation(operation)
        views = self.mapped("generated_view_id").exists()
        fields_to_drop = self.mapped("generated_field_id").exists()
        menus_to_drop = self.mapped("generated_menu_id").exists()
        # Unlink views first so inherit specs do not reference dropped fields.
        if views:
            views.unlink()
        res = super().unlink()
        if fields_to_drop:
            fields_to_drop.unlink()
        if menus_to_drop:
            menus_to_drop.unlink()
        return res
