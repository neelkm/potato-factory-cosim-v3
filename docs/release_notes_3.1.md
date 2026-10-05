FIELD / FLOW 3.1 adds post-wash PhysX scrubbing, a physics debug workspace, and two captioned videos to the NVIDIA cosim potato factory.

- Six driven brush rotors between washing and inspection. FMI acceptance requires measured brush contact and tangential slip.
- Updated Blender/USD scenes, stainless station housing, catch tray, service lighting, and a dedicated app station view.
- Forklift/pallet alignment and PhysX-side Newton handoff debugger, with native contact samples and body metadata. Its bundled recording is the preserved pre-scrubber capture and is labelled accordingly.
- Complete scrubber run: 126 scrubbed, 108 packed, 18 discarded, six cartons, seven committed engine transfers, successful forklift delivery. All 45 production checks passed.
- 30-second 1080p factory film (`potato_factory_scrub.mp4`) and 26-second debugger demonstration (`physics_debug_demo.mp4`).

## Install

Clone this release's source and run `py -3.12 scripts/download_latest.py` from the project folder with GitHub CLI available. It downloads the preserved v3.0.0 base bundles and the v3.1.0 update, checks hashes, and extracts both. Follow `docs/setup.md` for the three native environments and required NVIDIA repository/package access. The public source does not remove those upstream access requirements.

The `factory-scrub-v3.zip` parts are an **update bundle requiring v3.0.0 assets/replay/media**, not a standalone scene. Keep every part beside `scrub-manifest.json`. Existing base downloads can be reused; extraction refuses to overwrite differing local files. The original release and its film remain available.

The scrubber uses compliant rigid brush envelopes and an empirical contact/slip cleaning proxy. Individual bristle bending and soil-grain detachment are not simulated. This is not a calibrated sanitation model. Source references and measured limits are documented in `docs/post_wash_scrubbing.md` and `docs/scrub_validation.md`.
