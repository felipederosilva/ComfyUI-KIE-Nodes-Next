import { app } from "../../scripts/app.js";

const NODE_ID = "KIE_Next_Camera_Path";
const PREVIEW_PROPERTY = "kieCameraPathPreview";
const SIZE = [320, 240];
const X = value => SIZE[0] / 2 + Math.max(-10, Math.min(10, value)) * 12;
const Y = value => SIZE[1] / 2 + Math.max(-10, Math.min(10, value)) * 9;
const WORLD_X = value => Math.max(-10, Math.min(10, (value - SIZE[0] / 2) / 12));
const WORLD_Z = value => Math.max(-10, Math.min(10, (value - SIZE[1] / 2) / 9));

function number(node, name) {
    return Number(node.widgets?.find(widget => widget.name === name)?.value || 0);
}

function point(node, prefix) {
    return [X(number(node, `${prefix}_x`)), Y(number(node, `${prefix}_z`))];
}

function draw(node) {
    const canvas = node._kiePathCanvas;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#17202a";
    ctx.fillRect(0, 0, ...SIZE);
    ctx.strokeStyle = "#344554";
    ctx.lineWidth = 1;
    for (let n = -10; n <= 10; n += 5) {
        ctx.beginPath(); ctx.moveTo(X(n), 0); ctx.lineTo(X(n), SIZE[1]); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(0, Y(n)); ctx.lineTo(SIZE[0], Y(n)); ctx.stroke();
    }
    const start = point(node, "start");
    const end = point(node, "end");
    const mid = point(node, "mid");
    const target = point(node, "look_at");
    const mode = node.widgets?.find(widget => widget.name === "path_mode")?.value;
    ctx.strokeStyle = "#57c5eb";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(...start);
    if (mode === "custom path") ctx.quadraticCurveTo(...mid, ...end);
    else if (mode === "orbit") {
        const degrees = number(node, "orbit_degrees") * Math.PI / 180;
        const dx = start[0] - target[0], dy = start[1] - target[1];
        for (let index = 1; index <= 30; index++) {
            const angle = degrees * index / 30;
            ctx.lineTo(target[0] + dx * Math.cos(angle) - dy * Math.sin(angle),
                       target[1] + dx * Math.sin(angle) + dy * Math.cos(angle));
        }
    } else ctx.lineTo(...end);
    ctx.stroke();
    for (const [label, position, color] of [["START", start, "#6ee7b7"],
                                           ["END", end, "#ffc773"], ["LOOK", target, "#f787a9"]]) {
        ctx.fillStyle = color;
        ctx.beginPath(); ctx.arc(position[0], position[1], 8, 0, Math.PI * 2); ctx.fill();
        ctx.font = "12px sans-serif";
        ctx.fillText(label, position[0] + 10, position[1] - 8);
    }
    if (mode === "custom path") {
        ctx.fillStyle = "#b7dded";
        ctx.beginPath(); ctx.arc(mid[0], mid[1], 6, 0, Math.PI * 2); ctx.fill();
        ctx.fillText("MID", mid[0] + 9, mid[1] - 7);
    }
    ctx.fillStyle = "#d0d9e1";
    ctx.font = "12px sans-serif";
    ctx.fillText("TOP VIEW · drag points (−10 to +10 units)", 10, 19);
}

function installControls(node, canvas) {
    let active = null;
    const coordinates = event => {
        const box = canvas.getBoundingClientRect();
        return [(event.clientX - box.left) * SIZE[0] / box.width,
                (event.clientY - box.top) * SIZE[1] / box.height];
    };
    canvas.addEventListener("pointerdown", event => {
        const cursor = coordinates(event);
        const options = ["start", "end", "look_at"];
        if (node.widgets?.find(widget => widget.name === "path_mode")?.value === "custom path") options.push("mid");
        const match = options.map(name => ({ name, distance: Math.hypot(
            cursor[0] - point(node, name)[0], cursor[1] - point(node, name)[1]) }))
            .sort((a, b) => a.distance - b.distance)[0];
        if (!match || match.distance > 22) return;
        active = match.name;
        canvas.setPointerCapture(event.pointerId);
        event.stopPropagation();
        event.preventDefault();
    });
    canvas.addEventListener("pointermove", event => {
        if (!active) return;
        const cursor = coordinates(event);
        for (const [axis, value] of [["x", WORLD_X(cursor[0])], ["z", WORLD_Z(cursor[1])]]) {
            const widget = node.widgets?.find(item => item.name === `${active}_${axis}`);
            if (widget) {
                widget.value = Math.round(value * 10) / 10;
                widget.callback?.(widget.value, node, app.canvas);
            }
        }
        draw(node);
        node.setDirtyCanvas?.(true, true);
        event.stopPropagation();
    });
    for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) {
        canvas.addEventListener(type, () => { active = null; });
    }
}

function showSaved(node, record) {
    const preview = node._kiePathPreview;
    if (!preview || !record?.filename) return;
    node.properties ||= {};
    node.properties[PREVIEW_PROPERTY] = record;
    const query = new URLSearchParams({filename: record.filename,
                                       subfolder: record.subfolder || "", type: "output"});
    preview.src = `/view?${query}`;
    preview.style.display = "block";
}

app.registerExtension({
    name: "KIE.Nodes.Next.CameraPathControls",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData?.name !== NODE_ID) return;
        const created = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = created?.apply(this, arguments);
            if (typeof this.addDOMWidget !== "function") return result;
            const canvas = document.createElement("canvas");
            canvas.width = SIZE[0]; canvas.height = SIZE[1];
            canvas.style.cssText = "width:100%;height:240px;touch-action:none;border-radius:6px;cursor:crosshair";
            this._kiePathCanvas = canvas;
            installControls(this, canvas);
            const widget = this.addDOMWidget("kie_camera_path_editor", "canvas", canvas, {
                hideOnZoom: false, getMinHeight: () => 250, getMaxHeight: () => 270,
            });
            widget.serialize = false;
            widget.options.serialize = false;
            const preview = document.createElement("img");
            preview.alt = "Saved camera path top view";
            preview.style.cssText = "display:none;width:100%;max-height:220px;object-fit:contain;background:#17202a;border-radius:6px";
            this._kiePathPreview = preview;
            const previewWidget = this.addDOMWidget("kie_camera_path_preview", "image", preview, {
                hideOnZoom: false, getMinHeight: () => 220, getMaxHeight: () => 240,
            });
            previewWidget.serialize = false;
            previewWidget.options.serialize = false;
            showSaved(this, this.properties?.[PREVIEW_PROPERTY]);
            draw(this);
            return result;
        };
        const configure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const result = configure?.apply(this, arguments);
            showSaved(this, this.properties?.[PREVIEW_PROPERTY]);
            return result;
        };
        const executed = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const result = executed?.apply(this, arguments);
            showSaved(this, message?.kie_persistent_preview?.[0] || message?.images?.[0]);
            return result;
        };
        const foreground = nodeType.prototype.onDrawForeground;
        nodeType.prototype.onDrawForeground = function () {
            const result = foreground?.apply(this, arguments);
            draw(this);
            return result;
        };
    },
});
