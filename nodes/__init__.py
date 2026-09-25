from __future__ import annotations

from .config import KIEConfigNode, KIEConnectionStatusNode, KIECreditsNode
from .generated import generated_node_mappings
from .media import (
    KIEDownloadFileNode,
    KIEDownloadImageNode,
    KIEDownloadVideoNode,
    KIEPersistentPreviewImageNode,
    KIEPersistentLoadVideoNode,
    KIEPreviewVideoNode,
    KIESaveVideoNode,
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
from .characters import CHARACTER_CLASS_MAPPINGS, CHARACTER_DISPLAY_NAME_MAPPINGS
from .storyboard import KIEStoryboardContactSheetNode
from .planning import KIEScriptToShotDraftNode, KIEShotPlanReviewNode
from .elements import ELEMENT_CLASS_MAPPINGS, ELEMENT_DISPLAY_NAME_MAPPINGS
from .character_variants import VARIANT_CLASS_MAPPINGS, VARIANT_DISPLAY_NAME_MAPPINGS
from .consistency_board import KIEConsistencyBoardNode
from .video_events import KIEVideoEventAnalysisNode, KIEMusicBriefNode
from .reuse import REUSE_CLASS_MAPPINGS, REUSE_DISPLAY_NAME_MAPPINGS
from .recipes import RECIPE_CLASS_MAPPINGS, RECIPE_DISPLAY_NAME_MAPPINGS
from .camera_path import KIECameraPathNode
from .variations import KIEVariationMatrixNode
from .sound_cues import KIESoundCueSheetNode
from .task_board import KIETaskBoardNode
from .assembly import KIEAssembleVideoNode
from .text_review import KIETextReviewNode
from .variation_board import KIEVariationBoardNode
from .sfx_prompt import KIESFXPromptNode
from .semantic_events import KIEVideoFrameSamplerNode, KIEReviewedEventsNode

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
    "KIE_Next_Persistent_Preview_Image": KIEPersistentPreviewImageNode,
    "KIE_Next_Persistent_Load_Video": KIEPersistentLoadVideoNode,
    "KIE_Next_Preview_Video": KIEPreviewVideoNode,
    "KIE_Next_Save_Video": KIESaveVideoNode,
    "KIE_Next_Storyboard_Contact_Sheet": KIEStoryboardContactSheetNode,
    "KIE_Next_Script_To_Shot_Draft": KIEScriptToShotDraftNode,
    "KIE_Next_Shot_Plan_Review": KIEShotPlanReviewNode,
    "KIE_Next_Consistency_Board": KIEConsistencyBoardNode,
    "KIE_Next_Video_Event_Analysis": KIEVideoEventAnalysisNode,
    "KIE_Next_Music_Brief": KIEMusicBriefNode,
    "KIE_Next_Camera_Path": KIECameraPathNode,
    "KIE_Next_Variation_Matrix": KIEVariationMatrixNode,
    "KIE_Next_Sound_Cue_Sheet": KIESoundCueSheetNode,
    "KIE_Next_Task_Board": KIETaskBoardNode,
    "KIE_Next_Assemble_Video": KIEAssembleVideoNode,
    "KIE_Next_Text_Review": KIETextReviewNode,
    "KIE_Next_Variation_Board": KIEVariationBoardNode,
    "KIE_Next_SFX_Prompt": KIESFXPromptNode,
    "KIE_Next_Video_Frame_Sampler": KIEVideoFrameSamplerNode,
    "KIE_Next_Reviewed_Events": KIEReviewedEventsNode,
    "KIE_Next_Config": KIEConfigNode,
    "KIE_Next_Universal_Task": KIEUniversalTaskNode,
    "KIE_Next_API_Describe": KIEAPIDescribeNode,
}
_BASE_CLASS_MAPPINGS.update(STUDIO_CLASS_MAPPINGS)
_BASE_CLASS_MAPPINGS.update(CHARACTER_CLASS_MAPPINGS)
_BASE_CLASS_MAPPINGS.update(ELEMENT_CLASS_MAPPINGS)
_BASE_CLASS_MAPPINGS.update(VARIANT_CLASS_MAPPINGS)
_BASE_CLASS_MAPPINGS.update(REUSE_CLASS_MAPPINGS)
_BASE_CLASS_MAPPINGS.update(RECIPE_CLASS_MAPPINGS)

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
    "KIE_Next_Persistent_Preview_Image": "KIE • Persistent Preview Image",
    "KIE_Next_Persistent_Load_Video": "KIE • Persistent Load Video",
    "KIE_Next_Preview_Video": "KIE • Preview Video",
    "KIE_Next_Save_Video": "KIE • Save Video",
    "KIE_Next_Storyboard_Contact_Sheet": "KIE • Storyboard Contact Sheet",
    "KIE_Next_Script_To_Shot_Draft": "KIE • Script to Shot Draft",
    "KIE_Next_Shot_Plan_Review": "KIE • Shot Plan Review",
    "KIE_Next_Consistency_Board": "KIE • Consistency Board",
    "KIE_Next_Video_Event_Analysis": "KIE • Video Event Analysis",
    "KIE_Next_Music_Brief": "KIE • Music Brief from Video",
    "KIE_Next_Camera_Path": "KIE • Camera Path",
    "KIE_Next_Variation_Matrix": "KIE • Variation Matrix",
    "KIE_Next_Sound_Cue_Sheet": "KIE • Sound Cue Sheet",
    "KIE_Next_Task_Board": "KIE • Task Board",
    "KIE_Next_Assemble_Video": "KIE • Assemble Video + Music",
    "KIE_Next_Text_Review": "KIE • Review Text",
    "KIE_Next_Variation_Board": "KIE • Variation Board",
    "KIE_Next_SFX_Prompt": "KIE • SFX Prompt from Cue",
    "KIE_Next_Video_Frame_Sampler": "KIE • Sample Video Frames",
    "KIE_Next_Reviewed_Events": "KIE • Review Video Events",
    "KIE_Next_Config": "KIE • Advanced Connection Override",
    "KIE_Next_Universal_Task": "KIE • Universal Market Task (Advanced)",
    "KIE_Next_API_Describe": "KIE • Inspect API Definition (Advanced)",
}
_BASE_DISPLAY_NAME_MAPPINGS.update(STUDIO_DISPLAY_NAME_MAPPINGS)
_BASE_DISPLAY_NAME_MAPPINGS.update(CHARACTER_DISPLAY_NAME_MAPPINGS)
_BASE_DISPLAY_NAME_MAPPINGS.update(ELEMENT_DISPLAY_NAME_MAPPINGS)
_BASE_DISPLAY_NAME_MAPPINGS.update(VARIANT_DISPLAY_NAME_MAPPINGS)
_BASE_DISPLAY_NAME_MAPPINGS.update(REUSE_DISPLAY_NAME_MAPPINGS)
_BASE_DISPLAY_NAME_MAPPINGS.update(RECIPE_DISPLAY_NAME_MAPPINGS)

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

