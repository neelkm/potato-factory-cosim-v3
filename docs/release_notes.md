FIELD / FLOW 3.0 is a Blender/OpenUSD agricultural factory with NVIDIA cosim coordination, ovphysx washing and conveyors, an ovnewton Franka packing cell, ovfmi inspection/control and ovrtx rendering.

The release includes the editable app and source, Blender/USD scenes, Franka and SimReady assets, native FMU and bridge binaries, the measured full production replay, station images and a 57-second 1080p film. Validation covers the complete 126-potato batch, six cartons, seven engine ownership transfers and forklift delivery.

Download `potato_factory.mp4` for the film. For the app, clone the repository and follow `docs/setup.md`. Download all manifest files and every archive part; `scripts/unpack_release.py` verifies and reconstructs the bundles. Use the three separate, pinned Python environments described in setup. NVIDIA development repositories and the internal ovstage build require existing access.

The factory uses complete-assembly ownership transactions. NVIDIA teleport, replica and force-exchange APIs remain available through capability-checked extension points; native cross-engine proxy/force contact is outside this release's qualified factory mode. Physical scope and measured results are documented in the repository.

The contribution kit includes tested patches and reproductions for transactional replica routing and ovfmi extraction-error propagation, a proposed handoff-validation skill, and designs for portable workers and assembly transfer. No upstream issue or pull request has been submitted.
