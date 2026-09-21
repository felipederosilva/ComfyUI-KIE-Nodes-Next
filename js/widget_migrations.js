const WAN_3_NODE_IDS = new Set([
    "KIE_Next_wan_3_0_video_f9eae250",
    "KIE_Next_wan_3_0_video_prime_7a7b762c",
]);

function normalizedName(value) {
    return String(value || "").trim().toLowerCase().replace(/[\s-]+/g, "_");
}

function indexOfWidget(widgetNames, wanted) {
    const target = normalizedName(wanted);
    return widgetNames.findIndex((name) => normalizedName(name) === target);
}

function booleanValue(value, fallback = false) {
    if (typeof value === "boolean") return value;
    if (typeof value === "number") return value !== 0;
    const text = String(value ?? "").trim().toLowerCase();
    if (["true", "1", "yes", "on"].includes(text)) return true;
    if (["false", "0", "no", "off", ""].includes(text)) return false;
    return fallback;
}

/**
 * Repair workflows saved while Wan's boolean ``audio`` field was incorrectly
 * exposed as an AUDIO socket. Adding the proper boolean widget shifted the
 * remaining serialized values by one position: seed received ``randomize``,
 * nsfw received the timeout, and timeout received the callback string.
 *
 * The distinctive seed/control mismatch makes the migration idempotent and
 * avoids touching workflows already saved with the corrected schema.
 */
export function migrateWan3WidgetValues(nodeType, widgetNames, values) {
    if (!WAN_3_NODE_IDS.has(String(nodeType || ""))) return false;
    if (!Array.isArray(widgetNames) || !Array.isArray(values)) return false;

    const seedIndex = indexOfWidget(widgetNames, "seed");
    const controlIndex = indexOfWidget(widgetNames, "control_after_generate");
    const nsfwIndex = indexOfWidget(widgetNames, "nsfw_checker");
    const timeoutIndex = indexOfWidget(widgetNames, "timeout_seconds");
    const callbackIndex = indexOfWidget(widgetNames, "callback_url");
    if (seedIndex < 0 || controlIndex < 0) return false;

    const modes = new Set(["fixed", "increment", "decrement", "randomize"]);
    const staleMode = String(values[seedIndex] || "").trim().toLowerCase();
    if (!modes.has(staleMode)) return false;

    const previous = values.slice();
    values[seedIndex] = 0;
    values[controlIndex] = staleMode;
    if (nsfwIndex >= 0 && controlIndex < previous.length) {
        values[nsfwIndex] = booleanValue(previous[controlIndex], false);
    }
    if (timeoutIndex >= 0 && nsfwIndex >= 0) {
        const timeout = Number(previous[nsfwIndex]);
        values[timeoutIndex] = Number.isFinite(timeout) && timeout >= 30 ? Math.trunc(timeout) : 1200;
    }
    if (callbackIndex >= 0 && timeoutIndex >= 0 && typeof previous[timeoutIndex] === "string") {
        values[callbackIndex] = previous[timeoutIndex];
    }
    return true;
}

