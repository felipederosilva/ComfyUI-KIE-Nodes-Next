import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

let internalUpdate = false;
let lastStatus = null;

function toast(severity, summary, detail = "") {
    try {
        app.extensionManager.toast.add({ severity, summary, detail, life: 5000 });
    } catch (e) {
        try { app.extensionManager.toast.addAlert(`${summary}${detail ? `\n${detail}` : ""}`); } catch (_) {}
    }
}

function statusText(status) {
    if (!status?.configured) return "⚪ No API key saved";
    const credits = status?.last_credits;
    const creditsText = Number.isFinite(Number(credits)) ? ` • ${Number(credits).toLocaleString()} credits` : "";
    const keyText = status?.masked_key ? ` • ${status.masked_key}` : "";
    const state = String(status?.validation_state || "");
    if (state === "connected") return `✅ CONNECTED${keyText}${creditsText}`;
    if (state === "invalid") return `❌ SAVED KEY REJECTED BY KIE${keyText}`;
    if (state === "unreachable") return `⚠️ KEY SAVED • KIE currently unreachable${keyText}`;
    if (state === "environment") return `✅ CONNECTED through KIE_API_KEY${keyText}${creditsText}`;
    return `✅ KEY SAVED${keyText}${creditsText}`;
}

function savedKeyText(status) {
    if (!status?.configured) return "No saved key";
    const where = status?.source === "environment" ? "Environment variable" : "Saved in ComfyUI backend";
    return `🔐 ${where} • ${status?.masked_key || "••••"}`;
}

async function setSetting(id, value) {
    internalUpdate = true;
    try {
        await app.extensionManager.setting.set(id, value);
    } finally {
        internalUpdate = false;
    }
}

async function applyStatus(status) {
    lastStatus = status;
    await setSetting("KIE.Next.SavedKey", savedKeyText(status));
    await setSetting("KIE.Next.ConnectionState", statusText(status));
    if (status?.plugin_version) await setSetting("KIE.Next.PluginVersion", `v${status.plugin_version}`);
    if (status?.plugin_path) await setSetting("KIE.Next.PluginPath", String(status.plugin_path));
}

async function getStatus() {
    const res = await api.fetchApi("/kie-next/settings");
    if (!res.ok) throw new Error(await res.text());
    const status = await res.json();
    await applyStatus(status);
    return status;
}

async function saveKey(value) {
    const key = String(value || "").trim();
    if (!key || internalUpdate) return;

    await setSetting("KIE.Next.ConnectionState", "⏳ Validating new API key with KIE.ai…");
    const res = await api.fetchApi("/kie-next/settings/api-key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: key }),
    });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) {
        await getStatus().catch(() => {});
        const unreachable = payload?.attempt_validation_state === "unreachable";
        toast(
            unreachable ? "warn" : "error",
            unreachable ? "KIE.ai could not be reached" : "KIE.ai rejected that API key",
            "Your previously saved key was not replaced."
        );
        throw new Error(payload?.error || "Could not validate API key");
    }

    await applyStatus(payload);
    // This is now intentional and visually confirmed by the separate Saved key row.
    // Leaving secrets in the frontend settings store would be worse than clearing it.
    await setSetting("KIE.Next.APIKey", "");
    const credits = Number.isFinite(Number(payload?.credits)) ? `${Number(payload.credits).toLocaleString()} credits available.` : "";
    toast("success", "KIE.ai API key saved and connected", `${payload?.masked_key || "Key saved"}. ${credits}`.trim());
}

async function testConnection({ notify = true } = {}) {
    await setSetting("KIE.Next.ConnectionState", "⏳ Testing saved KIE.ai key…");
    const res = await api.fetchApi("/kie-next/settings/test", { method: "POST" });
    const payload = await res.json().catch(() => ({}));
    await applyStatus(payload);
    if (notify) {
        if (res.ok) toast("success", "KIE.ai connection OK", statusText(payload));
        else toast("error", "KIE.ai connection failed", payload?.error || "Check the saved key and network connection.");
    }
    return payload;
}

async function clearSavedKey() {
    const res = await api.fetchApi("/kie-next/settings/api-key", { method: "DELETE" });
    const payload = await res.json().catch(() => ({}));
    await applyStatus(payload);
    await setSetting("KIE.Next.APIKey", "");
    toast("info", "KIE.ai API key removed", "KIE Next no longer has a backend-saved key.");
}

async function refreshCatalogIfNeeded() {
    try {
        const statusRes = await api.fetchApi("/kie-next/settings");
        if (!statusRes.ok) return;
        const status = await statusRes.json();
        const catalog = status?.catalog || {};
        const age = Number(catalog.age_seconds ?? 999999999);
        const oldOps = Number(catalog.operations ?? 0);
        const deepDone = catalog.deep_sync_complete === true;

        // v0.3 ships a small polished bootstrap catalog, then fills the entire
        // official KIE model/API tree automatically from KIE's live documentation.
        if (oldOps === 0) {
            await setSetting("KIE.Next.CatalogState", "⏳ Discovering every KIE model/API…");
            const indexRes = await api.fetchApi("/kie-next/catalog/index", { method: "POST" });
            if (!indexRes.ok) return;
            const indexed = await indexRes.json();
            await setSetting("KIE.Next.CatalogState", `✅ ${Number(indexed?.operations || 0)} API pages discovered • building controls…`);
        }

        if (!deepDone) {
            await setSetting("KIE.Next.CatalogState", `⏳ Building individual model nodes from KIE's official docs…`);
            const syncRes = await api.fetchApi("/kie-next/catalog/sync", { method: "POST" });
            if (!syncRes.ok) return;
            const synced = await syncRes.json();
            await setSetting("KIE.Next.CatalogState", `✅ ${Number(synced?.models || 0)} model IDs • ${Number(synced?.operations || 0)} individual APIs ready`);
            if (synced?.deep_sync_complete === true) {
                const marker = `KIE.Next.V03DeepReloaded.${synced?.generated_at || "now"}`;
                if (sessionStorage.getItem(marker) !== "1") {
                    sessionStorage.setItem(marker, "1");
                    toast("success", "KIE model library ready", `${Number(synced?.operations || 0)} official KIE API pages were turned into individual nodes.`);
                    setTimeout(() => window.location.reload(), 600);
                }
            }
            return;
        }

        await setSetting("KIE.Next.CatalogState", `✅ ${Number(catalog.models || 0)} model IDs • ${Number(catalog.operations || 0)} individual APIs ready`);
        if (age >= 24 * 60 * 60) {
            const syncRes = await api.fetchApi("/kie-next/catalog/sync", { method: "POST" });
            if (syncRes.ok) {
                const synced = await syncRes.json();
                await setSetting("KIE.Next.CatalogState", `✅ ${Number(synced?.models || 0)} model IDs • ${Number(synced?.operations || 0)} individual APIs ready`);
            }
        }
    } catch (e) {
        console.warn("KIE Next: catalog auto-sync failed", e);
        await setSetting("KIE.Next.CatalogState", "⚠️ Live catalog refresh failed • cached individual nodes remain available");
    }
}

app.registerExtension({
    name: "KIE.Nodes.Next.Settings",
    settings: [
        {
            id: "KIE.Next.APIKey",
            name: "Paste / replace KIE.ai API key",
            type: "text",
            defaultValue: "",
            category: ["KIE.ai Nodes Next", "Connection", "API key"],
            tooltip: "Paste once. KIE Next validates the key with KIE.ai before saving it on the backend. The full key is never stored in the workflow or kept in this frontend field.",
            attrs: { type: "password", autocomplete: "off", placeholder: "Paste a KIE API key, then wait for confirmation" },
            onChange: async (_setting, newVal) => {
                // Current Comfy calls onChange(setting, new, old); older builds may
                // pass only the value. Handle both without forcing users to update.
                const value = typeof newVal === "undefined" ? _setting : newVal;
                if (!value || internalUpdate) return;
                try { await saveKey(value); } catch (e) { console.error("KIE Next: could not save API key", e); }
            },
        },
        {
            id: "KIE.Next.SavedKey",
            name: "Saved API key",
            type: "text",
            defaultValue: "Checking backend…",
            category: ["KIE.ai Nodes Next", "Connection", "Saved key"],
            tooltip: "Persistent backend state. Only a masked fingerprint is shown here so you can verify which key is saved.",
            attrs: { readonly: true, disabled: true },
        },
        {
            id: "KIE.Next.ConnectionState",
            name: "KIE.ai connection",
            type: "text",
            defaultValue: "Checking…",
            category: ["KIE.ai Nodes Next", "Connection", "Status"],
            tooltip: "A green CONNECTED state means KIE.ai accepted the saved key. Credits are shown after a successful validation.",
            attrs: { readonly: true, disabled: true },
        },
        {
            id: "KIE.Next.TestConnectionTrigger",
            name: "Test saved key now",
            type: "boolean",
            defaultValue: false,
            category: ["KIE.ai Nodes Next", "Connection", "Test"],
            tooltip: "Turn on once to validate the saved backend key again. It automatically switches back off.",
            onChange: async (_setting, newVal) => {
                const value = typeof newVal === "undefined" ? _setting : newVal;
                if (!value || internalUpdate) return;
                try { await testConnection(); } finally { await setSetting("KIE.Next.TestConnectionTrigger", false); }
            },
        },
        {
            id: "KIE.Next.ClearKeyTrigger",
            name: "Remove saved API key",
            type: "boolean",
            defaultValue: false,
            category: ["KIE.ai Nodes Next", "Connection", "Remove"],
            tooltip: "Turn on once to delete the backend-saved API key. It automatically switches back off.",
            onChange: async (_setting, newVal) => {
                const value = typeof newVal === "undefined" ? _setting : newVal;
                if (!value || internalUpdate) return;
                try { await clearSavedKey(); } finally { await setSetting("KIE.Next.ClearKeyTrigger", false); }
            },
        },
        {
            id: "KIE.Next.PluginVersion",
            name: "Loaded KIE Next version",
            type: "text",
            defaultValue: "Checking backend...",
            category: ["KIE.ai Nodes Next", "Diagnostics", "Version"],
            tooltip: "This is the version actually loaded by the running ComfyUI backend, not the installer version.",
            attrs: { readonly: true, disabled: true },
        },
        {
            id: "KIE.Next.PluginPath",
            name: "Loaded from folder",
            type: "text",
            defaultValue: "Checking backend...",
            category: ["KIE.ai Nodes Next", "Diagnostics", "Path"],
            tooltip: "Exact folder imported by ComfyUI. Useful for detecting duplicate installations.",
            attrs: { readonly: true, disabled: true },
        },
        {
            id: "KIE.Next.CatalogState",
            name: "Individual model library",
            type: "text",
            defaultValue: "Loading…",
            category: ["KIE.ai Nodes Next", "Models", "Catalog status"],
            attrs: { readonly: true, disabled: true },
        },
        {
            id: "KIE.Next.AutoCatalogSync",
            name: "Automatically keep KIE model nodes current",
            type: "boolean",
            defaultValue: true,
            category: ["KIE.ai Nodes Next", "Models", "Auto refresh"],
            tooltip: "Uses KIE's official API docs to add/update individual model nodes when KIE releases new APIs. Refreshes at most once per day after the first full sync.",
        },
    ],
    async setup() {
        try { await getStatus(); } catch (e) { console.warn("KIE Next: settings status failed", e); }
        if (app.extensionManager.setting.get("KIE.Next.AutoCatalogSync") !== false) {
            setTimeout(() => refreshCatalogIfNeeded(), 1200);
        }
    },
});

window.KIENextTestConnection = testConnection;

