import "./customization_banner";
import "./customization_field_patch";
import "./customization_kanban_patch";
import "./customization_list_patch";
import "./customization_navbar_patch";
import "./customization_search_patch";
import "./customization_service";
import {Component, onWillStart, useState} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {user} from "@web/core/user";
import {useService} from "@web/core/utils/hooks";

export class CustomizationSystray extends Component {
    static template = "web_customizer.Systray";
    static props = {};

    setup() {
        this.customization = useService("web_customizer");
        this.state = useState(this.customization.state);
        this.isManager = false;
        onWillStart(async () => {
            this.isManager = await user.hasGroup(
                "web_customizer.group_customization_manager"
            );
        });
    }

    get title() {
        return this.state.enabled
            ? _t("Exit customization mode")
            : _t("Customize this view");
    }

    get onLabel() {
        return _t("On");
    }

    toggle() {
        this.customization.toggle();
    }
}

registry
    .category("systray")
    .add("web_customizer", {Component: CustomizationSystray}, {sequence: 16});
