import {SUBVIEW_MODES} from "./customization_service";
import {X2ManyField} from "@web/views/fields/x2many/x2many_field";
import {patch} from "@web/core/utils/patch";
import {useSubEnv} from "@odoo/owl";

// A table inside a form has no view of its own on the client: it renders
// with the parent's config, so a column click cannot tell which model it
// belongs to. Publishing the holder for the subtree gives the renderers
// below the scope the ledger needs to anchor on.
patch(X2ManyField.prototype, {
    setup() {
        super.setup(...arguments);
        if (SUBVIEW_MODES.includes(this.props.viewMode)) {
            useSubEnv({
                customizationSubview: {
                    name: this.props.name,
                    viewMode: this.props.viewMode,
                },
            });
        }
    },
});
