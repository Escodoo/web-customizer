import {Component} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {useCustomizationService} from "./customization_service";

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

    exit() {
        this.customization.toggle();
    }
}

registry.category("main_components").add("web_customizer.Banner", {
    Component: CustomizationBanner,
});
