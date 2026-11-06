"""Operators for preparing, baking, and clearing deterministic damping."""

import math

from bpy.types import Operator
from mathutils import Matrix, Quaternion

from ..helpers import (
    _ensure_rig_structure,
    _insert_pivot_transform,
    _remove_keyframes_in_range,
    _replace_scene_marker,
    _sample_local_transform,
    _set_interpolation,
    get_rig_camera,
)
from .base import _RigOperator


class CFR_OT_setup_damping(_RigOperator, Operator):
    bl_idname = "cfr.setup_damping"
    bl_label = "Prepare Damping Pivot"
    bl_description = "Insert a neutral pivot between the Mover and Camera without changing the current camera view"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cam = get_rig_camera(context)
        if not _ensure_rig_structure(cam, context):
            self.report({'ERROR'}, "Could not prepare the damping pivot")
            return {'CANCELLED'}
        self.report({'INFO'}, "Damping pivot is ready")
        return {'FINISHED'}

class CFR_OT_damping_scene_range(_RigOperator, Operator):
    bl_idname = "cfr.damping_scene_range"
    bl_label = "Use Scene Range"
    bl_description = "Set Damping Start and End Frames to the current Scene frame range"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cam = get_rig_camera(context)
        if cam is None:
            return {'CANCELLED'}
        cam.cfr.damping_start_frame = int(context.scene.frame_start)
        cam.cfr.damping_end_frame = int(context.scene.frame_end)
        self.report({'INFO'}, "Damping range set to Scene range (%d-%d)" %
                    (context.scene.frame_start, context.scene.frame_end))
        return {'FINISHED'}

class CFR_OT_bake_damping(_RigOperator, Operator):
    bl_idname = "cfr.bake_damping"
    bl_label = "Bake Damping"
    bl_description = "Bake position and rotation lag onto the Damping Pivot over the selected frame range"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cam = get_rig_camera(context)
        if not _ensure_rig_structure(cam, context):
            return {'CANCELLED'}

        cfr = cam.cfr
        if not cfr.damping_position_enabled and not cfr.damping_rotation_enabled:
            self.report({'WARNING'}, "Enable Position Damping or Rotation Damping first")
            return {'CANCELLED'}
        if ((not cfr.damping_position_enabled or cfr.damping_position_time <= 1e-6)
                and (not cfr.damping_rotation_enabled or cfr.damping_rotation_time <= 1e-6)):
            self.report({'WARNING'}, "Set at least one damping response above zero seconds")
            return {'CANCELLED'}

        scene = context.scene
        mover = cfr.mover
        pivot = cfr.damping_pivot
        start_frame = int(cfr.damping_start_frame)
        end_frame = int(cfr.damping_end_frame)
        if start_frame < scene.frame_start or end_frame > scene.frame_end:
            self.report({'ERROR'}, "Bake range must stay inside the Scene range (%d-%d)" %
                        (scene.frame_start, scene.frame_end))
            return {'CANCELLED'}
        if end_frame < start_frame:
            self.report({'ERROR'}, "End Frame must be greater than or equal to Start Frame")
            return {'CANCELLED'}

        fps_base = max(float(scene.render.fps_base), 1e-6)
        fps = max(float(scene.render.fps) / fps_base, 1e-6)
        original_frame = scene.frame_current
        original_subframe = scene.frame_subframe
        transform_paths = {"location", "rotation_quaternion", "scale"}
        samples = []
        start_boundary = None
        end_boundary = None
        previous_position = None
        previous_rotation = None
        previous_local_rotation = None
        previous_frame = None

        try:
            # Capture the existing pivot at the frames immediately outside the
            # requested interval. These boundary samples prevent partial bakes
            # from changing motion outside the selected range.
            if start_frame > scene.frame_start:
                scene.frame_set(start_frame - 1)
                context.view_layer.update()
                loc, rot, scale, world = _sample_local_transform(pivot, context)
                start_boundary = (loc, rot, scale)
                previous_local_rotation = rot.copy()
                previous_position, previous_rotation, _ = world.decompose()
                previous_rotation.normalize()
                previous_frame = start_frame - 1

            if end_frame < scene.frame_end:
                scene.frame_set(end_frame + 1)
                context.view_layer.update()
                loc, rot, scale, _world = _sample_local_transform(pivot, context)
                end_boundary = (loc, rot, scale)

            for frame in range(start_frame, end_frame + 1):
                scene.frame_set(frame)
                context.view_layer.update()
                depsgraph = context.evaluated_depsgraph_get()
                mover_eval = mover.evaluated_get(depsgraph)
                source_matrix = mover_eval.matrix_world.copy()
                source_position, source_rotation, source_scale = source_matrix.decompose()
                source_rotation.normalize()

                if previous_rotation is not None and previous_rotation.dot(source_rotation) < 0.0:
                    source_rotation = Quaternion(tuple(-component for component in source_rotation))

                if previous_frame is None:
                    filtered_position = source_position.copy()
                    filtered_rotation = source_rotation.copy()
                else:
                    delta_seconds = (frame - previous_frame) / fps
                    if cfr.damping_position_enabled and cfr.damping_position_time > 1e-6:
                        alpha_position = 1.0 - math.exp(-delta_seconds / cfr.damping_position_time)
                        filtered_position = previous_position.lerp(source_position, alpha_position)
                    else:
                        filtered_position = source_position.copy()

                    if cfr.damping_rotation_enabled and cfr.damping_rotation_time > 1e-6:
                        alpha_rotation = 1.0 - math.exp(-delta_seconds / cfr.damping_rotation_time)
                        filtered_rotation = previous_rotation.slerp(source_rotation, alpha_rotation)
                    else:
                        filtered_rotation = source_rotation.copy()

                # Convert the damped world transform into the pivot's local
                # transform relative to the evaluated Mover.
                damped_world = Matrix.LocRotScale(
                    filtered_position, filtered_rotation, source_scale
                )
                local_matrix = source_matrix.inverted_safe() @ damped_world
                local_position, local_rotation, local_scale = local_matrix.decompose()
                local_rotation.normalize()
                if (previous_local_rotation is not None
                        and previous_local_rotation.dot(local_rotation) < 0.0):
                    local_rotation = Quaternion(tuple(-component for component in local_rotation))

                samples.append((frame, (local_position.copy(), local_rotation.copy(), local_scale.copy())))
                previous_position = filtered_position.copy()
                previous_rotation = filtered_rotation.copy()
                previous_local_rotation = local_rotation.copy()
                previous_frame = frame

            if (end_boundary is not None and previous_local_rotation is not None
                    and previous_local_rotation.dot(end_boundary[1]) < 0.0):
                end_boundary = (
                    end_boundary[0],
                    Quaternion(tuple(-component for component in end_boundary[1])),
                    end_boundary[2],
                )

            # Replace only keys in the selected interval. Keep all existing
            # animation before/after it, with evaluated boundary keys to avoid
            # extrapolation changing the surrounding frames.
            _remove_keyframes_in_range(pivot, start_frame, end_frame, transform_paths)
            if start_boundary is not None:
                _insert_pivot_transform(pivot, start_frame - 1, start_boundary)
            for frame, transform in samples:
                _insert_pivot_transform(pivot, frame, transform)
            if end_boundary is not None:
                _insert_pivot_transform(pivot, end_frame + 1, end_boundary)

            # Dense linear samples make the baked result deterministic when
            # playing, rendering, or scrubbing the Timeline.
            interpolation_start = start_frame - 1 if start_boundary is not None else start_frame
            for data_path in transform_paths:
                _set_interpolation(pivot, data_path, interpolation_start, end_frame, 'LINEAR')

            pivot["cfr_damping_baked"] = True
            pivot["cfr_damping_start"] = start_frame
            pivot["cfr_damping_end"] = end_frame
            pivot["cfr_damping_fps"] = fps
            _replace_scene_marker(scene, "CFR Damping Start", start_frame)
            _replace_scene_marker(scene, "CFR Damping End", end_frame)

        except Exception as exc:
            self.report({'ERROR'}, "Damping bake failed: %s" % exc)
            return {'CANCELLED'}
        finally:
            scene.frame_set(original_frame, subframe=original_subframe)
            context.view_layer.update()

        self.report({'INFO'}, "Damping baked on the Damping Pivot: frames %d-%d" %
                    (start_frame, end_frame))
        return {'FINISHED'}

class CFR_OT_clear_damping(_RigOperator, Operator):
    bl_idname = "cfr.clear_damping"
    bl_label = "Clear Damping Bake"
    bl_description = "Remove all baked damping keys and make the Camera follow the Mover directly again"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cam = get_rig_camera(context)
        if not _ensure_rig_structure(cam, context):
            return {'CANCELLED'}
        pivot = cam.cfr.damping_pivot
        _remove_keyframes_in_range(
            pivot, -1000000000, 1000000000,
            {"location", "rotation_quaternion", "scale"},
        )
        pivot.location = (0.0, 0.0, 0.0)
        pivot.rotation_mode = 'QUATERNION'
        pivot.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pivot.scale = (1.0, 1.0, 1.0)
        for key in ("cfr_damping_baked", "cfr_damping_start", "cfr_damping_end", "cfr_damping_fps"):
            if key in pivot:
                del pivot[key]
        for marker in list(context.scene.timeline_markers):
            if marker.name in {"CFR Damping Start", "CFR Damping End"}:
                context.scene.timeline_markers.remove(marker)
        context.view_layer.update()
        self.report({'INFO'}, "Damping bake cleared; Camera follows the Mover directly")
        return {'FINISHED'}
