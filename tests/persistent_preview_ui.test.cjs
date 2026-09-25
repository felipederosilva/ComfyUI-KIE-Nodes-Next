const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

let extension;
const app = { graph: { setDirtyCanvas() {} }, registerExtension(value) { extension = value; } };
const source = fs.readFileSync(path.join(__dirname, "../js/persistent_preview.js"), "utf8")
    .replace(/^import \{ app \} from .*;\s*/m, "");
const document = { createElement() { return { style: {} }; } };
vm.runInNewContext(source, { app, document, URLSearchParams, Image: class {} });

(async () => {
    class Node {
        constructor() { this.properties = {}; this.size = [300, 320]; this.widgets = []; }
        addDOMWidget(name, type, element, options) {
            const widget = { name, type, element, options };
            this.widgets.push(widget);
            return widget;
        }
        setSize(size) { this.size = size; }
    }
    await extension.beforeRegisterNodeDef(Node, { name: "KIE_Next_Consistency_Board" });
    const node = new Node();
    node.onNodeCreated();
    assert.equal(node.widgets.length, 1);
    node.onExecuted({ kie_persistent_preview: [{ filename: "board.png", subfolder: "KIE-Previews" }] });
    assert.match(node.widgets[0].element.src, /board.png/);
    assert.equal(node.properties.kiePersistentPreview.filename, "board.png");
    let drawCalls = 0;
    node._kiePersistentPreviewImage = { naturalWidth: 300, naturalHeight: 200 };
    node.onDrawForeground({ drawImage() { drawCalls++; } });
    assert.equal(drawCalls, 0, "DOM preview must not cover the board widgets");
    const restored = new Node();
    restored.properties = JSON.parse(JSON.stringify(node.properties));
    restored.onNodeCreated();
    restored.onConfigure();
    assert.match(restored.widgets[0].element.src, /board.png/);
    console.log("Persistent preview placement and reload passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
