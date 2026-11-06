"""Low-level rig, transform, and animation helpers.

This module intentionally has no dependency on operators, UI, or registration.
"""

import math

import bpy
from mathutils import Matrix, Quaternion, Vector

from .constants import FOLLOW_NAME, LIMIT_NAME, TRACK_NAME


def get_rig_camera(context):
    """Find the rig camera from the active object or the scene camera."""
    obj = context.active_object
    if obj is not None:
        if obj.type == 'CAMERA' and obj.cfr.is_rig:
            return obj
        cam = obj.cfr.camera
        if cam is not None and cam.cfr.is_rig:
            return cam
    cam = context.scene.camera
    if cam is not None and cam.cfr.is_rig:
        return cam
    return None

def _select_only(context, obj):
    for selected in list(context.selected_objects):
        selected.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj

def _set_world_pos(obj, pos):
    """Set an object's world position while respecting its parent."""
    if obj.parent is None:
        obj.location = pos
    else:
        parent_matrix = obj.parent.matrix_world @ obj.matrix_parent_inverse
        obj.location = parent_matrix.inverted() @ pos

def _focus_object(cam):
    cfr = cam.cfr
    return cfr.focus_anchor or cfr.target

def _create_focus_anchor(cam, context):
    """Create the invisible-to-render helper used for tracking and DOF."""
    cfr = cam.cfr
    anchor = cfr.focus_anchor
    if anchor is not None:
        return anchor

    target = cfr.target
    if target is not None:
        location = target.matrix_world.translation.copy()
    else:
        location = cam.matrix_world.translation.copy()

    anchor = bpy.data.objects.new(cam.name + "_FocusPoint", None)
    anchor.empty_display_type = 'SPHERE'
    anchor.empty_display_size = 0.22
    anchor.show_in_front = True
    anchor.hide_render = True
    collection = context.collection or context.scene.collection
    collection.objects.link(anchor)
    anchor.location = location
    cfr.focus_anchor = anchor
    anchor.cfr.camera = cam
    return anchor

def _ensure_damping_pivot(cam, context):
    """Insert a transform pivot between the Mover and Camera, preserving the camera world transform."""
    cfr = cam.cfr
    mover = cfr.mover
    if mover is None:
        return None

    pivot = cfr.damping_pivot
    if pivot is None:
        collection = context.collection or context.scene.collection
        pivot = bpy.data.objects.new(cam.name + "_DampingPivot", None)
        pivot.empty_display_type = 'PLAIN_AXES'
        pivot.empty_display_size = 0.45
        pivot.show_in_front = True
        pivot.hide_render = True
        collection.objects.link(pivot)
        pivot.parent = mover
        pivot.matrix_parent_inverse = Matrix.Identity(4)
        context.view_layer.update()
        pivot.location = (0.0, 0.0, 0.0)
        pivot.rotation_mode = 'QUATERNION'
        pivot.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pivot.scale = (1.0, 1.0, 1.0)
        cfr.damping_pivot = pivot
    elif pivot.parent is not mover:
        pivot_world = pivot.matrix_world.copy()
        pivot.parent = mover
        pivot.matrix_parent_inverse = Matrix.Identity(4)
        pivot.matrix_world = pivot_world

    # Keep the pivot neutral unless a damping bake has been generated.
    if cam.parent is not pivot:
        camera_world = cam.matrix_world.copy()
        cam.parent = pivot
        cam.matrix_parent_inverse = Matrix.Identity(4)
        cam.matrix_world = camera_world

    pivot.cfr.camera = cam
    return pivot

def _ensure_follow_constraint(anchor, target):
    """Make the focus helper follow a target object's world-space origin."""
    if target is None:
        return None
    follow = anchor.constraints.get(FOLLOW_NAME)
    if follow is None:
        follow = anchor.constraints.new('COPY_LOCATION')
        follow.name = FOLLOW_NAME
    follow.target = target
    follow.owner_space = 'WORLD'
    follow.target_space = 'WORLD'
    return follow

def _apply_target(cam):
    """Wire the focus helper to Track To, DOF, and Orbit Lock."""
    cfr = cam.cfr
    if not cfr.is_rig:
        return

    anchor = cfr.focus_anchor
    mover = cfr.mover
    if anchor is None:
        return

    # Editing the primary Target intentionally resets any animated path.
    if anchor.animation_data is not None:
        anchor.animation_data_clear()
    if cfr.target is not None:
        _ensure_follow_constraint(anchor, cfr.target)
    else:
        follow = anchor.constraints.get(FOLLOW_NAME)
        if follow is not None:
            anchor.constraints.remove(follow)

    track = mover.constraints.get(TRACK_NAME) if mover is not None else None
    if track is not None:
        track.target = anchor

    if cam.type == 'CAMERA':
        cam.data.dof.focus_object = anchor

    if mover is not None:
        limit = mover.constraints.get(LIMIT_NAME)
        if limit is not None:
            limit.target = anchor

def _apply_orbit(cam):
    """Enable/disable a fixed-radius orbit around the focus helper."""
    cfr = cam.cfr
    mover = cfr.mover
    anchor = _focus_object(cam)
    if mover is None:
        return

    limit = mover.constraints.get(LIMIT_NAME)
    if cfr.orbit_lock and anchor is not None:
        if limit is None:
            limit = mover.constraints.new('LIMIT_DISTANCE')
            limit.name = LIMIT_NAME
            limit.limit_mode = 'LIMITDIST_ONSURFACE'
            limit.use_transform_limit = True
            limit.distance = (mover.matrix_world.translation - anchor.matrix_world.translation).length
        limit.target = anchor
    elif limit is not None:
        mover.constraints.remove(limit)

def _ensure_rig_structure(cam, context):
    """Upgrade an older rig to the Mover -> Damping Pivot -> Camera structure."""
    cfr = cam.cfr
    mover = cfr.mover
    if not cfr.is_rig or mover is None:
        return False

    anchor = _create_focus_anchor(cam, context)

    # Older versions placed Track To on the camera. Move that constraint to
    # the Mover so the camera can rotate locally around its optical axis (Roll).
    old_track = cam.constraints.get(TRACK_NAME)
    track = mover.constraints.get(TRACK_NAME)
    old_track_axis = old_track.track_axis if old_track is not None else 'TRACK_NEGATIVE_Z'
    old_up_axis = old_track.up_axis if old_track is not None else 'UP_Y'
    if old_track is not None:
        cam.constraints.remove(old_track)

    if track is None:
        track = mover.constraints.new('TRACK_TO')
        track.name = TRACK_NAME
        track.track_axis = old_track_axis
        track.up_axis = old_up_axis
    elif old_track is not None:
        # Preserve the old rig's tracking orientation during migration.
        track.track_axis = old_track_axis
        track.up_axis = old_up_axis
    track.target = anchor

    cam.rotation_mode = 'XYZ'
    # A missing follow constraint plus animated location means the helper is
    # intentionally running a multi-target path. Do not overwrite that path
    # merely because another rig operator was invoked.
    if (cfr.target is not None and anchor.constraints.get(FOLLOW_NAME) is None
            and anchor.animation_data is None):
        _ensure_follow_constraint(anchor, cfr.target)
    if len(cfr.target_slots) == 0 and cfr.target is not None:
        first_slot = cfr.target_slots.add()
        first_slot.target = cfr.target
        cfr.active_target_index = 0
    track.target = anchor
    _ensure_damping_pivot(cam, context)
    cam.data.dof.focus_object = anchor
    limit = mover.constraints.get(LIMIT_NAME)
    if limit is not None:
        limit.target = anchor
    _apply_orbit(cam)
    if mover.cfr.camera is None:
        mover.cfr.camera = cam
    anchor.cfr.camera = cam
    return True

def _min_fov(cam_obj, scene):
    """Smallest camera FOV (horizontal/vertical) for the render aspect ratio."""
    render = scene.render
    aspect = ((render.resolution_x * render.pixel_aspect_x) /
              (render.resolution_y * render.pixel_aspect_y))
    angle = cam_obj.data.angle
    tangent = math.tan(angle * 0.5)
    if aspect >= 1.0:
        horizontal, vertical = angle, 2.0 * math.atan(tangent / aspect)
    else:
        horizontal, vertical = 2.0 * math.atan(tangent * aspect), angle
    return min(horizontal, vertical)

def _action_fcurves(obj):
    """Return this ID's F-Curves on Blender 5.x and older supported versions."""
    animation_data = obj.animation_data
    if animation_data is None or animation_data.action is None:
        return []

    action = animation_data.action
    # Blender 5.0+ uses layered Actions and channel bags instead of action.fcurves.
    slot = getattr(animation_data, "action_slot", None)
    if slot is not None:
        try:
            from bpy_extras import anim_utils
            channelbag = anim_utils.action_get_channelbag_for_slot(action, slot)
            if channelbag is not None:
                return list(channelbag.fcurves)
        except (ImportError, AttributeError, RuntimeError):
            pass

    legacy_curves = getattr(action, "fcurves", None)
    if legacy_curves is not None:
        return list(legacy_curves)
    return []

def _set_interpolation(obj, data_path, start, end, interpolation):
    """Set interpolation on keys in a frame range (including layered Actions)."""
    for curve in _action_fcurves(obj):
        if curve.data_path != data_path:
            continue
        for key in curve.keyframe_points:
            if start - 1e-4 <= key.co.x <= end + 1e-4:
                key.interpolation = interpolation
                if interpolation == 'BEZIER':
                    key.handle_left_type = 'AUTO_CLAMPED'
                    key.handle_right_type = 'AUTO_CLAMPED'
        curve.update()

def _remove_keyframes_in_range(obj, start, end, data_paths):
    """Remove keys only from the requested transform channels and frame range."""
    for curve in _action_fcurves(obj):
        if curve.data_path not in data_paths:
            continue
        points = curve.keyframe_points
        for key in reversed(list(points)):
            if start - 1e-4 <= key.co.x <= end + 1e-4:
                points.remove(key)
        curve.update()

def _sample_local_transform(obj, context):
    """Sample evaluated local location, quaternion rotation, and scale."""
    depsgraph = context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    location, rotation, scale = evaluated.matrix_basis.decompose()
    rotation.normalize()
    return location.copy(), rotation.copy(), scale.copy(), evaluated.matrix_world.copy()

def _insert_pivot_transform(pivot, frame, transform):
    """Insert one pivot transform sample as ordinary Blender keyframes."""
    location, rotation, scale = transform
    pivot.location = location
    pivot.rotation_mode = 'QUATERNION'
    pivot.rotation_quaternion = rotation
    pivot.scale = scale
    pivot.keyframe_insert(data_path="location", frame=frame, group="Camera Damping")
    pivot.keyframe_insert(data_path="rotation_quaternion", frame=frame, group="Camera Damping")
    pivot.keyframe_insert(data_path="scale", frame=frame, group="Camera Damping")

def _add_scene_marker(scene, name, frame):
    marker = scene.timeline_markers.new(name, frame=frame)
    return marker

def _replace_scene_marker(scene, name, frame):
    for marker in list(scene.timeline_markers):
        if marker.name == name:
            scene.timeline_markers.remove(marker)
    return scene.timeline_markers.new(name, frame=frame)

def _min_target_radius(target):
    radius = (Vector(target.dimensions) * 0.5).length
    return radius if radius >= 1e-4 else 1.0
