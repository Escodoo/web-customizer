import {openCustomizationFor, useCustomizationService} from "./customization_service";
import {PivotRenderer} from "@web/views/pivot/pivot_renderer";
import {patch} from "@web/core/utils/patch";

patch(PivotRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        this.customization = useCustomizationService();
    },
    onMeasureClick(cell) {
        const measure = cell?.measure;
        // __count is produced by the model and is never declared in the arch,
        // so it cannot be anchored on.
        if (
            measure &&
            measure !== "__count" &&
            openCustomizationFor(this, measure, null, {
                viewType: "pivot",
                fieldLabel: cell.title || measure,
                model: this.model?.metaData?.resModel,
            })
        ) {
            return;
        }
        return super.onMeasureClick(...arguments);
    },
});
