# Post-wash scrubber qualification

The production run completed 575.033 simulated seconds and passed all 45 end-to-end checks.

| Measurement | Result |
|---|---:|
| Washed and scrubbed potatoes | 126 |
| Good potatoes packed | 108 |
| Damaged potatoes discarded | 18 |
| Carton counts | 19, 17, 19, 17, 18, 18 |
| Committed ownership transfers | 7 |
| Native loaded brush contact rows | 143,949 |
| Minimum accumulated brush contact | 1.892 s |
| Minimum accumulated tangential slip | 63.8 mm |
| Peak normal brush contact force | 4.874 N |
| Maximum compliant-envelope penetration | 40.1 mm |

The brush is a compliant cylindrical contact envelope. Its penetration represents
soft-brush compression; individual bristle bending is not solved. The visual hub
has a 16 mm radius, with 44 mm bristles. This is a coarse mechanical approximation,
not a calibrated model of soil detachment or cleaning effectiveness.

The original stage, geometry, physics partitions, Blender model and scene manifest
match their pre-change checkpoint hashes. The old replay, cache and film remain
available through `Launch Factory Original.cmd`.

The measured USD replay has 17,252 frames in 39 value clips. All checked segment
boundaries match recorded positions with zero error. The native RTX app passed
station switching, scrubbing counter, seeking, playback, camera control, reload,
and physics-debug integration checks at both supported window sizes. The 33-test
regression suite also passes.

The captioned film is 30 seconds at 1920×1080 and 24 fps. All 720 encoded frames
passed a full FFmpeg decode with no errors. Its evidence is
`output/scrub_media/video_validation.json`; the delivery file hashes are in
`output/scrub_delivery_manifest.json`.

Evidence: `output/scrub_20261005/validation.json`, `simulation.json`,
`replay_validation.json`, `output/ui_scrub_smoke_validation.json`,
`output/scrub_probe_validation.json`, and `output/scrub_checkpoint_validation.json`.

See [the design and reproduction guide](post_wash_scrubbing.md) for references,
assumptions, launch options, and commands. These are local additions; the linked
GitHub v3.0.0 release remains the original release.
