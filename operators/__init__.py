"""Registered operator classes grouped by feature."""

from .rig import (
    CFR_OT_create_rig,
    CFR_OT_frame_target,
    CFR_OT_mover_to_view,
    CFR_OT_remove_rig,
    CFR_OT_reset_roll,
    CFR_OT_select_part,
    CFR_OT_upgrade_rig,
)
from .targets import (
    CFR_OT_add_target,
    CFR_OT_move_target,
    CFR_OT_remove_target,
    CFR_OT_reset_focus,
    CFR_OT_transition_targets,
)
from .turntable import CFR_OT_turntable
from .damping import (
    CFR_OT_bake_damping,
    CFR_OT_clear_damping,
    CFR_OT_damping_scene_range,
    CFR_OT_setup_damping,
)

__all__ = (
    "CFR_OT_create_rig",
    "CFR_OT_upgrade_rig",
    "CFR_OT_frame_target",
    "CFR_OT_mover_to_view",
    "CFR_OT_select_part",
    "CFR_OT_reset_focus",
    "CFR_OT_add_target",
    "CFR_OT_remove_target",
    "CFR_OT_move_target",
    "CFR_OT_transition_targets",
    "CFR_OT_turntable",
    "CFR_OT_setup_damping",
    "CFR_OT_damping_scene_range",
    "CFR_OT_bake_damping",
    "CFR_OT_clear_damping",
    "CFR_OT_reset_roll",
    "CFR_OT_remove_rig",
)
