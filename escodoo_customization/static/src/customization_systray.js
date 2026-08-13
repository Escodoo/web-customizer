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
    static template = "escodoo_customization.Systray";
    static props = {};

    setup() {
        this.customization = useService("escodoo_customization");
        this.state = useState(this.customization.state);
        this.isManager = false;
        onWillStart(async () => {
            this.isManager = await user.hasGroup(
                "escodoo_customization.group_customization_manager"
            );
        });
    }

    get title() {
        return this.state.enabled
            ? _t("Exit customization mode")
            : _t("Customize this view");
    }

    toggle() {
        this.customization.toggle();
    }
}

registry
    .category("systray")
    .add("escodoo_customization", {Component: CustomizationSystray}, {sequence: 16});
