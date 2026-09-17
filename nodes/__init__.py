from __future__ import annotations

from .config import KIEConfigNode, KIEConnectionStatusNode, KIECreditsNode
from .generated import generated_node_mappings
from .media import (
    KIEDownloadFileNode,
    KIEDownloadImageNode,
    KIEDownloadVideoNode,
    KIEUploadAudioNode,
    KIEUploadFilePathNode,
    KIEUploadImageNode,
    KIEUploadVideoNode,
)
from .universal import (
    KIEAPIDescribeNode,
    KIECatalogSyncNode,
    KIETaskStatusNode,
    KIEUniversalTaskNode,
    KIEWaitTaskNode,
)
from .studio import STUDIO_CLASS_MAPPINGS, STUDIO_DISPLAY_NAME_MAPPINGS

# The public product is the generated model tree. Raw transport tools remain under
# Advanced for debugging/power-user workflows; "Any KIE API" is intentionally no
# longer registered in v0.3.
_BASE_CLASS_MAPPINGS = {
    "KIE_Next_Connection_Status": KIEConnectionStatusNode,
    "KIE_Next_Credits": KIECreditsNode,
    "KIE_Next_Catalog_Sync": KIECatalogSyncNode,
    "KIE_Next_Wait_Task": KIEWaitTaskNode,
    "KIE_Next_Task_Status": KIETaskStatusNode,
    "KIE_Next_Upload_Image": KIEUploadImageNode,
    "KIE_Next_Upload_Video": KIEUploadVideoNode,
    "KIE_Next_Upload_Audio": KIEUploadAudioNode,
    "KIE_Next_Upload_File_Path": KIEUploadFilePathNode,
    "KIE_Next_Download_Image": KIEDownloadImageNode,
    "KIE_Next_Download_Video": KIEDownloadVideoNode,
    "KIE_Next_Download_File": KIEDownloadFileNode,
    "KIE_Next_Config": KIEConfigNode,
    "KIE_Next_Universal_Task": KIEUniversalTaskNode,
    "KIE_Next_API_Describe": KIEAPIDescribeNode,
}
_BASE_CLASS_MAPPINGS.update(STUDIO_CLASS_MAPPINGS)

_BASE_DISPLAY_NAME_MAPPINGS = {
    "KIE_Next_Connection_Status": "KIE • Connection Status",
    "KIE_Next_Credits": "KIE • Credits",
    "KIE_Next_Catalog_Sync": "KIE • Refresh Model Catalog",
    "KIE_Next_Wait_Task": "KIE • Wait for Task",
    "KIE_Next_Task_Status": "KIE • Task Status",
    "KIE_Next_Upload_Image": "KIE • Upload Image",
    "KIE_Next_Upload_Video": "KIE • Upload Video",
    "KIE_Next_Upload_Audio": "KIE • Upload Audio",
    "KIE_Next_Upload_File_Path": "KIE • Upload File",
    "KIE_Next_Download_Image": "KIE • Download Image",
    "KIE_Next_Download_Video": "KIE • Download Video",
    "KIE_Next_Download_File": "KIE • Download File",
    "KIE_Next_Config": "KIE • Advanced Connection Override",
    "KIE_Next_Universal_Task": "KIE • Universal Market Task (Advanced)",
    "KIE_Next_API_Describe": "KIE • Inspect API Definition (Advanced)",
}
_BASE_DISPLAY_NAME_MAPPINGS.update(STUDIO_DISPLAY_NAME_MAPPINGS)

NODE_CLASS_MAPPINGS: dict[str, type] = dict(_BASE_CLASS_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS: dict[str, str] = dict(_BASE_DISPLAY_NAME_MAPPINGS)
_GENERATED_IDS: set[str] = set()


def refresh_generated_nodes() -> tuple[int, int]:
    """Rebuild live model nodes while preserving mapping object identity.

    ComfyUI imports NODE_CLASS_MAPPINGS once. Mutating the same dict in-place lets
    the backend catalog sync expose new KIE nodes to the next frontend object-info
    reload without forcing a ComfyUI server restart.
    """
    global _GENERATED_IDS
    for node_id in tuple(_GENERATED_IDS):
        NODE_CLASS_MAPPINGS.pop(node_id, None)
        NODE_DISPLAY_NAME_MAPPINGS.pop(node_id, None)

    generated_classes, generated_names = generated_node_mappings()
    NODE_CLASS_MAPPINGS.update(generated_classes)
    NODE_DISPLAY_NAME_MAPPINGS.update(generated_names)
    _GENERATED_IDS = set(generated_classes)
    return len(generated_classes), len(NODE_CLASS_MAPPINGS)


refresh_generated_nodes()

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "refresh_generated_nodes",
]

