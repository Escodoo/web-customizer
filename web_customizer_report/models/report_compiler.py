# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import re
from xml.sax.saxutils import escape as xml_escape

from lxml import etree

from odoo.addons.web_customizer.models.compiler import (
    AnchorError,
    combined_arch_for_operation,
    view_xmlid_name,
    xpath_quote,
)

REPORT_VIEW_TYPE = "qweb"
# A report node is only stable through an upgrade when the core template
# already names it or already prints a record value there. Bootstrap
# classes and translatable text are neither.
REPORT_ANCHOR_KINDS = ("field", "t_field")
REPORT_OPERATION_TYPES = (
    "hide_field",
    "set_string",
    "place_field",
    "move_field",
)
REPORT_PLACEMENT_TYPES = ("place_field", "move_field")
# "replace" would drop the anchor, and "attributes" is what the writes
# below build on their own.
REPORT_POSITIONS = ("before", "after", "inside")
# A cell only makes sense next to a cell; anywhere else the surrounding
# markup expects an inline node.
CELL_TAGS = ("td", "th")
# Templates every report calls for its page container and letterhead.
# Naming them in the wrapper error would say nothing useful.
LAYOUT_TEMPLATES = (
    "web.html_container",
    "web.basic_layout",
    "web.internal_layout",
    "web.external_layout",
)
# Odoo names the per-record template after the report it belongs to, so
# the wrapper of ``…_document`` is the report action to read the model
# from. A missing wrapper only costs the model check.
DOCUMENT_SUFFIX = "_document"
DEFAULT_DOCUMENT_VAR = "o"
NAME_RE = re.compile(r"^[A-Za-z_][\w.-]*$")
EXPRESSION_RE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+$")


def is_report_operation(operation):
    """Whether this operation targets a QWeb report template."""
    return (operation.view_type or "") == REPORT_VIEW_TYPE


def _payload(operation):
    return operation.payload or {}


def _xml_attr(value):
    """Escape a value for use inside a double-quoted XML attribute."""
    return xml_escape(value or "", {'"': "&quot;"})


def _attribute_xml(name, value):
    return f'<attribute name="{name}">{xml_escape(str(value))}</attribute>'


def report_arch(operation):
    """Return the combined, untranslated arch of the targeted template."""
    view = operation.view_id
    if not view:
        raise AnchorError(operation.env._("A target report template is required."))
    if view.type != REPORT_VIEW_TYPE:
        raise AnchorError(
            operation.env._("View '%s' is not a QWeb template.") % view.display_name
        )
    tree = combined_arch_for_operation(view, operation)
    assert_document_template(operation, view, tree)
    return tree


def assert_document_template(operation, view, tree):
    """Refuse the wrapper template that only delegates to the document.

    ``account.report_invoice`` iterates the records and hands the markup
    to ``account.report_invoice_document``. Customizing the wrapper puts
    the change outside the template every localization extends, and the
    node the consultant aimed at is not even in that arch.
    """
    key = view.key
    if not key:
        return
    printed = (
        operation.env["ir.actions.report"]
        .sudo()
        .search_count([("report_name", "=", key)])
    )
    if not printed:
        return
    called = sorted(
        {
            call
            for call in tree.xpath("//*/@t-call")
            if isinstance(call, str) and "." in call and call not in LAYOUT_TEMPLATES
        }
    )
    if not called:
        # A report written as a single template has no document to aim at.
        return
    raise AnchorError(
        operation.env._(
            "'%(wrapper)s' only wraps the report. Target the document "
            "template it calls (%(document)s) so localization inherits "
            "keep applying.",
            wrapper=key,
            document=", ".join(called),
        )
    )


def assert_report_operation(operation):
    """Reject a type or anchor kind a report template cannot carry."""
    if operation.type not in REPORT_OPERATION_TYPES:
        raise AnchorError(
            operation.env._("Operation '%s' is not supported on a report template.")
            % (operation.type or "?")
        )
    kind = operation.anchor_kind or "field"
    if kind not in REPORT_ANCHOR_KINDS:
        raise AnchorError(
            operation.env._(
                "A report node is anchored on its name or on its t-field, "
                "not on a %s."
            )
            % kind
        )


def report_anchor(operation):
    """Return the ``(kind, value)`` pair identifying the anchored node."""
    assert_report_operation(operation)
    kind = operation.anchor_kind or "field"
    anchor = (operation.anchor_name or "").strip()
    if not anchor:
        raise AnchorError(operation.env._("An anchor is required."))
    pattern = EXPRESSION_RE if kind == "t_field" else NAME_RE
    if not pattern.match(anchor):
        raise AnchorError(
            operation.env._("'%s' is not a valid report anchor.") % anchor
        )
    return kind, anchor


def report_anchor_nodes(tree, kind, anchor):
    attribute = "t-field" if kind == "t_field" else "name"
    return tree.xpath(f"//*[@{attribute}={xpath_quote(anchor)}]")


def resolve_report_anchor(operation, tree):
    """Return the single node the anchor points at in the combined arch."""
    kind, anchor = report_anchor(operation)
    nodes = report_anchor_nodes(tree, kind, anchor)
    label = "t-field" if kind == "t_field" else "name"
    if not nodes:
        raise AnchorError(
            operation.env._(
                "Template '%(view)s' has no node with %(label)s '%(anchor)s'.",
                view=operation.view_id.display_name,
                label=label,
                anchor=anchor,
            )
        )
    occurrence = operation.anchor_occurrence or 0
    if occurrence:
        if occurrence > len(nodes):
            raise AnchorError(
                operation.env._(
                    "Occurrence %(occurrence)s of %(label)s '%(anchor)s' was "
                    "asked for, but the template declares %(count)s.",
                    occurrence=occurrence,
                    label=label,
                    anchor=anchor,
                    count=len(nodes),
                )
            )
        return nodes[occurrence - 1]
    if len(nodes) > 1:
        raise AnchorError(
            operation.env._(
                "%(label)s '%(anchor)s' appears %(count)s times in "
                "'%(view)s'; set the occurrence to pick one.",
                label=label,
                anchor=anchor,
                count=len(nodes),
                view=operation.view_id.display_name,
            )
        )
    return nodes[0]


def report_anchor_expr(operation):
    """Return the XPath the generated inherit carries."""
    kind, anchor = report_anchor(operation)
    attribute = "t-field" if kind == "t_field" else "name"
    expr = f"//*[@{attribute}={xpath_quote(anchor)}]"
    occurrence = operation.anchor_occurrence or 0
    if occurrence:
        expr = f"({expr})[{int(occurrence)}]"
    return expr


def report_inherit_arch(operation, inner_xml, position):
    expr = report_anchor_expr(operation)
    return f'<xpath expr="{_xml_attr(expr)}" position="{position}">{inner_xml}</xpath>'


def report_model(operation):
    """Return the model the report prints, when the action is findable."""
    key = operation.view_id.key
    if not key:
        return ""
    Report = operation.env["ir.actions.report"].sudo()
    report = Report.search([("report_name", "=", key)], limit=1)
    if not report and key.endswith(DOCUMENT_SUFFIX):
        wrapper = key[: -len(DOCUMENT_SUFFIX)]
        report = Report.search([("report_name", "=", wrapper)], limit=1)
    return report.model or ""


def template_variables(tree):
    """Return the QWeb variable names the template declares.

    A ``t-field`` may read the record the report iterates or any loop or
    ``t-set`` variable. Collecting them all is a superset of what is in
    scope at one node, which is enough to catch a typo without refusing a
    legitimate expression.
    """
    names = {DEFAULT_DOCUMENT_VAR}
    names.update(value for value in tree.xpath("//*/@t-as") if value)
    names.update(value for value in tree.xpath("//*/@t-set") if value)
    return names


def assert_field_path(operation, model_name, path):
    """Walk a dotted field path, refusing the first segment that is not there."""
    env = operation.env
    current = model_name
    names = path.split(".")
    for index, name in enumerate(names):
        field = env["ir.model.fields"]._get(current, name)
        if not field:
            raise AnchorError(
                env._(
                    "Field '%(field)s' does not exist on %(model)s.",
                    field=name,
                    model=current,
                )
            )
        if index == len(names) - 1:
            return
        if not field.relation:
            raise AnchorError(
                env._(
                    "Field '%(field)s' on %(model)s is not relational, so "
                    "'%(rest)s' cannot be read through it.",
                    field=name,
                    model=current,
                    rest=".".join(names[index + 1 :]),
                )
            )
        current = field.relation


def validated_report_expression(operation, tree):
    """Return the checked QWeb expression a place operation prints."""
    expression = (_payload(operation).get("field_name") or "").strip()
    if not EXPRESSION_RE.match(expression):
        raise AnchorError(
            operation.env._(
                "'%s' is not a report expression. Name the variable and the "
                "field path, for example o.invoice_date."
            )
            % (expression or "")
        )
    variable, path = expression.split(".", 1)
    known = template_variables(tree)
    if variable not in known:
        raise AnchorError(
            operation.env._(
                "Template '%(view)s' declares no variable '%(variable)s'. "
                "It knows %(known)s.",
                view=operation.view_id.display_name,
                variable=variable,
                known=", ".join(sorted(known)),
            )
        )
    if variable == DEFAULT_DOCUMENT_VAR:
        # Only the printed record has a model we can resolve; a loop
        # variable would need the arch to be evaluated first.
        model_name = report_model(operation)
        if model_name:
            assert_field_path(operation, model_name, path)
    return expression


def assert_renamable(operation, node):
    """Refuse a rename on a node whose body is a record value, not a label."""
    if node.get("t-field") or node.get("t-esc"):
        raise AnchorError(
            operation.env._(
                "Node '%s' prints a record value, so it carries no static "
                "label to rename."
            )
            % (operation.anchor_name or "")
        )


def resolve_move_source(operation, tree, anchor_node):
    """Return the name of the node a move relocates, refusing a shaky source.

    The inheritance engine takes the first match and raises at render time
    when there is none, which would take the whole report down.
    """
    name = (_payload(operation).get("field_name") or "").strip()
    if not name:
        raise AnchorError(
            operation.env._("A move needs the name of the node to relocate.")
        )
    if not NAME_RE.match(name):
        raise AnchorError(operation.env._("'%s' is not a valid node name.") % name)
    nodes = tree.xpath(f"//*[@name={xpath_quote(name)}]")
    if not nodes:
        raise AnchorError(
            operation.env._(
                "Template '%(view)s' has no node named '%(name)s', so there "
                "is nothing to move.",
                view=operation.view_id.display_name,
                name=name,
            )
        )
    if len(nodes) > 1:
        raise AnchorError(
            operation.env._(
                "Node '%(name)s' appears %(count)s times in '%(view)s', so "
                "the node to move is ambiguous.",
                name=name,
                count=len(nodes),
                view=operation.view_id.display_name,
            )
        )
    if nodes[0] is anchor_node:
        raise AnchorError(
            operation.env._("Node '%s' cannot be moved next to itself.") % name
        )
    return name


def report_position(operation):
    position = operation.position or "after"
    if position not in REPORT_POSITIONS:
        raise AnchorError(
            operation.env._("Position '%s' is not valid on a report template.")
            % position
        )
    return position


def _hide_arch(operation, _tree, _node):
    """Drop the node from the render instead of styling it away."""
    return report_inherit_arch(operation, _attribute_xml("t-if", "False"), "attributes")


def _rename_arch(operation, _tree, node):
    assert_renamable(operation, node)
    string = (_payload(operation).get("string") or "").strip()
    if not string:
        raise AnchorError(operation.env._("A new label is required."))
    # t-out replaces the body of the node, so the label changes without
    # the inherit having to restate the markup around it.
    return report_inherit_arch(
        operation, _attribute_xml("t-out", repr(string)), "attributes"
    )


def _place_arch(operation, tree, node):
    expression = validated_report_expression(operation, tree)
    position = report_position(operation)
    inner = f'<span t-field="{_xml_attr(expression)}"/>'
    tag = node.tag if isinstance(node.tag, str) else ""
    if tag in CELL_TAGS and position in ("before", "after"):
        inner = f"<{tag}>{inner}</{tag}>"
    return report_inherit_arch(operation, inner, position)


def _move_arch(operation, tree, node):
    name = resolve_move_source(operation, tree, node)
    position = report_position(operation)
    expr = f"//*[@name={xpath_quote(name)}]"
    inner = f'<xpath expr="{_xml_attr(expr)}" position="move"/>'
    return report_inherit_arch(operation, inner, position)


REPORT_ARCH_BUILDERS = {
    "hide_field": _hide_arch,
    "set_string": _rename_arch,
    "place_field": _place_arch,
    "move_field": _move_arch,
}


def upsert_report_view(operation, arch):
    """Create or rewrite the qweb inherit this operation owns.

    A qweb view needs a key, and ``create`` would otherwise mint a random
    one every time the exported addon is installed.
    """
    values = {
        "name": f"Customization {operation.bundle_id.code} operation {operation.id}",
        "type": REPORT_VIEW_TYPE,
        "model": False,
        "key": f"{operation.bundle_id.code}.{view_xmlid_name(operation)}",
        "inherit_id": operation.view_id.id,
        "mode": "extension",
        "arch": arch,
        "active": True,
        "priority": 100 + (operation.sequence or 0),
    }
    view = operation.generated_view_id
    if view:
        view.write(values)
        return view
    view = operation.env["ir.ui.view"].create(values)
    operation.generated_view_id = view
    return view


def compile_report_operation(operation):
    """Compile one report operation into a qweb inherit."""
    tree = report_arch(operation)
    node = resolve_report_anchor(operation, tree)
    build = REPORT_ARCH_BUILDERS[operation.type]
    upsert_report_view(operation, build(operation, tree, node))


def health_check_report_operation(operation):
    """Re-resolve the anchor and the payload without writing.

    :returns: (ok, reason)
    """
    try:
        tree = report_arch(operation)
        node = resolve_report_anchor(operation, tree)
        if operation.type == "set_string":
            assert_renamable(operation, node)
        elif operation.type == "place_field":
            validated_report_expression(operation, tree)
        elif operation.type == "move_field":
            resolve_move_source(operation, tree, node)
    except AnchorError as err:
        return False, err.reason
    except (ValueError, etree.ParseError) as err:
        return False, str(err)
    return True, ""
