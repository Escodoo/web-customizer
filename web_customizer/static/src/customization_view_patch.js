import {onMounted, onWillUnmount} from "@odoo/owl";
import {View} from "@web/views/view";
import {patch} from "@web/core/utils/patch";
import {useCustomizationService} from "./customization_service";

patch(View.prototype, {
    setup() {
        super.setup(...arguments);
        const customization = useCustomizationService();
        let unregister = null;
        // The view id only lands in env.config once the arch is loaded, which
        // happens after setup, so the view can only be published on mount.
        onMounted(() => {
            const config = this.env.config || {};
            if (!config.viewId || !config.viewType) {
                return;
            }
            unregister = customization.registerView({
                model: this.props.resModel,
                viewId: config.viewId,
                viewType: config.viewType,
            });
        });
        onWillUnmount(() => {
            if (unregister) {
                unregister();
                unregister = null;
            }
        });
    },
});
