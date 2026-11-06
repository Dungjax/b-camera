"""Operators for managing and animating multiple focus Targets."""

import bpy
from bpy.props import EnumProperty, IntProperty
from bpy.types import Operator

from ..constants import FOLLOW_NAME
from ..helpers import (
    _add_scene_marker,
    _apply_target,
    _ensure_rig_structure,
    _set_interpolation,
    get_rig_camera,
)
from .base import _RigOperator


class CFR_OT_reset_focus(_RigOperator, Operator):
    bl_idname = "cfr.reset_focus"
    bl_label = "Reset Focus Follow"
    bl_description = "Remove the animated focus path and make the helper follow the primary Target again"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cam = get_rig_camera(context)
        if not _ensure_rig_structure(cam, context):
            return {'CANCELLED'}
        if cam.cfr.target is None:
            self.report({'WARNING'}, "Choose a primary Target first")
            return {'CANCELLED'}
        _apply_target(cam)
        self.report({'INFO'}, "Focus helper is following the primary Target again")
        return {'FINISHED'}

class CFR_OT_add_target(_RigOperator, Operator):
    bl_idname = "cfr.add_target"
    bl_label = "Add Selected Target"
    bl_description = "Add the selected object to the target transition sequence"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cam = get_rig_camera(context)
        if not _ensure_rig_structure(cam, context):
            return {'CANCELLED'}
        cfr = cam.cfr
        candidates = [obj for obj in context.selected_objects
                      if obj not in (cam, cfr.mover, cfr.focus_anchor, cfr.damping_pivot)]
        target = context.active_object if context.active_object in candidates else None
        if target is None and candidates:
            target = candidates[0]
        if target is None:
            target = cfr.target
        if target is None:
            self.report({'WARNING'}, "Select an object to add as a Target")
            return {'CANCELLED'}
        if any(item.target == target for item in cfr.target_slots):
            self.report({'INFO'}, "That Target is already in the sequence")
            return {'CANCELLED'}

        item = cfr.target_slots.add()
        item.target = target
        cfr.active_target_index = len(cfr.target_slots) - 1
        self.report({'INFO'}, "Target added to sequence")
        return {'FINISHED'}

class CFR_OT_remove_target(_RigOperator, Operator):
    bl_idname = "cfr.remove_target"
    bl_label = "Remove Target"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=0, min=0)

    def execute(self, context):
        cam = get_rig_camera(context)
        slots = cam.cfr.target_slots
        if self.index >= len(slots):
            return {'CANCELLED'}
        slots.remove(self.index)
        cam.cfr.active_target_index = min(max(0, self.index - 1), max(0, len(slots) - 1))
        return {'FINISHED'}

class CFR_OT_move_target(_RigOperator, Operator):
    bl_idname = "cfr.move_target"
    bl_label = "Reorder Target"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=0, min=0)
    direction: EnumProperty(items=[('UP', "Up", ""), ('DOWN', "Down", "")])

    def execute(self, context):
        slots = get_rig_camera(context).cfr.target_slots
        if self.index >= len(slots):
            return {'CANCELLED'}
        destination = self.index - 1 if self.direction == 'UP' else self.index + 1
        if destination < 0 or destination >= len(slots):
            return {'CANCELLED'}
        slots.move(self.index, destination)
        return {'FINISHED'}

class CFR_OT_transition_targets(_RigOperator, Operator):
    bl_idname = "cfr.transition_targets"
    bl_label = "Keyframe Target Transitions"
    bl_description = "Animate the focus point through the Targets in list order"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cam = get_rig_camera(context)
        if not _ensure_rig_structure(cam, context):
            return {'CANCELLED'}
        cfr = cam.cfr
        anchor = cfr.focus_anchor
        scene = context.scene

        targets = []
        seen = set()
        for item in cfr.target_slots:
            obj = item.target
            if obj is not None and obj != anchor and obj.as_pointer() not in seen:
                seen.add(obj.as_pointer())
                targets.append(obj)
        if len(targets) < 2:
            self.report({'WARNING'}, "Add at least two different Targets to the sequence")
            return {'CANCELLED'}

        start_frame = scene.frame_current
        start_position = anchor.matrix_world.translation.copy()
        points = [obj.matrix_world.translation.copy() for obj in targets]

        # If the first slot is already the current focus point, skip its duplicate
        # so the first segment immediately travels to the next Target.
        if points and (points[0] - start_position).length < 1e-5:
            points = points[1:]
        if not points:
            self.report({'WARNING'}, "The listed Targets occupy the current focus position")
            return {'CANCELLED'}

        follow = anchor.constraints.get(FOLLOW_NAME)
        if follow is not None:
            anchor.constraints.remove(follow)
        if anchor.animation_data is not None:
            anchor.animation_data_clear()
        anchor.location = start_position
        anchor.keyframe_insert(data_path="location", frame=start_frame, group="Target Transitions")

        frame = start_frame
        for position in points:
            frame += cfr.transition_frames
            anchor.location = position
            anchor.keyframe_insert(data_path="location", frame=frame, group="Target Transitions")

        _set_interpolation(anchor, "location", start_frame, frame,
                           cfr.transition_interpolation)
        scene.frame_end = max(scene.frame_end, frame)
        _add_scene_marker(scene, "CFR Targets Start", start_frame)
        _add_scene_marker(scene, "CFR Targets End", frame)
        scene.frame_set(start_frame)
        context.view_layer.update()

        self.report({'INFO'}, "Target transition path created: %d segments, frames %d-%d" %
                    (len(points), start_frame, frame))
        return {'FINISHED'}
