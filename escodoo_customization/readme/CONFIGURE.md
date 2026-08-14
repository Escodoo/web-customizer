Assign groups under **Settings → Users**:

* **Customization / User** — read the ledger (bundles and operations).
  Settings (`Administration / Settings`) implies this group.
* **Customization / Manager** — create and apply operations, use the
  systray wand, export an addon, and unlink a bundle. Apply, re-apply
  and health-check are refused in Python even if called over RPC.

The wand and the bundle header buttons already require Manager. The
backend methods enforce the same group so a Settings user without
Manager cannot compile or drop customizations.

Compiled fields, views and menus store XML IDs under the bundle
``code``. Uninstalling this module leaves those records; unlink a
bundle to remove them. Export the addon to git — the database is not
the source of truth.

``company_id`` on a bundle is only a filter tag. The compiled field,
view and menu records are global: they apply to every company. Use
one bundle per project, not one per company, unless you accept that
overlap.
