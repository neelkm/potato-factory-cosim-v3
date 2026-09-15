# Complete rigid-body packet

For each stable body identity, carry world body-origin position, a unit quaternion with declared order, world COM linear velocity, world angular velocity, positive mass, body-local COM and a symmetric positive definite inertia tensor about COM in body axes. State units explicitly.

Carry complete container membership and supported joint endpoint identities and frames. Include a protocol version, an exact shared tick and a transaction identity. Reject duplicate bodies, non-finite values, missing members, joints crossing the transfer boundary and unsupported joint representations before changing active ownership.

Record source and echoed receiver packets. Compare orientation by its sign-invariant angular difference; `q` and `-q` are the same rotation. Use unitful absolute tolerances and scale-aware inertia tolerances. Check momentum from mass, COM velocity, world orientation and inertia, not merely velocity equality. Treat renderer poses and stale inactive replicas as observations, not authoritative physics state.

Activation semantics are engine-specific. For example, the qualified PhysX build clears velocity when disabling an actor and requires velocity restoration after activation. Its full inertia binding is already expressed in body axes; the COM quaternion identifies the internal principal axes and must not rotate that tensor a second time. Recheck these behaviors when upgrading the SDK.

Constraint data often contains immutable authoring and solver-maintained state. State which portions are transferred, reconstructed or retained in the receiving scene. A rigid closed-lid sample does not establish support for generic articulated joint topology, contact warm starts, deformables or fluid state migration.
