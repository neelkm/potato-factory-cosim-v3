"""Check every production cargo inertia tensor through the PhysX importer."""
import json,numpy as np,ctypes as C
from scipy.spatial.transform import Rotation
from config import OUT
from physx_engine import PhysXEngine
from ovphysx.types import TensorType
from mechanics import Mechanics
from state_protocol import continuity

def main():
    saved=json.loads((OUT/'cache/simulation.json').read_text())
    paths=sorted({'/World/Pallet'}|{p for request in saved['carton_requests'] for p in request['paths']})
    engine=PhysXEngine(str(OUT/'factory_physx.usda'),inactive=paths)
    try:
        native=Mechanics(engine.px);native.dll.mass_properties.argtypes=[C.c_void_p,C.c_void_p];native.dll.mass_properties.restype=None
        def native_error(rows):
            peak=0.
            for row in rows:
                values=np.empty(11,np.float32);native.dll.mass_properties(native.ptr(row['path']),values.ctypes.data)
                r=Rotation.from_quat(values[4:8]).as_matrix();expected=r@np.diag(values[8:11])@r.T
                peak=max(peak,float(np.max(abs(expected-row['inertia']))))
            return peak
        states=engine.export_state(paths);initial_native_error=native_error(states);cases=[]
        for label in ['authored_cargo','rotated_tensor_fixture']:
            if label=='rotated_tensor_fixture':
                rotation=Rotation.from_euler('xyz',[23,-31,47],degrees=True).as_matrix()
                for row in states:row['inertia']=(rotation@np.asarray(row['inertia'])@rotation.T).tolist()
            engine.set_active(paths,False);engine.import_state(states);engine.set_active(paths,True)
            after=engine.export_state(paths)
            relative=max(float(np.max(abs(np.asarray(a['inertia'])-b['inertia']))/np.max(abs(np.asarray(a['inertia'])))) for a,b in zip(states,after))
            residual=continuity(states,after)
            cases.append(dict(case=label,continuity=residual,relative_inertia_error=relative,native_getter_error=native_error(after)))
        report=dict(bodies=len(paths),initial_native_getter_error=initial_native_error,cases=cases,
                    passed=initial_native_error<2e-7 and all(c['relative_inertia_error']<1e-5 and c['native_getter_error']<2e-7 for c in cases),
                    scope='Native PhysX tensor import/export compared independently with PxRigidDynamic COM and principal-inertia getters; actual139 cargo bodies plus deliberately rotated anisotropic tensors; no simulation steps')
        (OUT/'inertia_roundtrip_validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
        if not report['passed']:raise RuntimeError('Native inertia-frame validation failed')
    finally:engine.close()

if __name__=='__main__':main()
