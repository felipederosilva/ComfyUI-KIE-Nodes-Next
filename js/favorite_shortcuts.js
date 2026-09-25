import { app } from "../../scripts/app.js";

const STORAGE_KEY = "KIE.Next.FavoriteNodeSlots.v1";
const SLOT_COUNT = 9;
let memorySlots = {};

function readSlots() {
    try {
        const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
        return value && typeof value === "object" && !Array.isArray(value) ? value : {};
    } catch (_) {
        return memorySlots;
    }
}

function writeSlots(slots) {
    memorySlots = slots;
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(slots)); } catch (_) {}
}

function notify(severity, summary, detail) {
    try { app.extensionManager.toast.add({ severity, summary, detail, life: 4500 }); }
    catch (_) { console.info(`[KIE Next] ${summary}: ${detail}`); }
}

function graphPosition(canvas) {
    const area = canvas?.visible_area;
    if (area?.length >= 4 && area.every?.(Number.isFinite)) {
        return [area[0] + area[2] / 2, area[1] + area[3] / 2];
    }
    const mouse = canvas?.graph_mouse;
    return mouse?.length === 2 && mouse.every?.(Number.isFinite) ? [...mouse] : [80, 80];
}

function insertSlot(index) {
    const favorite = readSlots()[index];
    if (!favorite?.nodeId) {
        notify("info", `Favorite ${index} is empty`, "Right-click a KIE Next node and assign it to this slot.");
        return;
    }
    const canvas = app.canvas;
    const graph = canvas?.graph || app.graph;
    if (!graph || canvas?.read_only) {
        notify("warn", "Cannot insert favorite", "Open an editable ComfyUI graph first.");
        return;
    }
    // Some ComfyUI frontends expose LiteGraph as a lexical global, not a
    // property of globalThis. Support both without relying on either alone.
    const liteGraph = typeof LiteGraph !== "undefined" ? LiteGraph : globalThis.LiteGraph;
    const node = liteGraph?.createNode?.(favorite.nodeId);
    if (!node) {
        notify("warn", "Favorite node unavailable", `${favorite.title || favorite.nodeId} is not registered in this ComfyUI session.`);
        return;
    }
    graph.beforeChange?.();
    try {
        node.pos = graphPosition(canvas);
        graph.add(node);
        canvas?.selectNode?.(node);
        canvas?.setDirty?.(true, true);
    } finally {
        graph.afterChange?.();
    }
}

function favoriteMenu(nodeData, node) {
    const slots = readSlots();
    const nodeId = String(nodeData.name);
    const title = String(nodeData.display_name || node.title || nodeId);
    return {
        content: "KIE Next · Favorite shortcut slot",
        has_submenu: true,
        submenu: {
            title: "Favorite slot",
            options: Array.from({ length: SLOT_COUNT }, (_, offset) => {
                const index = offset + 1;
                const current = slots[index];
                const same = current?.nodeId === nodeId;
                return {
                    content: `${index} · ${same ? "Remove favorite" : current?.title || "Empty"}`,
                    callback: () => {
                        const next = readSlots();
                        const alreadySaved = next[index]?.nodeId === nodeId;
                        if (alreadySaved) delete next[index];
                        else next[index] = { nodeId, title };
                        writeSlots(next);
                        notify("success", alreadySaved ? `Favorite ${index} removed` : `Favorite ${index} saved`, alreadySaved ? title : `${title} · assign a key in ComfyUI Settings → Keybindings`);
                    },
                };
            }),
        },
    };
}

app.registerExtension({
    name: "KIE.Nodes.Next.FavoriteShortcuts",
    commands: Array.from({ length: SLOT_COUNT }, (_, offset) => {
        const index = offset + 1;
        return {
            id: `KIE.Next.InsertFavorite${index}`,
            label: `KIE Next: Insert favorite node ${index}`,
            function: () => insertSlot(index),
        };
    }),
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!String(nodeData?.name || "").startsWith("KIE_Next_")) return;
        const original = nodeType.prototype.getExtraMenuOptions;
        nodeType.prototype.getExtraMenuOptions = function () {
            const options = original?.apply(this, arguments);
            const added = [favoriteMenu(nodeData, this)];
            return Array.isArray(options) ? [...options, ...added] : added;
        };
    },
});
