# Completed co-simulation validation

The complete native production run lasted 576.23 simulated seconds. All 39 production checks passed.

| Result | Measured outcome |
| --- | --- |
| Washing and inspection | All 126 potatoes washed before inspection; each inspected once |
| Good produce | Carton counts 20, 17, 17, 18, 18, 18; all 108 retained through delivery |
| Damaged produce | All 18 in the discard bin; no good potatoes discarded |
| Franka handling | Six pickups with four verified suction contacts; six controlled releases |
| Engine transfers | Six cartons to Newton, followed by the complete loaded pallet back to PhysX |
| Forklift | Loaded pallet delivered to dispatch; no floor spillage |

Seven ownership transfers committed at paused clock boundaries. Largest position discontinuity: 0 m.
Maximum measured carton plus tool load: 2.352 kg (3 kg limit).
Water inlet rate: 1794.93 particles/s; 2.000 times the original flow.
Film: 57 seconds, 1920 × 1080, 24 fps; all 1368 frames decoded. Native ovrtx path tracing, 16 samples per pixel and OptiX denoising.
Desktop viewer: station navigation, seeking, half-speed playback, orbit, zoom and replay reload passed with this complete run.

Detailed checks and measured handoff residuals: `output/cache/validation.json`. Exact package versions and video hashes: `output/delivery_manifest.json`.
The replay records measured dynamics. The simulation source remains `output/factory.usda`, with separate native engine partitions.
The native stress tests and protocol failure tests are separate qualification artifacts, not substitutes for this completed batch.

Physical scope and rebuild/rollback instructions are in the project README.

## Additional qualification

- 57 CPU tests: 22 project checks and 35 original NVIDIA cosim checks.
- Native FMI and reference controls compared across 600 samples.
- Loaded 23-body carton roundtrip, rotating moving-boundary transfer, and 139-body inertia checks.
- Positive and negative native fixtures for fork alignment, belt clearing and queue guides; a complete Newton pickup beside the guides.
- Fresh source fetch and three-environment installation on this workstation, plus extracted asset and replay portability checks.
- All thirteen film shots inspected at three decoded frames per shot; each assembled midpoint matches its source clip pixel-for-pixel.
- Desktop controls checked at 1100 × 840 and 1280 × 900 for all three run profiles.

Detailed JSON receipts are in the release media and replay bundles. Only Full simulation has a separately qualified complete production batch. Advanced replica and proxy-force APIs require their own native contact qualification; see [coupling options](coupling_options.md).
