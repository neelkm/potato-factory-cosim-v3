"""Upload a completed local release to an existing project repository."""
from pathlib import Path
import argparse,hashlib,json,subprocess,time
ROOT=Path(__file__).resolve().parents[1];REPOSITORY='neelkm/potato-factory-cosim-v3';TAG='v3.0.0'

def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024),b''):value.update(chunk)
    return value.hexdigest()

def gh(*args):return subprocess.check_output(['gh',*args],cwd=ROOT,text=True).strip()

def remote_release():return json.loads(gh('api',f'repos/{REPOSITORY}/releases/tags/{TAG}'))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true');args=parser.parse_args()
    dist=ROOT/'dist';manifest=json.loads((dist/'release_manifest.json').read_text())
    delivery=json.loads((ROOT/'output/delivery_manifest.json').read_text())
    if not manifest['verified'] or not delivery['passed']:raise RuntimeError('Complete local validation is required')
    portability=json.loads((ROOT/'output/replay_portability_validation.json').read_text())
    if not portability['passed']:raise RuntimeError('Extracted replay has not passed portability checks')
    for group in ['assets','replay']:
        if portability[group+'_manifest_sha256']!=digest(dist/(group+'-manifest.json')):raise RuntimeError('Portability check belongs to a different release bundle')
    files=[]
    for group in manifest['groups']:
        files.append(dist/(group['group']+'-manifest.json'))
        for part in group['parts']:
            path=dist/part['name']
            if path.stat().st_size!=part['bytes'] or digest(path)!=part['sha256']:raise RuntimeError('Local release part changed: '+path.name)
            files.append(path)
    files += [dist/'release_manifest.json',ROOT/'output/potato_factory.mp4',ROOT/'output/poster.jpg']
    if digest(ROOT/'output/potato_factory.mp4')!=delivery['video']['sha256']:raise RuntimeError('Delivered film changed')
    plan=[dict(name=p.name,bytes=p.stat().st_size,sha256=digest(p),path=str(p)) for p in files]
    if not args.publish:
        print(json.dumps(dict(repository=REPOSITORY,tag=TAG,assets=plan),indent=2));return
    if gh('repo','view',REPOSITORY,'--json','visibility','--jq','.visibility')!='PRIVATE':raise RuntimeError('This release targets a private project')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise RuntimeError('Commit the reviewed source before publication')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    remote_commit=gh('api',f'repos/{REPOSITORY}/commits/main','--jq','.sha')
    if remote_commit!=commit:raise RuntimeError('Remote source does not match the reviewed local commit')
    releases=json.loads(gh('api',f'repos/{REPOSITORY}/releases'))
    existing=next((r for r in releases if r['tag_name']==TAG),None)
    if existing and not existing['draft']:raise RuntimeError('Published release already exists; inspect it before making changes')
    if not existing:
        gh('release','create',TAG,'--repo',REPOSITORY,'--target',commit,'--title','FIELD / FLOW 3.0','--draft','--notes-file',str(ROOT/'docs/release_notes.md'))
    for row in plan:
        assets={a['name']:a for a in remote_release()['assets']};asset=assets.get(row['name'])
        if asset:
            if asset.get('digest')!='sha256:'+row['sha256'] or asset['size']!=row['bytes']:raise RuntimeError('Existing remote asset differs: '+row['name'])
            print('UPLOAD_VERIFIED_EXISTING',row['name'],flush=True);continue
        print('UPLOADING',row['name'],row['bytes'],flush=True)
        # A failed upload may already have reached GitHub. Read the resulting
        # asset before retrying so an uncertain response cannot overwrite it.
        for attempt in range(3):
            try:gh('release','upload',TAG,row['path'],'--repo',REPOSITORY);break
            except subprocess.CalledProcessError:
                assets={a['name']:a for a in remote_release()['assets']};asset=assets.get(row['name'])
                if asset and asset.get('digest')=='sha256:'+row['sha256'] and asset['size']==row['bytes']:break
                if asset or attempt==2:raise
                time.sleep(2)
        asset=next(a for a in remote_release()['assets'] if a['name']==row['name'])
        if asset.get('digest')!='sha256:'+row['sha256'] or asset['size']!=row['bytes']:raise RuntimeError('Remote upload verification failed: '+row['name'])
        print('UPLOAD_VERIFIED',row['name'],flush=True)
    gh('release','edit',TAG,'--repo',REPOSITORY,'--draft=false','--latest')
    release=remote_release()
    if release['draft']:raise RuntimeError('Release is still a draft')
    receipt=dict(passed=True,repository='https://github.com/'+REPOSITORY,release=release['html_url'],commit=commit,
                 assets=[dict(name=a['name'],bytes=a['size'],digest=a.get('digest'),url=a['browser_download_url']) for a in release['assets']])
    (ROOT/'output/publication_receipt.json').write_text(json.dumps(receipt,indent=2))
    print('GITHUB_RELEASE_COMPLETE',receipt['release'],flush=True)
if __name__=='__main__':main()
