import { app } from "../../scripts/app.js";

const DRAFT = "KIE_Next_Script_To_Shot_Draft";
const REVIEW = "KIE_Next_Shot_Plan_Review";
const PROPERTY = "kieShotPlanJson";

function viewPlan(plan) {
    if (!plan) return;
    const dialog = document.createElement("dialog");
    dialog.style.cssText = "width:min(760px,90vw);max-height:85vh;padding:18px;background:#23272e;color:#f2f4f5;border:1px solid #555;border-radius:10px;";
    const heading = document.createElement("h3");
    heading.textContent = "KIE Next · Shot plan";
    const editor = document.createElement("textarea");
    editor.readOnly = true;
    editor.value = plan;
    editor.style.cssText = "box-sizing:border-box;width:100%;height:55vh;resize:vertical;background:#15191e;color:#e9eef3;font:13px monospace;";
    const actions = document.createElement("div");
    actions.style.cssText = "display:flex;gap:10px;justify-content:flex-end;margin-top:12px;";
    const copy = document.createElement("button");
    copy.textContent = "Copy JSON";
    copy.onclick = async () => {
        try { await navigator.clipboard.writeText(plan); copy.textContent = "Copied"; }
        catch (_) { editor.focus(); editor.select(); copy.textContent = "Selected · press Ctrl+C"; }
    };
    const close = document.createElement("button");
    close.textContent = "Close";
    close.onclick = () => dialog.close();
    actions.append(copy, close);
    dialog.append(heading, editor, actions);
    dialog.addEventListener("close", () => dialog.remove());
    document.body.append(dialog);
    dialog.showModal();
}

function copyIntoReviews(node, plan) {
    if (!plan) return;
    let count = 0;
    for (const linkId of node.outputs?.[0]?.links || []) {
        const link = app.graph?.links?.[linkId];
        const targetId = link?.target_id ?? link?.[3];
        const target = app.graph?.getNodeById?.(targetId);
        if (target?.type !== REVIEW) continue;
        const widget = target.widgets?.find(w => w.name === "edited_json");
        if (!widget) continue;
        widget.value = plan;
        widget.callback?.(plan, target, app.canvas);
        target.setDirtyCanvas?.(true, true);
        count++;
    }
    if (!count) {
        viewPlan(plan);
        return;
    }
    app.graph?.setDirtyCanvas?.(true, true);
}

app.registerExtension({
    name: "KIE.Nodes.Next.ShotPlanReview",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (![DRAFT, REVIEW].includes(nodeData?.name)) return;
        const originalExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const result = originalExecuted?.apply(this, arguments);
            const plan = message?.kie_shot_plan?.[0];
            if (typeof plan === "string") {
                this.properties ||= {};
                this.properties[PROPERTY] = plan;
            }
            return result;
        };
        const originalMenu = nodeType.prototype.getExtraMenuOptions;
        nodeType.prototype.getExtraMenuOptions = function (_, options) {
            const result = originalMenu?.apply(this, arguments);
            options.push({ content: "KIE Next · View last shot plan", callback: () => viewPlan(this.properties?.[PROPERTY]) });
            if (nodeData.name === DRAFT) {
                options.push({ content: "KIE Next · Copy draft into connected review", callback: () => copyIntoReviews(this, this.properties?.[PROPERTY]) });
            }
            return result;
        };
    },
});
