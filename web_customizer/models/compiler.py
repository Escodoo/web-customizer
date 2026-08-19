# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import ast
import logging
import re
import unicodedata
from xml.sax.saxutils import escape as xml_escape

from lxml import etree

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools import sql

_logger = logging.getLogger(__name__)

FIELD_PREFIX = "x_cust_"
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
SUPPORTED_ANCHOR_KINDS = (
    "field",
    "page",
    "button",
    "group",
    "progressbar",
    "filter",
    "view",
)
# Mirrors GROUPABLE_TYPES in @web/search/utils/misc: grouping by anything else
# is refused by the client, so a filter built on it would never work.
GROUPABLE_TTYPES = (
    "boolean",
    "char",
    "date",
    "datetime",
    "integer",
    "many2one",
    "many2many",
    "selection",
)
# Pivot and graph describe themselves with measures and groupings instead of a
# tree of widgets, so they only ever anchor on <field> and only understand the
# attributes their arch parsers read.
AGGREGATE_VIEW_TYPES = ("pivot", "graph")
AGGREGATE_FIELD_TYPES = {
    "pivot": ("measure", "row", "col"),
    "graph": ("measure", "groupby"),
}
AGGREGATE_OPERATION_TYPES = (
    "place_field",
    "move_field",
    "set_string",
    "set_widget",
    "set_groups",
    "set_modifier",
    "hide_field",
)
ANCHOR_TAGS = {
    "field": "field",
    "page": "page",
    "button": "button",
    "group": "group",
    "progressbar": "progressbar",
    "filter": "filter",
}
FIELD_POSITIONS = ("before", "after", "inside", "replace")
# A move relocates the existing node, so "replace" would drop the anchor
# instead of relocating anything.
MOVE_POSITIONS = ("before", "after", "inside")
# Both types decide where a field sits in the view, so two of them on the
# same field would fight over the same node.
PLACEMENT_TYPES = ("place_field", "move_field")
PLACEMENT_LABELS = {
    "place_field": "Place Field",
    "move_field": "Move Field",
}
STRUCTURE_TYPES = ("add_page", "add_group")
# Classes the form, list and kanban renderers style a button with. Anything
# else is either inert or breaks the look of the view it lands on.
BUTTON_CLASSES = ("btn-primary", "btn-secondary", "btn-link", "")
MENU_TYPES = (
    "hide_menu",
    "set_menu_string",
    "set_menu_groups",
    "add_menu",
    "move_menu",
)
MENU_WRITE_TYPES = (
    "hide_menu",
    "set_menu_string",
    "set_menu_groups",
    "move_menu",
)
MENU_WRITE_LABELS = {
    "hide_menu": "Hide Menu",
    "set_menu_string": "Set Menu Label",
    "set_menu_groups": "Set Menu Groups",
    "move_menu": "Move Menu",
}
ATTRIBUTE_TYPES = (
    "set_string",
    "set_widget",
    "set_groups",
    "set_modifier",
    "set_optional",
    "set_view_attribute",
    "hide_field",
)
VIEW_WRITE_LABELS = {
    "set_string": "Set Label",
    "set_widget": "Set Widget",
    "set_groups": "Set Groups",
    "set_modifier": "Set Modifier",
    "set_optional": "Set Optional Column",
    "set_view_attribute": "Set View Options",
    "hide_field": "Hide Field",
}
# Attributes the arch parsers read off the view root. getActiveActions covers
# form, list and kanban; the rest are read by one parser only, so offering
# them elsewhere would write an attribute nothing looks at.
ROOT_ACTION_ATTRIBUTES = ("create", "edit", "delete", "duplicate")
ROOT_DECORATIONS = (
    "bf",
    "it",
    "danger",
    "info",
    "muted",
    "primary",
    "success",
    "warning",
)
# group_* are read by the kanban parser into activeActions; they only
# matter once the board is grouped, but writing them on an ungrouped
# board is still what the arch accepts and is not inert.
ROOT_ATTRIBUTES = {
    "form": ROOT_ACTION_ATTRIBUTES,
    "list": ROOT_ACTION_ATTRIBUTES + ("editable", "default_order", "multi_edit"),
    "kanban": ROOT_ACTION_ATTRIBUTES
    + (
        "default_order",
        "quick_create",
        "group_create",
        "group_delete",
        "group_edit",
    ),
}
ROOT_BOOLEAN_ATTRIBUTES = ROOT_ACTION_ATTRIBUTES + (
    "multi_edit",
    "quick_create",
    "group_create",
    "group_delete",
    "group_edit",
)
ROOT_EDITABLE_VALUES = ("top", "bottom")
OPTIONAL_VALUES = ("show", "hide")
MODIFIER_KEYS = ("invisible", "readonly", "required", "column_invisible")
BUTTON_TYPE_ANCHORS = (
    "edit",
    "open",
    "delete",
    "url",
    "set_cover",
    "archive",
    "unarchive",
)
LEGACY_XMLID_MODULE = "web_customizer"


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


def ensure_field_name(env, name):
    """Normalize and validate a generated field technical name."""
    name = (name or "").strip()
    if name and not name.startswith(FIELD_PREFIX):
        name = FIELD_PREFIX + name
    if not name:
        raise ValidationError(
            env._("Generated field names must start with '%s'.") % FIELD_PREFIX
        )
    if "__" in name:
        raise ValidationError(
            env._("Custom field names cannot contain double underscores.")
        )
    if not name.startswith(FIELD_PREFIX):
        raise ValidationError(
            env._("Generated field names must start with '%s'.") % FIELD_PREFIX
        )
    if not re.match(rf"^{re.escape(FIELD_PREFIX)}[a-z0-9_]+$", name):
        raise ValidationError(
            env._(
                "Field name '%s' is invalid. Use lowercase letters, digits and "
                "single underscores after the x_cust_ prefix."
            )
            % name
        )
    return name


def ensure_menu_xmlid_name(env, name):
    """Normalize and validate an exported menu XML ID (client addon)."""
    name = (name or "").strip()
    if not name:
        raise ValidationError(env._("A menu XML ID is required."))
    name = name.split(".", 1)[-1]
    name = re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_").lower()
    name = re.sub(r"_+", "_", name)
    if name and name[0].isdigit():
        name = f"menu_{name}"
    if not re.match(r"^[a-z][a-z0-9_]*$", name) or "__" in name:
        raise ValidationError(
            env._(
                "Menu XML ID '%s' is invalid. Use lowercase letters, digits "
                "and single underscores, starting with a letter."
            )
            % (name or env._("(empty)"))
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
            env._(
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
                env._(
                    "Related field '%(name)s' was not found on %(model)s.",
                    name=name,
                    model=current_model,
                )
            )
        if index == len(names) - 1:
            break
        if dest.ttype != "many2one" or not dest.relation:
            raise UserError(
                env._(
                    "Intermediate field '%(name)s' on %(model)s must be a many2one.",
                    name=name,
                    model=current_model,
                )
            )
        current_model = dest.relation
    if dest.ttype not in SUPPORTED_TTYPES:
        raise UserError(env._("Related field type '%s' is not supported.") % dest.ttype)
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
    anchored on another custom field (for example place after ``x_cust_vip``).
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
    env, arch_tree, anchor_name, anchor_kind="field", anchor_string=None
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
            extras.append(env._("page %s") % page)
        if after:
            extras.append(env._("after %s") % after)
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
    """Return matching view nodes by technical name or unnamed page title.

    The search is relative to ``arch_tree`` so that a caller can narrow it
    down to an embedded subview instead of the whole view.
    """
    name = (anchor_name or "").strip()
    if name:
        if not re.match(r"^[\w.]+$", name):
            return []
        attr = "field" if tag == "progressbar" else "name"
        nodes = arch_tree.xpath(f".//{tag}[@{attr}='{name}']")
        if nodes or tag != "button" or name not in BUTTON_TYPE_ANCHORS:
            return nodes
        return arch_tree.xpath(f".//{tag}[@type='{name}']")
    title = (anchor_string or "").strip()
    if tag not in ("page", "group") or not title:
        return []
    quoted = xpath_quote(title)
    return [
        node
        for node in arch_tree.xpath(f".//{tag}[@string={quoted}]")
        if not node.get("name")
    ]


# A form written next to the list is the dialog that opens a line. It is
# a subview of the same field, not a view of its own.
SUBVIEW_TAGS = ("list", "kanban", "form")
SUBVIEW_TTYPES = ("one2many", "many2many")


def _check_subview_model(operation, subview):
    """Refuse a subview anchor whose model no longer matches the arch.

    The operation targets the comodel while the view stays the parent one,
    so a field renamed or retyped upstream would otherwise compile against
    the wrong model without anyone noticing.
    """
    env = operation.env
    parent = operation.view_id.model
    field = env["ir.model.fields"]._get(parent, subview)
    if not field:
        raise AnchorError(
            env._(
                "Field '%(field)s' does not exist on %(model)s.",
                field=subview,
                model=parent or "?",
            )
        )
    if field.ttype not in SUBVIEW_TTYPES:
        raise AnchorError(
            env._(
                "Field '%(field)s' is a %(ttype)s, so it holds no subview.",
                field=subview,
                ttype=field.ttype,
            )
        )
    if operation.model and field.relation != operation.model:
        raise AnchorError(
            env._(
                "Field '%(field)s' points at %(relation)s, but the operation "
                "targets %(model)s.",
                field=subview,
                relation=field.relation,
                model=operation.model,
            )
        )


def subview_scope(operation, arch_tree):
    """Narrow the arch down to the embedded subview this operation targets.

    Odoo embeds the subview of an x2many field when it serves the parent
    view, so the client sees one either way. Only an arch that really
    carries it can be inherited here; a referenced one belongs to another
    view and has to be customized there.
    """
    subview = (operation.anchor_subview or "").strip()
    if not subview:
        return arch_tree
    env = operation.env
    tag = operation.view_type or ""
    if tag not in SUBVIEW_TAGS:
        raise AnchorError(
            env._("A subview anchor targets a list, a kanban or a form, not a %s.")
            % (tag or "?")
        )
    _check_subview_model(operation, subview)
    holders = arch_tree.xpath(f".//field[@name={xpath_quote(subview)}]")
    if not holders:
        raise AnchorError(env._("Field '%s' is not in the target view.") % subview)
    if len(holders) > 1:
        raise AnchorError(
            env._("Field '%s' appears more than once in the target view.") % subview
        )
    nodes = holders[0].xpath(f"./{tag}")
    if not nodes:
        raise AnchorError(
            env._(
                "Field '%(field)s' has no %(tag)s written in this view. Its "
                "table comes from a %(model)s view, so customize that view "
                "instead.",
                field=subview,
                tag=tag,
                model=operation.model or "?",
            )
        )
    return nodes[0]


def subview_expr_prefix(operation):
    """Inherit xpath prefix that scopes an anchor to the embedded subview."""
    subview = (operation.anchor_subview or "").strip()
    if not subview:
        return ""
    return f"//field[@name={xpath_quote(subview)}]/{operation.view_type}"


def resolve_anchor(
    env,
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
    if kind == "view":
        # The root is the anchor: every view has exactly one, and it carries
        # no name to disambiguate.
        return arch_tree
    tag = ANCHOR_TAGS.get(kind)
    if not tag:
        raise AnchorError(env._("Anchor kind '%s' is not supported yet.") % kind)
    name = (anchor_name or "").strip()
    title = (anchor_string or "").strip()
    if name and not re.match(r"^[\w.]+$", name):
        raise AnchorError(env._("Anchor name '%s' is invalid.") % name)
    if not name and not title:
        raise AnchorError(env._("Anchor name is missing."))
    nodes = _anchor_nodes(arch_tree, tag, name, title)
    label = name or title
    page = (anchor_page or "").strip()
    if not nodes:
        raise AnchorError(
            env._(
                "Anchor %(kind)s '%(name)s' was not found in the target view.",
                kind=kind,
                name=label,
            )
        )
    if occurrence:
        index = int(occurrence) - 1
        if not 0 <= index < len(nodes):
            raise AnchorError(
                env._(
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
                    env._(
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
                env._(
                    "Anchor %(kind)s '%(name)s' was not found on page '%(page)s'.",
                    kind=kind,
                    name=label,
                    page=page,
                )
            )
    if len(nodes) == 1:
        return nodes[0]
    raise AnchorError(
        env._(
            "Anchor %(kind)s '%(name)s' is ambiguous "
            "(%(count)s matches in the target view).",
            kind=kind,
            name=label,
            count=len(nodes),
        )
    )


def _check_move_source(operation, arch_tree, anchor_node):
    """Refuse a move whose source node the inheritance engine cannot relocate.

    A missing source makes the inherit raise at render time and takes the whole
    view down, and ``locate_node`` silently picks the first field carrying the
    name, so an ambiguous source would move a node the user never clicked.
    """
    field_name = (_payload(operation).get("field_name") or "").strip()
    if not field_name:
        raise AnchorError(operation.env._("move_field requires payload.field_name."))
    if not re.match(r"^[a-z_][a-z0-9_]*$", field_name):
        raise AnchorError(operation.env._("Field name '%s' is not valid.") % field_name)
    nodes = arch_tree.xpath(f".//field[@name={xpath_quote(field_name)}]")
    if not nodes:
        raise AnchorError(
            operation.env._(
                "Field '%s' is not in the target view, so it cannot be moved."
            )
            % field_name
        )
    if len(nodes) > 1:
        raise AnchorError(
            operation.env._(
                "Field '%(field)s' appears %(count)s times in the target view, "
                "so the node to move is ambiguous.",
                field=field_name,
                count=len(nodes),
            )
        )
    if nodes[0] is anchor_node:
        raise AnchorError(
            operation.env._("Field '%s' cannot be moved next to itself.") % field_name
        )


def health_check_operation(operation):
    """Resolve the operation anchor without writing fields or views.

    :returns: (ok, reason)
    """
    if operation.type == "add_field":
        return True, ""
    if operation.type in MENU_TYPES:
        return _health_check_menu(operation)
    if operation.anchor_kind not in SUPPORTED_ANCHOR_KINDS:
        return False, operation.env._("Anchor kind '%s' is not supported yet.") % (
            operation.anchor_kind
        )
    if not operation.view_id:
        return False, operation.env._("A target view is required.")
    try:
        arch_tree = combined_arch_for_operation(operation.view_id, operation)
        scope = subview_scope(operation, arch_tree)
        anchor_node = resolve_anchor(
            operation.env,
            scope,
            operation.anchor_name,
            operation.anchor_kind,
            operation.anchor_occurrence,
            operation.anchor_page,
            operation.anchor_string,
        )
        if operation.type == "move_field":
            # The engine resolves position="move" against the whole view, so
            # the source must be unique there, not only inside the subview.
            _check_move_source(operation, arch_tree, anchor_node)
    except AnchorError as err:
        return False, err.reason
    except (ValueError, etree.ParseError) as err:
        return False, str(err)
    return True, ""


def field_xmlid_name(field):
    """Stable XML ID name for a generated field (matches the exported addon)."""
    model_key = (field.model or "").replace(".", "_")
    return f"field_{model_key}_{field.name}"


def view_xmlid_name(operation):
    """Stable XML ID name for a generated inherit view."""
    return f"view_operation_{operation.id}"


def menu_xmlid_name(operation):
    """Stable XML ID name for a generated menu (matches the exported addon)."""
    payload = operation.payload or {}
    name = (payload.get("name") or "").strip()
    if name:
        return name
    slug = slugify_field_suffix(payload.get("string") or "menu")
    return f"menu_{slug}_{operation.id}"


def ensure_generated_xmlid(env, module, name, record):
    """Point ``module.name`` at ``record``, migrating a legacy xmlid if needed.

    Generated artifacts belong to the bundle code (the future exported
    addon), not to ``web_customizer``. Uninstalling this module
    must not cascade-delete compiled fields, views or menus.
    """
    Imd = env["ir.model.data"].sudo()
    wanted = Imd.search([("module", "=", module), ("name", "=", name)], limit=1)
    if wanted:
        if wanted.model != record._name or wanted.res_id != record.id:
            _logger.warning(
                "XML ID %s.%s already points to %s(%s); not rebinding %s(%s)",
                module,
                name,
                wanted.model,
                wanted.res_id,
                record._name,
                record.id,
            )
            return wanted
        return wanted
    existing = Imd.search(
        [
            ("model", "=", record._name),
            ("res_id", "=", record.id),
            "|",
            "|",
            ("name", "=like", "generated_%"),
            ("name", "=", name),
            ("module", "=", LEGACY_XMLID_MODULE),
        ],
        limit=1,
    )
    if existing:
        existing.write({"module": module, "name": name})
        return existing
    return Imd.create(
        {
            "module": module,
            "name": name,
            "model": record._name,
            "res_id": record.id,
            "noupdate": True,
        }
    )


def bind_generated_xmlids(operation):
    """Assign bundle-owned XML IDs to compiler-generated records."""
    module = operation.bundle_id.code
    if operation.generated_field_id:
        field = operation.generated_field_id
        ensure_generated_xmlid(operation.env, module, field_xmlid_name(field), field)
    if operation.generated_view_id:
        ensure_generated_xmlid(
            operation.env,
            module,
            view_xmlid_name(operation),
            operation.generated_view_id,
        )
    if operation.generated_menu_id:
        ensure_generated_xmlid(
            operation.env,
            module,
            menu_xmlid_name(operation),
            operation.generated_menu_id,
        )


def rebind_generated_xmlids(env):
    """Migrate legacy ledger-owned XML IDs onto the bundle code."""
    operations = (
        env["customization.operation"]
        .sudo()
        .search(
            [
                "|",
                "|",
                ("generated_view_id", "!=", False),
                ("generated_field_id", "!=", False),
                ("generated_menu_id", "!=", False),
            ]
        )
    )
    for operation in operations:
        bind_generated_xmlids(operation)


def assert_aggregate_support(operation):
    """Reject what a pivot or graph arch parser would silently ignore.

    Both parsers only visit ``<field>`` nodes, so an inherit anchored on a
    page, group or button would compile without ever changing the view.
    Failing here keeps the operation honest instead of applied-but-inert.
    """
    view_type = operation.view_type or ""
    if view_type not in AGGREGATE_VIEW_TYPES:
        return
    kind = operation.anchor_kind or "field"
    if kind != "field":
        raise AnchorError(
            operation.env._(
                "A %(view)s view can only anchor on a field, not on a %(kind)s.",
                view=view_type,
                kind=kind,
            )
        )
    if operation.type not in AGGREGATE_OPERATION_TYPES:
        raise UserError(
            operation.env._(
                "Operation '%(type)s' is not supported on a %(view)s view.",
                type=operation.type,
                view=view_type,
            )
        )


def apply_operation(operation):
    """Compile one operation into ir.model.fields / ir.ui.view records."""
    if operation.type == "add_field":
        _apply_add_field(operation)
    elif operation.type in MENU_TYPES:
        _apply_menu(operation)
    elif operation.anchor_kind not in SUPPORTED_ANCHOR_KINDS:
        raise AnchorError(
            operation.env._("Anchor kind '%s' is not supported yet.")
            % operation.anchor_kind
        )
    else:
        assert_aggregate_support(operation)
        ok, reason = health_check_operation(operation)
        if not ok:
            raise AnchorError(reason)
        if operation.type in PLACEMENT_TYPES:
            assert_no_place_field_conflict(operation)
            if operation.type == "move_field":
                _apply_move_field(operation)
            else:
                _apply_place_field(operation)
        elif operation.type == "add_filter":
            _apply_add_filter(operation)
        elif operation.type in STRUCTURE_TYPES:
            _apply_add_structure(operation)
        elif operation.type == "add_button":
            assert_no_button_action_conflict(operation)
            _apply_add_button(operation)
        elif operation.type in ATTRIBUTE_TYPES:
            assert_no_view_write_conflict(operation)
            _apply_attributes(operation)
        else:
            raise UserError(
                operation.env._("Unsupported operation type '%s'.") % operation.type
            )
    bind_generated_xmlids(operation)


def _health_check_menu(operation):
    menu = operation.menu_id
    if not menu:
        return False, operation.env._("A menu is required.")
    if not menu.exists():
        return False, operation.env._("The target menu is missing.")
    xmlid = menu.get_external_id().get(menu.id)
    if not xmlid:
        return False, operation.env._("Menu '%s' has no XML ID.") % menu.display_name
    if operation.type == "add_menu":
        action_xmlid = (_payload(operation).get("action_xmlid") or "").strip()
        if not action_xmlid:
            return False, operation.env._(
                "add_menu requires a window action with an XML ID."
            )
        try:
            operation.env.ref(action_xmlid)
        except ValueError:
            return False, operation.env._("Action '%s' is missing.") % action_xmlid
    if operation.type == "move_menu":
        target_xmlid = (_payload(operation).get("target_xmlid") or "").strip()
        if not target_xmlid:
            return False, operation.env._(
                "move_menu requires a destination menu with an XML ID."
            )
        try:
            target = operation.env.ref(target_xmlid)
        except ValueError:
            return False, operation.env._("Menu '%s' is missing.") % target_xmlid
        if target._name != "ir.ui.menu":
            return False, operation.env._(
                "Destination '%s' is not a menu."
            ) % target_xmlid
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


def menu_write_conflicts(operation):
    """Return other live writes of the same type on the same standard menu."""
    Operation = operation.env["customization.operation"]
    if operation.type not in MENU_WRITE_TYPES or not operation.menu_id:
        return Operation.browse()
    domain = [
        ("menu_id", "=", operation.menu_id.id),
        ("type", "=", operation.type),
        ("state", "in", ("draft", "applied")),
    ]
    if operation.id:
        domain.append(("id", "!=", operation.id))
    return Operation.search(domain, limit=1)


def menu_write_conflict_message(operation, other):
    """Explain which bundle already owns this menu write."""
    return operation.env._(
        "Bundle '%(bundle)s' already has a %(type)s operation on menu '%(menu)s'."
    ) % {
        "bundle": other.bundle_id.code,
        "type": MENU_WRITE_LABELS.get(other.type, other.type),
        "menu": operation.menu_id.display_name,
    }


def assert_no_menu_write_conflict(operation):
    """Refuse a second hide/rename/groups/move on the same menu record."""
    other = menu_write_conflicts(operation)
    if other:
        raise UserError(menu_write_conflict_message(operation, other))


def view_write_conflicts(operation):
    """Return other live writes of the same type on the same view anchor."""
    Operation = operation.env["customization.operation"]
    if operation.type not in ATTRIBUTE_TYPES or not operation.view_id:
        return Operation.browse()
    domain = [
        ("view_id", "=", operation.view_id.id),
        ("type", "=", operation.type),
        ("anchor_kind", "=", operation.anchor_kind or "field"),
        ("anchor_name", "=", operation.anchor_name or False),
        ("anchor_string", "=", operation.anchor_string or False),
        ("anchor_occurrence", "=", operation.anchor_occurrence or 0),
        ("anchor_page", "=", operation.anchor_page or False),
        ("anchor_subview", "=", operation.anchor_subview or False),
        ("state", "in", ("draft", "applied")),
    ]
    if operation.id:
        domain.append(("id", "!=", operation.id))
    return Operation.search(domain, limit=1)


def view_write_conflict_message(operation, other):
    """Explain which bundle already owns this view attribute write."""
    anchor = operation.anchor_name or operation.anchor_string
    if not anchor:
        anchor = operation.env._("the view root")
    return operation.env._(
        "Bundle '%(bundle)s' already has a %(type)s operation on "
        "'%(anchor)s' in view '%(view)s'."
    ) % {
        "bundle": other.bundle_id.code,
        "type": VIEW_WRITE_LABELS.get(other.type, other.type),
        "anchor": anchor,
        "view": operation.view_id.name,
    }


def assert_no_view_write_conflict(operation):
    """Refuse a second hide/label/widget/groups/modifier on the same node."""
    other = view_write_conflicts(operation)
    if other:
        raise UserError(view_write_conflict_message(operation, other))


def place_field_conflicts(operation):
    """Return another live placement of the same field on the same view."""
    Operation = operation.env["customization.operation"]
    if operation.type not in PLACEMENT_TYPES or not operation.view_id:
        return Operation.browse()
    field_name = (operation.payload or {}).get("field_name")
    if not field_name:
        return Operation.browse()
    domain = [
        ("view_id", "=", operation.view_id.id),
        ("type", "in", list(PLACEMENT_TYPES)),
        ("anchor_subview", "=", operation.anchor_subview or False),
        ("state", "in", ("draft", "applied")),
    ]
    if operation.id:
        domain.append(("id", "!=", operation.id))
    others = Operation.search(domain)
    return others.filtered(
        lambda rec: (rec.payload or {}).get("field_name") == field_name
    )[:1]


def place_field_conflict_message(operation, other):
    """Explain which bundle already positions this field on the view."""
    field_name = (operation.payload or {}).get("field_name") or ""
    return operation.env._(
        "Bundle '%(bundle)s' already has a %(type)s operation for "
        "'%(field)s' in view '%(view)s'."
    ) % {
        "bundle": other.bundle_id.code,
        "type": PLACEMENT_LABELS.get(other.type, other.type),
        "field": field_name,
        "view": operation.view_id.name,
    }


def assert_no_place_field_conflict(operation):
    """Refuse a second live place of the same field on the same view."""
    other = place_field_conflicts(operation)
    if other:
        raise UserError(place_field_conflict_message(operation, other))


def _apply_menu(operation):
    ok, reason = _health_check_menu(operation)
    if not ok:
        raise AnchorError(reason)
    if operation.type in MENU_WRITE_TYPES:
        assert_no_menu_write_conflict(operation)
    if operation.type == "add_menu":
        _apply_add_menu(operation)
        return
    if operation.type == "move_menu":
        _apply_move_menu(operation)
        return
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
            raise UserError(operation.env._("set_menu_string requires payload.string."))
        previous.setdefault("name", menu.name)
        menu.write({"name": string})
    elif operation.type == "set_menu_groups":
        groups = payload.get("groups")
        if not groups:
            raise UserError(operation.env._("set_menu_groups requires payload.groups."))
        previous.setdefault("groups", _menu_groups_xmlids(menu))
        group_recs = groups_from_xmlids(operation.env, groups)
        menu.write({"groups_id": [Command.set(group_recs.ids)]})
    else:
        raise UserError(
            operation.env._("Unsupported operation type '%s'.") % operation.type
        )
    payload["xmlid"] = xmlid
    payload["previous"] = previous
    operation.payload = payload


def _apply_add_menu(operation):
    """Create a sibling or child menu next to the clicked navbar item."""
    anchor = operation.menu_id
    payload = dict(_payload(operation))
    string = (payload.get("string") or "").strip()
    if not string:
        raise UserError(operation.env._("add_menu requires payload.string."))
    position = operation.position or "after"
    if position == "inside":
        parent = anchor
        sequence = max(parent.child_id.mapped("sequence") or [0]) + 10
    else:
        parent = anchor.parent_id
        sequence = (anchor.sequence or 10) + 1
    action_xmlid = (payload.get("action_xmlid") or "").strip()
    if not action_xmlid:
        raise UserError(
            operation.env._("add_menu requires a window action with an XML ID.")
        )
    action = operation.env.ref(action_xmlid)
    if action._name != "ir.actions.act_window":
        raise UserError(
            operation.env._("add_menu requires a window action with an XML ID.")
        )
    vals = {
        "name": string,
        "parent_id": parent.id if parent else False,
        "sequence": sequence,
        "action": f"{action._name},{action.id}",
    }
    menu = operation.generated_menu_id
    if menu:
        menu.write(vals)
    else:
        menu = operation.env["ir.ui.menu"].create(vals)
        operation.generated_menu_id = menu
    if not (payload.get("name") or "").strip():
        payload["name"] = ensure_menu_xmlid_name(
            operation.env, f"menu_{slugify_field_suffix(string)}_{operation.id}"
        )
    else:
        payload["name"] = ensure_menu_xmlid_name(operation.env, payload["name"])
    payload["xmlid"] = f"{operation.bundle_id.code}.{payload['name']}"
    payload["action_xmlid"] = action_xmlid
    operation.payload = payload


def _assert_safe_menu_move(menu, target):
    """Refuse moving a menu onto itself or into its own subtree."""
    if menu == target:
        raise UserError(menu.env._("Choose a different menu as the destination."))
    current = target
    while current:
        if current == menu:
            raise UserError(menu.env._("A menu cannot be moved under itself."))
        current = current.parent_id


def _apply_move_menu(operation):
    """Reparent the clicked menu after or inside another menu."""
    menu = operation.menu_id
    payload = dict(_payload(operation))
    target_xmlid = (payload.get("target_xmlid") or "").strip()
    if not target_xmlid:
        raise UserError(
            operation.env._("move_menu requires a destination menu with an XML ID.")
        )
    target = operation.env.ref(target_xmlid)
    if target._name != "ir.ui.menu":
        raise UserError(
            operation.env._("Destination '%s' is not a menu.") % target_xmlid
        )
    _assert_safe_menu_move(menu, target)
    position = operation.position or "after"
    if position == "inside":
        parent = target
        siblings = parent.child_id.filtered(lambda child: child != menu)
        sequence = max(siblings.mapped("sequence") or [0]) + 10
    else:
        parent = target.parent_id
        sequence = (target.sequence or 10) + 1
    if parent:
        parent_xmlid = parent.get_external_id().get(parent.id)
        if not parent_xmlid:
            raise UserError(
                operation.env._("Parent menu '%s' has no XML ID.") % parent.display_name
            )
    else:
        parent_xmlid = False
    previous = dict(payload.get("previous") or {})
    previous.setdefault("parent_id", menu.parent_id.id if menu.parent_id else False)
    if menu.parent_id:
        previous.setdefault(
            "parent_xmlid",
            menu.parent_id.get_external_id().get(menu.parent_id.id) or False,
        )
    else:
        previous.setdefault("parent_xmlid", False)
    previous.setdefault("sequence", menu.sequence)
    menu.write(
        {
            "parent_id": parent.id if parent else False,
            "sequence": sequence,
        }
    )
    payload["xmlid"] = menu.get_external_id().get(menu.id)
    payload["target_xmlid"] = target_xmlid
    payload["parent_xmlid"] = parent_xmlid
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
    elif operation.type == "move_menu" and "sequence" in previous:
        parent_id = previous.get("parent_id") or 0
        parent = operation.env["ir.ui.menu"].browse(parent_id).exists()
        vals["parent_id"] = parent.id if parent else False
        vals["sequence"] = previous["sequence"]
    if vals:
        menu.write(vals)


def _add_field_schema_changed(field, ttype, related, payload):
    """Return whether Re-apply must unlink and recreate the field."""
    if field.ttype != ttype:
        return True
    if (field.related or False) != (related or False):
        return True
    if ttype in ("many2one", "many2many"):
        return field.relation != (payload.get("relation") or False)
    return False


def _handle_existing_generated_field(operation, ttype, related, payload):
    """Update the generated field in place or unlink it when schema changed.

    Return ``(done, name)``. ``done`` means Re-apply finished without
    creating a new field. ``name`` is the technical name to reuse after
    a schema change.
    """
    field = operation.generated_field_id
    if not field:
        return False, None
    if not _add_field_schema_changed(field, ttype, related, payload):
        _update_generated_field(field, ttype, related, payload)
        return True, None
    name = field.name
    payload["name"] = name
    field.unlink()
    operation.generated_field_id = False
    operation.env.flush_all()
    operation.env.registry.clear_cache()
    return False, name


def _update_generated_field(field, ttype, related, payload):
    """Update metadata of an existing generated field on Re-apply."""
    vals = {
        "field_description": payload.get("string") or field.field_description,
        "help": payload.get("help") or False,
        "required": bool(payload.get("required")),
    }
    if ttype == "selection" and not related:
        selection = payload.get("selection") or []
        if not selection:
            raise UserError(field.env._("Selection fields need at least one option."))
        vals["selection_ids"] = _selection_commands(field, selection)
    if ttype == "monetary":
        currency_field = payload.get("currency_field")
        if currency_field:
            vals["currency_field"] = currency_field
    field.write(vals)


def _selection_commands(field, selection):
    """Sync selection options in place so existing values are kept."""
    existing = {opt.value: opt for opt in field.selection_ids}
    wanted = [(str(value), str(label)) for value, label in selection]
    wanted_values = {value for value, _label in wanted}
    commands = []
    for index, (value, label) in enumerate(wanted):
        current = existing.get(value)
        if current:
            commands.append(
                Command.update(current.id, {"name": label, "sequence": index})
            )
        else:
            commands.append(
                Command.create({"value": value, "name": label, "sequence": index})
            )
    for value, current in existing.items():
        if value not in wanted_values:
            commands.append(Command.delete(current.id))
    return commands


def _add_field_vals(operation, name, ttype, related, payload):
    """Build ``ir.model.fields`` values for a new generated field."""
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
            raise UserError(
                operation.env._("A relation model is required for %s fields.") % ttype
            )
        vals["relation"] = relation
    if ttype == "selection" and not related:
        selection = payload.get("selection") or []
        if not selection:
            raise UserError(
                operation.env._("Selection fields need at least one option.")
            )
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
            operation.env["ir.model.fields"]._get(operation.model, "currency_id")
            or operation.env["ir.model.fields"]._get(operation.model, "x_currency_id")
        ):
            raise UserError(
                operation.env._(
                    "Monetary fields need a currency field on the model "
                    "(currency_id or x_currency_id)."
                )
            )
    return vals


def _apply_add_field(operation):
    payload = dict(_payload(operation))
    model_name = operation.model
    if not model_name:
        raise UserError(operation.env._("A model is required to create a field."))
    Model = operation.env[model_name]
    table_kind = sql.table_kind(operation.env.cr, Model._table)
    if table_kind != sql.TableKind.Regular:
        raise UserError(
            operation.env._("The model %s does not support adding fields.") % model_name
        )

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
            operation.env._("Field type '%s' is not supported.")
            % (ttype or operation.env._("(missing)"))
        )

    requested = payload.get("name") or slugify_field_suffix(
        payload.get("string") or (related and related.split(".")[-1]) or ""
    )
    name = ensure_field_name(operation.env, requested)
    done, reused_name = _handle_existing_generated_field(
        operation, ttype, related, payload
    )
    if done:
        return
    if reused_name:
        name = reused_name

    name = unique_field_name(operation.env, model_name, name)
    vals = _add_field_vals(operation, name, ttype, related, payload)
    field = operation.env["ir.model.fields"].create(vals)
    operation.generated_field_id = field
    payload["name"] = field.name
    payload["ttype"] = ttype
    operation.payload = payload


def _unnamed_node_expr(env, arch_tree, node):
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
        raise AnchorError(env._("Unnamed %s anchor was not found.") % tag) from err
    return f"(//{tag}[not(@name)])[{index}]"


def _button_type_expr(operation, arch_tree, tag, anchor, page, occurrence):
    """Return an inherit xpath for a button anchored by ``@type``, or None."""
    if tag != "button" or not anchor:
        return None
    if arch_tree is None:
        arch_tree = combined_arch_for_operation(operation.view_id, operation)
    node = resolve_anchor(
        operation.env,
        arch_tree,
        operation.anchor_name,
        operation.anchor_kind,
        operation.anchor_occurrence,
        operation.anchor_page,
        operation.anchor_string,
    )
    if node.get("name") == anchor or node.get("type") != anchor:
        return None
    if occurrence:
        return f"(//button[@type={xpath_quote(anchor)}])[{int(occurrence)}]"
    if page:
        return f"//page[@name={xpath_quote(page)}]//button[@type={xpath_quote(anchor)}]"
    return f"//button[@type={xpath_quote(anchor)}]"


def _subview_inherit_arch(operation, inner_xml, position, arch_tree=None):
    """Inherit arch for an anchor inside an embedded subview.

    A bare ``<field name="x" position="...">`` spec would be resolved
    against the whole parent view, where the same name usually also exists
    on the record itself, so the scoped xpath is not optional here.
    """
    env = operation.env
    kind = operation.anchor_kind or "field"
    if arch_tree is None:
        arch_tree = combined_arch_for_operation(operation.view_id, operation)
    # Resolving the scope here turns a referenced subview into a readable
    # reason instead of an inherit whose xpath matches nothing.
    subview_scope(operation, arch_tree)
    prefix = subview_expr_prefix(operation)
    if kind == "view":
        expr = prefix
    else:
        tag = ANCHOR_TAGS.get(kind, "field")
        anchor = (operation.anchor_name or "").strip()
        if not anchor:
            raise AnchorError(
                env._("An anchor inside a subview must have a technical name.")
            )
        attr = "field" if tag == "progressbar" else "name"
        expr = f"{prefix}//{tag}[@{attr}={xpath_quote(anchor)}]"
        occurrence = operation.anchor_occurrence or 0
        if occurrence:
            expr = f"({expr})[{int(occurrence)}]"
    return f'<xpath expr="{_xml_attr(expr)}" position="{position}">{inner_xml}</xpath>'


def _inherit_arch(operation, inner_xml, position, arch_tree=None):
    kind = operation.anchor_kind or "field"
    if operation.anchor_subview:
        return _subview_inherit_arch(operation, inner_xml, position, arch_tree)
    if kind == "view":
        if arch_tree is None:
            arch_tree = combined_arch_for_operation(operation.view_id, operation)
        # Read the tag off the arch instead of deriving it from the view type,
        # so a renamed root tag cannot silently produce a dangling inherit.
        root = arch_tree.tag
        return f'<{root} position="{position}">{inner_xml}</{root}>'
    tag = ANCHOR_TAGS.get(kind, "field")
    anchor = (operation.anchor_name or "").strip()
    title = (operation.anchor_string or "").strip()
    page = (operation.anchor_page or "").strip()
    occurrence = operation.anchor_occurrence or 0
    if not anchor and tag in ("page", "group") and title:
        if arch_tree is None:
            arch_tree = combined_arch_for_operation(operation.view_id, operation)
        node = resolve_anchor(
            operation.env,
            arch_tree,
            operation.anchor_name,
            operation.anchor_kind,
            operation.anchor_occurrence,
            operation.anchor_page,
            operation.anchor_string,
        )
        expr = _unnamed_node_expr(operation.env, arch_tree, node)
        return (
            f'<xpath expr="{_xml_attr(expr)}" position="{position}">'
            f"{inner_xml}</xpath>"
        )
    type_expr = _button_type_expr(operation, arch_tree, tag, anchor, page, occurrence)
    if type_expr:
        return (
            f'<xpath expr="{_xml_attr(type_expr)}" position="{position}">'
            f"{inner_xml}</xpath>"
        )
    if tag == "progressbar":
        expr = f"//progressbar[@field={xpath_quote(anchor)}]"
        if occurrence:
            expr = f"({expr})[{int(occurrence)}]"
        return (
            f'<xpath expr="{_xml_attr(expr)}" position="{position}">'
            f"{inner_xml}</xpath>"
        )
    if occurrence:
        expr = f"(//{tag}[@name={xpath_quote(anchor)}])[{int(occurrence)}]"
        return (
            f'<xpath expr="{_xml_attr(expr)}" position="{position}">'
            f"{inner_xml}</xpath>"
        )
    if page:
        expr = f"//page[@name={xpath_quote(page)}]//{tag}[@name={xpath_quote(anchor)}]"
        return (
            f'<xpath expr="{_xml_attr(expr)}" position="{position}">'
            f"{inner_xml}</xpath>"
        )
    return (
        f'<{tag} name="{_xml_attr(anchor)}" position="{position}">'
        f"{inner_xml}</{tag}>"
    )


def _upsert_generated_view(operation, arch, active=True):
    view = operation.generated_view_id
    # An inherit belongs to the arch it extends. A subview operation targets
    # the related model, but the inherit still rides on the parent view, so
    # type and model have to follow that one instead of the anchor.
    if operation.anchor_subview:
        view_type = operation.view_id.type
        model = operation.view_id.model
    else:
        view_type = operation.view_type or operation.view_id.type
        model = operation.model
    values = {
        "name": (f"Customization {operation.bundle_id.code} operation {operation.id}"),
        "type": view_type,
        "model": model,
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
        raise UserError(operation.env._("A page title is required."))
    requested = payload.get("name") or slugify_field_suffix(string or tag)
    name = ensure_field_name(operation.env, requested)
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
        raise UserError(operation.env._("A page cannot be placed inside another page."))
    if position not in FIELD_POSITIONS:
        raise AnchorError(
            operation.env._(
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


def validated_button_action(env, xmlid):
    """Return the XML ID of an action a button may call, or raise.

    The arch keeps the XML ID rather than the database id, which is what
    the view validator and the client both accept, so the compiled button
    survives a reinstall of the module that owns the action and exports
    without a numeric id nobody can read.
    """
    xmlid = (xmlid or "").strip()
    if not xmlid:
        raise UserError(env._("A button needs an action to call."))
    model, res_id = env["ir.model.data"]._xmlid_to_res_model_res_id(
        xmlid, raise_if_not_found=False
    )
    if not res_id:
        raise UserError(env._("Action '%s' is missing.") % xmlid)
    if not issubclass(env.registry[model], env.registry["ir.actions.actions"]):
        raise UserError(
            env._(
                "'%(xmlid)s' is a %(model)s, not an action a button can call.",
                xmlid=xmlid,
                model=model,
            )
        )
    return xmlid


def _apply_add_button(operation):
    """Compile add_button into a button node calling an existing action."""
    payload = dict(_payload(operation))
    env = operation.env
    string = (payload.get("string") or "").strip()
    if not string:
        raise UserError(env._("A button label is required."))
    xmlid = validated_button_action(env, payload.get("action_xmlid"))
    btn_class = (payload.get("btn_class") or "").strip()
    if btn_class not in BUTTON_CLASSES:
        raise UserError(env._("Button class '%s' is not supported.") % btn_class)
    position = operation.position or "after"
    if position not in FIELD_POSITIONS:
        raise AnchorError(
            operation.env._("Position '%s' is not valid for placing a button.")
            % position
        )
    attrs = f'type="action" name="{_xml_attr(xmlid)}" string="{_xml_attr(string)}"'
    if btn_class:
        attrs += f' class="{_xml_attr(btn_class)}"'
    arch = _inherit_arch(operation, f"<button {attrs}/>", position)
    _upsert_generated_view(operation, arch, active=True)
    payload.update({"string": string, "action_xmlid": xmlid})
    operation.payload = payload


def button_action_conflicts(operation):
    """Return another live button calling the same action on the view."""
    Operation = operation.env["customization.operation"]
    if operation.type != "add_button" or not operation.view_id:
        return Operation.browse()
    xmlid = (_payload(operation).get("action_xmlid") or "").strip()
    if not xmlid:
        return Operation.browse()
    domain = [
        ("view_id", "=", operation.view_id.id),
        ("type", "=", "add_button"),
        ("anchor_subview", "=", operation.anchor_subview or False),
        ("state", "in", ("draft", "applied")),
    ]
    if operation.id:
        domain.append(("id", "!=", operation.id))
    others = Operation.search(domain)
    return others.filtered(
        lambda rec: (rec.payload or {}).get("action_xmlid") == xmlid
    )[:1]


def button_action_conflict_message(operation, other):
    """Explain which bundle already calls this action from the view."""
    return operation.env._(
        "Bundle '%(bundle)s' already adds a button calling '%(action)s' on "
        "view '%(view)s'. Two buttons for the same action would just sit "
        "next to each other.",
        bundle=other.bundle_id.code,
        action=(_payload(operation).get("action_xmlid") or "?"),
        view=operation.view_id.display_name,
    )


def assert_no_button_action_conflict(operation):
    other = button_action_conflicts(operation)
    if other:
        raise UserError(button_action_conflict_message(operation, other))


def validated_filter_domain(env, domain):
    """Refuse a domain that would otherwise fail later, at search time.

    A dynamic domain (``context_today()`` and friends) cannot be evaluated
    here, so it only gets a syntax check. A literal one is also checked for
    shape, which is what catches a missing tuple or a stray operator.
    """
    domain = (domain or "").strip()
    if not domain:
        raise UserError(env._("add_filter requires a domain or a grouping."))
    try:
        ast.parse(domain, mode="eval")
    except SyntaxError as err:
        raise UserError(
            env._("The filter domain is not valid Python: %s") % err
        ) from err
    try:
        literal = ast.literal_eval(domain)
    except (ValueError, SyntaxError):
        return domain
    if not isinstance(literal, list | tuple):
        raise UserError(env._("The filter domain must be a list of conditions."))
    try:
        expression.normalize_domain(list(literal))
    except (ValueError, AssertionError) as err:
        raise UserError(env._("The filter domain is malformed: %s") % err) from err
    return domain


def validated_group_by(operation, field_name):
    """Return a field name that the client will accept as a grouping."""
    field_name = (field_name or "").strip()
    if not re.match(r"^[a-z_][a-z0-9_]*$", field_name):
        raise UserError(
            operation.env._("Group by '%s' is not a valid field name.") % field_name
        )
    field = operation.env["ir.model.fields"]._get(operation.model, field_name)
    if not field:
        raise UserError(
            operation.env._(
                "Field '%(field)s' does not exist on %(model)s.",
                field=field_name,
                model=operation.model,
            )
        )
    if field.ttype not in GROUPABLE_TTYPES:
        raise UserError(
            operation.env._(
                "A %(ttype)s field cannot be grouped by.",
                ttype=field.ttype,
            )
        )
    return field_name


def _apply_add_filter(operation):
    """Compile add_filter into a <filter> node on a search view."""
    if operation.view_type != "search":
        raise UserError(operation.env._("Filters only exist on search views."))
    payload = dict(_payload(operation))
    string = (payload.get("string") or "").strip()
    if not string:
        raise UserError(operation.env._("A filter label is required."))
    name = ensure_field_name(
        operation.env, payload.get("name") or slugify_field_suffix(string)
    )
    group_by = (payload.get("group_by") or "").strip()
    domain = (payload.get("domain") or "").strip()
    if group_by and domain:
        raise UserError(
            operation.env._("A filter carries either a domain or a grouping.")
        )
    head = f'<filter name="{_xml_attr(name)}" string="{_xml_attr(string)}"'
    if group_by:
        group_by = validated_group_by(operation, group_by)
        context = f"{{'group_by': '{group_by}'}}"
        inner = f'{head} context="{_xml_attr(context)}"/>'
    else:
        domain = validated_filter_domain(operation.env, domain)
        inner = f'{head} domain="{_xml_attr(domain)}"/>'
    position = operation.position or "after"
    if position not in FIELD_POSITIONS:
        raise AnchorError(
            operation.env._("Position '%s' is not valid for adding a filter.")
            % position
        )
    arch = _inherit_arch(operation, inner, position)
    _upsert_generated_view(operation, arch, active=True)
    payload["name"] = name
    operation.payload = payload


def aggregate_field_type(operation):
    """Return the ``type`` attribute for a field placed on a pivot or graph.

    A pivot field without a type is parsed and then contributes nothing, so
    the type is required there. A graph groupby carries no type at all,
    which ``groupby`` compiles to.
    """
    view_type = operation.view_type or ""
    if view_type not in AGGREGATE_VIEW_TYPES:
        return ""
    allowed = AGGREGATE_FIELD_TYPES[view_type]
    field_type = (_payload(operation).get("field_type") or "measure").strip()
    if field_type not in allowed:
        raise UserError(
            operation.env._(
                "Field type '%(type)s' is not valid on a %(view)s view. "
                "Use one of: %(allowed)s.",
                type=field_type,
                view=view_type,
                allowed=", ".join(allowed),
            )
        )
    return "" if field_type == "groupby" else field_type


def placement_field_name(operation):
    """Return the field a place/move operation acts on."""
    field_name = _payload(operation).get("field_name")
    if not field_name:
        raise UserError(
            operation.env._("%s requires payload.field_name.")
            % (operation.type or "place_field")
        )
    if not re.match(r"^[a-z_][a-z0-9_]*$", field_name):
        raise UserError(operation.env._("Field name '%s' is not valid.") % field_name)
    return field_name


def _apply_move_field(operation):
    """Relocate an existing field node instead of adding a second one."""
    field_name = placement_field_name(operation)
    position = operation.position or "after"
    if position not in MOVE_POSITIONS:
        raise AnchorError(
            operation.env._("Position '%s' is not valid for moving a field.") % position
        )
    arch = _inherit_arch(
        operation,
        f'<field name="{_xml_attr(field_name)}" position="move"/>',
        position,
    )
    _upsert_generated_view(operation, arch, active=True)


def _apply_place_field(operation):
    field_name = placement_field_name(operation)
    position = operation.position or "after"
    if position not in FIELD_POSITIONS:
        raise AnchorError(
            operation.env._("Position '%s' is not valid for placing a field.")
            % position
        )
    field_type = aggregate_field_type(operation)
    type_attr = f' type="{_xml_attr(field_type)}"' if field_type else ""
    arch = _inherit_arch(
        operation, f'<field name="{_xml_attr(field_name)}"{type_attr}/>', position
    )
    _upsert_generated_view(operation, arch, active=True)


def _attribute_xml(name, value):
    return f'<attribute name="{name}">{xml_escape(str(value))}</attribute>'


def _set_string_parts(operation):
    string = _payload(operation).get("string")
    if not string:
        raise UserError(operation.env._("set_string requires payload.string."))
    return [_attribute_xml("string", string)]


def _set_widget_parts(operation):
    widget = _payload(operation).get("widget")
    if not widget:
        raise UserError(operation.env._("set_widget requires payload.widget."))
    return [_attribute_xml("widget", widget)]


def _set_groups_parts(operation):
    groups = _payload(operation).get("groups")
    if not groups:
        raise UserError(operation.env._("set_groups requires payload.groups."))
    return [_attribute_xml("groups", groups)]


def _set_modifier_parts(operation):
    modifiers = _payload(operation).get("modifiers") or {}
    if not modifiers:
        raise UserError(operation.env._("set_modifier requires payload.modifiers."))
    if operation.view_type in AGGREGATE_VIEW_TYPES:
        # Those parsers read invisible only, and only as a literal.
        unsupported = sorted(set(modifiers) - {"invisible"})
        if unsupported:
            raise UserError(
                operation.env._(
                    "Only invisible can be set on a %(view)s view, not %(keys)s.",
                    view=operation.view_type,
                    keys=", ".join(unsupported),
                )
            )
    return [
        _attribute_xml(key, modifiers[key]) for key in MODIFIER_KEYS if key in modifiers
    ]


def _set_optional_parts(operation):
    # Only the list renderer builds a column picker, so the attribute is inert
    # anywhere else.
    if operation.view_type != "list":
        raise UserError(operation.env._("Optional columns only exist on list views."))
    if (operation.anchor_kind or "field") != "field":
        raise UserError(operation.env._("Only a column can be made optional."))
    optional = (_payload(operation).get("optional") or "").strip()
    if optional not in OPTIONAL_VALUES:
        raise UserError(
            operation.env._(
                "set_optional requires payload.optional to be one of: %s.",
                ", ".join(OPTIONAL_VALUES),
            )
        )
    return [_attribute_xml("optional", optional)]


def _assert_root_attribute_name(operation, name):
    """Refuse an option the arch parser of this view type never reads."""
    view_type = operation.view_type or ""
    if name.startswith("decoration-"):
        if view_type != "list":
            raise UserError(
                operation.env._("Row decorations are only read on a list view.")
            )
        decoration = name[len("decoration-") :]
        if decoration not in ROOT_DECORATIONS:
            raise UserError(
                operation.env._(
                    "'%(name)s' is not a decoration. Use one of: %(allowed)s.",
                    name=name,
                    allowed=", ".join(ROOT_DECORATIONS),
                )
            )
        return
    allowed = ROOT_ATTRIBUTES.get(view_type)
    if not allowed:
        raise UserError(
            operation.env._("A %s view has no root options to set.")
            % (view_type or "?")
        )
    if name not in allowed:
        raise UserError(
            operation.env._(
                "Option '%(name)s' is not available on a %(view)s view. "
                "Use one of: %(allowed)s.",
                name=name,
                view=view_type,
                allowed=", ".join(allowed),
            )
        )


def _validated_root_default_order(operation, value):
    """Refuse an order the server would reject when it reads the records."""
    for part in value.split(","):
        tokens = part.split()
        if not tokens or len(tokens) > 2:
            raise UserError(
                operation.env._("'%s' is not a valid default order.") % part.strip()
            )
        field = operation.env["ir.model.fields"]._get(operation.model, tokens[0])
        if not field:
            raise UserError(
                operation.env._(
                    "Field '%(field)s' does not exist on %(model)s.",
                    field=tokens[0],
                    model=operation.model,
                )
            )
        if not field.store:
            raise UserError(
                operation.env._(
                    "Field '%s' is not stored, so records cannot be ordered by it."
                )
                % tokens[0]
            )
        if len(tokens) == 2 and tokens[1].lower() not in ("asc", "desc"):
            raise UserError(
                operation.env._("'%s' is not a sort direction.") % tokens[1]
            )
    return value


def _validated_root_value(operation, name, value):
    """Check the value against what the parser of this option accepts."""
    if name.startswith("decoration-"):
        # The condition is evaluated against a record, so only its syntax can
        # be checked here.
        try:
            ast.parse(value, mode="eval")
        except SyntaxError as err:
            raise UserError(
                operation.env._(
                    "The condition of '%(name)s' is not valid Python: %(error)s"
                )
                % {"name": name, "error": err}
            ) from err
        return value
    if name in ROOT_BOOLEAN_ATTRIBUTES:
        if value not in ("0", "1"):
            raise UserError(
                operation.env._(
                    "Option '%(name)s' takes 0 or 1, not '%(value)s'.",
                    name=name,
                    value=value,
                )
            )
        return value
    if name == "editable":
        if value not in ROOT_EDITABLE_VALUES:
            raise UserError(
                operation.env._(
                    "Option 'editable' takes %(allowed)s, not '%(value)s'.",
                    allowed=" or ".join(ROOT_EDITABLE_VALUES),
                    value=value,
                )
            )
        return value
    if name == "default_order":
        return _validated_root_default_order(operation, value)
    return value


def _set_view_attribute_parts(operation):
    attributes = _payload(operation).get("attributes") or {}
    if not attributes:
        raise UserError(
            operation.env._("set_view_attribute requires payload.attributes.")
        )
    parts = []
    for name in sorted(attributes):
        raw = attributes[name]
        value = "" if raw is None else str(raw).strip()
        _assert_root_attribute_name(operation, name)
        # An empty value drops the attribute, which is how an option the base
        # view already sets is turned back off.
        if value:
            value = _validated_root_value(operation, name, value)
        parts.append(_attribute_xml(name, value))
    return parts


def _hide_field_parts(operation):
    attr = "column_invisible" if operation.view_type == "list" else "invisible"
    return [_attribute_xml(attr, "True")]


ATTRIBUTE_PARTS = {
    "set_string": _set_string_parts,
    "set_widget": _set_widget_parts,
    "set_groups": _set_groups_parts,
    "set_modifier": _set_modifier_parts,
    "set_optional": _set_optional_parts,
    "set_view_attribute": _set_view_attribute_parts,
    "hide_field": _hide_field_parts,
}


def _apply_attributes(operation):
    if (
        operation.type == "hide_field"
        and (operation.anchor_kind or "field") == "progressbar"
    ):
        # The kanban parser ignores invisible on <progressbar>; drop the node.
        arch = _inherit_arch(operation, "", "replace")
        _upsert_generated_view(operation, arch, active=True)
        return
    build = ATTRIBUTE_PARTS.get(operation.type)
    if not build:
        raise UserError(
            operation.env._("Unsupported operation type '%s'.") % operation.type
        )
    arch = _inherit_arch(operation, "".join(build(operation)), "attributes")
    _upsert_generated_view(operation, arch, active=True)
