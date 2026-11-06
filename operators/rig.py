"""Operators for rig creation, maintenance, camera control, and cleanup."""

import math

import bpy
from bpy.props import EnumProperty, FloatProperty
from bpy.types import Operator
from mathutils import Matrix, Vector

from ..constants import FOLLOW_NAME, LIMIT_NAME, TRACK_NAME
from ..helpers import (
    _ensure_damping_pivot,
    _ensure_rig_structure,
    _focus_object,
    _min_fov,
    _min_target_radius,
    _select_only,
    _set_world_pos,
    get_rig_camera,
)
from .base import _RigOperator


class CFR_OT_create_rig(Operator):
    bl_idname = "cfr.create_rig"
    bl_label = "Create Focus Rig"
    bl_description = "Create a camera rig from the current selection"
    bl_options = {'REGISTER', 'UNDO'}

    distance: FloatProperty(
        name="Distance",
        description="Starting distance from camera to Target (0 = automatic)",
        default=0.0, min=0.0, unit='LENGTH',
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    @staticmethod
    def _view_dir(context):
        """Direction from the scene toward the current 3D viewport eye."""
        space = context.space_data
        if space is not None and space.type == 'VIEW_3D' and space.region_3d is not None:
            direction = space.region_3d.view_rotation @ Vector((0.0, 0.0, 1.0))
            if direction.length > 1e-6:
                return direction.normalized()
        return Vector((0.0, -1.0, 0.5)).normalized()

    def execute(self, context):
        scene = context.scene
        collection = context.collection or scene.collection
        selected = list(context.selected_objects)
        active = context.active_object

        cam = next((obj for obj in selected if obj.type == 'CAMERA'), None)
        if cam is not None and cam.cfr.is_rig:
            self.report({'ERROR'}, "This camera already has a focus rig")
            return {'CANCELLED'}

        non_cameras = [obj for obj in selected if obj.type != 'CAMERA']
        target = active if active in non_cameras else (non_cameras[0] if non_cameras else None)
        if target is None:
            target = bpy.data.objects.new("FocusTarget", None)
            target.empty_display_type = 'SPHERE'
            target.empty_display_size = 0.5
            target.location = scene.cursor.location
            collection.objects.link(target)
            target_position = scene.cursor.location.copy()
            target_size = 0.0
        else:
            target_position = target.matrix_world.translation.copy()
            target_size = max(target.dimensions)

        distance = self.distance if self.distance > 0.0 else max(target_size * 2.5, 6.0)

        if cam is not None:
            mover_position = cam.matrix_world.translation.copy()
        else:
            camera_data = bpy.data.cameras.new("FocusCam")
            cam = bpy.data.objects.new("FocusCam", camera_data)
            collection.objects.link(cam)
            mover_position = target_position + self._view_dir(context) * distance

        mover = bpy.data.objects.new(cam.name + "_Mover", None)
        mover.empty_display_type = 'ARROWS'
        mover.empty_display_size = 0.6
        collection.objects.link(mover)
        mover.location = mover_position

        anchor = bpy.data.objects.new(cam.name + "_FocusPoint", None)
        anchor.empty_display_type = 'SPHERE'
        anchor.empty_display_size = 0.22
        anchor.show_in_front = True
        anchor.hide_render = True
        collection.objects.link(anchor)
        anchor.location = target_position

        # The Mover aims at the helper; the camera child can now roll locally.
        track = mover.constraints.new('TRACK_TO')
        track.name = TRACK_NAME
        track.target = anchor
        track.track_axis = 'TRACK_NEGATIVE_Z'
        track.up_axis = 'UP_Y'

        cam.parent = mover
        cam.matrix_parent_inverse = Matrix.Identity(4)
        cam.location = (0.0, 0.0, 0.0)
        cam.rotation_mode = 'XYZ'
        cam.rotation_euler = (0.0, 0.0, 0.0)

        cam.data.dof.use_dof = True
        cam.data.dof.focus_object = anchor
        cam.data.dof.aperture_fstop = 2.8

        cam.cfr.mover = mover
        cam.cfr.focus_anchor = anchor
        cam.cfr.is_rig = True
        cam.cfr.target = target
        mover.cfr.camera = cam
        anchor.cfr.camera = cam
        if target.cfr.camera is None:
            target.cfr.camera = cam

        cam.cfr.target_slots.clear()
        first_slot = cam.cfr.target_slots.add()
        first_slot.target = target
        cam.cfr.active_target_index = 0
        cam.cfr.damping_start_frame = int(scene.frame_start)
        cam.cfr.damping_end_frame = int(scene.frame_end)
        _ensure_damping_pivot(cam, context)

        scene.camera = cam
        _select_only(context, mover)
        self.report({'INFO'}, "Rig created. Move Mover; adjust Roll on the camera child.")
        return {'FINISHED'}

class CFR_OT_upgrade_rig(_RigOperator, Operator):
    bl_idname = "cfr.upgrade_rig"
    bl_label = "Upgrade Rig for Roll & Animation"
    bl_description = "Move Track To from the camera to the Mover and create a focus helper"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cam = get_rig_camera(context)
        if not _ensure_rig_structure(cam, context):
            self.report({'ERROR'}, "Could not upgrade this rig")
            return {'CANCELLED'}
        self.report({'INFO'}, "Rig upgraded. Roll and animated target transitions are ready.")
        return {'FINISHED'}

class CFR_OT_frame_target(_RigOperator, Operator):
    bl_idname = "cfr.frame_target"
    bl_label = "Frame Target"
    bl_description = "Move the Mover so the Target fits in frame"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        cam = get_rig_camera(context)
        return (cam is not None and cam.cfr.mover is not None and cam.cfr.target is not None)

    def execute(self, context):
        cam = get_rig_camera(context)
        if not _ensure_rig_structure(cam, context):
            return {'CANCELLED'}
        cfr = cam.cfr
        target = cfr.target
        mover = cfr.mover

        distance = _min_target_radius(target) / math.sin(_min_fov(cam, context.scene) * 0.5)
        distance *= cfr.frame_margin

        target_position = target.matrix_world.translation
        direction = mover.matrix_world.translation - target_position
        if direction.length < 1e-6:
            direction = Vector((0.0, -1.0, 0.3))
        direction.normalize()

        _set_world_pos(mover, target_position + direction * distance)
        limit = mover.constraints.get(LIMIT_NAME)
        if limit is not None:
            limit.distance = distance
        return {'FINISHED'}

class CFR_OT_mover_to_view(_RigOperator, Operator):
    bl_idname = "cfr.mover_to_view"
    bl_label = "Snap Mover to View"
    bl_description = "Move the Mover to the current perspective viewport eye"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (super().poll(context) and space is not None
                and space.type == 'VIEW_3D' and space.region_3d is not None)

    def execute(self, context):
        cam = get_rig_camera(context)
        if not _ensure_rig_structure(cam, context):
            return {'CANCELLED'}
        region = context.space_data.region_3d
        if not region.is_perspective:
            self.report({'WARNING'}, "Use a perspective view")
            return {'CANCELLED'}

        eye = region.view_matrix.inverted().translation.copy()
        _set_world_pos(cam.cfr.mover, eye)
        limit = cam.cfr.mover.constraints.get(LIMIT_NAME)
        focus = _focus_object(cam)
        if limit is not None and focus is not None:
            limit.distance = (eye - focus.matrix_world.translation).length
        return {'FINISHED'}

class CFR_OT_select_part(_RigOperator, Operator):
    bl_idname = "cfr.select_part"
    bl_label = "Select Rig Part"
    bl_options = {'REGISTER', 'UNDO'}

    part: EnumProperty(
        items=[('CAMERA', "Camera", ""), ('MOVER', "Mover", ""),
               ('PIVOT', "Damping Pivot", ""), ('TARGET', "Target", ""),
               ('FOCUS', "Focus Point", "")],
        default='MOVER',
    )

    def execute(self, context):
        cam = get_rig_camera(context)
        cfr = cam.cfr
        obj = {'CAMERA': cam, 'MOVER': cfr.mover, 'PIVOT': cfr.damping_pivot,
               'TARGET': cfr.target, 'FOCUS': cfr.focus_anchor}[self.part]
        if obj is None:
            return {'CANCELLED'}
        _select_only(context, obj)
        return {'FINISHED'}

class CFR_OT_reset_roll(_RigOperator, Operator):
    bl_idname = "cfr.reset_roll"
    bl_label = "Reset Roll"
    bl_description = "Set the camera's local Roll to zero"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cam = get_rig_camera(context)
        if not _ensure_rig_structure(cam, context):
            return {'CANCELLED'}
        cam.rotation_mode = 'XYZ'
        cam.rotation_euler.z = 0.0
        return {'FINISHED'}

class CFR_OT_remove_rig(_RigOperator, Operator):
    bl_idname = "cfr.remove_rig"
    bl_label = "Remove Rig"
    bl_description = "Remove the Mover and focus helper; keep the camera in place"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cam = get_rig_camera(context)
        cfr = cam.cfr
        mover, target, anchor = cfr.mover, cfr.target, cfr.focus_anchor
        pivot = cfr.damping_pivot

        world_matrix = cam.matrix_world.copy()
        for constraint in list(cam.constraints):
            if constraint.name == TRACK_NAME:
                cam.constraints.remove(constraint)
        if mover is not None:
            for constraint in list(mover.constraints):
                if constraint.name in {TRACK_NAME, LIMIT_NAME}:
                    mover.constraints.remove(constraint)

        cam.parent = None
        cam.matrix_world = world_matrix
        cam.data.dof.focus_object = target
        cfr.is_rig = False
        cfr.target = None
        cfr.mover = None
        cfr.focus_anchor = None
        cfr.damping_pivot = None
        cfr.orbit_lock = False
        cfr.target_slots.clear()
        if target is not None and target.cfr.camera == cam:
            target.cfr.camera = None
        if anchor is not None:
            bpy.data.objects.remove(anchor, do_unlink=True)
        if pivot is not None:
            bpy.data.objects.remove(pivot, do_unlink=True)
        if mover is not None:
            bpy.data.objects.remove(mover, do_unlink=True)

        _select_only(context, cam)
        return {'FINISHED'}
