import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "KIE.Nodes.Next.ModelUI",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        const category = String(nodeData?.category || "");
        if (!category.startsWith("KIE Next/")) return;
        if (category.includes("Utility") || category.includes("Advanced") || category.includes("Setup")) return;

        const original = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = original?.apply(this, arguments);
            try {
                // Model nodes should feel like generation tools, not tiny utility
                // boxes. Give prompt-heavy nodes useful room on creation while
                // still allowing the user to resize them normally afterwards.
                const widgets = this.widgets || [];
                const prompt = widgets.find((w) => ["prompt", "text", "lyrics", "system_prompt"].includes(String(w?.name || "")));
                if (prompt) {
                    const width = Math.max(Number(this.size?.[0] || 0), 440);
                    const height = Math.max(Number(this.size?.[1] || 0), widgets.length > 10 ? 520 : 400);
                    this.setSize?.([width, height]);
                    if (prompt.inputEl?.style) {
                        prompt.inputEl.style.minHeight = "120px";
                    }
                }
            } catch (e) {
                console.debug("KIE Next: optional node sizing skipped", e);
            }
            return result;
        };
    },
});

