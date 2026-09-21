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
        if (!name.startsWith("KIE_Next_wan_3_0_video")) return;

        const originalConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (info) {
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

