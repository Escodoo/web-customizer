1. Go to **Settings → Technical → Customization → Bundles** (debug mode).
   Install creates an empty **Sandbox** bundle (`code` ``sandbox``) so the
   wand can be tried immediately. Create a real bundle (`client_acme`)
   before shipping; rename ``code`` before the first Apply, or
   **Re-apply** after renaming so XML IDs follow the new code.
2. On any form, list, kanban or search view, click the magic-wand icon in the
   systray (customization managers). Fields, page tabs, group titles and
   named buttons are outlined on forms; list column headers, kanban card
   fields and buttons, kanban header buttons, column progressbars, and
   search fields are outlined on those views.
   Navbar menus
   (apps and sections with an XML ID) are also outlined. Click one to add a
   **new** field after it (or **inside** a page or group), **place an
   existing field**,
   add a **page** or **group**, hide it, change its label, set a widget,
   restrict it to groups (search by name), or set modifiers (invisible /
   readonly / required). Click a **menu** to hide it, rename it, restrict
   it to groups, add a **sibling menu** after it, add a **submenu**, or
   **move** it after another menu or as a submenu. New menus need a
   window action that already has an XML ID. The destination of a move
   must also have an XML ID. The clicked
   node is the semantic anchor. **Move an existing field** relocates a
   field the view already declares instead of adding a second copy of it,
   so the field keeps its widget, label and modifiers; the field must
   appear exactly once in the view. To
   mirror another field, fill **Related path** (for example
   `parent_id.email`) instead of a field type. Pages and groups without
   a technical ``name`` are anchored by their title (stored on the
   operation; the generated inherit xpath uses a unique field inside the
   node or the node position, because Odoo forbids ``@string``
   selectors). If the same name appears more than once, choose the node
   in the dialog. A new page after a field is wrapped in a notebook; a
   new page after an existing tab is a sibling.
3. A table inside a form (order lines, bank accounts, any x2many written
   with its own ``<list>`` or ``<kanban>``) is customized in place: its
   column headers, or its card fields and buttons, are outlined too. A
   node there belongs to the **related** model, so the dialog adds or
   places fields there, while the inherit is written on the form that
   declares the table. The same field name on the record and in the
   table are separate anchors and never conflict. Click the x2many field
   itself and choose **Set options of this table** to make a list of
   lines inline editable, drop its Add a line, or set its default order.
   If the table is not written in the form but taken from another view,
   the dialog says so and names the model whose list view to open
   instead.
4. Some settings belong to the view itself rather than to a node, so they
   have no outline to click. On a form, list or kanban, use **View
   options** in the customization banner. There you can stop users from
   creating, editing, deleting or duplicating records; a list can also
   turn inline editing on or off, set a default order and colour its rows
   with a condition. Options left on *Leave as is* are not written, so a
   bundle only owns what it declares. An option set to an empty value
   drops it from the view, which is how an inline-editable list is turned
   back into a read-only one. Only options the arch parser of that view
   type reads are accepted: decorations exist on lists only, and pivot,
   graph and search views have none.
5. Or add operations from the bundle form. Fill the payload fields for the
   selected type. The **Raw JSON** tab shows the stored intent. View
   options are written there as one `name=value` per line.
6. Click **Apply** to compile fields and inherited views.
7. After an Odoo upgrade (`-u`), a health check runs automatically and
   re-resolves anchors. You can still click **Health Check** on the bundle.
   Missing anchors are marked broken (inherit deactivated) and show
   `broken_reason`. If the anchor comes back, Health Check rewrites the
   inherit — no extra **Re-apply** click. **Re-apply** still recompiles
   every live operation. Changing an `add_field` type or relation
   recreates the field and deletes values already stored in that
   column (label, help and required update in place).
8. When the bundle is applied, click **Export Addon**. In the dialog, click
   **Download ZIP** and put that module in git; it does not depend on this
   module at runtime. Compiled fields, views and menus store their XML IDs
   under the bundle ``code`` (the future addon name). Uninstalling
   ``web_customizer`` leaves those records in the database. Unlink a bundle or
   operation to undo a customization. Hide, rename, groups and move write
   the standard ``ir.ui.menu`` record; only one live operation of each
   type may target the same menu, so two bundles cannot overwrite each
   other. Unlink restores that snapshot. Hide, label, widget, groups and
   modifier operations on a view node are exclusive the same way: only
   one live operation of each type may target the same anchor, so two
   bundles cannot compile two inherits for the same hide. Placing or
   moving the same field twice on the same view is refused the same way,
   and so is a second live set of view options on the same root.

## Single-company pilot

Use one company. Cover the surfaces below, then ship the ZIP — do not
leave this module as the production runtime.

1. **Form** — add, place or move a field; hide or rename a page, group or
   button.
2. **List** — add, hide, relabel a column, or make it optional so users
   can turn it on from the column picker.
3. **Embedded table** — on a form with order lines or bank accounts,
   click a column header and add or relabel a column of the related
   model, then click the field itself and make the table inline
   editable.
4. **Search** — add, hide or relabel a search chip, or add a filter with a
   domain or a group by.
5. **Kanban** — hide a card field, a header button or the column progressbar.
6. **Pivot** — click a measure header to relabel, hide or add a measure.
7. **Menus** — hide, rename or move one navbar item that has an XML ID.
8. **View options** — from the banner, drop the Create button on one list
   and colour its rows by a condition.
9. Click **Apply**. Broken operations show `broken_reason`; fix the
   anchor and run **Health Check** (or **Re-apply**).
10. Click **Export Addon** → **Download ZIP**.
11. Install that module on staging (`-i <bundle.code>`). Do not install
   `web_customizer` there unless the wand is still needed.

Graph operations are written from the operation form rather than in
place. Calendar and gantt stay out of this pilot.

Generated field names always start with `x_cust_` and cannot contain `__`.
Selection fields take one option per line as `value:Label`. Monetary
fields need `currency_id` or `x_currency_id` on the model, or a
currency field name in the payload.
