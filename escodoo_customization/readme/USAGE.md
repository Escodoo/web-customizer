1. Go to **Settings → Technical → Customization → Bundles** (debug mode).
2. Create a bundle (`code` is the future addon technical name, for example
   `client_acme`).
3. On any form, list, kanban or search view, click the magic-wand icon in the
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
   node is the semantic anchor. To
   mirror another field, fill **Related path** (for example
   `parent_id.email`) instead of a field type. Pages and groups without
   a technical ``name`` are anchored by their title (stored on the
   operation; the generated inherit xpath uses a unique field inside the
   node or the node position, because Odoo forbids ``@string``
   selectors). If the same name appears more than once, choose the node
   in the dialog. A new page after a field is wrapped in a notebook; a
   new page after an existing tab is a sibling.
4. Or add operations from the bundle form. Fill the payload fields for the
   selected type. The **Raw JSON** tab shows the stored intent.
5. Click **Apply** to compile fields and inherited views.
6. After an Odoo upgrade (`-u`), a health check runs automatically and
   re-resolves anchors. You can still click **Health Check** on the bundle.
   Missing anchors are marked broken (inherit deactivated) and show
   `broken_reason`. If the anchor comes back, Health Check rewrites the
   inherit — no extra **Re-apply** click. **Re-apply** still recompiles
   every live operation. Changing an `add_field` type or relation
   recreates the field (label, help and required update in place).
7. When the bundle is applied, click **Export Addon**. In the dialog, click
   **Download ZIP** and put that module in git; it does not depend on this
   ledger at runtime. Compiled fields, views and menus store their XML IDs
   under the bundle ``code`` (the future addon name). Uninstalling this
   ledger leaves those records in the database. Unlink a bundle or
   operation to undo a customization. Hide, rename, groups and move write
   the standard ``ir.ui.menu`` record; only one live operation of each
   type may target the same menu, so two bundles cannot overwrite each
   other. Unlink restores that snapshot. Hide, label, widget, groups and
   modifier operations on a view node are exclusive the same way: only
   one live operation of each type may target the same anchor, so two
   bundles cannot compile two inherits for the same hide. Placing the
   same field twice on the same view is refused the same way.

Generated field names always start with `x_esc_` and cannot contain `__`.
Selection fields take one option per line as `value:Label`. Monetary
fields need `currency_id` or `x_currency_id` on the model, or a
currency field name in the payload.
