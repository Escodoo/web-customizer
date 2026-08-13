1. Go to **Settings → Technical → Customization → Bundles** (debug mode).
2. Create a bundle (`code` is the future addon technical name, for example
   `client_acme`).
3. Add operations (field, placement, modifiers). Fill the payload fields for
   the selected type (label, technical name, field to place, …). The **Raw
   JSON** tab shows the stored intent. Anchors use a field name on the target
   view, not a numeric XPath.
4. Click **Apply** to compile fields and inherited views.
5. After an Odoo upgrade, click **Health Check**. Broken operations keep their
   generated field and show `broken_reason`. **Re-apply** retries them.
6. When the bundle is applied, click **Export Addon**. In the dialog, click
   **Download ZIP** and put that module in git; it does not depend on this
   ledger at runtime.

Generated field names always start with `x_esc_` and cannot contain `__`.
