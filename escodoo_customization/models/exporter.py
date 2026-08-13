# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import io
import re
import zipfile
from xml.sax.saxutils import escape

from lxml import etree

from odoo import _
from odoo.exceptions import UserError

from .compiler import MENU_TYPES

XML_HEADER = """<?xml version="1.0" encoding="utf-8" ?>
<!-- Copyright 2026 Escodoo
     License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl). -->
"""


def export_bundle_zip(bundle):
    """Return ``(zip_bytes, filename)`` for an installable addon.

    Only applied operations are exported. The zip is the source of truth for
    git; it does not depend on escodoo_customization at runtime.
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
            _("There are no applied operations to export in bundle '%s'.") % bundle.code
        )

    fields = operations.mapped("generated_field_id").exists()
    views = operations.mapped("generated_view_id").filtered("active").exists()
    menu_ops = operations.filtered(lambda o: o.type in MENU_TYPES and o.menu_id)
    if not fields and not views and not menu_ops:
        raise UserError(
            _(
                "Applied operations in bundle '%s' did not generate "
                "fields, views or menus."
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

    if menu_ops:
        files["data/ir_ui_menu.xml"] = _menus_xml(menu_ops)
        data_files.append("data/ir_ui_menu.xml")
        depends.update(_menu_modules(menu_ops))

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
        _("Model %s has no XML ID; it cannot be exported.") % field.model,
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
    xmlid = f"view_operation_{operation.id}"
    inherit_xmlid = _record_xmlid(
        view.inherit_id,
        _("Target view '%s' has no XML ID. Export needs a stable inherit_id.")
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
        '        <field name="priority">99</field>\n'
        '        <field name="arch" type="xml">\n'
        f"{_indent(arch, '            ')}\n"
        "        </field>\n"
        "    </record>"
    )


def _pretty_arch(view):
    arch = view.arch_db or view.arch
    if not arch:
        raise UserError(_("Generated view '%s' has an empty arch.") % view.display_name)
    if isinstance(arch, bytes):
        arch = arch.decode()
    tree = etree.fromstring(arch.encode() if isinstance(arch, str) else arch)
    pretty = etree.tostring(tree, pretty_print=True, encoding=str)
    return pretty.strip()


def _indent(text, prefix):
    return "\n".join(prefix + line if line else line for line in text.splitlines())


def _field_xmlid(field):
    model_key = (field.model or "").replace(".", "_")
    return f"field_{model_key}_{field.name}"


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


def _menu_modules(operations):
    modules = set()
    for operation in operations:
        xmlid = (operation.payload or {}).get("xmlid")
        if not xmlid and operation.menu_id:
            xmlid = operation.menu_id.get_external_id().get(operation.menu_id.id)
        if xmlid and "." in xmlid:
            modules.add(xmlid.split(".", 1)[0])
    return modules


def _menus_xml(operations):
    records = "\n".join(_menu_record(operation) for operation in operations)
    return f"{XML_HEADER}<odoo>\n{records}\n</odoo>\n"


def _menu_record(operation):
    menu = operation.menu_id
    xmlid = _record_xmlid(
        menu,
        _("Menu '%s' has no XML ID and cannot be exported.") % menu.display_name,
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
                _("Menu groups operation '%s' has no group XML IDs.") % operation.name
            )
        lines.append(f'        <field name="groups_id" eval="[(6, 0, [{refs}])]"/>')
    lines.append("    </record>")
    return "\n".join(lines)
