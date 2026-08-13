1. Go to **Settings → Technical → Customization → Bundles** (debug mode).
2. Create a bundle (`code` is the future addon technical name, for example
   `client_acme`).
3. On any form, list or search view, click the magic-wand icon in the
   systray (customization managers). Fields, named page tabs and named
   buttons are outlined on forms; list column headers and search fields
   are outlined on those views. Click one to add a **new** field after
   it (or **inside** a page), **place an existing field**, hide it,
   change its label, set a widget, restrict it to groups, or set
   modifiers (invisible / readonly / required). The clicked node is the
   semantic anchor. To mirror another field, fill **Related path** (for
   example `parent_id.email`) instead of a field type. Pages and buttons
   need a technical ``name`` in the view. If the same name appears more
   than once, choose the node in the dialog.
4. Or add operations from the bundle form. Fill the payload fields for the
   selected type. The **Raw JSON** tab shows the stored intent.
5. Click **Apply** to compile fields and inherited views.
6. After an Odoo upgrade, click **Health Check**. Broken operations keep their
   generated field and show `broken_reason`. **Re-apply** retries them.
7. When the bundle is applied, click **Export Addon**. In the dialog, click
   **Download ZIP** and put that module in git; it does not depend on this
   ledger at runtime.

Generated field names always start with `x_esc_` and cannot contain `__`.
