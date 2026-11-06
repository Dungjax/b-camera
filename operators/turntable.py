"""Automatic world-axis turntable animation operator."""

import math

from bpy.types import Operator
from mathutils import Quaternion, Vector

from ..helpers import (
    _action_fcurves,
    _add_scene_marker,
    _ensure_rig_structure,
    _set_interpolation,
    _set_world_pos,
    get_rig_camera,
)
from .base import _RigOperator


class CFR_OT_turntable(_RigOperator, Operator):
    bl_idname = "cfr.turntable"
    bl_label = "Generate Turntable"
    bl_description = "Create a world-axis orbit animation for the Mover"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cam = get_rig_camera(context)
        if not _ensure_rig_structure(cam, context):
            return {'CANCELLED'}
        cfr = cam.cfr
        mover = cfr.mover
        anchor = cfr.focus_anchor
        scene = context.scene

        duration = cfr.turntable_frames
        revolutions = cfr.turntable_revolutions
        if abs(revolutions) < 1e-6:
            self.report({'WARNING'}, "Revolutions must be non-zero")
            return {'CANCELLED'}

        axes = {'X': Vector((1.0, 0.0, 0.0)),
                'Y': Vector((0.0, 1.0, 0.0)),
                'Z': Vector((0.0, 0.0, 1.0))}
        axis = axes[cfr.turntable_axis]
        start_frame = scene.frame_current
        end_frame = start_frame + duration

        start_position = mover.matrix_world.translation.copy()
        start_focus = anchor.matrix_world.translation.copy()
        relative = start_position - start_focus
        if relative.length < 1e-5:
            self.report({'WARNING'}, "The Mover and focus point are too close")
            return {'CANCELLED'}
        if (relative - axis * relative.dot(axis)).length < 1e-5:
            self.report({'WARNING'}, "The selected orbit axis is parallel to the camera direction")
            return {'CANCELLED'}

        if cfr.turntable_replace and mover.animation_data is not None:
            mover.animation_data_clear()
        if cfr.turntable_replace:
            _set_world_pos(mover, start_position)

        # Sample every frame so a linear F-Curve follows a smooth circular path.
        for frame in range(start_frame, end_frame + 1):
            scene.frame_set(frame)
            context.view_layer.update()
            focus_position = anchor.matrix_world.translation.copy()
            angle = (2.0 * math.pi * revolutions *
                     ((frame - start_frame) / float(duration)))
            rotation = Quaternion(axis, angle)
            world_position = focus_position + rotation @ relative
            _set_world_pos(mover, world_position)
            mover.keyframe_insert(data_path="location", frame=frame, group="Turntable")

        _set_interpolation(mover, "location", start_frame, end_frame, 'LINEAR')

        if cfr.turntable_loop:
            if abs(revolutions - round(revolutions)) > 1e-4:
                self.report({'WARNING'}, "Loop needs a whole number of revolutions; Cycles modifier skipped")
            else:
                for curve in _action_fcurves(mover):
                    if curve.data_path == "location" and not any(m.type == 'CYCLES' for m in curve.modifiers):
                        modifier = curve.modifiers.new('CYCLES')
                        modifier.mode_before = 'REPEAT'
                        modifier.mode_after = 'REPEAT'

        scene.frame_end = max(scene.frame_end, end_frame)
        _add_scene_marker(scene, "CFR Turntable Start", start_frame)
        _add_scene_marker(scene, "CFR Turntable End", end_frame)
        scene.frame_set(start_frame)
        context.view_layer.update()

        self.report({'INFO'}, "Turntable created: %d frames, %.2f revolution(s)" %
                    (duration, revolutions))
        return {'FINISHED'}
