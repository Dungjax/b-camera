# Graph Report - b-camera  (2026-11-06)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 123 nodes · 321 edges · 9 communities (6 shown, 3 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 1 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9a9380e8`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8

## God Nodes (most connected - your core abstractions)
1. `get_rig_camera()` - 27 edges
2. `_RigOperator` - 22 edges
3. `_ensure_rig_structure()` - 21 edges
4. `_set_interpolation()` - 9 edges
5. `CFR_OT_create_rig` - 7 edges
6. `CFR_OT_frame_target` - 7 edges
7. `CFR_OT_mover_to_view` - 7 edges
8. `_apply_target()` - 7 edges
9. `_set_world_pos()` - 7 edges
10. `CFR_OT_turntable` - 6 edges

## Surprising Connections (you probably didn't know these)
- `register()` --uses--> `CFR_Props`  [INFERRED]
  registration.py → properties.py
- `CFR_OT_turntable` --inherits--> `_RigOperator`  [EXTRACTED]
  operators/turntable.py → operators/base.py
- `CFR_OT_bake_damping` --inherits--> `_RigOperator`  [EXTRACTED]
  operators/damping.py → operators/base.py
- `CFR_OT_clear_damping` --inherits--> `_RigOperator`  [EXTRACTED]
  operators/damping.py → operators/base.py
- `CFR_OT_damping_scene_range` --inherits--> `_RigOperator`  [EXTRACTED]
  operators/damping.py → operators/base.py

## Import Cycles
- None detected.

## Communities (9 total, 3 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.12
Nodes (9): _apply_orbit(), _apply_target(), _ensure_follow_constraint(), CFR_Props, CFR_TargetItem, _update_orbit(), _update_target(), register() (+1 more)

### Community 1 - "Community 1"
Cohesion: 0.14
Nodes (6): _ensure_damping_pivot(), _focus_object(), _min_fov(), _min_target_radius(), _select_only(), CFR_OT_create_rig

### Community 2 - "Community 2"
Cohesion: 0.16
Nodes (7): _action_fcurves(), _add_scene_marker(), _create_focus_anchor(), _ensure_rig_structure(), _set_interpolation(), _set_world_pos(), CFR_OT_turntable

### Community 3 - "Community 3"
Cohesion: 0.16
Nodes (8): _insert_pivot_transform(), _remove_keyframes_in_range(), _replace_scene_marker(), _sample_local_transform(), CFR_OT_bake_damping, CFR_OT_clear_damping, CFR_OT_damping_scene_range, CFR_OT_setup_damping

### Community 4 - "Community 4"
Cohesion: 0.28
Nodes (7): _RigOperator, CFR_OT_frame_target, CFR_OT_mover_to_view, CFR_OT_remove_rig, CFR_OT_reset_roll, CFR_OT_select_part, CFR_OT_upgrade_rig

### Community 5 - "Community 5"
Cohesion: 0.27
Nodes (4): CFR_OT_add_target, CFR_OT_move_target, CFR_OT_remove_target, CFR_OT_transition_targets

## Knowledge Gaps
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_rig_camera()` connect `Community 7` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 8`?**
  _High betweenness centrality (0.143) - this node is a cross-community bridge._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.11594202898550725 - nodes in this community are weakly interconnected._
- **Why does `_ensure_rig_structure()` connect `Community 2` to `Community 0`, `Community 1`, `Community 3`, `Community 4`, `Community 5`, `Community 8`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.1422924901185771 - nodes in this community are weakly interconnected._
- **Why does `CFR_OT_create_rig` connect `Community 1` to `Community 0`, `Community 4`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._