import { app } from "../../scripts/app.js";

const NODE_ID = "KIE_Next_Persistent_Load_Video";

function descriptor(value) {
    const text = String(value || "");
    const output = text.endsWith(" [output]");
    const filename = output ? text.slice(0, -9) : text;
    const splitAt = filename.lastIndexOf("/");
    return {
        filename: splitAt >= 0 ? filename.slice(splitAt + 1) : filename,
        subfolder: splitAt >= 0 ? filename.slice(0, splitAt) : "",
        type: output ? "output" : "input",
    };
}

function videoUrl(value) {
    const record = descriptor(value);
    return `/view?${new URLSearchParams(record).toString()}`;
}

function loadVideo(node, value) {
    if (!value) return;
    const video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;
    video.preload = "auto";
    video.addEventListener("loadeddata", () => {
        node._kiePersistentPreviewVideo = video;
        try { video.currentTime = Math.min(0.1, Number(video.duration || 0)); } catch (_) {}
        app.graph?.setDirtyCanvas?.(true, true);
    });
    video.addEventListener("seeked", () => app.graph?.setDirtyCanvas?.(true, true));
    video.src = videoUrl(value);
}

app.registerExtension({
    name: "KIE.Nodes.Next.PersistentVideoPreview",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData?.name !== NODE_ID) return;

        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = originalCreated?.apply(this, arguments);
            this.setSize?.([Math.max(this.size?.[0] || 0, 360), Math.max(this.size?.[1] || 0, 300)]);
            const widget = this.widgets?.find((item) => item?.name === "file");
            if (widget) {
                const originalCallback = widget.callback;
                widget.callback = (...args) => {
                    const callbackResult = originalCallback?.apply(widget, args);
                    loadVideo(this, widget.value);
                    return callbackResult;
                };
                loadVideo(this, widget.value);
            }
            return result;
        };

        const originalConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const result = originalConfigure?.apply(this, arguments);
            loadVideo(this, this.widgets?.find((item) => item?.name === "file")?.value);
            return result;
        };

        const originalDrawForeground = nodeType.prototype.onDrawForeground;
        nodeType.prototype.onDrawForeground = function (ctx) {
            const result = originalDrawForeground?.apply(this, arguments);
            const video = this._kiePersistentPreviewVideo;
            if (!video?.videoWidth || !video?.videoHeight) return result;
            const top = 72;
            const maxWidth = Math.max(1, this.size[0] - 20);
            const maxHeight = Math.max(1, this.size[1] - top - 10);
            const scale = Math.min(maxWidth / video.videoWidth, maxHeight / video.videoHeight);
            const width = video.videoWidth * scale;
            const height = video.videoHeight * scale;
            ctx.drawImage(video, (this.size[0] - width) / 2, top + (maxHeight - height) / 2, width, height);
            return result;
        };
    },
});
