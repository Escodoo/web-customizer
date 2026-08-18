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
  set inline editing, a default order or row colours.
