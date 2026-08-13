1. Go to **Settings → Technical → Customization → Bundles** (debug mode).
2. Create a bundle (`code` is the future addon technical name, for example
   `client_acme`).
3. On any form, list or search view, click the magic-wand icon in the
   systray (customization managers). Fields, page tabs, group titles and
   named buttons are outlined on forms; list column headers and search
   fields are outlined on those views. Click one to add a **new** field
   after it (or **inside** a page or group), **place an existing field**,
   add a **page** or **group**, hide it, change its label, set a widget,
   restrict it to groups (search by name), or set modifiers (invisible /
   readonly / required). The clicked node is the semantic anchor. To
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
6. After an Odoo upgrade, click **Health Check**. Broken operations keep their
   generated field and show `broken_reason`. **Re-apply** retries them.
7. When the bundle is applied, click **Export Addon**. In the dialog, click
   **Download ZIP** and put that module in git; it does not depend on this
   ledger at runtime.

Generated field names always start with `x_esc_` and cannot contain `__`.
Selection fields take one option per line as `value:Label`. Monetary
fields need `currency_id` or `x_currency_id` on the model, or a
currency field name in the payload.
