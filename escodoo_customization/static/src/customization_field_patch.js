import {isFormRootField, openCustomizationFor} from "./customization_service";
import {useService} from "@web/core/utils/hooks";
import {patch} from "@web/core/utils/patch";
import {Field} from "@web/views/fields/field";
import {FormLabel} from "@web/views/form/form_label";

patch(Field.prototype, {
    setup() {
        super.setup(...arguments);
        this.customization = useService("escodoo_customization");
    },
    get classNames() {
        const names = super.classNames;
        if (this.customization?.state.enabled && isFormRootField(this)) {
            names.o_esc_customization_target = true;
        }
        return names;
    },
    onCustomizationClick(ev) {
        openCustomizationFor(this, this.props.name, ev);
    },
});

patch(FormLabel.prototype, {
    setup() {
        super.setup?.(...arguments);
        this.customization = useService("escodoo_customization");
    },
    get className() {
        const names = super.className;
        if (this.customization?.state.enabled && isFormRootField(this)) {
            return `${names} o_esc_customization_target`.trim();
        }
        return names;
    },
    onCustomizationClick(ev) {
        openCustomizationFor(this, this.props.fieldName, ev);
    },
});
