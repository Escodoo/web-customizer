import {ROOT_OPTION_VIEW_TYPES, useCustomizationService} from "./customization_service";
import {Component} from "@odoo/owl";
import {GraphFieldsDialog} from "./customization_graph_dialog";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

export class CustomizationBanner extends Component {
    static template = "web_customizer.Banner";
    static props = {};

    setup() {
        this.customization = useCustomizationService();
        this.dialog = useService("dialog");
    }

    get title() {
        return _t("Customization mode");
    }

    get hint() {
        if (this.graphTarget) {
            return _t("Open Graph fields — the chart has no node to click");
        }
        return _t("Click an outlined item");
    }

    get exitLabel() {
        return _t("Exit");
    }

    get viewOptionsLabel() {
        return _t("View options");
    }

    get graphFieldsLabel() {
        return _t("Graph fields");
    }

    get rootTarget() {
        const view = this.customization.state.view;
        if (!view || !ROOT_OPTION_VIEW_TYPES.includes(view.viewType)) {
            return null;
        }
        return view;
    }

    get graphTarget() {
        const view = this.customization.state.view;
        if (!view || view.viewType !== "graph") {
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

    openGraphFields() {
        const view = this.graphTarget;
        if (!view) {
            return;
        }
        this.dialog.add(GraphFieldsDialog, {
            viewId: view.viewId,
            model: view.model,
            viewType: "graph",
        });
    }

    exit() {
        this.customization.toggle();
    }
}

registry.category("main_components").add("web_customizer.Banner", {
    Component: CustomizationBanner,
});
