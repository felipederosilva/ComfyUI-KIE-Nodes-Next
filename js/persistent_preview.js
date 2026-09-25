import { app } from "../../scripts/app.js";

const NODE_ID = "KIE_Next_Persistent_Preview_Image";
const PROPERTY = "kiePersistentPreview";

function firstRecord(message) {
    const records = message?.kie_persistent_preview || message?.images || [];
    return Array.isArray(records) && records.length ? records[0] : null;
}

function recordUrl(record) {
    const params = new URLSearchParams({
        filename: String(record.filename || ""),
        subfolder: String(record.subfolder || ""),
        type: String(record.type || "output"),
    });
    return `/view?${params.toString()}`;
}

function loadPreview(node, record) {
    if (!record?.filename) return;
    node.properties ||= {};
    node.properties[PROPERTY] = record;
    if (node._kiePersistentPreviewElement) {
        node._kiePersistentPreviewElement.src = recordUrl(record);
        node._kiePersistentPreviewElement.style.display = "block";
        return;
    }
    const image = new Image();
    image.onload = () => {
        node._kiePersistentPreviewImage = image;
        app.graph?.setDirtyCanvas?.(true, true);
    };
    image.onerror = () => {
        node._kiePersistentPreviewImage = null;
        app.graph?.setDirtyCanvas?.(true, true);
    };
    image.src = recordUrl(record);
}

app.registerExtension({
    name: "KIE.Nodes.Next.PersistentPreview",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (![NODE_ID, "KIE_Next_Storyboard_Contact_Sheet", "KIE_Next_Consistency_Board", "KIE_Next_Variation_Board"].includes(nodeData?.name)) return;
        const board = nodeData.name === "KIE_Next_Variation_Board";
        const previewHeight = board ? 570 : 260;

        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = originalCreated?.apply(this, arguments);
            if (typeof this.addDOMWidget === "function") {
                const preview = document.createElement("img");
                preview.alt = "Saved KIE preview";
                preview.style.cssText = `display:none;width:100%;height:${previewHeight}px;object-fit:contain;background:#17202a;border-radius:6px;cursor:zoom-in`;
                preview.title = "Click to inspect at full size";
                preview.onclick = () => { if (preview.src) window.open(preview.src, "_blank", "noopener"); };
                this._kiePersistentPreviewElement = preview;
                const widget = this.addDOMWidget("kie_persistent_image_preview", "image", preview, {
                    hideOnZoom: false, getMinHeight: () => previewHeight + 10, getMaxHeight: () => previewHeight + 30,
                });
                widget.serialize = false;
                widget.options.serialize = false;
            }
            this.setSize?.([Math.max(this.size?.[0] || 0, board ? 720 : 420),
                            Math.max(this.size?.[1] || 0, board ? 760 : 470)]);
            loadPreview(this, this.properties?.[PROPERTY]);
            return result;
        };

        const originalConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const result = originalConfigure?.apply(this, arguments);
            loadPreview(this, this.properties?.[PROPERTY]);
            return result;
        };

        const originalExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const result = originalExecuted?.apply(this, arguments);
            loadPreview(this, firstRecord(message));
            return result;
        };

        const originalDrawForeground = nodeType.prototype.onDrawForeground;
        nodeType.prototype.onDrawForeground = function (ctx) {
            const result = originalDrawForeground?.apply(this, arguments);
            const image = this._kiePersistentPreviewImage;
            if (this._kiePersistentPreviewElement || !image?.naturalWidth || !image?.naturalHeight) return result;

            const top = 116;
            const maxWidth = Math.max(1, this.size[0] - 20);
            const maxHeight = Math.max(1, this.size[1] - top - 10);
            const scale = Math.min(maxWidth / image.naturalWidth, maxHeight / image.naturalHeight);
            const width = image.naturalWidth * scale;
            const height = image.naturalHeight * scale;
            ctx.drawImage(image, (this.size[0] - width) / 2, top + (maxHeight - height) / 2, width, height);
            return result;
        };
    },
});
