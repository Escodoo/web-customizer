## 18.0.1.0.0

First public Beta.

- Ledger of semantic operations compiled to ``x_cust_*`` fields, inherited
  views and writes on standard ``ir.ui.menu`` records.
- Systray customization mode for form, list, kanban, search and navbar
  menus.
- Health check on module update; generated XML IDs belong to the bundle
  ``code``.
- Exclusive live writes per menu type, view-anchor attribute type and
  place of the same field on one view.
- Export as a standalone addon ZIP that does not depend on this module.
- Kanban header buttons and column progressbars are semantic anchors.
- Pivot and graph fields compile with their aggregate role (measure, row,
  col or grouping); pivot measures are clickable in customization mode.
- A list column can be made optional, so it moves to the column picker
  instead of being pinned or hidden outright.
- Search filters and groupings are semantic anchors, and a filter can be
  added with a validated domain or a group by.
- A field already declared in a view can be moved to another spot, keeping
  the attributes the base view gave it.
- The view root is a semantic anchor of its own, so a form, list or kanban
  can drop its Create, Edit, Delete or Duplicate buttons, and a list can
  set inline editing, multi-edit, a default order or row colours. A
  kanban can drop quick-create and the create, delete or rename of its
  columns.
- Columns and cards of a table written inside a form are semantic anchors
  on the related model, so order lines and the like are customized in
  place, options of the table included. The form that opens a line is
  an anchor of the same field when it is written next to the list.
- A button calling an action that already exists can be added to a form, a
  list or a kanban; the arch keeps the XML ID, so the export depends on
  the module owning the action.
- A field can be given a global default (``ir.default``). The value is
  validated, related fields are refused, and the export writes
  ``data/ir_default.xml``. Unlink restores a native default the bundle
  overwrote.
- Graph fields are listed from the banner, so a measure or grouping can
  be customized in place even though the chart draws on a canvas.
- Compiling and health-checking one operation are extension points, and
  the export writes a view without a model and with a key when the
  target has none, so a sibling addon can own another view type.
  ``web_customizer_report`` uses both for QWeb reports.
