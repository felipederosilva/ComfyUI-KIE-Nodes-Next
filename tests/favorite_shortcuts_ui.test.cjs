const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

let extension;
const data = new Map();
const localStorage = {
    getItem(key) { return data.get(key) || null; },
    setItem(key, value) { data.set(key, value); },
};
const added = [];
const graph = {
    beforeChange() { this.before = true; },
    afterChange() { this.after = true; },
    add(node) { added.push(node); },
};
const app = {
    graph,
    canvas: { graph, visible_area: [0, 0, 800, 600], selectNode() {}, setDirty() {} },
    extensionManager: { toast: { add() {} } },
    registerExtension(value) { extension = value; },
};
const LiteGraph = { createNode(type) { return { type }; } };
const source = fs.readFileSync(path.join(__dirname, "../js/favorite_shortcuts.js"), "utf8")
    .replace(/^import \{ app \} from .*;\s*/m, "");
vm.runInNewContext(source, { app, localStorage, LiteGraph, console });
assert.equal(extension.commands.length, 9);

(async () => {
    class Node {}
    await extension.beforeRegisterNodeDef(Node, { name: "KIE_Next_Seedance_Studio", display_name: "KIE • Seedance Studio" });
    const menu = new Node().getExtraMenuOptions();
    const slots = menu[0].submenu.options;
    assert.equal(slots.length, 9);
    slots[0].callback();
    assert.equal(JSON.parse(data.values().next().value)[1].nodeId, "KIE_Next_Seedance_Studio");

    extension.commands[0].function();
    assert.equal(added[0].type, "KIE_Next_Seedance_Studio");
    assert.deepEqual(Array.from(added[0].pos), [400, 300]);
    assert.ok(graph.before && graph.after);

    new Node().getExtraMenuOptions()[0].submenu.options[0].callback();
    assert.equal(JSON.parse(data.values().next().value)[1], undefined);
    console.log("Favorite shortcut UI behavior passed");
})().catch((error) => { console.error(error); process.exitCode = 1; });
