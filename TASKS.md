# Camera Focus Rig — Tasks

> Task status is based on the refactored `1.2.2` source package and the development notes available on 2026-11-06. Items under Backlog are proposals, not promises or implemented functionality.

## Current release status

**Documented version:** `1.2.2`  
**Blender target:** `5.2`  
**Manifest minimum:** `4.2.0`  
**Runtime verification:** Pending — static/import-registration smoke tests passed, but no direct Blender runtime test has been recorded for this package.

## Completed

### Core rig
- [x] Create a camera focus rig from selected objects or an existing camera.
- [x] Generate Mover, Focus Point, and Damping Pivot helpers.
- [x] Keep the hierarchy `Mover → Damping Pivot → Camera`.
- [x] Track the shared Focus Point with Mover's Track To constraint.
- [x] Use the Focus Point for camera Depth of Field.
- [x] Provide rig-part selection from the sidebar.
- [x] Upgrade the older Camera-Track-To rig layout.
- [x] Add `Prepare Damping Pivot` for older compatible rigs.
- [x] Remove the rig while preserving the camera's world transform.

### Camera, framing, and orbit
- [x] Expose camera lens and basic DOF controls.
- [x] Add local Camera Roll and Reset Roll.
- [x] Add Frame Target with a margin control.
- [x] Add Snap Mover to View.
- [x] Add Orbit Lock and distance control.

### Generated animation
- [x] Generate Automatic Turntable animation around a Focus Point.
- [x] Support world X/Y/Z orbit axes and positive/negative revolutions.
- [x] Add optional Cycles repeat for whole-revolution loops.
- [x] Add replace-existing-Mover-animation option.
- [x] Add ordered multiple-Target sequence management.
- [x] Support Smooth (Bezier) and Linear Target transitions.
- [x] Add Reset Follow to return to the primary Target.

### Damping
- [x] Add independent Position and Rotation Damping switches.
- [x] Add response values in seconds.
- [x] Bake exponential position smoothing and quaternion rotation smoothing to ordinary keys.
- [x] Calculate time steps using Scene FPS and FPS base.
- [x] Add editable Start Frame and End Frame.
- [x] Add Use Scene Range.
- [x] Preserve keys outside a partial bake interval, with adjacent boundary samples.
- [x] Add Clear Bake and bake metadata/Timeline markers.

### Compatibility and packaging
- [x] Declare Blender 4.2.0 minimum in `blender_manifest.toml`.
- [x] Add a Blender 5.x layered Action/channel-bag path with legacy F-Curve fallback.
- [x] Replace the unsupported `ORBIT` panel icon with `CON_TRACKTO`.
- [x] Keep manifest, Python module, and README at the root of the install ZIP.


### Source architecture (1.2.2)
- [x] Split the monolithic implementation into helpers, properties, operator feature modules, UI, and registration.
- [x] Keep root `__init__.py` as a thin public entry point.
- [x] Centralize registration order and rollback partial registration on errors.
- [x] Preserve public operator IDs, property identifiers, and constraint names.
- [ ] Run the refactored package inside Blender 4.2 and 5.2 to verify actual registration and UI drawing.
- [ ] Exercise representative operators in Blender to confirm no behavior regression after the refactor.

## High-priority next steps

### P0 — Runtime regression testing
- [ ] Install and enable the add-on in Blender 5.2; confirm registration and that the Camera Rig sidebar draws without errors.
- [ ] Install and enable the add-on in Blender 4.2 (the declared minimum); confirm registration and panel drawing.
- [ ] Test Create Rig with: selected mesh Target, Empty Target, existing Camera + Target, and no explicit Target.
- [ ] Verify that inserting/upgrading the Damping Pivot preserves the camera's evaluated world transform.
- [ ] Verify Roll still works while Mover tracking is active.
- [ ] Verify Target Sequence updates both tracking direction and DOF focus.
- [ ] Verify Turntable in X/Y/Z, positive/negative revolution, loop on/off, and replace animation on/off.
- [ ] Verify Damping: position only, rotation only, both, zero response, and one-frame range.
- [ ] Verify partial Damping Bake at the Scene start, Scene end, and an interior interval; inspect adjacent boundary frames and keys outside the interval.
- [ ] Verify Clear Bake restores a neutral Pivot and document exactly which animation channels/markers are removed.
- [ ] Verify Remove Rig leaves the Camera at its evaluated world transform and retains the intended camera settings.

### P1 — Safer animation editing and diagnostics
- [ ] Decide whether partial bakes should preserve pre-existing keys at `Start-1` and `End+1`; currently boundary samples are inserted at those exact frames and can replace transform keys there.
- [ ] Decide whether multiple disjoint damping intervals need per-interval metadata/markers. Current Pivot metadata and named Timeline markers describe only the latest bake operation, although keys outside the newly baked interval are retained.
- [ ] Add explicit confirmation or clearer UI wording that Clear Bake removes all transform keys on Damping Pivot, not merely keys in the currently selected range.
- [ ] Add a warning/status when source animation or FPS changes after a bake and the baked result may be stale.
- [ ] Test animation actions containing unrelated curves and confirm the add-on only edits intended transform channels.

### P2 — Feature ideas
- [ ] Camera Presets: save/apply repeatable configurations such as Product Showcase, Orbit Shot, Tracking Shot, and Cinematic.
- [ ] Optional Spring Camera mode with physical inertia, overshoot, and settling; keep it distinct from the current critically smoothed follow behavior.
- [ ] Target Sequence mode that can follow moving Targets after generation, rather than using their sampled world-space origins only.
- [ ] More convenient damping preview workflow before committing a bake.
- [ ] Optional per-segment timing/easing settings for Target Sequence.
- [ ] Add a sample `.blend` scene demonstrating the complete rig and a set of reference animations.

## Known limitations / cautions

- The current Target Sequence operator captures Target world-space origins when the transition keys are generated. Moving a Target afterward does not automatically retarget the already-keyed path.
- Damping is baked, not evaluated live. Rebake after upstream animation or FPS changes.
- Partial bake adds boundary keys at `Start-1` and `End+1` when those frames are available; a key already at one of those exact frames may be replaced by the sampled boundary value.
- Clear Bake removes all location, quaternion rotation, and scale keys on the Damping Pivot and clears the damping markers/metadata. Do not put unrelated custom animation on that Pivot.
- The custom metadata and named markers represent the most recent bake, not a full list of all disjoint bake intervals.
- The package has not yet been verified by a live Blender runtime test in the available development environment. Static compilation and ZIP validation alone are insufficient.

## Release checklist

Before creating a new release ZIP:

- [ ] Increment `version` in `blender_manifest.toml`.
- [ ] Update the version heading and behavior notes in `README.md`.
- [ ] Add a dated entry to `CHANGELOG.md`.
- [ ] Update this file's Completed/Backlog sections and runtime test results.
- [ ] Run `python -m py_compile` over every `.py` file and import the package with a Blender API stub.
- [ ] Validate Blender manifest syntax and required fields.
- [ ] Check UI icon identifiers against the Blender versions being targeted.
- [ ] Check Blender 5.x layered Action API usage and older-version fallbacks.
- [ ] Build the ZIP with the thin `__init__.py`, every imported module/package folder, `blender_manifest.toml`, and `README.md` at archive root.
- [ ] Inspect the ZIP contents and run the release test matrix in Blender where available.
