# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import re
import unicodedata
from xml.sax.saxutils import escape as xml_escape

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
SUPPORTED_ANCHOR_KINDS = ("field", "page", "button", "group")
ANCHOR_TAGS = {
    "field": "field",
    "page": "page",
    "button": "button",
    "group": "group",
}
FIELD_POSITIONS = ("before", "after", "inside", "replace")
STRUCTURE_TYPES = ("add_page", "add_group")
MENU_TYPES = ("hide_menu", "set_menu_string", "set_menu_groups")
ATTRIBUTE_TYPES = (
    "set_string",
    "set_widget",
    "set_groups",
    "set_modifier",
    "hide_field",
)
MODIFIER_KEYS = ("invisible", "readonly", "required", "column_invisible")
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


def unique_node_name(arch_tree, base_name):
    """Append a numeric suffix when the view already has that node name."""
    name = base_name
    attempt = 1
    while arch_tree.xpath(f"//*[@name='{name}']"):
        name = f"{base_name}_{attempt}"
        attempt += 1
    return name


def _xml_attr(value):
    """Escape a value for use inside a double-quoted XML attribute."""
    return xml_escape(value or "", {'"': "&quot;"})


def xpath_quote(value):
    """Return an XPath 1.0 string literal."""
    value = value or ""
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = "', \"'\", '".join(value.split("'"))
    return f"concat('{parts}')"


def arch_tree(view):
    """Return the combined architecture of ``view`` as an etree."""
    arch = view.get_combined_arch()
    if isinstance(arch, str):
        return etree.fromstring(arch.encode())
    return arch


def source_unnamed_page_string(view, title, tag="page"):
    """Return the untranslated ``@string`` of an unnamed page or group.

    The in-place UI sends the label in the user language. Inherit xpaths
    must target the source architecture, so map the displayed title back.
    """
    title = (title or "").strip()
    tag = tag or "page"
    if not title:
        return ""

    def unnamed_nodes(tree):
        return [node for node in tree.xpath(f"//{tag}") if not node.get("name")]

    tree_en = arch_tree(view.with_context(lang=None))
    nodes_en = unnamed_nodes(tree_en)
    for node in nodes_en:
        if (node.get("string") or "").strip() == title:
            return title
    lang = view.env.lang
    if not lang or not nodes_en:
        return title
    nodes_loc = unnamed_nodes(arch_tree(view.with_context(lang=lang)))
    for source, localized in zip(nodes_en, nodes_loc, strict=False):
        if (localized.get("string") or "").strip() == title:
            return (source.get("string") or "").strip() or title
    return title


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
        # Inherit xpaths use source (untranslated) @string values.
        return view.with_context(lang=None)._get_combined_arch()
    finally:
        if was_active:
            was_active.write({"active": True})


def list_anchor_candidates(
    arch_tree, anchor_name, anchor_kind="field", anchor_string=None
):
    """Describe every node that matches the semantic anchor name or title."""
    kind = anchor_kind or "field"
    tag = ANCHOR_TAGS.get(kind, "field")
    nodes = _anchor_nodes(arch_tree, tag, anchor_name, anchor_string)
    label_base = (anchor_name or anchor_string or "").strip()
    if not nodes or not label_base:
        return []
    candidates = []
    for index, node in enumerate(nodes):
        page_names = node.xpath("ancestor::page[@name][1]/@name")
        page = page_names[0] if page_names else ""
        previous = node.getprevious()
        after = ""
        if previous is not None:
            after = previous.get("name") or previous.get("string") or ""
        extras = []
        if page:
            extras.append(_("page %s") % page)
        if after:
            extras.append(_("after %s") % after)
        suffix = f" ({', '.join(extras)})" if extras else ""
        candidates.append(
            {
                "index": index,
                "page": page,
                "after": after,
                "label": f"{index + 1}. {label_base}{suffix}",
            }
        )
    return candidates


def _anchor_nodes(arch_tree, tag, anchor_name, anchor_string=None):
    """Return matching view nodes by technical name or unnamed page title."""
    name = (anchor_name or "").strip()
    if name:
        if not re.match(r"^[\w.]+$", name):
            return []
        return arch_tree.xpath(f"//{tag}[@name='{name}']")
    title = (anchor_string or "").strip()
    if tag not in ("page", "group") or not title:
        return []
    quoted = xpath_quote(title)
    return [
        node
        for node in arch_tree.xpath(f"//{tag}[@string={quoted}]")
        if not node.get("name")
    ]


def resolve_anchor(
    arch_tree,
    anchor_name,
    anchor_kind="field",
    occurrence=0,
    anchor_page=None,
    anchor_string=None,
):
    """Return the unique semantic anchor node or raise AnchorError.

    ``occurrence`` is 1-based. 0 means the remaining matches must be unique.
    Pages and groups without a technical name are matched by ``anchor_string``.
    """
    kind = anchor_kind or "field"
    tag = ANCHOR_TAGS.get(kind)
    if not tag:
        raise AnchorError(_("Anchor kind '%s' is not supported yet.") % kind)
    name = (anchor_name or "").strip()
    title = (anchor_string or "").strip()
    if name and not re.match(r"^[\w.]+$", name):
        raise AnchorError(_("Anchor name '%s' is invalid.") % name)
    if not name and not title:
        raise AnchorError(_("Anchor name is missing."))
    nodes = _anchor_nodes(arch_tree, tag, name, title)
    label = name or title
    page = (anchor_page or "").strip()
    if not nodes:
        raise AnchorError(
            _(
                "Anchor %(kind)s '%(name)s' was not found in the target view.",
                kind=kind,
                name=label,
            )
        )
    if occurrence:
        index = int(occurrence) - 1
        if not 0 <= index < len(nodes):
            raise AnchorError(
                _(
                    "Anchor %(kind)s '%(name)s' has no occurrence %(index)s.",
                    kind=kind,
                    name=label,
                    index=int(occurrence),
                )
            )
        node = nodes[index]
        if page:
            node_page = (node.xpath("ancestor::page[@name][1]/@name") or [""])[0]
            if node_page != page:
                raise AnchorError(
                    _(
                        "Anchor %(kind)s '%(name)s' occurrence %(index)s "
                        "is not on page '%(page)s'.",
                        kind=kind,
                        name=label,
                        index=int(occurrence),
                        page=page,
                    )
                )
        return node
    if page:
        nodes = [
            node
            for node in nodes
            if (node.xpath("ancestor::page[@name][1]/@name") or [""])[0] == page
        ]
        if not nodes:
            raise AnchorError(
                _(
                    "Anchor %(kind)s '%(name)s' was not found on page '%(page)s'.",
                    kind=kind,
                    name=label,
                    page=page,
                )
            )
    if len(nodes) == 1:
        return nodes[0]
    raise AnchorError(
        _(
            "Anchor %(kind)s '%(name)s' is ambiguous "
            "(%(count)s matches in the target view).",
            kind=kind,
            name=label,
            count=len(nodes),
        )
    )


def resolve_field_anchor(arch_tree, anchor_name):
    """Backward-compatible wrapper around :func:`resolve_anchor`."""
    return resolve_anchor(arch_tree, anchor_name, "field")


def health_check_operation(operation):
    """Resolve the operation anchor without writing fields or views.

    :returns: (ok, reason)
    """
    if operation.type == "add_field":
        return True, ""
    if operation.type in MENU_TYPES:
        return _health_check_menu(operation)
    if operation.anchor_kind not in SUPPORTED_ANCHOR_KINDS:
        return False, _("Anchor kind '%s' is not supported yet.") % (
            operation.anchor_kind
        )
    if not operation.view_id:
        return False, _("A target view is required.")
    try:
        arch_tree = combined_arch_for_operation(operation.view_id, operation)
        resolve_anchor(
            arch_tree,
            operation.anchor_name,
            operation.anchor_kind,
            operation.anchor_occurrence,
            operation.anchor_page,
            operation.anchor_string,
        )
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
    if operation.type in MENU_TYPES:
        _apply_menu(operation)
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
    if operation.type in STRUCTURE_TYPES:
        _apply_add_structure(operation)
        return
    if operation.type in ATTRIBUTE_TYPES:
        _apply_attributes(operation)
        return
    raise UserError(_("Unsupported operation type '%s'.") % operation.type)


def _health_check_menu(operation):
    menu = operation.menu_id
    if not menu:
        return False, _("A menu is required.")
    if not menu.exists():
        return False, _("The target menu is missing.")
    xmlid = menu.get_external_id().get(menu.id)
    if not xmlid:
        return False, _("Menu '%s' has no XML ID.") % menu.display_name
    return True, ""


def _menu_groups_xmlids(menu):
    mapping = menu.groups_id.get_external_id()
    xmlids = []
    for group in menu.groups_id:
        xmlid = mapping.get(group.id)
        if xmlid:
            xmlids.append(xmlid)
    return ",".join(xmlids)


def groups_from_xmlids(env, xmlids):
    groups = env["res.groups"]
    for xmlid in (xmlids or "").split(","):
        xmlid = xmlid.strip()
        if not xmlid:
            continue
        groups |= env.ref(xmlid)
    return groups


def _apply_menu(operation):
    ok, reason = _health_check_menu(operation)
    if not ok:
        raise AnchorError(reason)
    menu = operation.menu_id
    xmlid = menu.get_external_id().get(menu.id)
    payload = dict(_payload(operation))
    previous = dict(payload.get("previous") or {})
    if operation.type == "hide_menu":
        previous.setdefault("active", menu.active)
        menu.write({"active": False})
    elif operation.type == "set_menu_string":
        string = (payload.get("string") or "").strip()
        if not string:
            raise UserError(_("set_menu_string requires payload.string."))
        previous.setdefault("name", menu.name)
        menu.write({"name": string})
    elif operation.type == "set_menu_groups":
        groups = payload.get("groups")
        if not groups:
            raise UserError(_("set_menu_groups requires payload.groups."))
        previous.setdefault("groups", _menu_groups_xmlids(menu))
        group_recs = groups_from_xmlids(operation.env, groups)
        menu.write({"groups_id": [Command.set(group_recs.ids)]})
    else:
        raise UserError(_("Unsupported operation type '%s'.") % operation.type)
    payload["xmlid"] = xmlid
    payload["previous"] = previous
    operation.payload = payload


def restore_menu_operation(operation):
    """Undo a menu write using the snapshot stored on first apply."""
    menu = operation.menu_id.exists()
    if not menu:
        return
    previous = (_payload(operation).get("previous")) or {}
    vals = {}
    if operation.type == "hide_menu" and "active" in previous:
        vals["active"] = previous["active"]
    elif operation.type == "set_menu_string" and "name" in previous:
        vals["name"] = previous["name"]
    elif operation.type == "set_menu_groups" and "groups" in previous:
        groups = groups_from_xmlids(operation.env, previous["groups"])
        vals["groups_id"] = [Command.set(groups.ids)]
    if vals:
        menu.write(vals)


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


def _unnamed_node_expr(arch_tree, node):
    """Inherit xpath for a page or group without ``@name``.

    Odoo rejects ``@string`` in inherit specs because it is translated.
    Prefer a unique named descendant, then fall back to document order.
    """
    tag = node.tag
    for child_tag in ("field", "button"):
        for name in node.xpath(f".//{child_tag}[@name]/@name"):
            if not re.match(r"^[\w.]+$", name):
                continue
            expr = f"//{tag}[not(@name)][.//{child_tag}[@name='{name}']]"
            matches = arch_tree.xpath(expr)
            if len(matches) == 1 and matches[0] is node:
                return expr
    unnamed = [item for item in arch_tree.xpath(f"//{tag}") if not item.get("name")]
    try:
        index = unnamed.index(node) + 1
    except ValueError as err:
        raise AnchorError(_("Unnamed %s anchor was not found.") % tag) from err
    return f"(//{tag}[not(@name)])[{index}]"


def _inherit_arch(operation, inner_xml, position, arch_tree=None):
    kind = operation.anchor_kind or "field"
    tag = ANCHOR_TAGS.get(kind, "field")
    anchor = (operation.anchor_name or "").strip()
    title = (operation.anchor_string or "").strip()
    page = (operation.anchor_page or "").strip()
    occurrence = operation.anchor_occurrence or 0
    if not anchor and tag in ("page", "group") and title:
        if arch_tree is None:
            arch_tree = combined_arch_for_operation(operation.view_id, operation)
        node = resolve_anchor(
            arch_tree,
            operation.anchor_name,
            operation.anchor_kind,
            operation.anchor_occurrence,
            operation.anchor_page,
            operation.anchor_string,
        )
        expr = _unnamed_node_expr(arch_tree, node)
        return (
            f'<xpath expr="{_xml_attr(expr)}" position="{position}">'
            f"{inner_xml}</xpath>"
        )
    if occurrence:
        expr = f"(//{tag}[@name='{anchor}'])[{int(occurrence)}]"
        return f'<xpath expr="{expr}" position="{position}">{inner_xml}</xpath>'
    if page:
        expr = f"//page[@name='{page}']//{tag}[@name='{anchor}']"
        return f'<xpath expr="{expr}" position="{position}">{inner_xml}</xpath>'
    return f'<{tag} name="{anchor}" position="{position}">{inner_xml}</{tag}>'


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


def _apply_add_structure(operation):
    """Compile add_page / add_group into an inherited view node."""
    tag = "page" if operation.type == "add_page" else "group"
    payload = dict(_payload(operation))
    string = (payload.get("string") or "").strip()
    if tag == "page" and not string:
        raise UserError(_("A page title is required."))
    requested = payload.get("name") or slugify_field_suffix(string or tag)
    name = ensure_field_name(requested)
    arch_tree = combined_arch_for_operation(operation.view_id, operation)
    name = unique_node_name(arch_tree, name)
    attrs = f'name="{name}"'
    if string:
        attrs += f' string="{_xml_attr(string)}"'
    node_xml = f"<{tag} {attrs}/>"
    if tag == "page" and (operation.anchor_kind or "field") != "page":
        node_xml = f"<notebook>{node_xml}</notebook>"
    position = operation.position or (
        "inside" if tag == "group" and operation.anchor_kind == "page" else "after"
    )
    if tag == "page" and position == "inside":
        raise UserError(_("A page cannot be placed inside another page."))
    if position not in FIELD_POSITIONS:
        raise AnchorError(
            _(
                "Position '%(position)s' is not valid for placing a %(tag)s.",
                position=position,
                tag=tag,
            )
        )
    arch = _inherit_arch(operation, node_xml, position, arch_tree)
    _upsert_generated_view(operation, arch, active=True)
    payload["name"] = name
    if string:
        payload["string"] = string
    operation.payload = payload


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
        for key in MODIFIER_KEYS:
            if key in modifiers:
                parts.append(_attribute_xml(key, modifiers[key]))
    elif operation.type == "hide_field":
        attr = "column_invisible" if operation.view_type == "list" else "invisible"
        parts.append(_attribute_xml(attr, "True"))
    arch = _inherit_arch(operation, "".join(parts), "attributes")
    _upsert_generated_view(operation, arch, active=True)
