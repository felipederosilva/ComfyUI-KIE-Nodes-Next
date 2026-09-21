"""Compatibility helpers for ComfyUI's evolving input-media layout."""

from __future__ import annotations

import os
from collections.abc import Callable
from importlib import import_module


def recursive_input_files(input_dir: str, is_media: Callable[[str], bool]) -> list[str]:
    """Return media files relative to *input_dir*, using ComfyUI separators."""
    result: list[str] = []
    if not os.path.isdir(input_dir):
        return result

    for root, dirs, files in os.walk(input_dir, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(root, d)))
        for filename in files:
            path = os.path.join(root, filename)
            if not os.path.isfile(path):
                continue
            relative = os.path.relpath(path, input_dir).replace(os.sep, "/")
            if is_media(relative):
                result.append(relative)
    return sorted(result)


def media_file_options(folder_paths, media_types: list[str]) -> list[str]:
    """List compatible input files and durable output files for a media widget.

    ComfyUI accepts annotated ``[output]`` paths, but its built-in loaders only
    advertise top-level input files. Including the files here makes restored
    workflows valid without moving, copying, or rewriting user media.
    """
    def is_media(name: str) -> bool:
        return bool(folder_paths.filter_files_content_types([name], media_types))

    options = set(recursive_input_files(folder_paths.get_input_directory(), is_media))
    output_dir = getattr(folder_paths, "get_output_directory", lambda: "")()
    for name in recursive_input_files(output_dir, is_media):
        options.add(f"{name} [output]")
    return sorted(options)


def _patch_load_image(folder_paths, comfy_nodes) -> bool:
    load_image = getattr(comfy_nodes, "LoadImage", None)
    if load_image is None or getattr(load_image, "_kie_nested_media_compat", False):
        return False

    original_input_types = load_image.INPUT_TYPES

    def input_types(cls):
        types = original_input_types()
        required = types.get("required", {})
        image_spec = required.get("image")
        if not image_spec or not isinstance(image_spec, tuple) or not image_spec:
            return types

        current = list(image_spec[0]) if isinstance(image_spec[0], (list, tuple)) else []
        options = sorted(set(current).union(media_file_options(folder_paths, ["image"])))
        required["image"] = (options, *image_spec[1:])
        return types

    load_image.INPUT_TYPES = classmethod(input_types)
    load_image._kie_nested_media_compat = True
    return True


def _patch_schema_loader(module_name: str, class_name: str, field_name: str, media_types: list[str], folder_paths) -> bool:
    """Extend a Node 2.0 loader's combo options without changing its executor."""
    try:
        module = import_module(module_name)
        loader = getattr(module, class_name)
    except Exception:
        return False

    if getattr(loader, "_kie_nested_media_compat", False):
        return False

    original_define_schema = loader.define_schema

    def define_schema(cls):
        schema = original_define_schema()
        for input_spec in getattr(schema, "inputs", []):
            if getattr(input_spec, "id", None) == field_name:
                input_spec.options = media_file_options(folder_paths, media_types)
                break
        return schema

    loader.define_schema = classmethod(define_schema)
    loader._kie_nested_media_compat = True
    return True


def _patch_output_video_preview(folder_paths) -> bool:
    """Keep Load Video previews in the output folder when the value is annotated."""
    try:
        module = import_module("comfy_extras.nodes_video")
    except Exception:
        return False

    if getattr(module, "_kie_output_video_preview_compat", False):
        return False

    original_preview = module.preview_input_video

    def preview_input_video(file, video=None):
        name, base_dir = folder_paths.annotated_filepath(file)
        output_dir = folder_paths.get_output_directory()
        is_output = base_dir and os.path.normcase(os.path.realpath(base_dir)) == os.path.normcase(os.path.realpath(output_dir))
        if not is_output:
            return original_preview(file, video)

        subfolder, _, filename = name.replace("\\", "/").rpartition("/")
        result = module.ui.SavedResult(filename, subfolder, module.io.FolderType.output)
        if video is not None:
            module._preview_results[video] = (folder_paths.get_annotated_filepath(file), result)
        return module.ui.PreviewVideo([result])

    module.preview_input_video = preview_input_video
    module._kie_output_video_preview_compat = True
    return True


def install() -> bool:
    """Make ComfyUI loaders accept restored nested and output media paths."""
    try:
        import folder_paths  # type: ignore
        import nodes as comfy_nodes  # type: ignore
    except Exception:
        return False

    patched = _patch_load_image(folder_paths, comfy_nodes)
    patched = _patch_schema_loader(
        "comfy_extras.nodes_video", "LoadVideo", "file", ["video"], folder_paths
    ) or patched
    patched = _patch_output_video_preview(folder_paths) or patched
    patched = _patch_schema_loader(
        "comfy_extras.nodes_audio", "LoadAudio", "audio", ["audio", "video"], folder_paths
    ) or patched
    return patched
