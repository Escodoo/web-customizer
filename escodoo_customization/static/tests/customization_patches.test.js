import {expect, test} from "@odoo/hoot";
import {animationFrame} from "@odoo/hoot-mock";
import {customizationService} from "@escodoo_customization/customization_service";
import {user} from "@web/core/user";
import {
    contains,
    defineMenus,
    defineModels,
    fields,
    getService,
    mockService,
    models,
    mountView,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import {KanbanCompiler} from "@web/views/kanban/kanban_compiler";
import {NavBar} from "@web/webclient/navbar/navbar";

class Partner extends models.Model {
    _name = "partner";

    name = fields.Char();
    email = fields.Char();
    is_favorite = fields.Boolean();
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
            is_favorite: false,
            state: "draft",
        },
        {
            id: 2,
            name: "Bob",
            email: "bob@example.com",
            is_favorite: true,
            state: "done",
        },
    ];
}

class Users extends models.Model {
    _name = "res.users";

    name = fields.Char();

    has_group() {
        return true;
    }
}

defineModels([Partner, Users]);

function enableCustomization() {
    mockService("escodoo_customization", (env, {dialog, notification}) => {
        const service = customizationService.start(env, {dialog, notification});
        service.state.enabled = true;
        service.openFieldDialog = (info) => {
            expect.step(`${info.anchorKind || "field"}:${info.fieldName}`);
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
    mockService("escodoo_customization", (env, {dialog, notification}) =>
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
    getService("escodoo_customization").toggle();
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
            xmlid: "escodoo_customization.tester_app",
            children: [2],
        },
        {
            id: 2,
            name: "Users",
            xmlid: "escodoo_customization.tester_users",
        },
    ]);
    await mountWithCleanup(NavBar);
    getService("menu").setCurrentMenu(1);
    await animationFrame();
    await contains(
        ".o_menu_sections [data-menu-xmlid='escodoo_customization.tester_users']"
    ).click();
    expect.verifySteps(["menu:escodoo_customization.tester_users"]);
});
