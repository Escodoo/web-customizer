import {
    contains,
    defineMenus,
    defineModels,
    fields,
    getService,
    makeDialogMockEnv,
    mockService,
    models,
    mountView,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import {expect, test} from "@odoo/hoot";
import {CustomizationFieldDialog} from "@web_customizer/customization_field_dialog";
import {KanbanCompiler} from "@web/views/kanban/kanban_compiler";
import {MainComponentsContainer} from "@web/core/main_components_container";
import {NavBar} from "@web/webclient/navbar/navbar";
import {animationFrame} from "@odoo/hoot-mock";
import {customizationService} from "@web_customizer/customization_service";
import {user} from "@web/core/user";

class Partner extends models.Model {
    _name = "partner";

    name = fields.Char();
    email = fields.Char();
    revenue = fields.Integer();
    is_favorite = fields.Boolean();
    line_ids = fields.One2many({relation: "partner.line"});
    state = fields.Selection({
        selection: [
            ["draft", "Draft"],
            ["done", "Done"],
        ],
    });

    action_view_tasks() {
        return true;
    }

    _records = [
        {
            id: 1,
            name: "Ada",
            email: "ada@example.com",
            revenue: 10,
            is_favorite: false,
            state: "draft",
            line_ids: [1],
        },
        {
            id: 2,
            name: "Bob",
            email: "bob@example.com",
            revenue: 20,
            is_favorite: true,
            state: "done",
        },
    ];
}

class PartnerLine extends models.Model {
    _name = "partner.line";

    note = fields.Char();
    partner_id = fields.Many2one({relation: "partner"});

    _records = [{id: 1, note: "First", partner_id: 1}];
}

class Users extends models.Model {
    _name = "res.users";

    name = fields.Char();

    has_group() {
        return true;
    }
}

defineModels([Partner, PartnerLine, Users]);

function enableCustomization() {
    mockService("web_customizer", (env, {dialog, notification}) => {
        const service = customizationService.start(env, {dialog, notification});
        service.state.enabled = true;
        service.openFieldDialog = (info) => {
            const scope = info.anchorSubview ? `@${info.anchorSubview}` : "";
            expect.step(`${info.anchorKind || "field"}:${info.fieldName}${scope}`);
        };
        return service;
    });
}

function compileKanban(arch) {
    const parser = new DOMParser();
    const xml = parser.parseFromString(arch, "text/xml");
    const compiler = new KanbanCompiler({kanban: xml.documentElement});
    return compiler.compile("kanban");
}

test("form fields become targets after the wand is turned on", async () => {
    mockService("web_customizer", (env, {dialog, notification}) =>
        customizationService.start(env, {dialog, notification})
    );
    await mountView({
        type: "form",
        resModel: "partner",
        resId: 1,
        arch: `
            <form>
                <sheet>
                    <group>
                        <field name="name"/>
                        <field name="email"/>
                    </group>
                </sheet>
            </form>`,
    });
    expect(".o_esc_customization_target").toHaveCount(0);
    getService("web_customizer").toggle();
    await animationFrame();
    expect(".o_field_widget[name=email]").toHaveClass("o_esc_customization_target");
});

test("form fields are not targets while customization is off", async () => {
    await mountView({
        type: "form",
        resModel: "partner",
        resId: 1,
        arch: `
            <form>
                <sheet>
                    <group>
                        <field name="name"/>
                        <field name="email"/>
                    </group>
                </sheet>
            </form>`,
    });
    expect(".o_esc_customization_target").toHaveCount(0);
});

test("Field patch outlines form fields and opens the dialog", async () => {
    enableCustomization();
    await mountView({
        type: "form",
        resModel: "partner",
        resId: 1,
        arch: `
            <form>
                <sheet>
                    <group>
                        <field name="name"/>
                        <field name="email"/>
                    </group>
                </sheet>
            </form>`,
    });
    expect(".o_field_widget[name=email]").toHaveClass("o_esc_customization_target");
    await contains(".o_field_widget[name=email]").click();
    expect.verifySteps(["field:email"]);
});

test("ViewButton patch outlines named buttons and intercepts the click", async () => {
    enableCustomization();
    onRpc("toggle_active", () => {
        expect.step("rpc:toggle_active");
        return true;
    });
    await mountView({
        type: "form",
        resModel: "partner",
        resId: 1,
        arch: `
            <form>
                <header>
                    <button name="toggle_active" type="object" string="Archive"/>
                </header>
                <sheet>
                    <field name="name"/>
                </sheet>
            </form>`,
    });
    expect("button[name=toggle_active]").toHaveClass("o_esc_customization_target");
    await contains("button[name=toggle_active]").click();
    expect.verifySteps(["button:toggle_active"]);
});

test("KanbanCompiler marks span fields and type-only buttons", () => {
    const compiled = compileKanban(`
        <kanban>
            <templates>
                <t t-name="card">
                    <field name="name"/>
                    <button type="edit" string="Edit"/>
                </t>
            </templates>
        </kanban>`);
    const html = compiled.outerHTML;
    expect(html).toMatch("o_esc_kanban_field");
    expect(html).toMatch("onCustomizationFieldClick");
    expect(html).toMatch("t-on-click.capture");
    expect(html).toMatch("o_esc_kanban_button");
    expect(html).toMatch("onCustomizationButtonClick");
});

test("kanban header button opens the dialog", async () => {
    enableCustomization();
    await mountView({
        type: "kanban",
        resModel: "partner",
        arch: `
            <kanban>
                <header>
                    <button name="toggle_active" type="object" string="Archive" display="always"/>
                </header>
                <templates>
                    <t t-name="card">
                        <field name="name"/>
                    </t>
                </templates>
            </kanban>`,
    });
    expect(".o_control_panel button[name=toggle_active]").toHaveClass(
        "o_esc_customization_target"
    );
    await contains(".o_control_panel button[name=toggle_active]").click();
    expect.verifySteps(["button:toggle_active"]);
});

test("kanban progressbar opens the dialog", async () => {
    enableCustomization();
    await mountView({
        type: "kanban",
        resModel: "partner",
        arch: `
            <kanban default_group_by="state">
                <progressbar field="state" colors='{"draft": "success", "done": "warning"}'/>
                <templates>
                    <t t-name="card">
                        <field name="name"/>
                    </t>
                </templates>
            </kanban>`,
    });
    expect(".o_kanban_counter").toHaveCount(2);
    await contains(".o_kanban_counter").click();
    expect.verifySteps(["progressbar:state"]);
});

test("kanban card field and type-only button open the dialog", async () => {
    enableCustomization();
    await mountView({
        type: "kanban",
        resModel: "partner",
        arch: `
            <kanban>
                <templates>
                    <t t-name="card">
                        <field name="name"/>
                        <button type="edit" string="Edit"/>
                    </t>
                </templates>
            </kanban>`,
    });
    expect(".o_kanban_record:not(.o_kanban_ghost)").toHaveClass(
        "o_esc_customization_mode"
    );
    expect(".o_kanban_record .o_esc_kanban_field").toHaveCount(2);
    await contains(".o_kanban_record .o_esc_kanban_field").click();
    expect.verifySteps(["field:name"]);
    await contains(".o_kanban_record .o_esc_kanban_button").click();
    expect.verifySteps(["button:edit"]);
});

test("kanban widget with stop still opens the dialog", async () => {
    enableCustomization();
    await mountView({
        type: "kanban",
        resModel: "partner",
        arch: `
            <kanban>
                <templates>
                    <t t-name="card">
                        <field name="name"/>
                        <field name="is_favorite" widget="boolean_favorite"/>
                    </t>
                </templates>
            </kanban>`,
    });
    expect(".o_kanban_record .o_favorite").toHaveCount(2);
    await contains(".o_kanban_record .o_favorite").click();
    expect.verifySteps(["field:is_favorite"]);
    expect(".o_kanban_record:not(.o_kanban_ghost) .fa-star-o").toHaveCount(1);
});

test("kanban object link opens the dialog instead of the action", async () => {
    enableCustomization();
    onRpc("action_view_tasks", () => {
        expect.step("rpc:action_view_tasks");
        return true;
    });
    await mountView({
        type: "kanban",
        resModel: "partner",
        arch: `
            <kanban>
                <templates>
                    <t t-name="card">
                        <a name="action_view_tasks" type="object">
                            <field name="name"/>
                        </a>
                    </t>
                </templates>
            </kanban>`,
    });
    expect(".o_kanban_record a[name=action_view_tasks]").toHaveClass(
        "o_esc_customization_target"
    );
    await contains(".o_kanban_record a[name=action_view_tasks]").click();
    expect.verifySteps(["button:action_view_tasks"]);
});

test("kanban card does not open the record while the wand is on", async () => {
    enableCustomization();
    await mountView({
        type: "kanban",
        resModel: "partner",
        arch: `
            <kanban>
                <templates>
                    <t t-name="card">
                        <div class="o_esc_card_chrome">Chrome</div>
                        <field name="name"/>
                    </t>
                </templates>
            </kanban>`,
    });
    await contains(".o_kanban_record .o_esc_card_chrome").click();
    expect.verifySteps([]);
    expect(".o_kanban_view").toHaveCount(1);
    expect(".o_form_view").toHaveCount(0);
});

test("ListRenderer outlines columns and opens the dialog", async () => {
    enableCustomization();
    await mountView({
        type: "list",
        resModel: "partner",
        arch: `
            <list>
                <field name="name"/>
                <field name="email"/>
            </list>`,
    });
    expect("th[data-name=email]").toHaveClass("o_esc_customization_target");
    await contains("th[data-name=email]").click();
    expect.verifySteps(["field:email"]);
});

test("a column of a written table anchors inside that table", async () => {
    enableCustomization();
    await mountView({
        type: "form",
        resModel: "partner",
        resId: 1,
        arch: `
            <form>
                <sheet>
                    <field name="line_ids">
                        <list>
                            <field name="note"/>
                        </list>
                    </field>
                </sheet>
            </form>`,
    });
    expect("th[data-name=note]").toHaveClass("o_esc_customization_target");
    await contains("th[data-name=note]").click();
    expect.verifySteps(["field:note@line_ids"]);
});

test("a card of a written kanban anchors inside that table", async () => {
    enableCustomization();
    await mountView({
        type: "form",
        resModel: "partner",
        resId: 1,
        arch: `
            <form>
                <sheet>
                    <field name="line_ids" mode="kanban">
                        <kanban>
                            <templates>
                                <t t-name="card">
                                    <field name="note"/>
                                </t>
                            </templates>
                        </kanban>
                    </field>
                </sheet>
            </form>`,
    });
    await contains(".o_kanban_record .o_esc_kanban_field").click();
    expect.verifySteps(["field:note@line_ids"]);
});

test("a field of the record itself keeps anchoring on the view", async () => {
    enableCustomization();
    await mountView({
        type: "form",
        resModel: "partner",
        resId: 1,
        arch: `
            <form>
                <sheet>
                    <group>
                        <field name="email"/>
                    </group>
                    <field name="line_ids">
                        <list>
                            <field name="note"/>
                        </list>
                    </field>
                </sheet>
            </form>`,
    });
    await contains(".o_field_widget[name=email]").click();
    expect.verifySteps(["field:email"]);
});

test("PivotRenderer opens the dialog for a measure instead of sorting", async () => {
    enableCustomization();
    await mountView({
        type: "pivot",
        resModel: "partner",
        arch: `
            <pivot>
                <field name="state" type="row"/>
                <field name="revenue" type="measure"/>
            </pivot>`,
    });
    await contains(".o_pivot_measure_row").click();
    expect.verifySteps(["field:revenue"]);
});

test("PivotRenderer still sorts while customization is off", async () => {
    await mountView({
        type: "pivot",
        resModel: "partner",
        arch: `
            <pivot>
                <field name="state" type="row"/>
                <field name="revenue" type="measure"/>
            </pivot>`,
    });
    await contains(".o_pivot_measure_row").click();
    expect(".o_pivot_sort_order_asc, .o_pivot_sort_order_desc").toHaveCount(1);
});

test("SearchBar outlines arch filters and opens the dialog", async () => {
    enableCustomization();
    await mountView({
        type: "list",
        resModel: "partner",
        arch: `
            <list>
                <field name="name"/>
            </list>`,
        searchViewId: 99,
        searchViewArch: `
            <search>
                <filter name="favorites" string="Favorites"
                    domain="[('is_favorite', '=', True)]"/>
            </search>`,
    });
    await contains(".o_searchview .o_esc_customization_target").click();
    expect.verifySteps(["filter:favorites"]);
});

test("SearchBar outlines search fields and opens the dialog", async () => {
    enableCustomization();
    await mountView({
        type: "list",
        resModel: "partner",
        arch: `
            <list>
                <field name="name"/>
            </list>`,
        searchViewId: 99,
        searchViewArch: `
            <search>
                <field name="email"/>
            </search>`,
    });
    expect(".o_searchview .o_esc_customization_target").toHaveCount(1);
    await contains(".o_searchview .o_esc_customization_target").click();
    expect.verifySteps(["field:email"]);
});

test.tags("desktop");
test("NavBar patch opens the dialog for a menu with an XML ID", async () => {
    enableCustomization();
    patchWithCleanup(user, {
        async hasGroup() {
            return true;
        },
    });
    defineMenus([
        {
            id: 1,
            name: "App",
            xmlid: "web_customizer.tester_app",
            children: [2],
        },
        {
            id: 2,
            name: "Users",
            xmlid: "web_customizer.tester_users",
        },
    ]);
    await mountWithCleanup(NavBar);
    getService("menu").setCurrentMenu(1);
    await animationFrame();
    await contains(
        ".o_menu_sections [data-menu-xmlid='web_customizer.tester_users']"
    ).click();
    expect.verifySteps(["menu:web_customizer.tester_users"]);
});

test("banner appears in customization mode and Exit turns it off", async () => {
    enableCustomization();
    await mountWithCleanup(MainComponentsContainer);
    expect(".o_esc_customization_banner").toHaveCount(1);
    expect(".o_esc_customization_banner_title").toHaveText("Customization mode");
    expect(".o_esc_customization_banner_options").toHaveCount(0);
    await contains(".o_esc_customization_banner_exit").click();
    expect(".o_esc_customization_banner").toHaveCount(0);
});

test("banner offers view options once a list is mounted", async () => {
    enableCustomization();
    await mountView({
        type: "list",
        resModel: "partner",
        arch: `<list><field name="name"/></list>`,
    });
    expect(".o_esc_customization_banner_options").toHaveCount(1);
    await contains(".o_esc_customization_banner_options").click();
    expect.verifySteps(["view:"]);
});

test("banner stays quiet on a view type without root options", async () => {
    enableCustomization();
    await mountView({
        type: "pivot",
        resModel: "partner",
        arch: `<pivot><field name="revenue" type="measure"/></pivot>`,
    });
    expect(".o_esc_customization_banner_options").toHaveCount(0);
});

test("options of a table are written on its own model", async () => {
    mockService("orm", {
        async call(model, method, args) {
            if (method === "get_ui_context") {
                return {
                    bundles: [{id: 1, name: "Sandbox"}],
                    anchor_count: 1,
                    anchor_unique: true,
                    candidates: [],
                    field_subview: {type: "list", model: "partner.line"},
                };
            }
            if (method === "create_from_ui") {
                const params = args[0];
                expect.step(
                    [
                        params.model,
                        params.view_type,
                        params.anchor_kind,
                        params.anchor_subview,
                        JSON.stringify(params.payload),
                    ].join("|")
                );
                return {operation_ids: [1], broken: []};
            }
            throw new Error(`Unexpected ORM call ${model}.${method}`);
        },
        async read() {
            return [];
        },
    });
    const env = await makeDialogMockEnv();
    await mountWithCleanup(CustomizationFieldDialog, {
        env,
        props: {
            close() {
                expect.step("close");
            },
            fieldName: "line_ids",
            fieldLabel: "Lines",
            model: "partner",
            viewId: 1,
            viewType: "form",
        },
    });
    await contains(".o_esc_action_select").select("set_view_attribute");
    await contains(".o_esc_root_editable").select("bottom");
    await contains(".modal-footer .btn-primary").click();
    expect.verifySteps([
        'partner.line|list|view|line_ids|{"attributes":{"editable":"bottom"}}',
        "close",
    ]);
});

test("dialog reports RPC failures and stays open", async () => {
    mockService("notification", {
        add(message, options) {
            expect.step(`${options.type}:${message}`);
        },
    });
    mockService("orm", {
        async call(model, method) {
            if (method === "get_ui_context") {
                return {
                    bundles: [{id: 1, name: "Sandbox"}],
                    anchor_count: 1,
                    anchor_unique: true,
                    candidates: [],
                };
            }
            if (method === "create_from_ui") {
                const error = new Error("Could not apply customization.");
                error.data = {message: "Could not apply customization."};
                throw error;
            }
            throw new Error(`Unexpected ORM call ${model}.${method}`);
        },
        async read() {
            return [];
        },
    });
    const env = await makeDialogMockEnv();
    await mountWithCleanup(CustomizationFieldDialog, {
        env,
        props: {
            close() {
                expect.step("close");
            },
            fieldName: "email",
            fieldLabel: "Email",
            model: "res.partner",
            viewId: 1,
            viewType: "form",
        },
    });
    expect(".o_esc_customization_dialog").toHaveCount(1);
    await contains(".modal-footer .btn-primary").click();
    expect.verifySteps(["danger:Could not apply customization."]);
    expect(".o_esc_customization_dialog").toHaveCount(1);
});
