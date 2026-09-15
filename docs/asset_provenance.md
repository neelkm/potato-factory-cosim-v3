# Asset provenance

The factory, truck, irregular potatoes, conveyors, wash station, inspection station, lightweight cartons and custom vacuum tool were authored procedurally in Blender for this project. The version 3 geometry preserves the qualified factory layout and source materials; the framework and recorded dynamics are newly built.

## Source assets

- **Franka FR3:** NVIDIA Isaac asset retained in `assets/franka_fr3/fr3.usd`. Original joint geometry and limits are retained. Stock fingers are replaced with the four-cup tool. The native scene uses a seven-joint, torque-controlled robot. The release manifest records the exact asset hash; the original remote download URL was not retained.
- **Forklift:** SimReady `Vehicle_Forklift_Blue_C01`, accessed through [SimReady Central](https://simready-central.nvidia.com/). Source USD layers and actual UDIM texture tiles are retained in `assets/forklift_blue_c01`. Exact download URLs, sizes and SHA-256 values are in `download_manifest.json`. The detailed shell follows explicitly simulated chassis/fork actuator bodies.
- **Hangar Interior HDRI:** [Poly Haven](https://polyhaven.com/a/hangar_interior), CC0, Dimitrios Savva and Jarod Guest. Used for illumination and reflections.
- **Concrete Floor 02:** [Poly Haven](https://polyhaven.com/a/concrete_floor_02), CC0, Rob Tuytel. Diffuse, roughness and normal textures are in `output/textures`.

NVIDIA assets retain their original notices and applicable asset terms. Project code licensing does not replace third-party asset terms.

## Photographic inspiration

The earlier refinement used Wyma's wet hopper photography, Bulk Lines tipper photographs and KRONEN potato-processing equipment as proportion and material references. These photographs are not composited into the scene or included in the release bundle. Original reference details are retained in `prior_asset_provenance.md`.

The potato skin is a generated tileable base-color texture. Its source prompt and provenance are preserved in that prior record. The visible damage regions are authored mesh materials and correspond to the inspector's defect scores.

## Measured and authored motion

All potato, carton and pallet trajectories in the finished film come from the new recorded native physics run. Water is a surface reconstructed from PhysX particles. Cameras, labels and the inspection tracking marker are presentation elements. Machine actuators follow authored targets; their loads respond to native contacts and constraints.

The editable Blender scene contains 2,576 objects and 223 packed images. `output/asset_validation.json` records that the composed source USD resolves its files within the project. `OmniGlass.mdl` and `OmniPBR.mdl` are renderer-supplied material modules.
