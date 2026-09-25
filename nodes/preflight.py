"""Read-only bridge for the node's Check inputs / model controls action."""
from __future__ import annotations

from ..kie.catalog import load_catalog
from ..kie.capabilities import operation_capabilities
from .generated import _friendly_input_types, _media_aliases, _payload_template, kind_for, preflight_llm_inputs, preflight_model_inputs
from .studio import KIEKlingOmniStudioNode, KIESeedanceStudioNode, _studio_report, studio_operation


def inspect_node_inputs(node_type: str, inputs: dict, connected: list) -> dict:
    from . import NODE_CLASS_MAPPINGS

    cls = NODE_CLASS_MAPPINGS.get(node_type)
    if cls is None:
        raise ValueError("This node is not registered. Reload ComfyUI's node catalog.")
    inputs = dict(inputs)
    op = getattr(cls, "OP", None)
    model = getattr(cls, "MODEL", "")
    if op is not None:
        op = next((candidate for candidate in load_catalog().get("operations", [])
                   if candidate.get("docs_url") == op.get("docs_url") and op.get("docs_url")), op)
        if kind_for(op) == "llm":
            return preflight_llm_inputs(op, model, inputs, deferred_fields=connected)
        widgets = _friendly_input_types(op, model=model)
    elif cls in (KIEKlingOmniStudioNode, KIESeedanceStudioNode):
        widgets = cls.INPUT_TYPES()
    else:
        raise ValueError("Input inspection is available for generation and Studio nodes.")
    specs = {**widgets.get("required", {}), **widgets.get("optional", {})}
    deferred = set()
    scalar_links = set()
    for name in connected:
        if name not in specs:
            continue
        deferred.add(name)
        if specs[name][0] in ("IMAGE", "VIDEO", "AUDIO"):
            inputs[name] = object()  # Presence only: never open or upload connected media.
        else:
            scalar_links.add(name)
            inputs.pop(name, None)
    if op is not None:
        body, _ = _payload_template(op)
        for name, value in body.items():
            if any(alias in deferred for alias, _, _ in _media_aliases(name, value)):
                deferred.add(name)
        for name, hint in (op.get("parameter_hints") or {}).items():
            if any(alias in deferred for alias, _, _ in _media_aliases(name, [] if hint.get("type") == "array" else None)):
                deferred.add(name)
        try:
            return preflight_model_inputs(op, model, inputs, deferred_fields=deferred)
        except (ValueError, TypeError) as exc:
            return {"valid": False, "errors": [str(exc)], "warnings": [], "capabilities": operation_capabilities(op, model),
                    "scope": "Local input check; no media uploaded and no generation submitted."}
    default_model = "bytedance/seedance-2" if cls is KIESeedanceStudioNode else (
        "kling-3.0-omni/image-to-video" if "first_frame" in deferred else "kling-3.0-omni/text-to-video")
    model = inputs.get("model", default_model)
    op = studio_operation(model)
    if scalar_links:
        return {"valid": True, "errors": [], "warnings": ["Studio validation requires the connected values at execution: " + ", ".join(sorted(scalar_links))],
                "capabilities": operation_capabilities(op, model), "scope": "Partial inspection; connected values are not evaluated by this action."}
    try:
        model, payload = cls().prepare_request(**inputs, dry_run=True)
        report = _studio_report(model, payload)
    except (ValueError, TypeError, IndexError) as exc:
        report = {"valid": False, "errors": [str(exc)], "warnings": [], "capabilities": operation_capabilities(op, model)}
    if deferred:
        report["warnings"].append("Connected media was checked for presence only; batch size and content are unavailable until execution.")
    report["scope"] = "Local input check; no media uploaded and no generation submitted."
    return report
