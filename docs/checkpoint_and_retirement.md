# Local rollback and retained references

These paths refer to the original `C:\Users\neelakantanm\AIClaude\Codex` workstation workspace. They are independent of the new GitHub project.

## Master before version 3

`factory_checkpoints/master_20260915/potato_factory_cosim` contains the complete previously delivered co-simulation app, source, runtimes, assets, measured runs, Blender/USD stages and video. The checkpoint consists of 127,890 independent file copies totaling 94,656,297,849 bytes. Every destination file was checked against its source SHA-256 when the checkpoint was created; no hardlinks were used.

The checkpoint's `manifest.json` records the relative path, size and hash of every file. The original working app remains in `potato_factory_cosim` and is separate from both the checkpoint and `potato_factory_v3`.

Run **Restore Factory master.cmd** in the workspace to restore the checkpoint. The restore helper verifies the checkpoint, copies it to a fresh `potato_factory_restored_master` folder and checks the result. It refuses to overwrite an existing destination. Open the restored folder's **Launch Factory.cmd** after restoration succeeds.

The host Python installation, Windows C++ runtime and NVIDIA driver are system dependencies. This is a complete file checkpoint of the project, not a disk image or a live solver/FMU-state checkpoint.

## Original version 1

`factory_reference/v1` retains 38 individually verified reference files: USD stages, geometry, Blender scene, textures, images, video and provenance. `retirement_manifest.json` records their hashes and original paths. The old version 1 application source, runtime outputs and launchers were removed after preservation was verified.

Version 2 remains in `potato_factory`. Its shared Blender helper was moved into `shared_helpers` and its callers were updated before retiring the original `src` folder. The earlier `factory_checkpoints/v2_20260914` checkpoint also remains available.

## Version 3

`potato_factory_v3` has its own source, runtime copies, assets, simulation cache and render outputs. New app runs create a fresh cache rather than overwriting the delivered production run. The GitHub release contains the version 3 source and downloadable asset, replay and media bundles; the large historical local checkpoints are not duplicated into that release.
