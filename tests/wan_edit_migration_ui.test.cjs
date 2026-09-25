const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

let extension;
const app = { graph: { setDirtyCanvas() {} }, registerExtension(value) { extension = value; } };
const source = fs.readFileSync(path.join(__dirname, "../js/workflow_migrations.js"), "utf8")
    .replace(/^import .*;\s*/gm, "");
vm.runInNewContext(source, { app, migrateWan3WidgetValues() { return false; }, console });

(async () => {
    class Node {
        constructor() {
            this.widgets = ["prompt", "negative_prompt", "resolution", "aspect_ratio", "reference_image_url"]
                .map(name => ({ name, value: "" }));
        }
        onConfigure(info) { this.widgets.forEach((widget, index) => { widget.value = info.widgets_values[index]; }); }
    }
    await extension.beforeRegisterNodeDef(Node, { name: "KIE_Next_wan_2_7_videoedit_2336129f" });
    const node = new Node();
    const old = { widgets_values: ["Change jacket", "avoid blur", "https://example.test/approved.png", "1080p", "16:9", ""] };
    node.onConfigure(old);
    assert.equal(node.widgets.find(w => w.name === "resolution").value, "1080p");
    assert.equal(node.widgets.find(w => w.name === "reference_image_url").value, "https://example.test/approved.png");
    assert.equal(node.properties.kieWidgetSchema, 2);
    console.log("Wan Video Edit legacy URL migration passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
