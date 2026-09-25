import { app } from "../../scripts/app.js";

const PROPERTY = "kieReviewText";

function show(node, record) {
    if (!record || typeof record.text !== "string") return;
    node.properties ||= {};
    node.properties[PROPERTY] = { label: String(record.label || "Review"), text: record.text.slice(0, 50000) };
    if (node._kieReviewTextarea) {
        node._kieReviewTextarea.value = node.properties[PROPERTY].text;
        node._kieReviewTextarea.title = node.properties[PROPERTY].label;
    }
}

app.registerExtension({
    name: "KIE.Nodes.Next.TextReview",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData?.name !== "KIE_Next_Text_Review") return;
        const created = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = created?.apply(this, arguments);
            if (typeof this.addDOMWidget !== "function") return result;
            const textarea = document.createElement("textarea");
            textarea.readOnly = true;
            textarea.setAttribute("aria-label", "KIE planning text review");
            textarea.style.cssText = "width:100%;height:240px;resize:vertical;white-space:pre-wrap;background:#17202a;color:#e6edf3;border:1px solid #526272;border-radius:6px;padding:9px;box-sizing:border-box";
            this._kieReviewTextarea = textarea;
            const widget = this.addDOMWidget("kie_text_review", "text", textarea, {
                hideOnZoom: false, getMinHeight: () => 250, getMaxHeight: () => 300,
            });
            widget.serialize = false;
            widget.options.serialize = false;
            show(this, this.properties?.[PROPERTY]);
            return result;
        };
        const configured = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const result = configured?.apply(this, arguments);
            show(this, this.properties?.[PROPERTY]);
            return result;
        };
        const executed = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const result = executed?.apply(this, arguments);
            show(this, message?.kie_review_text?.[0]);
            return result;
        };
    },
});
