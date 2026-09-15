"""Check composed USD asset dependencies before packaging or rendering."""
from pathlib import Path
import argparse,json
from pxr import Usd,Sdf,Ar
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=ROOT);args=parser.parse_args();root=args.root.resolve()
    stage=Usd.Stage.Open(str(root/'output/factory.usda'));missing=[];outside=[];resolved=set();builtins=set()
    for prim in stage.Traverse():
        for attribute in prim.GetAttributes():
            if attribute.GetTypeName() not in (Sdf.ValueTypeNames.Asset,Sdf.ValueTypeNames.AssetArray):continue
            value=attribute.Get();values=[value] if isinstance(value,Sdf.AssetPath) else (list(value) if value else [])
            for asset in values:
                if not asset.path:continue
                if asset.path in ('OmniGlass.mdl','OmniPBR.mdl','UsdPreviewSurface'):builtins.add(asset.path);continue
                location=asset.resolvedPath
                if not location and '<UDIM>' in asset.path:
                    layer=attribute.GetPropertyStack()[0].layer
                    pattern=Path(layer.realPath).parent/asset.path
                    matches=list(pattern.parent.glob(pattern.name.replace('<UDIM>','1[0-9][0-9][0-9]')))
                    if matches:
                        resolved.update(str(p.resolve()) for p in matches)
                        outside.extend(str(p.resolve()) for p in matches if not p.resolve().is_relative_to(root));continue
                if not location:missing.append(dict(attribute=str(attribute.GetPath()),asset=asset.path));continue
                path=Path(location).resolve();resolved.add(str(path))
                if not path.is_relative_to(root):outside.append(str(path))
    layers=[Path(layer.realPath).resolve() for layer in stage.GetUsedLayers() if layer.realPath]
    outside.extend(str(path) for path in layers if not path.is_relative_to(root))
    report=dict(passed=not missing and not outside,missing=missing,outside_project=sorted(set(outside)),
                native_mdl_modules=sorted(builtins),resolved_assets=sorted(resolved),usd_layers=[str(p.relative_to(root)) for p in layers if p.is_relative_to(root)])
    (root/'output/asset_validation.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='resolved_assets'},indent=2))
    if not report['passed']:raise SystemExit(1)
if __name__=='__main__':main()
