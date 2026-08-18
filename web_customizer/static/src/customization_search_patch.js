import {patch} from "@web/core/utils/patch";
import {SearchBar} from "@web/search/search_bar/search_bar";
import {openCustomizationFor, useCustomizationService} from "./customization_service";

patch(SearchBar.prototype, {
    setup() {
        super.setup(...arguments);
        this.customization = useCustomizationService();
    },
    get showCustomizationSearchFields() {
        return Boolean(
            this.customization?.state.enabled && this.env.searchModel?.searchViewId
        );
    },
    get customizationSearchFields() {
        const items =
            this.env.searchModel?.getSearchItems((item) => item.type === "field") || [];
        return items.filter((item) => item.fieldName);
    },
    onCustomizationSearchFieldClick(ev, item) {
        openCustomizationFor(this, item.fieldName, ev, {
            viewType: "search",
            viewId: this.env.searchModel.searchViewId,
            fieldLabel: item.description || item.fieldName,
            model: this.env.searchModel.resModel,
        });
    },
});
