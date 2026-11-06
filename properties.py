"""Blender PropertyGroups that store per-object Camera Focus Rig settings."""

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
)
from bpy.types import PropertyGroup

from .helpers import _apply_orbit, _apply_target


def _poll_camera(self, obj):
    return obj.type == 'CAMERA'

def _poll_target(self, obj):
    return (obj != self.id_data and obj != self.mover
            and obj != self.focus_anchor and obj != self.damping_pivot)

def _update_target(self, context):
    _apply_target(self.id_data)

def _update_orbit(self, context):
    if self.is_rig:
        _apply_orbit(self.id_data)

class CFR_TargetItem(PropertyGroup):
    target: PointerProperty(
        name="Target",
        description="Object to include in the animated focus sequence",
        type=bpy.types.Object,
    )

class CFR_Props(PropertyGroup):
    is_rig: BoolProperty(default=False)
    camera: PointerProperty(type=bpy.types.Object, poll=_poll_camera)
    mover: PointerProperty(type=bpy.types.Object)
    focus_anchor: PointerProperty(type=bpy.types.Object)
    damping_pivot: PointerProperty(type=bpy.types.Object)
    target: PointerProperty(
        name="Target",
        description="Object the camera follows and focuses on",
        type=bpy.types.Object,
        poll=_poll_target,
        update=_update_target,
    )
    orbit_lock: BoolProperty(
        name="Orbit Lock",
        description="Keep the Mover at a fixed distance from the focus point",
        default=False,
        update=_update_orbit,
    )
    frame_margin: FloatProperty(
        name="Margin",
        description="Extra room around the Target when framing",
        default=1.2, min=1.0, max=5.0,
    )

    # Turntable settings
    turntable_frames: IntProperty(
        name="Duration",
        description="Turntable duration in frames, starting at the current frame",
        default=120, min=2, max=5000,
    )
    turntable_revolutions: FloatProperty(
        name="Revolutions",
        description="Number of full rotations (negative values reverse direction)",
        default=1.0, min=-20.0, max=20.0,
    )
    turntable_axis: EnumProperty(
        name="Axis",
        description="World-space axis around which the camera orbits",
        items=[('Z', "World Z / Up", "Horizontal turntable around the world up axis"),
               ('Y', "World Y", "Orbit around the world Y axis"),
               ('X', "World X", "Orbit around the world X axis")],
        default='Z',
    )
    turntable_loop: BoolProperty(
        name="Loop",
        description="Add Cycles modifiers for seamless repeated playback (requires whole revolutions)",
        default=False,
    )
    turntable_replace: BoolProperty(
        name="Replace Mover Animation",
        description="Clear existing Mover animation before generating the turntable",
        default=True,
    )

    # Damping settings. These values are applied by the Bake Damping operator.
    damping_position_enabled: BoolProperty(
        name="Position Damping",
        description="Smooth the camera position behind the animated Mover",
        default=True,
    )
    damping_rotation_enabled: BoolProperty(
        name="Rotation Damping",
        description="Smooth the camera orientation behind the animated Mover",
        default=True,
    )
    damping_position_time: FloatProperty(
        name="Position Response",
        description="Position follow time constant in seconds; higher values create more lag",
        default=0.20, min=0.0, max=5.0, precision=2,
    )
    damping_rotation_time: FloatProperty(
        name="Rotation Response",
        description="Rotation follow time constant in seconds; higher values create more lag",
        default=0.25, min=0.0, max=5.0, precision=2,
    )
    damping_start_frame: IntProperty(
        name="Start Frame",
        description="First frame to bake damping on (must be inside the Scene frame range)",
        default=1, min=-100000, max=1000000,
    )
    damping_end_frame: IntProperty(
        name="End Frame",
        description="Last frame to bake damping on (must be inside the Scene frame range)",
        default=250, min=-100000, max=1000000,
    )

    # Target transition settings
    target_slots: CollectionProperty(type=CFR_TargetItem)
    active_target_index: IntProperty(default=0, min=0)
    transition_frames: IntProperty(
        name="Frames / Target",
        description="Frames used to move from one target to the next",
        default=48, min=2, max=2000,
    )
    transition_interpolation: EnumProperty(
        name="Interpolation",
        items=[('BEZIER', "Smooth", "Ease between targets with smooth Bezier curves"),
               ('LINEAR', "Linear", "Move at a constant rate between target points")],
        default='BEZIER',
    )
