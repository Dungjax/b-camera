"""3D View sidebar panel for Camera Focus Rig."""

from bpy.types import Panel

from ..constants import LIMIT_NAME, TRACK_NAME
from ..helpers import get_rig_camera


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
