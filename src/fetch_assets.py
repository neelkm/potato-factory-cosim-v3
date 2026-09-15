"""Download public SimReady USD layers and concrete UDIM tiles, recording hashes."""
from pathlib import Path
import json, urllib.request, urllib.error, hashlib
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'assets/forklift_blue_c01/download_manifest.json'
def main():
    m=json.loads(SOURCE.read_text());base=m['source'].rsplit('/',1)[0]+'/'
    out=ROOT/'assets/forklift_blue_c01';out.mkdir(parents=True,exist_ok=True)
    urls=[f['url'] for f in m['files'] if 'sha256' in f]
    def fetch(url):
        dest=out/url.removeprefix(base)
        try:
            if not dest.exists():
                with urllib.request.urlopen(url,timeout=90) as r: data=r.read()
                dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
            else:data=dest.read_bytes()
            print('ASSET',dest.relative_to(out),len(data),flush=True)
            return dict(url=url,path=dest.relative_to(ROOT).as_posix(),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        except urllib.error.HTTPError as e:
            if e.code not in (403,404):raise
            return dict(url=url,unavailable=e.code)
    with ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(fetch,urls))
    report=dict(catalog='https://simready-central.nvidia.com',source=m['source'],files=results)
    (out/'download_manifest.json').write_text(json.dumps(report,indent=2))
    print('ASSET_DOWNLOAD_COMPLETE',sum('sha256' in r for r in results),flush=True)
if __name__=='__main__':main()
