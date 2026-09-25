import { app } from "../../scripts/app.js";
import { migrateWan3WidgetValues } from "./widget_migrations.js";

function widgetNames(node) {
    return (node.widgets || []).map((widget) => String(widget?.name || ""));
}

function migrateLiveNode(node, nodeType) {
    const widgets = node.widgets || [];
    const values = widgets.map((widget) => widget?.value);
    if (!migrateWan3WidgetValues(nodeType, widgetNames(node), values)) return false;
    widgets.forEach((widget, index) => {
        if (index < values.length) widget.value = values[index];
    });
    return true;
}

app.registerExtension({
    name: "KIE.Nodes.Next.WorkflowMigrations",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        const name = String(nodeData?.name || "");
        const wan3 = name.startsWith("KIE_Next_wan_3_0_video");
        const wanEdit = name.startsWith("KIE_Next_wan_2_7_videoedit_");
        if (!wan3 && !wanEdit) return;

        const originalConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (info) {
            if (wanEdit) {
                const values = info?.widgets_values;
                // Older workflows stored a URL widget between negative_prompt and
                // resolution. The new schema uses an IMAGE socket plus a legacy URL
                // field at the end; remove that old slot before LiteGraph maps values.
                const legacy = Array.isArray(values) && values.length > 3 &&
                    ["720p", "1080p"].includes(values[3]) &&
                    (typeof values[2] === "string") ? values.splice(2, 1)[0] : null;
                const result = originalConfigure?.apply(this, arguments);
                if (legacy !== null) {
                    const widget = this.widgets?.find(item => item.name === "reference_image_url");
                    if (widget && legacy && !legacy.includes("example.com/demo/reference.png")) widget.value = legacy;
                    this.properties ||= {};
                    this.properties.kieWidgetSchema = 2;
                    app.graph?.setDirtyCanvas?.(true, true);
                }
                return result;
            }
            const names = widgetNames(this);
            let migrated = false;
            if (Array.isArray(info?.widgets_values)) {
                migrated = migrateWan3WidgetValues(name, names, info.widgets_values) || migrated;
            }

            const result = originalConfigure?.apply(this, arguments);
            migrated = migrateLiveNode(this, name) || migrated;
            if (migrated) {
                this.properties ||= {};
                this.properties.kieWidgetSchema = 2;
                console.info("KIE Next: repaired legacy Wan 3.0 widget values", this.id);
                app.graph?.setDirtyCanvas?.(true, true);
            }
            return result;
        };
    },
});
