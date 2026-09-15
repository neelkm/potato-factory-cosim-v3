# Choosing a coupling approach

Use the least complex approach that preserves the physical contacts the scene needs. The factory's selected strategy is a complete-assembly transfer: all bodies touching closely during palletizing stay in Newton together, then return to PhysX as a loaded pallet.

| Approach | Good fit | Limits | Version 3 access |
|---|---|---|---|
| Complete-assembly transaction | Cartons with contained produce, a robot carrying a carton, a loaded pallet | Requires the whole group and supported joints in both scenes | Production default, `Coordinator.transfer` |
| NVIDIA halo teleport | Separated rigid objects crossing a boundary with duplicated support geometry | Bodies on opposite sides do not contact each other | `HandoffPolicy`, `NvidiaTeleportBridge` and native moving-body fixture |
| NVIDIA halo replica | Distributed piles where both engines can maintain proxies | One-step stale replica contact; scene-specific stability and capacity qualification | `create_nvidia_zone_policy`, `TransactionalReplicaRouter`, original `SlotPool` |
| NVIDIA explicit force exchange | A narrow seam where one engine can measure proxy contact wrench | Requires force/torque extraction, a receiver wrench port and same-tick ordering | Original `CouplingMode.EXPLICIT_FORCE_EXCHANGE` via `connect_boundary` |
| One engine for a strongly coupled region | Tight contacts, stiff constraints, repeated seam instability | Less backend separation within that region | Factory packing cell demonstrates this partitioning |

The app's whole-factory profiles share the qualified assembly-transfer path. The released complete batch uses Full simulation. Simple controls has a 600-sample native/reference comparison, and Diagnostic transport retains the native engines while replacing shared snapshots with message payloads. These alternatives have not each received a separate full-batch release run. Advanced boundary APIs live alongside the production API so a new scene can choose differently without replacing the framework; native proxy-contact experiments require their own scene qualification.

## Run the examples

From the project folder:

```powershell
.\.venv_coordinator\Scripts\python.exe examples/coupling_policies.py
.\.venv_coordinator\Scripts\python.exe src/check_moving_boundary.py
.\.venv_coordinator\Scripts\python.exe src/check_handoff.py
```

Run native qualifications when no factory PhysX run is active. The first example executes NVIDIA's actual teleport, replica and force policy state machines on known input records. It validates routing decisions and command ports, not contact physics. The moving-boundary example executes both native engines and uses NVIDIA zone decisions. The loaded-carton example checks all 23 bodies and the native FMI packing interlock.

```python
from framework.coupling import FACTORY_CAPABILITIES, select_policy

policy = select_policy(
    assembly=True,
    contact_across_boundary=True,
    capabilities=FACTORY_CAPABILITIES,
)
# assembly_transaction
```

For native replica or proxy-force experiments, use the pinned upstream examples and their compatible engine package set. The original factory adapters intentionally declare no proxy-force or replica capability. Supplying a capability object is not an implementation: the chosen adapter must expose and validate the corresponding native port bindings.

NVIDIA's `HandoffPolicy` has a one-tick active overlap when leaving a force-capable cell; `ReplicaRouter` uses promotion/demotion at the next barrier. Those semantics differ from this factory's explicit freeze/import/activate transaction. Do not combine both owners' trajectories into the replay or interpret a proxy as another physical potato.

`TransactionalReplicaRouter` adds preparation before bookkeeping commits. If a boundary buffer overflows, input buffers and ownership remain unchanged. This is a candidate upstream improvement. It does not provide distributed retries, durable messaging or mid-run worker restart.
