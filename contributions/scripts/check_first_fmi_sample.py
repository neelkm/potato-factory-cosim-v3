"""Native reproduction of ovfmi's first mapped-input sample, without physics.

Run with .venv_physx/Scripts/python.exe. The delivered controller FMU is used
unchanged. This records current behavior and the factory's explicit workaround;
it does not modify ovfmi or assert a proposed new initialization contract.
"""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from config import OUT
from fmi_control import Controller, INPUTS, author


def sample(primed):
    from pxr import Usd, UsdGeom
    import ovstage

    path = OUT / ('fmi_first_sample_primed.usda' if primed else 'fmi_first_sample_raw.usda')
    authored = Usd.Stage.CreateNew(str(path))
    UsdGeom.Xform.Define(authored, '/World')
    author(authored)
    authored.GetRootLayer().Save()
    stage = ovstage.Stage('fmi-first-sample-' + str(primed))
    ovstage.population.open_usd(stage, str(path), ordinal=1)
    stage.advance_write_floor(1).wait()
    controller = Controller(stage, path)
    try:
        inputs = dict.fromkeys(INPUTS, 0.)
        inputs['targetCount'] = 18.
        if primed:
            controller.step(1 / 30, **inputs)
        inputs.update(boxCount=18., boxReady=1.)
        return [controller.step(1 / 30, **inputs) for _ in range(2)]
    finally:
        controller.close()
        stage.destroy()


def main():
    raw = sample(False)
    primed = sample(True)
    report = dict(
        passed=raw[0]['packRequest'] == 0. and raw[1]['packRequest'] == 1.
        and all(row['packRequest'] == 1. for row in primed),
        qualification='Observed initialization behavior and explicit idle-step workaround',
        ovfmi_source_commit='da9ce230ccaf464aca6a5246ac3ace1c925c4eeb',
        fmu_sha256=hashlib.sha256((OUT / 'FactoryController.fmu').read_bytes()).hexdigest(),
        input=dict(boxCount=18., boxReady=1., targetCount=18.),
        unprimed=raw,
        primed=primed,
        explicit_initialization_offset_seconds=1 / 30,
        physics_engine_created=False,
    )
    (OUT / 'fmi_first_sample_contribution_validation.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if not report['passed']:
        raise SystemExit('Upstream initialization behavior differs; review the workaround and reproduction')


if __name__ == '__main__':
    main()
