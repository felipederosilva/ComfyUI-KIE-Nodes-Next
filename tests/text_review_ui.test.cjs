const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

let extension;
const app = { registerExtension(value) { extension = value; } };
const document = { createElement() { return { style: {}, setAttribute() {} }; } };
const source = fs.readFileSync(path.join(__dirname, "../js/text_review.js"), "utf8")
    .replace(/^import \{ app \} from .*;\s*/m, "");
vm.runInNewContext(source, { app, document });

(async () => {
    class Node {
        constructor() { this.properties = {}; }
        addDOMWidget(name, type, element, options) { return { name, type, element, options }; }
    }
    await extension.beforeRegisterNodeDef(Node, { name: "KIE_Next_Text_Review" });
    const node = new Node();
    node.onNodeCreated();
    node.onExecuted({ kie_review_text: [{ label: "Music", text: "Quiet opening, rise at 4s" }] });
    assert.equal(node._kieReviewTextarea.value, "Quiet opening, rise at 4s");
    const restored = new Node();
    restored.properties = JSON.parse(JSON.stringify(node.properties));
    restored.onNodeCreated();
    restored.onConfigure();
    assert.equal(restored._kieReviewTextarea.value, node._kieReviewTextarea.value);
    console.log("Text review display and reload passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
