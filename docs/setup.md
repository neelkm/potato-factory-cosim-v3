# Setup and reproducibility

The delivered local folder already contains working isolated environments and Blender. Open `Launch Factory.cmd`. Native execution was qualified on Windows x64, CPython 3.12.6 and an NVIDIA RTX A6000 with 48 GB memory. The base Python installation, Windows C++ runtime and NVIDIA driver are workstation dependencies.

## From GitHub

Clone the private project and download its release asset bundle and replay parts. Use `scripts/unpack_release.py` to verify hashes and extract them into the project root. They contain Blender/USD scenes, textures, original asset provenance, bridge DLLs, the FMU, measured replay and video. Large media and caches are kept out of Git history.

```powershell
gh repo clone neelkm/potato-factory-cosim-v3
cd potato-factory-cosim-v3
gh release download v3.0.0 --dir downloads/release --pattern '*manifest.json' --pattern '*.part*' --pattern 'factory-*.zip'
py -3.12 scripts/unpack_release.py downloads/release/release_manifest.json
```

Multipart archives are reassembled automatically. Keep every part beside its manifest. Extraction verifies all hashes and refuses to overwrite a different local file. To verify a download without extracting, add `--verify-only`.

The source repositories and native runtimes are independently pinned. Inspect the plan first:

```powershell
py -3.12 scripts/bootstrap.py --plan
py -3.12 scripts/bootstrap.py --fetch-sources
py -3.12 scripts/bootstrap.py --install
```

The source download uses the GitHub CLI's existing authentication. It retrieves NVIDIA cosim, ovnewton and ovfmi at the recorded commits. It refuses to overwrite an existing source folder. The internal ovstage wheel requires the user's existing NVIDIA network/package access. No access tokens or authenticated configuration files are included in this project.

The installer creates three environments and refuses to alter any existing one. Partial setup should be inspected before rerunning; the installer deliberately does not repair an arbitrary pre-existing environment. Exact package snapshots are in `requirements-*.lock.txt`. Source-only tests cannot qualify GPU dynamics.

| Environment | Purpose | Native stack |
|---|---|---|
| `.venv_coordinator` | NVIDIA graph, orchestration, portable tests | CPU Warp buffers, usd-core; no physics engine |
| `.venv_physx` | Line and water worker, FMI worker, authoring, RTX viewer/rendering | ovphysx 0.5.11; ovstage 0.1.1.355824; ovfmi 0.2.0; ovrtx 0.4.1.364340 |
| `.venv_newton` | Robot and packing worker | ovnewton internal `fe5dcfe9`; Newton 1.5.0; ovstage 0.2.0.378985; Warp 1.16.0 |

The FMI worker uses the PhysX environment's packages but never constructs a PhysX engine. The source and rendering stages are opened in separate native processes. Do not merge these environments or upgrade one native USD package in isolation.

## Editable geometry and native bridges

The asset release includes the stamped Blender scene and all resolved textures. The Blender application itself can be downloaded from the [official Blender 4.5 distribution directory](https://download.blender.org/release/Blender4.5/). This release uses `blender-4.5.13-windows-x64.zip`; the recorded SHA-256 is `b5fdf800ce65fa2f209e8f68d02667e4d720fa1c42f247c72d1882ab04decba6`. Extract its folder under `tools`.

To rebuild the factory geometry, run `src/build_scene.py` through that Blender executable, then `src/assemble_stage.py` and `src/author_topology.py` through the PhysX environment. Keep `output/franka_cell.usda`, `output/franka_kinematics.json`, `output/manifest.json`, source textures and asset folders from the release bundle. `src/rebuild_scene.py`, run through the PhysX environment, orchestrates the complete rebuild, including `prepare_franka.py`, `plan_cell.py`, `author_robot_cell.py` and the forklift preparation.

The two small PhysX bridge DLLs are built from `src/mechanics_bridge.cpp` and `src/fluid_bridge.cpp`. Their existing DLLs are included in the asset release; the matching header snapshot is in Git under `tools/physx_include`. Rebuild with the two `tools/build_*_bridge.cmd` scripts using Visual Studio 2022 C++ Build Tools. These bridges use a native ABI; upgrade them together with the qualified PhysX package and rerun the native checks.

The FMI model is editable in `src/fmu/FactoryController.cpp`. `src/build_fmu.py` rebuilds the DLL and packages its source into `output/FactoryController.fmu`. The model does not implement serialized FMU state; project checkpoints are not live simulation resume points.

## Verification

```powershell
.\.venv_coordinator\Scripts\python.exe -m pytest tests -q
.\.venv_coordinator\Scripts\python.exe examples/coupling_policies.py
.\.venv_physx\Scripts\python.exe src/check_control_parity.py
.\.venv_coordinator\Scripts\python.exe src/check_handoff.py
.\.venv_coordinator\Scripts\python.exe src/check_moving_boundary.py
```

Run the native checks sequentially when no other factory simulation is active. A full rerun is available through the app or `Run simulation.cmd`. It writes a fresh cache, validates the entire batch and exports its replay before opening it. Short or failed runs cannot be used by the release renderer.

The bootstrap recipe was also executed in a fresh project folder on this workstation: it fetched all three pinned source repositories, created three new environments, passed their package-dependency checks, imported the native libraries from their independent installation paths, and passed all 57 CPU tests. `output/clean_install_validation.json` records that qualification. The full native production batch uses the original qualified environments; the fresh-install test does not claim a second full GPU batch. Installation on another workstation still depends on upstream package availability, the matching Windows build environment and the user's repository/package access.
