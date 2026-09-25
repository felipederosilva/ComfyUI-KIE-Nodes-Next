const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

let extension;
const app = { registerExtension(value) { extension = value; } };
const document = {
    createElement(tag) {
        return {
            tag,
            style: {},
            append(...children) { this.children = children; },
            pause() { this.paused = true; },
            load() { this.loaded = true; },
            removeAttribute(name) { if (name === "src") this.src = ""; },
        };
    },
};

const source = fs.readFileSync(path.join(__dirname, "../js/video_output.js"), "utf8")
    .replace(/^import \{ app \} from .*;\s*/m, "");
vm.runInNewContext(source, { app, document, URLSearchParams, window: {} });
assert.equal(extension.name, "KIE.Nodes.Next.VideoOutput");

class Node {
    constructor() {
        this.size = [200, 100];
        this.properties = {};
    }
    addDOMWidget(name, type, element, options) {
        this.widget = { name, type, element, options };
        return this.widget;
    }
    setSize(size) { this.size = size; }
}

(async () => {
    await extension.beforeRegisterNodeDef(Node, { name: "KIE_Next_Save_Video" });
    const node = new Node();
    node.onNodeCreated();
    assert.ok(node.widget.element.children[0].controls);
    const record = { filename: "shot_1.mp4", subfolder: "KIE-Videos", type: "output" };
    node.onExecuted({ kie_persistent_video: record });
    assert.equal(node.properties.kiePersistentVideo.filename, "shot_1.mp4");
    assert.match(node._kieVideoPlayer.src, /filename=shot_1.mp4/);
    assert.match(node._kieVideoPlayer.src, /type=output/);
    assert.equal(node._kieVideoLink.href, node._kieVideoPlayer.src);

    const restored = new Node();
    restored.properties.kiePersistentVideo = record;
    restored.onNodeCreated();
    restored.onConfigure();
    assert.equal(restored._kieVideoPlayer.src, node._kieVideoPlayer.src);
    restored.onRemoved();
    assert.equal(restored._kieVideoPlayer.src, "");
    console.log("Video output UI behavior passed");
})().catch((error) => { console.error(error); process.exitCode = 1; });
