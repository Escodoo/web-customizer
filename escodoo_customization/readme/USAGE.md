1. Go to **Settings → Technical → Customization → Bundles** (debug mode).
2. Create a bundle (`code` is the future addon technical name, for example
   `client_acme`).
3. On any form, click the magic-wand icon in the systray (customization
   managers). Fields are outlined; click one to add a **new** field after
   it, **place an existing field** after it, hide it, or change its label.
   The clicked field is the semantic anchor. To mirror another field, fill
   **Related path** (for example `parent_id.email`) instead of a field type.
4. Or add operations from the bundle form. Fill the payload fields for the
   selected type. The **Raw JSON** tab shows the stored intent.
5. Click **Apply** to compile fields and inherited views.
6. After an Odoo upgrade, click **Health Check**. Broken operations keep their
   generated field and show `broken_reason`. **Re-apply** retries them.
7. When the bundle is applied, click **Export Addon**. In the dialog, click
   **Download ZIP** and put that module in git; it does not depend on this
   ledger at runtime.

Generated field names always start with `x_esc_` and cannot contain `__`.
