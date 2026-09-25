const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

let extension;
const app = { registerExtension(value) { extension = value; } };
const events = {};
const drawing = { fillRect() {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {}, arc() {}, fill() {}, fillText() {} };
const document = { createElement(tag) {
    if (tag === "canvas") return { style: {}, addEventListener(name, callback) { events[name] = callback; },
        getContext() { return drawing; }, getBoundingClientRect() { return { left: 0, top: 0, width: 320, height: 240 }; },
        setPointerCapture() {} };
    return { style: {} };
} };
const source = fs.readFileSync(path.join(__dirname, "../js/camera_path_controls.js"), "utf8")
    .replace(/^import \{ app \} from .*;\s*/m, "");
vm.runInNewContext(source, { app, document, URLSearchParams, Math });

(async () => {
    class Node {
        constructor() {
            this.properties = {};
            this.widgets = [
                ["path_mode", "dolly"], ["start_x", 0], ["start_z", -4],
                ["end_x", 0], ["end_z", -2], ["look_at_x", 0], ["look_at_z", 0],
            ].map(([name, value]) => ({ name, value }));
        }
        addDOMWidget(name, type, element, options) { return { name, type, element, options }; }
        setDirtyCanvas() {}
    }
    await extension.beforeRegisterNodeDef(Node, { name: "KIE_Next_Camera_Path" });
    const node = new Node();
    node.onNodeCreated();
    assert.ok(node._kiePathCanvas);
    events.pointerdown({ clientX: 160, clientY: 84, pointerId: 1, stopPropagation() {}, preventDefault() {} });
    events.pointermove({ clientX: 220, clientY: 120, stopPropagation() {} });
    assert.equal(node.widgets.find(w => w.name === "start_x").value, 5);
    assert.equal(node.widgets.find(w => w.name === "start_z").value, 0);
    node.onExecuted({ kie_persistent_preview: [{ filename: "Path.png", subfolder: "KIE-Camera" }] });
    assert.match(node._kiePathPreview.src, /filename=Path.png/);
    assert.equal(node.properties.kieCameraPathPreview.filename, "Path.png");
    console.log("Camera path drag and saved preview UI behavior passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
