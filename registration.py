"""Centralized Blender class and Object property registration."""

import bpy
from bpy.props import PointerProperty

from .properties import CFR_Props, CFR_TargetItem
from .operators import (
    CFR_OT_create_rig,
    CFR_OT_upgrade_rig,
    CFR_OT_frame_target,
    CFR_OT_mover_to_view,
    CFR_OT_select_part,
    CFR_OT_reset_focus,
    CFR_OT_add_target,
    CFR_OT_remove_target,
    CFR_OT_move_target,
    CFR_OT_transition_targets,
    CFR_OT_turntable,
    CFR_OT_setup_damping,
    CFR_OT_damping_scene_range,
    CFR_OT_bake_damping,
    CFR_OT_clear_damping,
    CFR_OT_reset_roll,
    CFR_OT_remove_rig,
)
from .ui import CFR_PT_panel


CLASSES = (
    CFR_TargetItem,
    CFR_Props,
    CFR_OT_create_rig,
    CFR_OT_upgrade_rig,
    CFR_OT_frame_target,
    CFR_OT_mover_to_view,
    CFR_OT_select_part,
    CFR_OT_reset_focus,
    CFR_OT_add_target,
    CFR_OT_remove_target,
    CFR_OT_move_target,
    CFR_OT_transition_targets,
    CFR_OT_turntable,
    CFR_OT_setup_damping,
    CFR_OT_damping_scene_range,
    CFR_OT_bake_damping,
    CFR_OT_clear_damping,
    CFR_OT_reset_roll,
    CFR_OT_remove_rig,
    CFR_PT_panel,
)


def register():
    """Register classes in dependency order; roll back on partial failure."""
    registered = []
    try:
        for cls in CLASSES:
            bpy.utils.register_class(cls)
            registered.append(cls)
        bpy.types.Object.cfr = PointerProperty(type=CFR_Props)
    except Exception:
        if hasattr(bpy.types.Object, "cfr"):
            del bpy.types.Object.cfr
        for cls in reversed(registered):
            try:
                bpy.utils.unregister_class(cls)
            except Exception:
                pass
        raise


def unregister():
    """Unregister the Object property and classes in reverse dependency order."""
    if hasattr(bpy.types.Object, "cfr"):
        del bpy.types.Object.cfr
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
