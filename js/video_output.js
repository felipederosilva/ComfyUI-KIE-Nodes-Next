import { app } from "../../scripts/app.js";

const NODE_IDS = new Set(["KIE_Next_Preview_Video", "KIE_Next_Save_Video"]);
const PROPERTY = "kiePersistentVideo";

function videoUrl(record) {
    if (!record?.filename || record?.type !== "output") return "";
    return `/view?${new URLSearchParams({
        filename: String(record.filename),
        subfolder: String(record.subfolder || ""),
        type: "output",
    }).toString()}`;
}

function showVideo(node, record) {
    const url = videoUrl(record);
    if (!url) return;
    node.properties ||= {};
    node.properties[PROPERTY] = record;
    if (node._kieVideoPlayer) {
        node._kieVideoPlayer.pause();
        node._kieVideoPlayer.src = url;
        node._kieVideoPlayer.load();
    }
    if (node._kieVideoLink) node._kieVideoLink.href = url;
}

app.registerExtension({
    name: "KIE.Nodes.Next.VideoOutput",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!NODE_IDS.has(nodeData?.name)) return;

        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = originalCreated?.apply(this, arguments);
            const container = document.createElement("div");
            container.style.cssText = "display:flex;flex-direction:column;gap:6px;padding:4px;width:100%;box-sizing:border-box";
            const player = document.createElement("video");
            player.controls = true;
            player.playsInline = true;
            player.preload = "metadata";
            player.style.cssText = "display:block;width:100%;max-height:220px;background:#111;border-radius:6px";
            const link = document.createElement("a");
            link.textContent = "Open saved video";
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.style.cssText = "color:#99ceff;font-size:12px;text-align:center";
            container.append(player, link);
            this._kieVideoPlayer = player;
            this._kieVideoLink = link;
            if (typeof this.addDOMWidget === "function") {
                const widget = this.addDOMWidget("kie_video_player", "video", container, {
                    hideOnZoom: false,
                    getMinHeight: () => 240,
                    getMaxHeight: () => 280,
                });
                widget.serialize = false;
                widget.options.serialize = false;
            } else {
                this.addWidget?.("button", "Open saved video", "", () => {
                    const url = videoUrl(this.properties?.[PROPERTY]);
                    if (url) window.open(url, "_blank", "noopener,noreferrer");
                });
            }
            this.setSize?.([Math.max(this.size?.[0] || 0, 380), Math.max(this.size?.[1] || 0, 340)]);
            showVideo(this, this.properties?.[PROPERTY]);
            return result;
        };

        const originalConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const result = originalConfigure?.apply(this, arguments);
            showVideo(this, this.properties?.[PROPERTY]);
            return result;
        };

        const originalExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const result = originalExecuted?.apply(this, arguments);
            showVideo(this, message?.kie_persistent_video || message?.videos?.[0]);
            return result;
        };

        const originalRemoved = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function () {
            this._kieVideoPlayer?.pause();
            this._kieVideoPlayer?.removeAttribute("src");
            return originalRemoved?.apply(this, arguments);
        };
    },
});
