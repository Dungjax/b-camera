# Camera Focus Rig 1.2.1

Camera Focus Rig is a Blender add-on for a camera controller rig with local camera Roll, automatic turntables, animated transitions between multiple focus Targets, and baked position/rotation damping.

## Install

1. In Blender, open **Edit → Preferences → Get Extensions → Install from Disk** (or **Install from Disk** in the Add-ons section, depending on the Blender build).
2. Select `camera_focus_rig_1.2.1.zip`.
3. Enable **Camera Focus Rig**.
4. Open the 3D View sidebar with `N` and choose the **Camera Rig** tab.

## Create a rig

1. Select the object to look at. Optionally select an existing camera too; make the Target the active object.
2. Click **Create Focus Rig**.
3. Move the generated **Mover** Empty to position the camera. The camera continuously looks at the Target.
4. Select the Camera to edit lens, DOF, and **Roll**.

The hierarchy is **Mover → Damping Pivot → Camera**. The Mover controls the intended camera position and aim. The Damping Pivot can add delayed position and rotation motion. The Camera child retains local Roll and lens/DOF controls.

## Roll

Use the **Roll** field in the Camera section. It is the Camera child's local Z rotation, so it can also be keyframed using Blender's normal keyframe workflow (hover the field and press `I`). **Reset Roll** sets it to zero.

## Damping & inertia

Damping is baked to ordinary Blender keyframes so that playback, rendering, and timeline scrubbing are deterministic. It does not rely on a frame-change handler or previous-frame state.

1. Enable **Position Damping**, **Rotation Damping**, or both.
2. Set each **Response** value in seconds. A higher value creates more follow lag; `0` means that channel follows the Mover directly.
3. Set **Start** and **End** under **Bake Range**. Both frames must be inside the Scene frame range. **Use Scene Range** copies the current Scene start/end values into these fields. New rigs initialize the fields from the Scene range.
4. Click **Bake Damping**. The add-on writes damped transform keys only across the selected interval. Existing Damping Pivot animation outside the interval is retained; the adjacent boundary frames are sampled so the partial bake does not unexpectedly change the surrounding motion.
5. Use **Clear Bake** to remove all generated Damping Pivot transform keys and return the Camera to direct following.

The filter uses exponential smoothing with a time constant in seconds and calculates each frame step from the current Scene FPS. Position and rotation are independent. Rotation filtering uses quaternion spherical interpolation to avoid Euler-angle flips. The bake adds `CFR Damping Start` and `CFR Damping End` timeline markers and records the FPS used.

**Important workflow:** after changing Mover, Turntable, Target-transition animation, or Scene FPS, rebake the affected frame range. You can bake a smaller interval without deleting generated keys outside that interval. **Clear Bake** removes the generated transform animation from the Damping Pivot, but does not clear Mover, Target, or Camera animation. Changing FPS after baking changes the real-time duration of the baked keys, so rebake after FPS changes.

## Automatic turntable

In **Automatic Turntable**:

- **Duration**: number of frames from the current frame.
- **Revolutions**: number of rotations; negative values reverse direction.
- **Axis**: world X, Y, or Z.
- **Loop**: adds Cycles modifiers for repeated playback. Use a whole number of revolutions for a seamless loop.
- **Replace Mover Animation**: clears existing Mover animation before generating new keys.

Click **Generate Turntable**. The add-on samples every frame, uses linear keys for even angular speed, extends the Scene end frame as needed, and adds timeline markers.

## Transitions between multiple Targets

1. Select each object in the desired order and click **Add Selected**. The first Target created with the rig is already in the list.
2. Use the up/down arrows to reorder the list; use `X` to remove an entry.
3. Set **Frames / Target** and choose **Smooth** (Bezier) or **Linear** interpolation.
4. Click **Keyframe Target Transitions**.

The Camera's Focus Point moves through the listed objects' world-space origins. Track To and Depth of Field both follow that helper. The helper is no longer constrained to the primary Target while the animated path is active. Click **Reset Follow** to discard the animated path and follow the primary Target again.

For best results, use Empty objects as Targets when you need a custom focus point rather than an object's origin.

## Existing rigs

Rigs made with version 1.0 can be migrated using **Upgrade Rig for Roll & Animation**. Rigs from 1.1.x can create the new neutral Damping Pivot with **Prepare Damping Pivot**; the operation preserves the current Camera world transform. New rigs create the pivot automatically.

## Remove Rig

**Remove Rig** removes the Mover, Focus Point helper, and Damping Pivot while keeping the Camera at its current world transform.

## Compatibility

- Designed for Blender 4.2+ and Blender 5.2.
- Uses Blender 5.x layered Action channel-bag access when available, with a fallback for older Action F-Curve APIs.
- Blender 5.2 UI icons use supported enum values (the unsupported `ORBIT` icon from earlier builds was replaced).
