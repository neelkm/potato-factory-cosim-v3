# Physics debug workspace

Open **Physics debug workspace** in the factory app sidebar, or run `Launch Physics Debug.cmd` to open it directly without starting the RTX renderer. The production simulation and existing film remain unchanged.

## Two views

- **Forklift alignment:** measured versus nominal pallet centre, side-shift correction and travel limit, actual body-origin alignment, authored collision proxies, fork/pallet contact points, contact normals, signed separation, and a per-step impulse graph.
- **Engine handoff:** the loaded-pallet Newton export as a frozen magenta outline, PhysX import readback, activation flags, continuity residuals, assembly membership/counts and mass, followed by native PhysX restart contacts. This view covers the loaded-pallet return; it does not run or inspect Newton's internal solver.

Select a body in the list or click near its centre in the scene. **Body details** exposes its sampled world pose, world COM linear velocity, angular velocity, imported mass, body-local COM and full body-axis inertia tensor about COM, plus the corresponding Newton export. **Contact details** lists sensor/other-body paths, position, normal, separation and signed normal impulse for the current sample. **Data & scope** explains provenance and limitations.

Drag to orbit, scroll to zoom, or use Dock close-up. Left/right arrows advance one 1/240-second step. Timeline bookmarks find the handoff, first native step, first fork/pallet contact and lift. Playback supports 0.1–1× speed. The graph preserves peaks when multiple physics samples occupy one pixel. Produce is shown as optional point markers; it is hidden by default to keep the pallet visible.

## What the data means

This is an **isolated native PhysX reproduction**, initialized from the actual production return packet at tick 125328 (522.2 s), not contact data reconstructed from the original USD movie. It uses the existing forklift trajectory, native carton joints and complete 139-body load. The chassis/fork carriage remains a prescribed actuator; the load responds to native contacts.

The capture covers 16 seconds at 240 Hz: import readback, insertion, lift and the beginning of withdrawal. Sensors are attached to `/World/Pallet` and `/World/Forks`. They include contacts against their other bodies, not every contact elsewhere in the factory. Forklift mode filters specifically to fork/pallet pairs. Duplicate pallet/fork sensor directions are removed before plotting/counting.

The `ovphysx.ContactBinding.read_raw_contact_data` API reports a timestep-averaged normal force. We multiply it by the actual 1/240 s timestep to store the corresponding **normal impulse (N·s)**. Graphs show the largest absolute normal impulse in the filtered sample, not total support force or peak instantaneous force. Signed separation is in metres in the data, millimetres in the UI. Positive values may be predictive contacts inside the configured contact distance with zero impulse. Negative values indicate overlap. Arrows have a fixed 65 mm display length; their length does not encode force. Orange-red markers indicate separation below −1 mm, a display threshold rather than a solver failure verdict.

Collision surfaces come from authored USD collision geometry. Meshes configured as convex hulls are triangulated for display; these are not dumps of the cooked PhysX hulls. Large nonessential structures are wireframes. Native contact positions are independently sampled and can differ slightly from displayed proxy surfaces due to cooking/contact offsets. Centre ΔX is a body-origin diagnostic, not an automatic insertion-clearance or collision-safety certificate.

The magenta outline never implies active Newton simulation. State at capture tick zero is the imported/activated PhysX readback; subsequent samples are PhysX only. Detailed freeze/import/activate timing across the original two processes is outside this capture.

## Capture and reproduce

Use `Capture Physics Debug.cmd` with the installed factory runtimes and the production output present. It acquires `output/simulation.lock`, creates a separate timestamped output directory, records the native tensors, extracts collision proxies, and validates the result. It never overwrites the production replay. Raw buffers are copied before the next step, and capacity overflow aborts instead of silently dropping points.

The viewer loads `output/physics_debug/view.json`, which names the matching timestamped `capture.json` and `motion.npz`. No native physics runtime is loaded inside the debug window. Its UI needs only the factory's existing NumPy/Pillow/Tk dependencies. This separation also allows later OVD or other contact providers to produce the same viewer data without mixing incompatible native libraries.

To record the captioned 26-second demo:

```powershell
.venv_physx/Scripts/python.exe scripts/record_debug_demo.py
```

The script drives the actual window and captures only that window. It writes `output/physics_debug/physics_debug_demo.mp4`, six review stills, and a video manifest. Simulation playback is deliberately slowed or skipped between explanatory chapters; the movie duration is not the simulated duration.

## OvdNext compatibility

OvdNext 0.2.6 successfully read the earlier box/ground compatibility capture, including contact payloads. It rejected the larger loaded-pallet recording with **“Capture load failed: unknown OVD command”**, including outside the filesystem sandbox. Root cause has not been established. The 486 MB recording is retained locally for diagnosis. Consequently the shipped workspace uses direct ovphysx contact tensors. No preview debugger binaries are redistributed or required.

The optional `--ovd` capture flag enables additional OVD output for future compatibility checks. The existing `PhysXEngine` defaults are unchanged. A native plugin dependency warning occurs on capture shutdown, but the direct sensor capture finalized and its process exited successfully.

## Validation

`scripts/validate_debug_capture.py` checks complete finite per-step arrays, contact indexing and unit normals, source hashes, activation readback, continuity, actual fork contact, successful lift and retained carton contents at every 30 Hz checkpoint. `scripts/qualify_debug_ui.py` exercises real controls at three sizes. Unit tests cover exact sample selection, sensor-pair deduplication, coordinate transforms and wireframe edges. The factory's existing UI smoke check also opens the debug workspace through the main app.

Current recorded outcome: 3,840 native steps; 780,284 raw sensor contact rows; first fork/pallet contact at 9.416667 s after return; all 108 potatoes retained in cartons with counts 20, 17, 17, 18, 18, 18. Raw row count includes both sensor directions before viewer deduplication.

## Further extensions

The neutral capture format can accommodate additional sensors or OVD decoding when compatible. Useful next additions are authored fork-entry clearance measurements, support/contact classification, outgoing carton transfer views, and explicit per-phase ownership traces. Full Newton contact introspection would require a separate Newton-native producer; it should retain an explicit engine/source identity.

The pre-change committed source archive is `output/physics_debug/source_before_viewer.zip`. The earlier full master checkpoint remains available.
