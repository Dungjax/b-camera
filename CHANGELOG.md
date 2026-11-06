# Changelog

All notable changes recorded for Camera Focus Rig are listed here. This changelog reflects the project history available from the supplied packages and development conversation; dates for earlier releases were not retained.

## [1.2.1] — 2026-11 project state

### Added
- User-editable Damping Bake Range fields: Start Frame and End Frame.
- `Use Scene Range` action to copy the current Scene frame range into the bake fields.
- New rigs initialize the damping range from the Scene start/end values.

### Changed
- Damping bake operates only on the selected inclusive frame interval.
- Partial bakes preserve existing Damping Pivot transform keys outside the selected interval and sample adjacent boundary frames to stabilize the surrounding interpolation.
- Bake validation checks that the selected range stays within the Scene range and that End Frame is not earlier than Start Frame.

## [1.2.0] — date not recorded

### Added
- Damping Pivot inserted between Mover and Camera: `Mover → Damping Pivot → Camera`.
- Independent Position Damping and Rotation Damping controls.
- Response/time-constant settings in seconds.
- Exponential position smoothing and quaternion Slerp rotation smoothing, with time step based on Scene FPS.
- Bake Damping and Clear Bake operators; baked output is ordinary Blender transform keyframes for deterministic playback, rendering, and Timeline scrubbing.
- Damping Timeline markers and custom metadata recording the baked interval and FPS.
- `Prepare Damping Pivot` workflow for compatible older rigs.

### Changed
- New rigs create the Damping Pivot automatically.
- Camera world transform is preserved when the neutral Pivot is inserted.

## [1.1.1] — date not recorded

### Fixed
- Replaced unsupported Blender UI icon identifier `ORBIT` with the supported `CON_TRACKTO` icon, fixing the `CFR_PT_panel.draw` error reported in Blender 5.2.

## [1.1.0] — date not recorded

### Added
- Camera Roll on the Camera child's local Z axis, with Reset Roll.
- Automatic Turntable keyframe generation with configurable duration, revolution count, world axis, optional Cycles loop, and replace-animation option.
- Ordered multiple-Target focus transitions with Add, Remove, Reorder, Smooth/Linear interpolation, and Reset Follow.
- Separate Focus Point helper shared by Track To and Depth of Field.
- Mover-based tracking so the Camera child can apply local Roll without the tracking constraint overriding it.
- Rig migration support for earlier layouts where Track To was placed on the Camera.

### Retained
- Existing framing, viewport snap, orbit lock, Depth of Field, and rig removal workflows.

## Earlier versions

The supplied 1.1.1 README and source identify an earlier 1.0 rig layout and a migration path, but a complete 1.0 release changelog was not present in the supplied project artifacts. No unverified feature history is inferred here.
