# Camera Focus Rig — Project Context

> **Purpose:** This file is the durable hand-off document for future development sessions and contributors. Read it before modifying the add-on.

## 1. Project identity

- **Project:** Camera Focus Rig
- **Current documented version:** `1.2.1`
- **Type:** Blender Python add-on / Blender Extension package
- **Extension ID:** `camera_focus_rig`
- **Minimum Blender version in manifest:** `4.2.0`
- **Primary target for development and user reports:** Blender `5.2`
- **License declared in manifest:** `GPL-3.0-or-later`
- **Current implementation layout:** one main Python module (`__init__.py`), `blender_manifest.toml`, and `README.md` at the ZIP root.
- **Last project state reviewed for this document:** 2026-11-06.

The authoritative implementation for this context is the `camera_focus_rig_1.2.1.zip` package. Do not assume that a later version exists unless the repository or user supplies it.

## 2. Product goal

Provide a compact, reusable camera-control rig for Blender scenes. The user should be able to position and orbit a camera around a focus target, add local camera roll, generate turntable motion, animate focus changes between multiple targets, and add smooth follow lag without relying on stateful playback handlers.

The rig should remain friendly to normal Blender workflows: constraints, objects, keyframes, the Timeline, Graph Editor, Dope Sheet, render pipeline, and standard camera lens/Depth of Field settings.

## 3. Current rig architecture

### Main transform hierarchy

```text
Mover
└── Damping Pivot
    └── Camera
```

- **Mover** is the principal camera-position controller. A `TRACK_TO` constraint aims it at the Focus Point.
- **Damping Pivot** is a neutral child pivot between Mover and Camera. Baked position/rotation offsets are stored here.
- **Camera** is the child camera. Its local Z Euler rotation is exposed as Roll; lens, DOF enablement, aperture, and other camera-data settings remain on the camera.

### Focus helper (separate object)

The **Focus Point** is a separate Empty, not a child of the camera hierarchy.

- The Mover's `CFR_TrackTo` constraint targets the Focus Point.
- Camera Depth of Field uses the Focus Point as `dof.focus_object`.
- Orbit Lock uses a `LIMIT_DISTANCE` constraint on Mover targeting the Focus Point.
- A `CFR_FollowTarget` Copy Location constraint can make the Focus Point follow the primary Target.
- Target Sequence animation removes the follow constraint and keyframes the Focus Point's location.

This separation is intentional: tracking, DOF, orbit distance, and animated focus all use the same helper.

### Named constraints

Keep these names stable unless there is a deliberate migration plan:

- `CFR_TrackTo`
- `CFR_LimitDistance`
- `CFR_FollowTarget`

### Object custom properties / references

`CFR_Props` is registered as `bpy.types.Object.cfr`. Important references include `camera`, `mover`, `focus_anchor`, `damping_pivot`, `target`, and `target_slots`. The camera owns the authoritative rig settings; helper objects also keep back-references where required by selection and discovery logic.

## 4. Implemented feature set (version 1.2.1)

### Rig creation and maintenance

- Create a rig around the active/selected Target, optionally reusing a selected Camera.
- Create a default Focus Point and Damping Pivot.
- Select the Camera, Mover, Pivot, Target, or Focus Point from the panel.
- Upgrade legacy rigs whose Track To constraint is still on the Camera.
- Prepare a Damping Pivot for older 1.1.x rigs.
- Remove the rig while preserving the Camera's current world transform.

### Camera and framing

- Local camera Roll around the optical axis (Camera local Z / `rotation_euler.z`).
- Reset Roll.
- Lens and basic DOF controls, including aperture f-stop.
- Frame Target with a margin control.
- Snap Mover to the current perspective viewport eye.
- Optional Orbit Lock at a fixed distance from the Focus Point.

### Automatic Turntable

- Generate Mover location keys around the Focus Point.
- Configurable duration in frames, number of revolutions (negative values reverse direction), and world axis X/Y/Z.
- Samples every frame and uses linear interpolation for even angular motion.
- Optional Cycles modifiers for repeated playback. A whole number of revolutions is required for a seamless loop; the operator warns and skips the Cycles modifier otherwise.
- Option to replace existing Mover animation before generating a turntable.
- Extends Scene end frame when necessary and adds `CFR Turntable Start` / `CFR Turntable End` markers.

### Multiple Target Sequence

- Store an ordered list of Target objects; add selected objects, reorder, and remove entries.
- Set frames per Target and choose Smooth (Bezier) or Linear interpolation.
- Keyframe the Focus Point through the listed Targets in order.
- Track To and DOF follow the same Focus Point.
- `Reset Follow` removes the animated focus path and restores following of the primary Target.

**Current behavior to preserve/document:** the operator samples each Target's world-space origin when the transition sequence is generated. The generated path is keyframed on the Focus Point; it is not a live constraint chain that continuously follows moving Targets after generation. Use Empty Targets to define custom focus positions.

### Damping and inertia (baked workflow)

- Independent Position Damping and Rotation Damping toggles.
- Independent response/time-constant values in seconds; higher values create more follow lag. Zero response means that channel follows Mover directly.
- Exponential smoothing for position and quaternion Slerp for rotation.
- Frame delta is converted to seconds using Scene FPS (`fps / fps_base`).
- Bake to ordinary Blender transform keyframes on Damping Pivot. No frame-change handler or previous-frame runtime state is required for playback/render/scrubbing.
- User-editable Start Frame and End Frame; both must be inside the Scene frame range and End must be greater than or equal to Start.
- `Use Scene Range` copies the Scene's current start/end values into the two fields. New rigs initialize those values from the Scene range.
- Partial bake replaces transform keys in the selected interval and inserts sampled boundary keys at Start-1 and End+1 when those frames exist, to stabilize interpolation around the selected segment.
- Adds/replaces `CFR Damping Start` and `CFR Damping End` Timeline markers; records baked range and FPS as custom properties on the Pivot.
- `Clear Bake` removes all Pivot location/quaternion-rotation/scale keys, resets the Pivot transform, clears damping metadata, and removes the two damping markers.

**Important operational details:**

1. Rebake the affected range after changing Mover animation, Turntable animation, Target Sequence animation, damping settings, or Scene FPS.
2. Partial bake preserves keys outside the selected range, but it may replace keys exactly at the adjacent boundary frames (`Start-1` and `End+1`) because those frames are sampled and inserted as boundary keys.
3. `Clear Bake` is global to the Damping Pivot's transform channels; it is not a range-limited clear. Avoid storing unrelated hand-authored transform animation on the Damping Pivot.
4. The Pivot custom properties and the two named markers describe the most recent bake operation, not a complete registry of every disjoint baked interval.
5. Changing Scene FPS after baking changes the real-time interpretation of frame-based baked motion; rebake after FPS changes.

## 5. Main source structure

The current package keeps implementation in `__init__.py`. Important areas:

- **Helpers:** rig discovery, parenting, Focus Point creation, constraint wiring, action/F-Curve compatibility, transform sampling, key insertion/removal, Timeline markers.
- **Property groups:** `CFR_TargetItem`, `CFR_Props`.
- **Operators:**
  - `cfr.create_rig`
  - `cfr.upgrade_rig`
  - `cfr.frame_target`
  - `cfr.mover_to_view`
  - `cfr.select_part`
  - `cfr.reset_focus`
  - `cfr.add_target`, `cfr.remove_target`, `cfr.move_target`
  - `cfr.transition_targets`
  - `cfr.turntable`
  - `cfr.setup_damping`, `cfr.damping_scene_range`, `cfr.bake_damping`, `cfr.clear_damping`
  - `cfr.reset_roll`
  - `cfr.remove_rig`
- **UI:** `CFR_PT_panel` in the 3D View sidebar, tab `Camera Rig`.
- **Registration:** `classes` tuple, `register()`, and `unregister()`.

Important property names include `damping_position_enabled`, `damping_rotation_enabled`, `damping_position_time`, `damping_rotation_time`, `damping_start_frame`, `damping_end_frame`, `turntable_frames`, `turntable_revolutions`, `turntable_axis`, `turntable_loop`, `turntable_replace`, `transition_frames`, and `transition_interpolation`.

## 6. Compatibility and implementation guardrails

- The manifest declares Blender 4.2.0 as the minimum, while Blender 5.2 is the primary user-reported target. Preserve both where possible.
- Blender 5.0+ uses layered Actions/channel bags. The helper `_action_fcurves()` first attempts Blender's channel-bag API and falls back to `action.fcurves` for older versions. Test changes to animation APIs on both code paths where possible.
- Do not assume `action.fcurves` exists in Blender 5.x.
- Validate every UI icon against Blender's supported icon enum. A previous Blender 5.2 panel error was caused by the unsupported icon identifier `ORBIT`; it was replaced with `CON_TRACKTO`.
- Preserve the Camera world transform when inserting/reparenting helper objects or removing the rig.
- Keep damping deterministic. Prefer explicit baking to ordinary keyframes over frame-change handlers that depend on evaluation order or previous-frame state.
- Position and rotation smoothing should remain independently switchable. Keep rotation interpolation quaternion-based to avoid Euler flips.
- Use named constraints and custom-property identifiers consistently; renaming them may break migration or cleanup code.
- Operators should validate the active rig, selected objects, frame ranges, and settings before mutating animation.
- Keep the installation ZIP layout compatible with Blender Extensions: `blender_manifest.toml`, `__init__.py`, and `README.md` at archive root.
- Update the manifest version, README, CHANGELOG, and TASKS together for each release.

## 7. Development and validation workflow

Before editing:

1. Read this file, `CHANGELOG.md`, and `TASKS.md`.
2. Inspect the exact source ZIP or repository checkout supplied for the current task. Do not assume prior generated ZIPs are the latest.
3. Preserve existing public property names, operator IDs, helper names, and rig hierarchy unless a migration is explicitly implemented.

For each change:

1. Make the smallest coherent implementation change.
2. Run Python syntax compilation (`python -m py_compile __init__.py`). This catches syntax errors but does not validate Blender API behavior.
3. Validate the manifest and ZIP structure; ensure package files are at archive root.
4. Scan UI icon identifiers and animation API changes.
5. When Blender is available, install and test in the actual minimum supported version and Blender 5.2. Exercise create, edit, animate, bake, clear, upgrade, and remove workflows.
6. Update docs and add test cases/results to `TASKS.md`.

## 8. Known validation limitation at version 1.2.1

The source and ZIP structure have been inspected, but no live Blender runtime test result is recorded for version 1.2.1. Static Python compilation and archive checks are not substitutes for opening Blender, registering the add-on, drawing the panel, and executing operators. Treat Blender 4.2 and 5.2 runtime compatibility as **pending verification** until actual runtime test results are recorded.

## 9. Proposed direction (not implemented)

These are ideas, not current features:

- Camera Presets for reusable setups such as Product Showcase, Orbit Shot, Tracking Shot, and Cinematic.
- A physical Spring Camera mode with optional overshoot/bounce, distinct from current exponential follow damping.
- Preview/live damping controls or a more discoverable bake workflow.
- More robust per-segment bake metadata and safer boundary-key handling.
- Target Sequence modes that can follow moving Targets after the path is generated.
- Automated Blender-background integration tests and a regression scene.
