import {registry} from "@web/core/registry";

registry.category("web_tour.tours").add("escodoo_customization_wand_form", {
    url: "/odoo/res.partner/1",
    steps: () => [
        {
            content: "Partner form is open",
            trigger: ".o_form_view",
        },
        {
            content: "Turn on customization mode",
            trigger: ".o_esc_customization_systray button",
            run: "click",
        },
        {
            content: "Customization mode is on",
            trigger: "body.o_esc_customization_mode",
        },
        {
            content: "Click a field outlined by the wand",
            trigger: ".o_form_view .o_esc_customization_target",
            run: "click",
        },
        {
            content: "The customization dialog is open",
            trigger: ".o_esc_customization_dialog",
        },
        {
            content: "Close the dialog",
            trigger: ".o_dialog footer .btn-secondary",
            run: "click",
        },
    ],
});
