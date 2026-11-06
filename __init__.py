# Camera Focus Rig
# Blender 4.2+ / 5.2
# Move the Mover to position the camera. A child damping pivot can bake
# delayed position/rotation motion before the Camera applies local Roll.

import math

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
)
from bpy.types import Operator, Panel, PropertyGroup
from mathutils import Matrix, Quaternion, Vector

TRACK_NAME = "CFR_TrackTo"
LIMIT_NAME = "CFR_LimitDistance"
FOLLOW_NAME = "CFR_FollowTarget"


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


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


# ----------------------------------------------------------------------------
# Properties
# ----------------------------------------------------------------------------


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


# ----------------------------------------------------------------------------
# Operators
# ----------------------------------------------------------------------------


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


class _RigOperator:
    @classmethod
    def poll(cls, context):
        cam = get_rig_camera(context)
        return cam is not None and cam.cfr.mover is not None


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


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------


class CFR_PT_panel(Panel):
    bl_label = "Camera Focus Rig"
    bl_idname = "CFR_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Camera Rig"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        cam = get_rig_camera(context)
        if cam is None:
            column = layout.column(align=True)
            column.label(text="Select an object to look at")
            column.label(text="(+ optionally a camera), then:")
            layout.operator("cfr.create_rig", icon='CAMERA_DATA')
            return

        cfr = cam.cfr
        layout.label(text=cam.name, icon='OUTLINER_OB_CAMERA')

        legacy = (cfr.mover is None or cfr.focus_anchor is None
                  or cfr.mover.constraints.get(TRACK_NAME) is None)
        if legacy:
            box = layout.box()
            box.label(text="Legacy rig detected", icon='INFO')
            box.operator("cfr.upgrade_rig", icon='FILE_REFRESH')
            box.label(text="Upgrade to enable Roll and animation tools")
            layout.prop(cfr, "target")
            return

        layout.prop(cfr, "target")
        row = layout.row(align=True)
        for part, label in (('CAMERA', "Camera"), ('MOVER', "Mover"), ('PIVOT', "Pivot")):
            row.operator("cfr.select_part", text=label).part = part
        row = layout.row(align=True)
        for part, label in (('TARGET', "Target"), ('FOCUS', "Focus")):
            row.operator("cfr.select_part", text=label).part = part

        layout.separator()
        camera_box = layout.box()
        camera_box.label(text="Camera", icon='CAMERA_DATA')
        camera_box.prop(cam.data, "lens")
        camera_box.prop(cam.data.dof, "use_dof", text="Depth of Field")
        dof_column = camera_box.column(align=True)
        dof_column.active = cam.data.dof.use_dof
        dof_column.prop(cam.data.dof, "aperture_fstop")
        row = camera_box.row(align=True)
        row.prop(cam, "rotation_euler", index=2, text="Roll")
        row.operator("cfr.reset_roll", text="", icon='LOOP_BACK')

        layout.separator()
        orbit_box = layout.box()
        orbit_box.label(text="Orbit & Framing", icon='CON_TRACKTO')
        orbit_box.prop(cfr, "orbit_lock")
        limit = cfr.mover.constraints.get(LIMIT_NAME) if cfr.mover else None
        if limit is not None:
            orbit_box.prop(limit, "distance", text="Distance")
        row = orbit_box.row(align=True)
        row.operator("cfr.frame_target", icon='FULLSCREEN_ENTER')
        row.prop(cfr, "frame_margin", text="")
        orbit_box.operator("cfr.mover_to_view", icon='VIEW3D')

        layout.separator()
        damping_box = layout.box()
        damping_box.label(text="Damping & Inertia", icon='TIME')
        damping_box.prop(cfr, "damping_position_enabled")
        position_row = damping_box.row()
        position_row.active = cfr.damping_position_enabled
        position_row.prop(cfr, "damping_position_time", text="Position Response (s)")
        damping_box.prop(cfr, "damping_rotation_enabled")
        rotation_row = damping_box.row()
        rotation_row.active = cfr.damping_rotation_enabled
        rotation_row.prop(cfr, "damping_rotation_time", text="Rotation Response (s)")
        damping_box.label(text="Bake Range", icon='PREVIEW_RANGE')
        range_row = damping_box.row(align=True)
        range_row.prop(cfr, "damping_start_frame", text="Start")
        range_row.prop(cfr, "damping_end_frame", text="End")
        range_row = damping_box.row(align=True)
        range_row.operator("cfr.damping_scene_range", text="Use Scene Range", icon='PREVIEW_RANGE')
        range_row.label(text="Scene: %d-%d" %
                        (context.scene.frame_start, context.scene.frame_end))
        pivot = cfr.damping_pivot
        if pivot is None:
            damping_box.operator("cfr.setup_damping", text="Prepare Damping Pivot", icon='EMPTY_AXIS')
        else:
            if pivot.get("cfr_damping_baked", False):
                damping_box.label(text="Baked: %s-%s" %
                                  (pivot.get("cfr_damping_start", "?"),
                                   pivot.get("cfr_damping_end", "?")), icon='CHECKMARK')
            else:
                damping_box.label(text="Not baked — settings apply after baking", icon='INFO')
            row = damping_box.row(align=True)
            row.operator("cfr.bake_damping", icon='REC')
            row.operator("cfr.clear_damping", text="Clear Bake", icon='LOOP_BACK')

        layout.separator()
        turntable_box = layout.box()
        turntable_box.label(text="Automatic Turntable", icon='DRIVER_ROTATIONAL_DIFFERENCE')
        turntable_box.prop(cfr, "turntable_frames")
        turntable_box.prop(cfr, "turntable_revolutions")
        turntable_box.prop(cfr, "turntable_axis")
        turntable_box.prop(cfr, "turntable_loop")
        turntable_box.prop(cfr, "turntable_replace")
        turntable_box.operator("cfr.turntable", icon='REC')

        layout.separator()
        targets_box = layout.box()
        targets_box.label(text="Target Sequence", icon='OUTLINER_OB_EMPTY')
        if len(cfr.target_slots) == 0:
            targets_box.label(text="Add selected objects in transition order")
        for index, item in enumerate(cfr.target_slots):
            row = targets_box.row(align=True)
            row.prop(item, "target", text="")
            up = row.operator("cfr.move_target", text="", icon='TRIA_UP')
            up.index = index
            up.direction = 'UP'
            down = row.operator("cfr.move_target", text="", icon='TRIA_DOWN')
            down.index = index
            down.direction = 'DOWN'
            remove = row.operator("cfr.remove_target", text="", icon='X')
            remove.index = index

        row = targets_box.row(align=True)
        row.operator("cfr.add_target", text="Add Selected", icon='ADD')
        row.operator("cfr.reset_focus", text="Reset Follow", icon='LOOP_BACK')
        targets_box.prop(cfr, "transition_frames")
        targets_box.prop(cfr, "transition_interpolation")
        targets_box.operator("cfr.transition_targets", icon='KEY_HLT')

        layout.separator()
        layout.operator("cfr.create_rig", text="New Rig from Selection", icon='ADD')
        layout.operator("cfr.remove_rig", icon='X')


# ----------------------------------------------------------------------------
# Registration
# ----------------------------------------------------------------------------


classes = (
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
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.cfr = PointerProperty(type=CFR_Props)


def unregister():
    del bpy.types.Object.cfr
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
