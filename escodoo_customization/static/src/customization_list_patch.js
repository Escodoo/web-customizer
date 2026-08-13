import {isListRoot, openCustomizationFor} from "./customization_service";
import {useService} from "@web/core/utils/hooks";
import {patch} from "@web/core/utils/patch";
import {ListRenderer} from "@web/views/list/list_renderer";

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        this.customization = useService("escodoo_customization");
    },
    getColumnClass(column) {
        const names = super.getColumnClass(column);
        if (
            column.type === "field" &&
            column.name &&
            this.customization?.state.enabled &&
            isListRoot(this)
        ) {
            return `${names} o_esc_customization_target`.trim();
        }
        return names;
    },
    onClickSortColumn(column) {
        if (
            column?.type === "field" &&
            column.name &&
            openCustomizationFor(this, column.name, null, {
                viewType: "list",
                fieldLabel: column.label || column.name,
                model: this.props.list?.resModel,
            })
        ) {
            return;
        }
        return super.onClickSortColumn(...arguments);
    },
});
