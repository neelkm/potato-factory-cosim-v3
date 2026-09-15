# Opportunities for NVIDIA cosim

These candidates come from implementing and testing FIELD / FLOW 3.0 against NVIDIA cosim `8b45d424641ebc74cbc5660a16aa7bc7eb4efeb3`. They are prepared locally; no upstream issue or pull request has been submitted.

## Recommended first contribution: transactional replica routing

`ReplicaRouter.route` updates owner identities and writes command rows while iterating a batch. If a later row overflows an input buffer, earlier state can already be committed. The factory's `TransactionalReplicaRouter` prepares into temporary buffers and rolls back bookkeeping on failure. A small upstream patch can instead keep owners and transitions local until preparation succeeds.

**Deliverable:** `patches/0001-transactional-replica-router.patch`, plus `scripts/check_router_patch.py`. The regression deliberately triggers an overflow after a valid first row and checks that owner identities, transition count and caller buffers remain unchanged. It also checks a successful two-object crossing. This is a contained code contribution independent of PhysX or Newton installation.

## Portable isolated workers

The original multiprocess implementation uses Linux-oriented process/resource helpers. This workstation needs Windows and incompatible ovstage versions in separate interpreters. Version 3 provides authenticated local RPC, explicit executable selection, sequence IDs, clock preconditions, bounded waits and shared host snapshot arrays.

**Possible contribution:** a portable executor/worker protocol behind the existing scheduler interface, with explicit platform capability checks. Port the minimal worker lifecycle and transport tests, not the entire factory controller. Preserve single-threaded Warp/native host execution inside each worker. Add late-reply, worker-exit, timeout and clock-divergence tests before claiming restart support.

Evidence lives in `src/framework/process.py`, `shared_snapshot.py`, `graph.py` and `tests`. A full distributed retry protocol would additionally need epochs, idempotency, durable ownership commits and solver-state checkpoint support; this release does not claim those features.

## Complete-assembly transfer contract and sample

The upstream boundary payload carries rigid pose and velocities. A loaded carton also needs body identities, contained-body membership, mass, COM, full inertia and supported joint frames. A sample can show a complete contact island moving between engines, followed by a loaded pallet transfer.

**Possible contribution:** an optional versioned assembly packet and paused transaction API above the per-body seam policies. Keep immutable authoring data distinct from measured state and native activation receipts. Specify full inertia axes, COM velocity conventions and quaternion order. Reject unsupported joints and incomplete groups before freezing the sender.

The reusable tests should include a moving, rotating body with an off-centre COM and anisotropic inertia; a loaded 23-body carton; bad receiver readback; activation failure; and first-step continuity. `src/check_moving_boundary.py`, `check_handoff.py` and `state_protocol.py` provide starting material. The factory's PhysX return preserves existing lid constraints, so this is not a general joint-topology transfer implementation.

Include downstream docking as well as immediate state continuity. A returned pallet can preserve every state value correctly yet miss a receiving machine that still targets its nominal authored position. `check_pallet_return.py` compares native docking outcomes and verifies a measured-alignment fork carriage against the same 139-body packet. The full run exposed spilled contents; the isolated nominal-docking control instead dragged the pallet away during withdrawal. Both violate delivery requirements, while the aligned fixture completes delivery.

The replay download includes that exact saved packet and carton membership in `output/qualification/pallet_return/simulation.json`. Its provenance identifies the diagnostic run; it is deliberately labelled as an isolated fixture. With no factory simulation running, reproduce the aligned test with `.venv_physx/Scripts/python.exe src/check_pallet_return.py --cache qualification/pallet_return`, then run the nominal negative control by adding `--nominal`. Omitting `--cache` tests the newly delivered production packet instead.

Machine sequencing needs outcome checks too. `src/check_fill_tail.py` and the small `output/qualification/fill_tail/fixture.json` reproduce a potato missing a carton when the terminal belt stops too early. The production `TerminalBeltDrive` keeps the belt moving briefly after the upstream gate stops the queue. The native fixture retains all 20 potatoes; `--stop` selects the original control and loses one. Initial velocities are estimated from adjacent recorded poses, so this fixture is explicitly distinguished from an exact solver-state restoration.

`src/check_fill_guide.py` adds a separate queue-release fixture from the recorded poses and estimated velocities in `output/qualification/fill_guide/fixture.json`. The original short guide (`--legacy`) loses one of five potatoes; the extended guide retains all five. `src/check_robot_guide_cycle.py` then uses the saved carton packet in `output/qualification/robot_guide_cycle/carton.json` to check one complete Newton pickup and placement beside that guide. These are small, reproducible station outcomes that complement state-transfer tests. The full run also verifies that the gate waits for each replacement carton.

## Port contracts and explicit rate adapters

The core graph validates shape and connection structure. The factory additionally validates semantic layout, units, frame and communication rate before opening the graph. This prevents a matching array shape from hiding an incompatible signal or coordinate convention.

**Possible contribution:** optional contract metadata and a registration point for explicit frame/unit/rate adapters. Begin with rejecting mismatches and proving current-sample ordering. Add physical rate-conversion examples only when required by a real sample. Avoid silently converting time-sensitive proxy-force feedback into a delayed observation edge.

## Handoff-validation skill

`skills/cosim-handoff-validation/SKILL.md` is a proposed reusable skill for building or reviewing native handoff qualification. It focuses on state conventions, active ownership, contact-boundary choice and evidence. It does not install packages, publish work or change global settings by itself.

A useful upstream skill should distinguish policy-only tests from native dynamics, and a replay from a live simulation. This distinction prevented successful standalone tests from being mistaken for a complete factory delivery.

## Factory sample and reproducible media

A compact sample could retain the three engine partitions, the topology, one carton, one robot cycle and a small FMU. The full factory adds fluid washing, a SimReady forklift and six-carton dispatch, but is too large to be the first upstream review.

**Possible contribution:** a reduced sample with generated geometry, an optional SimReady asset download manifest, native outcome validators and a measured USD replay exporter. Keep original asset terms and internal package requirements explicit. The video pipeline could separately demonstrate value clips, capture provenance, same-state RTX frame settling and bounded rendering memory.

## Separate ovfmi issue: first mapped input sample

The pinned FMPy backend's initialization path uses start values without applying the current mapped inputs. The later path applies them. Version 3 runs one idle initialization interval before plant tick zero and verifies native/reference controller agreement across 600 samples.

**Native reproduction:** run `.venv_physx/Scripts/python.exe contributions/scripts/check_first_fmi_sample.py`. With a full carton already present in the mapped inputs, the unprimed controller reports no packing request on its first step and reports the request on its second. After the explicit idle initialization step, the request is present on the first plant step. `output/fmi_first_sample_contribution_validation.json` records both sequences and the 1/30-second initialization offset. This check loads the real FMU through ovfmi without creating a physics engine.

**Possible contribution to ovfmi:** a minimal first-step input regression and a defined initialization contract, followed by a fix that supplies input values during initialization if that is the intended behavior. Do not hide the time offset or claim that a controller with a missed first sample is strictly equivalent.

An additional small candidate is already prepared: `patches/0002-ovfmi-propagate-extraction-errors.patch` and `scripts/check_fmi_error_patch.py`. The current extractor prints an extraction exception and returns an incompletely initialized object, producing a later missing-attribute error. The proposed change re-raises the original exception. The reproduction executes the actual upstream class with an injected permission error and verifies that the candidate preserves that exact exception. It neither patches the installed runtime nor loads a physics engine. Cleanup of partially extracted directories can be considered separately.

## Suggested order

1. Submit the small router failure regression and transactional fix.
2. Offer the validation skill and a minimal moving-body transfer sample.
3. Discuss the portable worker and assembly contract designs before proposing larger code changes.
4. Add the reduced factory/FMU example once package compatibility and asset distribution expectations are agreed.

The measured release checks are in `output/VALIDATION.md`; the architectural implementation and limits are in `docs/architecture.md`. Contribution claims should use those actual results rather than the older master or an unfinished diagnostic run.
