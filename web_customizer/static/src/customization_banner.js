import {ROOT_OPTION_VIEW_TYPES, useCustomizationService} from "./customization_service";
import {Component} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";

export class CustomizationBanner extends Component {
    static template = "web_customizer.Banner";
    static props = {};

    setup() {
        this.customization = useCustomizationService();
    }

    get title() {
        return _t("Customization mode");
    }

    get hint() {
        return _t("Click an outlined item");
    }

    get exitLabel() {
        return _t("Exit");
    }

    get viewOptionsLabel() {
        return _t("View options");
    }

    get rootTarget() {
        const view = this.customization.state.view;
        if (!view || !ROOT_OPTION_VIEW_TYPES.includes(view.viewType)) {
            return null;
        }
        return view;
    }

    openViewOptions() {
        const view = this.rootTarget;
        if (!view) {
            return;
        }
        this.customization.openFieldDialog({
            fieldName: "",
            fieldLabel: view.viewType,
            model: view.model,
            viewId: view.viewId,
            viewType: view.viewType,
            anchorKind: "view",
        });
    }

    exit() {
        this.customization.toggle();
    }
}

registry.category("main_components").add("web_customizer.Banner", {
    Component: CustomizationBanner,
});
