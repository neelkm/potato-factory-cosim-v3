---
name: cosim-handoff-validation
description: Build or review qualification for rigid-body ownership handoff between physics engines in a USD co-simulation. Use when changing a handoff protocol, engine adapter or contact-boundary strategy.
---

# Qualify a cross-engine handoff

Establish which engine owns each real body and which copies are inactive or proxies. Select a boundary approach appropriate to the contacts: move a complete assembly into one solver for tightly coupled loads; use halo teleport for separated bodies with duplicated support; require actual proxy/wrench capabilities for cross-boundary contact.

Inspect the installed adapter APIs and pinned source revisions. A supported USD schema or a matching buffer shape does not prove the engine can export or import the required state.

Specify pose origin, coordinate frame, quaternion order, velocity reference point, units, COM and inertia axes. Read [the packet contract](references/packet-contract.md) when implementing a complete-state transfer. Verify mass properties independently where possible: a roundtrip between two adapters can hide the same incorrect convention in both.

For a paused ownership transaction, export the full group, freeze and verify the sender, import into the inactive receiver, activate and read back, then commit ownership. Preserve packet and receiver echo as evidence. If a result is ambiguous, halt the coordinator; a late reply must not satisfy a subsequent request. A rollback is successful only after confirming the receiver is inactive and the restored sender is active. A known rollback does not establish that a partially stepped multi-engine run is safe to continue.

Use qualification scenes that reveal the changed behavior. Include nonzero velocity, rotation, an off-centre COM and anisotropic inertia when testing a rigid-body importer. Check both the paused transfer and the receiver's first integration step. For a container, include separate contents and joints, then check containment after motion. For a force boundary, check contact stability and same-tick feedback under the intended rates and object density.

Separate evidence levels in the result: graph/policy tests, native isolated dynamics, full application outcomes and replay/render validation. A policy-only example cannot establish native proxy contact support. A clean-looking video cannot establish correct ownership or physical mass properties. Report unqualified capabilities explicitly and preserve user-selected scope.

Checkpoint a working project before changing incompatible native packages or representations. A file checkpoint is not a serialized solver/FMU state unless that capability has actually been implemented and checked.
