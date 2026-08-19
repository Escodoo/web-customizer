import {
    isListRoot,
    openCustomizationFor,
    useCustomizationService,
} from "./customization_service";
import {ListRenderer} from "@web/views/list/list_renderer";
import {patch} from "@web/core/utils/patch";

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        this.customization = useCustomizationService();
    },
    get customizationSubview() {
        return this.env.customizationSubview || null;
    },
    getColumnClass(column) {
        const names = super.getColumnClass(column);
        if (
            column.type === "field" &&
            column.name &&
            this.customization?.state.enabled &&
            (isListRoot(this) || this.customizationSubview)
        ) {
            return `${names} o_esc_customization_target`.trim();
        }
        return names;
    },
    onClickSortColumn(column) {
        const subview = this.customizationSubview;
        if (
            column?.type === "field" &&
            column.name &&
            openCustomizationFor(this, column.name, null, {
                viewType: "list",
                fieldLabel: column.label || column.name,
                model: this.props.list?.resModel,
                anchorSubview: subview?.name,
            })
        ) {
            return;
        }
        return super.onClickSortColumn(...arguments);
    },
});
