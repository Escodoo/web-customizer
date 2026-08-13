# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import re
import unicodedata

from lxml import etree

from odoo import Command, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import sql

FIELD_PREFIX = "x_esc_"
SUPPORTED_TTYPES = (
    "char",
    "text",
    "integer",
    "float",
    "boolean",
    "date",
    "datetime",
    "selection",
    "many2one",
    "many2many",
    "binary",
    "monetary",
)
SUPPORTED_ANCHOR_KINDS = ("field",)
FIELD_POSITIONS = ("before", "after", "replace")
ATTRIBUTE_TYPES = (
    "set_string",
    "set_widget",
    "set_groups",
    "set_modifier",
    "hide_field",
)
XMLID_MODULE = "escodoo_customization"


class AnchorError(Exception):
    """Semantic anchor could not be resolved against the current view."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def slugify_field_suffix(label):
    """Return a lowercase ascii slug without double underscores."""
    uni = (
        unicodedata.normalize("NFKD", label or "")
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", uni).strip("_").lower()
    slug = re.sub(r"_+", "_", slug)
    return slug or "field"


def ensure_field_name(name):
    """Normalize and validate a generated field technical name."""
    name = (name or "").strip()
    if name and not name.startswith(FIELD_PREFIX):
        name = FIELD_PREFIX + name
    if not name:
        raise ValidationError(
            _("Generated field names must start with '%s'.") % FIELD_PREFIX
        )
    if "__" in name:
        raise ValidationError(
            _("Custom field names cannot contain double underscores.")
        )
    if not name.startswith(FIELD_PREFIX):
        raise ValidationError(
            _("Generated field names must start with '%s'.") % FIELD_PREFIX
        )
    if not re.match(r"^x_esc_[a-z0-9_]+$", name):
        raise ValidationError(
            _(
                "Field name '%s' is invalid. Use lowercase letters, digits and "
                "single underscores after the x_esc_ prefix."
            )
            % name
        )
    return name


def unique_field_name(env, model_name, base_name):
    """Append a numeric suffix when the technical name is already used."""
    name = base_name
    attempt = 1
    IrModelFields = env["ir.model.fields"]
    while IrModelFields._get(model_name, name):
        name = f"{base_name}_{attempt}"
        attempt += 1
    return name


def resolve_related_field(env, model_name, related):
    """Return the destination ``ir.model.fields`` for a dotted related path."""
    related = (related or "").strip()
    if not related or not re.match(r"^[\w]+(?:\.[\w]+)*$", related):
        raise UserError(
            _(
                "Related path '%s' is invalid. Use dotted field names, "
                "for example parent_id.email."
            )
            % (related or "")
        )
    names = related.split(".")
    current_model = model_name
    dest = None
    for index, name in enumerate(names):
        dest = env["ir.model.fields"]._get(current_model, name)
        if not dest:
            raise UserError(
                _(
                    "Related field '%(name)s' was not found on %(model)s.",
                    name=name,
                    model=current_model,
                )
            )
        if index == len(names) - 1:
            break
        if dest.ttype != "many2one" or not dest.relation:
            raise UserError(
                _(
                    "Intermediate field '%(name)s' on %(model)s must be a many2one.",
                    name=name,
                    model=current_model,
                )
            )
        current_model = dest.relation
    if dest.ttype not in SUPPORTED_TTYPES:
        raise UserError(_("Related field type '%s' is not supported.") % dest.ttype)
    return dest


def _payload(operation):
    return operation.payload or {}


def _is_same_or_later_operation(other, current):
    """Return whether ``other`` must be hidden while compiling ``current``."""
    if other == current:
        return True
    if other.sequence != current.sequence:
        return other.sequence > current.sequence
    return other.id >= current.id


def combined_arch_for_operation(view, operation):
    """Combined arch as seen when compiling ``operation``.

    Earlier operations of the same bundle stay active so a field can be
    anchored on another custom field (for example place after ``x_esc_vip``).
    This operation and later ones are excluded so re-apply does not see
    its own inherit.
    """
    later = operation.bundle_id.operation_ids.filtered(
        lambda other: other.generated_view_id
        and _is_same_or_later_operation(other, operation)
    )
    generated = later.mapped("generated_view_id").filtered("id")
    was_active = generated.filtered("active")
    if was_active:
        was_active.write({"active": False})
    try:
        return view._get_combined_arch()
    finally:
        if was_active:
            was_active.write({"active": True})


def resolve_field_anchor(arch_tree, anchor_name):
    """Locate a unique ``field`` node named ``anchor_name``.

    :raises AnchorError: when the anchor is missing or ambiguous
    """
    if not anchor_name:
        raise AnchorError(_("Anchor field name is missing."))
    if not re.match(r"^[\w.]+$", anchor_name):
        raise AnchorError(_("Anchor field name '%s' is invalid.") % anchor_name)
    nodes = arch_tree.xpath(f"//field[@name='{anchor_name}']")
    if not nodes:
        raise AnchorError(
            _("Anchor field '%s' was not found in the target view.") % anchor_name
        )
    if len(nodes) > 1:
        raise AnchorError(
            _(
                "Anchor field '%(name)s' is ambiguous "
                "(%(count)s matches in the target view).",
                name=anchor_name,
                count=len(nodes),
            )
        )
    return nodes[0]


def health_check_operation(operation):
    """Resolve the operation anchor without writing fields or views.

    :returns: (ok, reason)
    """
    if operation.type == "add_field":
        return True, ""
    if operation.anchor_kind not in SUPPORTED_ANCHOR_KINDS:
        return False, _("Anchor kind '%s' is not supported yet.") % (
            operation.anchor_kind
        )
    if not operation.view_id:
        return False, _("A target view is required.")
    try:
        arch_tree = combined_arch_for_operation(operation.view_id, operation)
        resolve_field_anchor(arch_tree, operation.anchor_name)
    except AnchorError as err:
        return False, err.reason
    except (ValueError, etree.ParseError) as err:
        return False, str(err)
    return True, ""


def apply_operation(operation):
    """Compile one operation into ir.model.fields / ir.ui.view records."""
    if operation.type == "add_field":
        _apply_add_field(operation)
        return
    if operation.anchor_kind not in SUPPORTED_ANCHOR_KINDS:
        raise AnchorError(
            _("Anchor kind '%s' is not supported yet.") % operation.anchor_kind
        )
    ok, reason = health_check_operation(operation)
    if not ok:
        raise AnchorError(reason)
    if operation.type == "place_field":
        _apply_place_field(operation)
        return
    if operation.type in ATTRIBUTE_TYPES:
        _apply_attributes(operation)
        return
    raise UserError(_("Unsupported operation type '%s'.") % operation.type)


def _apply_add_field(operation):
    payload = dict(_payload(operation))
    model_name = operation.model
    if not model_name:
        raise UserError(_("A model is required to create a field."))
    Model = operation.env[model_name]
    table_kind = sql.table_kind(operation.env.cr, Model._table)
    if table_kind != sql.TableKind.Regular:
        raise UserError(_("The model %s does not support adding fields.") % model_name)

    related = (payload.get("related") or "").strip() or False
    if related:
        dest = resolve_related_field(operation.env, model_name, related)
        payload["related"] = related
        payload["ttype"] = dest.ttype
        if dest.relation:
            payload["relation"] = dest.relation
        if dest.ttype == "monetary" and dest.currency_field:
            payload.setdefault("currency_field", dest.currency_field)

    ttype = payload.get("ttype")
    if ttype not in SUPPORTED_TTYPES:
        raise UserError(
            _("Field type '%s' is not supported.") % (ttype or _("(missing)"))
        )

    requested = payload.get("name") or slugify_field_suffix(
        payload.get("string") or (related and related.split(".")[-1]) or ""
    )
    name = ensure_field_name(requested)
    if operation.generated_field_id:
        field = operation.generated_field_id
        field.write(
            {
                "field_description": payload.get("string") or field.field_description,
                "help": payload.get("help") or False,
                "required": bool(payload.get("required")),
            }
        )
        return

    name = unique_field_name(operation.env, model_name, name)
    vals = {
        "name": name,
        "model_id": operation.model_id.id,
        "ttype": ttype,
        "state": "manual",
        "field_description": payload.get("string") or name,
        "help": payload.get("help") or False,
        "required": bool(payload.get("required")),
    }
    if related:
        vals["related"] = related
        vals["store"] = bool(payload.get("store"))
        vals["readonly"] = True
        vals["copied"] = False
    if ttype in ("many2one", "many2many"):
        relation = payload.get("relation")
        if not relation:
            raise UserError(_("A relation model is required for %s fields.") % ttype)
        vals["relation"] = relation
    if ttype == "selection" and not related:
        selection = payload.get("selection") or []
        if not selection:
            raise UserError(_("Selection fields need at least one option."))
        vals["selection_ids"] = [
            Command.create(
                {
                    "value": str(value),
                    "name": str(label),
                    "sequence": index,
                }
            )
            for index, (value, label) in enumerate(selection)
        ]
    if ttype == "monetary":
        currency_field = payload.get("currency_field")
        if currency_field:
            vals["currency_field"] = currency_field
        elif not (
            operation.env["ir.model.fields"]._get(model_name, "currency_id")
            or operation.env["ir.model.fields"]._get(model_name, "x_currency_id")
        ):
            raise UserError(
                _(
                    "Monetary fields need a currency field on the model "
                    "(currency_id or x_currency_id)."
                )
            )

    field = operation.env["ir.model.fields"].create(vals)
    operation.generated_field_id = field
    payload["name"] = field.name
    payload["ttype"] = ttype
    operation.payload = payload


def _inherit_arch(operation, inner_xml, position):
    anchor = operation.anchor_name
    return f'<field name="{anchor}" position="{position}">{inner_xml}</field>'


def _upsert_generated_view(operation, arch, active=True):
    view = operation.generated_view_id
    values = {
        "name": (f"Customization {operation.bundle_id.code} operation {operation.id}"),
        "type": operation.view_type or operation.view_id.type,
        "model": operation.model,
        "inherit_id": operation.view_id.id,
        "mode": "extension",
        "arch": arch,
        "active": active,
        "priority": 100 + (operation.sequence or 0),
    }
    if view:
        view.write(values)
        return view
    view = operation.env["ir.ui.view"].create(values)
    operation.env["ir.model.data"].create(
        {
            "name": f"generated_view_{operation.id}",
            "model": "ir.ui.view",
            "module": XMLID_MODULE,
            "res_id": view.id,
            "noupdate": True,
        }
    )
    operation.generated_view_id = view
    return view


def _deactivate_generated_view(operation):
    if operation.generated_view_id:
        operation.generated_view_id.active = False


def _apply_place_field(operation):
    payload = _payload(operation)
    field_name = payload.get("field_name")
    if not field_name:
        raise UserError(_("place_field requires payload.field_name."))
    position = operation.position or "after"
    if position not in FIELD_POSITIONS:
        raise AnchorError(
            _("Position '%s' is not valid for placing a field.") % position
        )
    arch = _inherit_arch(operation, f'<field name="{field_name}"/>', position)
    _upsert_generated_view(operation, arch, active=True)


def _attribute_xml(name, value):
    return f'<attribute name="{name}">{value}</attribute>'


def _apply_attributes(operation):
    payload = _payload(operation)
    parts = []
    if operation.type == "set_string":
        string = payload.get("string")
        if not string:
            raise UserError(_("set_string requires payload.string."))
        parts.append(_attribute_xml("string", string))
    elif operation.type == "set_widget":
        widget = payload.get("widget")
        if not widget:
            raise UserError(_("set_widget requires payload.widget."))
        parts.append(_attribute_xml("widget", widget))
    elif operation.type == "set_groups":
        groups = payload.get("groups")
        if not groups:
            raise UserError(_("set_groups requires payload.groups."))
        parts.append(_attribute_xml("groups", groups))
    elif operation.type == "set_modifier":
        modifiers = payload.get("modifiers") or {}
        if not modifiers:
            raise UserError(_("set_modifier requires payload.modifiers."))
        for key in ("invisible", "readonly", "required", "column_invisible"):
            if key in modifiers:
                parts.append(_attribute_xml(key, modifiers[key]))
    elif operation.type == "hide_field":
        attr = "column_invisible" if operation.view_type == "list" else "invisible"
        parts.append(_attribute_xml(attr, "True"))
    arch = _inherit_arch(operation, "".join(parts), "attributes")
    _upsert_generated_view(operation, arch, active=True)
