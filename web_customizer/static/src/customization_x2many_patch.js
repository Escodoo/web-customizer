import {SUBVIEW_MODES, useCustomizationService} from "./customization_service";
import {onWillUnmount, useSubEnv} from "@odoo/owl";
import {X2ManyField} from "@web/views/fields/x2many/x2many_field";
import {X2ManyFieldDialog} from "@web/views/fields/relational_utils";
import {patch} from "@web/core/utils/patch";

// A table inside a form has no view of its own on the client: it renders
// with the parent's config, so a column click cannot tell which model it
// belongs to. Publishing the holder for the subtree gives the renderers
// below the scope the ledger needs to anchor on. The line form opens in
// a dialog, outside that subtree, so the same holder is also registered
// on the service for the dialog to pick up.
patch(X2ManyField.prototype, {
    setup() {
        super.setup(...arguments);
        const isTable = SUBVIEW_MODES.includes(this.props.viewMode);
        useSubEnv(
            isTable
                ? {
                      customizationSubview: {
                          name: this.props.name,
                          viewMode: this.props.viewMode,
                      },
                  }
                : {}
        );
        const customization = useCustomizationService();
        const unregister = isTable
            ? customization.registerSubview({
                  name: this.props.name,
                  viewMode: this.props.viewMode,
              })
            : null;
        onWillUnmount(() => unregister?.());
    },
});

// The dialog that edits a line is mounted on the overlay, so it never
// sees the useSubEnv of the table. The holder still registered on the
// service is the x2many that opened it; remap to form so a field click
// there compiles against the written <form>, not the list.
patch(X2ManyFieldDialog.prototype, {
    setup() {
        super.setup(...arguments);
        const customization = useCustomizationService();
        const holder = customization.currentSubview();
        useSubEnv(
            holder
                ? {
                      customizationSubview: {
                          name: holder.name,
                          viewMode: "form",
                      },
                  }
                : {}
        );
    },
});
