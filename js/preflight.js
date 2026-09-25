import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

function element(tag, text) {
    const el = document.createElement(tag);
    if (text != null) el.textContent = text;
    return el;
}

function showReport(report) {
    const dialog = element("dialog");
    dialog.style.cssText = "width:min(760px,90vw);max-height:85vh;overflow:auto;background:#202024;color:#eee;border:1px solid #666;border-radius:12px;padding:24px;font:14px/1.5 sans-serif";
    const capabilities = report.capabilities || {};
    dialog.append(element("h2", capabilities.title || "KIE input check"));
    dialog.append(element("p", report.valid ? "No local input errors found." : "Please fix these inputs before generating."));
    for (const message of report.errors || []) {
        const p = element("p", message);
        p.style.color = "#ffb2a8";
        dialog.append(p);
    }
    for (const message of report.warnings || []) {
        const p = element("p", message);
        p.style.color = "#ead39b";
        dialog.append(p);
    }
    dialog.append(element("p", report.scope || "Local checks only."));
    const camera = capabilities.camera || {};
    dialog.append(element("p", camera.mode === "api_fields"
        ? `Documented camera fields: ${(camera.fields || []).join(", ")}. ${camera.note || ""}`
        : camera.mode === "prompt_guidance" ? "Camera direction: prompt guidance. This does not guarantee an exact physical camera path."
        : "Camera controls: not established by the available documentation."));
    const fields = element("details");
    fields.append(element("summary", "Documented model controls"));
    for (const [name, field] of Object.entries(capabilities.fields || {})) {
        const row = element("div");
        row.style.cssText = "border-top:1px solid #444;padding:10px 0";
        row.append(element("strong", `${name}${field.required ? " · required" : ""}`));
        if (field.evidence === "example") row.append(element("div", "Found in an example; constraints are not documented in the catalog."));
        if (field.enum) row.append(element("div", `Options: ${field.enum.join(", ")}`));
        for (const [key, label] of [["minimum", "Minimum"], ["maximum", "Maximum"], ["maxLength", "Maximum characters"], ["maxItems", "Maximum items"]]) {
            if (field[key] != null) row.append(element("div", `${label}: ${field[key]}`));
        }
        if (field.description) row.append(element("div", field.description));
        fields.append(row);
    }
    dialog.append(fields);
    try {
        const url = new URL(capabilities.source);
        if (url.protocol === "https:" && url.hostname === "docs.kie.ai") {
            const link = element("a", "Open official KIE documentation");
            link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer";
            link.style.cssText = "display:block;color:#9bd3ff;margin:14px 0";
            dialog.append(link);
        }
    } catch (_) {}
    const close = element("button", "Close");
    close.onclick = () => dialog.close();
    dialog.append(close);
    dialog.addEventListener("close", () => dialog.remove(), { once: true });
    document.body.append(dialog);
    dialog.showModal();
}

async function checkNode(node, nodeData) {
    const inputs = {};
    const specs = { ...nodeData.input?.required, ...nodeData.input?.optional };
    for (const widget of node.widgets || []) {
        if (widget.name in specs && widget.value !== undefined && typeof widget.value !== "function") inputs[widget.name] = widget.value;
    }
    const connected = (node.inputs || []).filter(input => input.link != null).map(input => input.name);
    try {
        const response = await api.fetchApi("/kie-next/preflight", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ node_type: nodeData.name, inputs, connected }),
        });
        const report = await response.json();
        if (!response.ok || !report.ok) throw new Error(report.error || "Could not check the node inputs.");
        showReport(report);
    } catch (error) {
        app.extensionManager.toast.add({ severity: "error", summary: "KIE input check", detail: error.message, life: 6000 });
    }
}

app.registerExtension({
    name: "KIE.Nodes.Next.Preflight",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        const studio = ["KIE_Next_Seedance_Studio", "KIE_Next_Kling_Omni_Studio"].includes(nodeData.name);
        if (!studio && !(String(nodeData.name).startsWith("KIE_Next_") && /^KIE Next\/(Video|Image|Audio|LLM)(\/|$)/.test(nodeData.category || ""))) return;
        const original = nodeType.prototype.getExtraMenuOptions;
        nodeType.prototype.getExtraMenuOptions = function () {
            const previous = original?.apply(this, arguments);
            return [...(Array.isArray(previous) ? previous : []), {
                content: "KIE Next · Check inputs & model controls",
                callback: () => checkNode(this, nodeData),
            }];
        };
    },
});
