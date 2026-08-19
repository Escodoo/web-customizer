# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import io
import json
import re
import zipfile
from xml.sax.saxutils import escape

from lxml import etree

from odoo.exceptions import UserError

from .compiler import (
    MENU_TYPES,
    SET_DEFAULT_TYPE,
    default_xmlid_name,
    field_xmlid_name,
    menu_xmlid_name,
    view_xmlid_name,
)

XML_HEADER = """<?xml version="1.0" encoding="utf-8" ?>
<!-- Copyright 2026 Escodoo
     License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl). -->
"""


def export_bundle_zip(bundle):
    """Return ``(zip_bytes, filename)`` for an installable addon.

    Only applied operations are exported. The zip is the source of truth for
    git; it does not depend on web_customizer at runtime.
    """
    bundle.ensure_one()
    files = export_bundle_files(bundle)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(f"{bundle.code}/{path}", content)
    return buf.getvalue(), f"{bundle.code}.zip"


def export_bundle_files(bundle):
    """Return an ordered mapping of addon-relative paths to file contents."""
    bundle.ensure_one()
    operations = bundle.operation_ids.filtered(lambda o: o.state == "applied").sorted(
        "sequence"
    )
    if not operations:
        raise UserError(
            bundle.env._("There are no applied operations to export in bundle '%s'.")
            % bundle.code
        )

    fields = operations.mapped("generated_field_id").exists()
    views = operations.mapped("generated_view_id").filtered("active").exists()
    menu_ops = operations.filtered(lambda o: o.type in MENU_TYPES and o.menu_id)
    default_ops = operations.filtered(
        lambda o: o.type == SET_DEFAULT_TYPE and o.generated_default_id
    )
    if not fields and not views and not menu_ops and not default_ops:
        raise UserError(
            bundle.env._(
                "Applied operations in bundle '%s' did not generate "
                "fields, views, menus or defaults."
            )
            % bundle.code
        )

    files = {
        "__init__.py": "# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).\n",
    }
    data_files = []
    depends = {"base"}

    if fields:
        files["data/ir_model_fields.xml"] = _fields_xml(fields)
        data_files.append("data/ir_model_fields.xml")
        depends.update(_model_modules(fields.mapped("model_id")))

    if views:
        files["views/inherited_views.xml"] = _views_xml(views, operations)
        data_files.append("views/inherited_views.xml")
        depends.update(_view_modules(views))
        depends.update(_button_action_modules(operations))

    if menu_ops:
        files["data/ir_ui_menu.xml"] = _menus_xml(menu_ops)
        data_files.append("data/ir_ui_menu.xml")
        depends.update(_menu_modules(menu_ops))

    if default_ops:
        files["data/ir_default.xml"] = _defaults_xml(default_ops)
        data_files.append("data/ir_default.xml")
        depends.update(_default_modules(default_ops))

    files["__manifest__.py"] = _manifest(bundle, sorted(depends), data_files)
    return files


def _manifest(bundle, depends, data_files):
    depends_py = ", ".join(repr(name) for name in depends)
    data_py = ", ".join(repr(name) for name in data_files)
    return (
        "# Copyright 2026 Escodoo\n"
        "# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).\n"
        "\n"
        "{\n"
        f"    'name': {bundle.name!r},\n"
        "    'version': '18.0.1.0.0',\n"
        f"    'summary': {('Exported customizations: ' + bundle.name)!r},\n"
        "    'category': 'Customization',\n"
        "    'license': 'AGPL-3',\n"
        "    'author': 'Escodoo',\n"
        "    'depends': ["
        f"{depends_py}],\n"
        "    'data': ["
        f"{data_py}],\n"
        "    'installable': True,\n"
        "    'application': False,\n"
        "}\n"
    )


def _fields_xml(fields):
    records = "\n".join(_field_record(field) for field in fields.sorted("id"))
    return f"{XML_HEADER}<odoo>\n{records}\n</odoo>\n"


def _field_record(field):
    xmlid = _field_xmlid(field)
    model_xmlid = _record_xmlid(
        field.model_id,
        field.env._("Model %s has no XML ID; it cannot be exported.") % field.model,
    )
    lines = [
        f'    <record id="{xmlid}" model="ir.model.fields">',
        f'        <field name="name">{escape(field.name)}</field>',
        f'        <field name="model_id" ref="{model_xmlid}"/>',
        f'        <field name="ttype">{escape(field.ttype)}</field>',
        '        <field name="state">manual</field>',
        '        <field name="field_description">'
        f"{escape(field.field_description or field.name)}</field>",
    ]
    if field.help:
        lines.append(f'        <field name="help">{escape(field.help)}</field>')
    if field.required:
        lines.append('        <field name="required" eval="True"/>')
    if field.relation:
        lines.append(f'        <field name="relation">{escape(field.relation)}</field>')
    if field.related:
        lines.append(f'        <field name="related">{escape(field.related)}</field>')
        lines.append('        <field name="readonly" eval="True"/>')
        if field.store:
            lines.append('        <field name="store" eval="True"/>')
    if field.ttype == "monetary" and field.currency_field:
        lines.append(
            '        <field name="currency_field">'
            f"{escape(field.currency_field)}</field>"
        )
    lines.append("    </record>")
    if field.ttype == "selection":
        lines.extend(_selection_records(field, xmlid))
    return "\n".join(lines)


def _selection_records(field, field_xmlid):
    lines = []
    for index, option in enumerate(field.selection_ids.sorted("sequence")):
        sel_id = f"{field_xmlid}_sel_{re.sub('[^a-zA-Z0-9_]', '_', option.value)}"
        lines.append(f'    <record id="{sel_id}" model="ir.model.fields.selection">')
        lines.append(f'        <field name="field_id" ref="{field_xmlid}"/>')
        lines.append(f'        <field name="value">{escape(option.value)}</field>')
        lines.append(f'        <field name="name">{escape(option.name)}</field>')
        lines.append(f'        <field name="sequence">{index}</field>')
        lines.append("    </record>")
    return lines


def _views_xml(views, operations):
    records = []
    seen = set()
    for operation in operations:
        view = operation.generated_view_id
        if not view or not view.active or view.id in seen:
            continue
        seen.add(view.id)
        records.append(_view_record(view, operation))
    return f"{XML_HEADER}<odoo>\n" + "\n".join(records) + "\n</odoo>\n"


def _view_record(view, operation):
    xmlid = view_xmlid_name(operation)
    inherit_xmlid = _record_xmlid(
        view.inherit_id,
        view.env._("Target view '%s' has no XML ID. Export needs a stable inherit_id.")
        % (view.inherit_id.display_name if view.inherit_id else view.display_name),
    )
    arch = _pretty_arch(view)
    view_type = operation.view_type or view.type
    return (
        f'    <record id="{xmlid}" model="ir.ui.view">\n'
        f'        <field name="name">{escape(view.name)}</field>\n'
        f'        <field name="model">{escape(view.model)}</field>\n'
        f'        <field name="type">{escape(view_type)}</field>\n'
        f'        <field name="inherit_id" ref="{inherit_xmlid}"/>\n'
        '        <field name="mode">extension</field>\n'
        f'        <field name="priority">{int(view.priority or 16)}</field>\n'
        '        <field name="arch" type="xml">\n'
        f"{_indent(arch, '            ')}\n"
        "        </field>\n"
        "    </record>"
    )


def _pretty_arch(view):
    arch = view.arch_db or view.arch
    if not arch:
        raise UserError(
            view.env._("Generated view '%s' has an empty arch.") % view.display_name
        )
    if isinstance(arch, bytes):
        arch = arch.decode()
    tree = etree.fromstring(arch.encode() if isinstance(arch, str) else arch)
    pretty = etree.tostring(tree, pretty_print=True, encoding=str)
    return pretty.strip()


def _indent(text, prefix):
    return "\n".join(prefix + line if line else line for line in text.splitlines())


def _field_xmlid(field):
    return field_xmlid_name(field)


def _record_xmlid(record, missing_message):
    if not record:
        raise UserError(missing_message)
    xmlid = record.get_external_id().get(record.id)
    if not xmlid:
        raise UserError(missing_message)
    return xmlid


def _model_modules(models):
    modules = set()
    for model in models:
        for name in (model.modules or "").split(","):
            name = name.strip()
            if name:
                modules.add(name)
    return modules


def _view_modules(views):
    modules = set()
    for view in views:
        if not view.inherit_id:
            continue
        xmlid = view.inherit_id.get_external_id().get(view.inherit_id.id)
        if xmlid and "." in xmlid:
            modules.add(xmlid.split(".", 1)[0])
    return modules


def _add_xmlid_module(modules, xmlid):
    if xmlid and "." in xmlid:
        modules.add(xmlid.split(".", 1)[0])


def _button_action_modules(operations):
    """Modules owning the actions the exported buttons call by XML ID."""
    modules = set()
    for operation in operations:
        if operation.type != "add_button":
            continue
        _add_xmlid_module(modules, (operation.payload or {}).get("action_xmlid"))
    return modules


def _menu_modules(operations):
    modules = set()
    for operation in operations:
        if operation.type == "add_menu":
            payload = operation.payload or {}
            _add_xmlid_module(modules, payload.get("action_xmlid"))
            parent = (
                operation.menu_id
                if operation.position == "inside"
                else operation.menu_id.parent_id
            )
            if parent:
                parent_xmlid = parent.get_external_id().get(parent.id)
                _add_xmlid_module(modules, parent_xmlid)
            continue
        if operation.type == "move_menu":
            payload = operation.payload or {}
            xmlid = payload.get("xmlid")
            if not xmlid and operation.menu_id:
                xmlid = operation.menu_id.get_external_id().get(operation.menu_id.id)
            _add_xmlid_module(modules, xmlid)
            _add_xmlid_module(modules, payload.get("parent_xmlid"))
            continue
        xmlid = (operation.payload or {}).get("xmlid")
        if not xmlid and operation.menu_id:
            xmlid = operation.menu_id.get_external_id().get(operation.menu_id.id)
        _add_xmlid_module(modules, xmlid)
    return modules


def _menus_xml(operations):
    records = "\n".join(_menu_record(operation) for operation in operations)
    return f"{XML_HEADER}<odoo>\n{records}\n</odoo>\n"


def _menu_record(operation):
    if operation.type == "add_menu":
        return _add_menu_record(operation)
    menu = operation.menu_id
    xmlid = _record_xmlid(
        menu,
        operation.env._("Menu '%s' has no XML ID and cannot be exported.")
        % menu.display_name,
    )
    payload = operation.payload or {}
    lines = [f'    <record id="{escape(xmlid)}" model="ir.ui.menu">']
    if operation.type == "hide_menu":
        lines.append('        <field name="active" eval="False"/>')
    elif operation.type == "set_menu_string":
        name = payload.get("string") or menu.name or ""
        lines.append(f'        <field name="name">{escape(name)}</field>')
    elif operation.type == "set_menu_groups":
        refs = ", ".join(
            f"ref('{group_xmlid.strip()}')"
            for group_xmlid in (payload.get("groups") or "").split(",")
            if group_xmlid.strip()
        )
        if not refs:
            raise UserError(
                operation.env._("Menu groups operation '%s' has no group XML IDs.")
                % operation.name
            )
        lines.append(f'        <field name="groups_id" eval="[(6, 0, [{refs}])]"/>')
    elif operation.type == "move_menu":
        parent_xmlid = (payload.get("parent_xmlid") or "").strip()
        if parent_xmlid:
            lines.append(
                f'        <field name="parent_id" ref="{escape(parent_xmlid)}"/>'
            )
        else:
            lines.append('        <field name="parent_id" eval="False"/>')
        sequence = int(menu.sequence or 10)
        lines.append(f'        <field name="sequence" eval="{sequence}"/>')
    lines.append("    </record>")
    return "\n".join(lines)


def _add_menu_record(operation):
    """Export a newly created menu as a record in the client addon."""
    payload = operation.payload or {}
    record_id = menu_xmlid_name(operation)
    string = payload.get("string") or ""
    if operation.generated_menu_id:
        string = string or operation.generated_menu_id.name or ""
    action_xmlid = (payload.get("action_xmlid") or "").strip()
    if not action_xmlid:
        raise UserError(
            operation.env._("Menu '%s' has no window action XML ID.")
            % operation.display_name
        )
    position = operation.position or "after"
    anchor = operation.menu_id
    parent = anchor if position == "inside" else anchor.parent_id
    lines = [f'    <record id="{escape(record_id)}" model="ir.ui.menu">']
    lines.append(f'        <field name="name">{escape(string)}</field>')
    if parent:
        parent_xmlid = _record_xmlid(
            parent,
            operation.env._("Parent menu '%s' has no XML ID and cannot be exported.")
            % parent.display_name,
        )
        lines.append(f'        <field name="parent_id" ref="{escape(parent_xmlid)}"/>')
    lines.append(f'        <field name="action" ref="{escape(action_xmlid)}"/>')
    if operation.generated_menu_id:
        sequence = int(operation.generated_menu_id.sequence or 10)
        lines.append(f'        <field name="sequence" eval="{sequence}"/>')
    lines.append("    </record>")
    return "\n".join(lines)


def _defaults_xml(operations):
    records = "\n".join(_default_record(operation) for operation in operations)
    return f"{XML_HEADER}<odoo>\n{records}\n</odoo>\n"


def _default_record(operation):
    default = operation.generated_default_id
    field = default.field_id
    field_ref = _default_field_ref(field, operation.bundle_id.code)
    xmlid = default_xmlid_name(operation)
    payload = operation.payload or {}
    value_xmlid = (payload.get("value_xmlid") or "").strip()
    lines = [
        f'    <record id="{escape(xmlid)}" model="ir.default">',
        f'        <field name="field_id" ref="{escape(field_ref)}"/>',
    ]
    if value_xmlid:
        lines.append(f'        <field name="json_value" eval="ref({value_xmlid!r})"/>')
    else:
        json_value = default.json_value
        if json_value is False:
            json_value = json.dumps(payload.get("value"), ensure_ascii=False)
        lines.append(f'        <field name="json_value">{escape(json_value)}</field>')
    lines.append("    </record>")
    return "\n".join(lines)


def _default_field_ref(field, bundle_code):
    """Return a field XML ID, local when the field belongs to this addon."""
    xmlid = field.get_external_id().get(field.id)
    if xmlid:
        module, name = xmlid.split(".", 1) if "." in xmlid else ("", xmlid)
        if module == bundle_code:
            return name
        return xmlid
    if (field.name or "").startswith("x_cust_"):
        return field_xmlid_name(field)
    raise UserError(
        field.env._("Field '%s' has no XML ID and cannot be exported.")
        % f"{field.model}.{field.name}"
    )


def _default_modules(operations):
    """Modules owning the defaulted fields and many2one value XML IDs."""
    modules = set()
    for operation in operations:
        default = operation.generated_default_id
        if default and default.field_id:
            xmlid = default.field_id.get_external_id().get(default.field_id.id)
            _add_xmlid_module(modules, xmlid)
        _add_xmlid_module(modules, (operation.payload or {}).get("value_xmlid"))
        if operation.model_id:
            modules.update(_model_modules(operation.model_id))
    modules.discard(operations[:1].bundle_id.code)
    return modules
