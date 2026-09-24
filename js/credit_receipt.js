import { app } from "../../scripts/app.js";

function hasCreditOutputs(nodeData) {
    const names = (nodeData?.outputs || []).map((output) => String(output?.name || "").toLowerCase());
    return names.includes("credits_consumed") && names.includes("credits_left");
}

app.registerExtension({
    name: "KIE.Nodes.Next.CreditReceipt",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!hasCreditOutputs(nodeData)) return;

        const originalExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const result = originalExecuted?.apply(this, arguments);
            const receipt = message?.kie_credit_receipt;
            this._kieCreditReceipt = Array.isArray(receipt) ? String(receipt[0] || "") : "";
            if (this._kieCreditReceipt && !this._kieCreditBadgeExpanded) {
                this.setSize?.([Math.max(this.size?.[0] || 0, 360), (this.size?.[1] || 0) + 28]);
                this._kieCreditBadgeExpanded = true;
            }
            app.graph?.setDirtyCanvas?.(true, true);
            return result;
        };

        const originalDrawForeground = nodeType.prototype.onDrawForeground;
        nodeType.prototype.onDrawForeground = function (ctx) {
            const result = originalDrawForeground?.apply(this, arguments);
            const label = this._kieCreditReceipt;
            if (!label || this.flags?.collapsed) return result;

            const width = this.size?.[0] || 0;
            const y = (this.size?.[1] || 0) - 25;
            ctx.save();
            ctx.fillStyle = "rgba(25, 111, 69, 0.92)";
            ctx.beginPath();
            if (ctx.roundRect) ctx.roundRect(8, y, Math.max(0, width - 16), 21, 5);
            else ctx.rect(8, y, Math.max(0, width - 16), 21);
            ctx.fill();
            ctx.fillStyle = "#eafff2";
            ctx.font = "12px sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(label, width / 2, y + 10.5, width - 28);
            ctx.restore();
            return result;
        };
    },
});
