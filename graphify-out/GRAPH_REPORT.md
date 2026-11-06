# Graph Report - b-camera  (2026-11-06)

## Corpus Check
- Corpus is ~9,872 words - fits in a single context window. You may not need a graph.

## Summary
- 159 nodes · 354 edges · 12 communities (10 shown, 2 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 2 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Feature Operators
- Rig and Animation Helpers
- Animation Keyframes
- Rig Structure and Operators
- Camera Transforms
- Camera Rig Concepts
- Interface and Constants
- Project Plans and Context
- User Workflows
- Change History
- Graphify Project Rules
- Registration Rollback

## God Nodes (most connected - your core abstractions)
1. `get_rig_camera()` - 27 edges
2. `_RigOperator` - 22 edges
3. `_ensure_rig_structure()` - 21 edges
4. `_set_interpolation()` - 9 edges
5. `_set_world_pos()` - 7 edges
6. `_apply_target()` - 7 edges
7. `CFR_OT_create_rig` - 7 edges
8. `CFR_OT_frame_target` - 7 edges
9. `CFR_OT_mover_to_view` - 7 edges
10. `_apply_orbit()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `_update_target()` --calls--> `_apply_target()`  [EXTRACTED]
  properties.py → helpers.py
- `_update_orbit()` --calls--> `_apply_orbit()`  [EXTRACTED]
  properties.py → helpers.py
- `register()` --uses--> `CFR_Props`  [INFERRED]
  registration.py → properties.py
- `Damping Bake Workflow` --references--> `Baked Position and Rotation Damping`  [INFERRED]
  README.md → PROJECT_CONTEXT.md
- `CFR_OT_bake_damping` --inherits--> `_RigOperator`  [EXTRACTED]
  operators/damping.py → operators/base.py

## Import Cycles
- None detected.

## Communities (12 total, 2 thin omitted)

### Community 0 - "Feature Operators"
Cohesion: 0.19
Nodes (17): _RigOperator, CFR_OT_bake_damping, CFR_OT_clear_damping, CFR_OT_damping_scene_range, CFR_OT_setup_damping, CFR_OT_frame_target, CFR_OT_mover_to_view, CFR_OT_remove_rig (+9 more)

### Community 1 - "Rig and Animation Helpers"
Cohesion: 0.10
Nodes (9): _apply_orbit(), _apply_target(), _ensure_follow_constraint(), CFR_Props, CFR_TargetItem, _update_orbit(), _update_target(), register() (+1 more)

### Community 2 - "Animation Keyframes"
Cohesion: 0.13
Nodes (7): _action_fcurves(), _add_scene_marker(), _insert_pivot_transform(), _remove_keyframes_in_range(), _replace_scene_marker(), _sample_local_transform(), _set_interpolation()

### Community 3 - "Rig Structure and Operators"
Cohesion: 0.14
Nodes (4): _create_focus_anchor(), _ensure_rig_structure(), get_rig_camera(), _select_only()

### Community 4 - "Camera Transforms"
Cohesion: 0.15
Nodes (6): _ensure_damping_pivot(), _focus_object(), _min_fov(), _min_target_radius(), _set_world_pos(), CFR_OT_create_rig

### Community 5 - "Camera Rig Concepts"
Cohesion: 0.24
Nodes (11): Baked Position and Rotation Damping, Camera Child, Damping Pivot, Depth of Field Focus, Focus Point Helper, Mover Controller, Multiple Target Sequence, Orbit Lock (+3 more)

### Community 7 - "Project Plans and Context"
Cohesion: 0.20
Nodes (9): Blender Camera Control Add-on, Camera Focus Rig Project Context, Proposed Future Features, Pending Blender Runtime Verification, Animation Editing Diagnostics, Camera Focus Rig Task Status, Camera Presets Proposal, Physical Spring Camera Proposal (+1 more)

### Community 8 - "User Workflows"
Cohesion: 0.33
Nodes (6): Camera Focus Rig README, Camera Roll, Add-on Installation Workflow, Legacy Rig Migration, Target Transition Workflow, Turntable Workflow

### Community 9 - "Change History"
Cohesion: 0.40
Nodes (5): Camera Focus Rig Changelog, Damping Bake Range, Damping Pivot, Target Sequence, Version 1.2.2 Refactor

### Community 10 - "Graphify Project Rules"
Cohesion: 0.67
Nodes (3): Existing Graph Query Rule, Graph Update Rule, Graphify Project Rules

## Knowledge Gaps
- **20 isolated node(s):** `Existing Graph Query Rule`, `Graph Update Rule`, `Damping Bake Range`, `Damping Pivot`, `Target Sequence` (+15 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 57 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_rig_camera()` connect `Rig Structure and Operators` to `Feature Operators`, `Rig and Animation Helpers`, `Animation Keyframes`, `Camera Transforms`, `Interface and Constants`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **What connects `Existing Graph Query Rule`, `Graph Update Rule`, `Damping Bake Range` to the rest of the system?**
  _20 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Rig and Animation Helpers` be split into smaller, more focused modules?**
  _Cohesion score 0.10333333333333333 - nodes in this community are weakly interconnected._
- **Why does `_ensure_rig_structure()` connect `Rig Structure and Operators` to `Feature Operators`, `Rig and Animation Helpers`, `Animation Keyframes`, `Camera Transforms`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Should `Animation Keyframes` be split into smaller, more focused modules?**
  _Cohesion score 0.13043478260869565 - nodes in this community are weakly interconnected._
- **Why does `CFR_OT_create_rig` connect `Camera Transforms` to `Feature Operators`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Should `Rig Structure and Operators` be split into smaller, more focused modules?**
  _Cohesion score 0.13725490196078433 - nodes in this community are weakly interconnected._