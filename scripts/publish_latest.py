"""Publish the verified 3.1 overlay without modifying the preserved 3.0 release."""
from pathlib import Path
import argparse,json,subprocess
from publish_release import digest,gh,remote_release,ROOT,REPOSITORY

TAG='v3.1.0'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true');args=parser.parse_args()
    manifest=ROOT/'dist/scrub-manifest.json'
    report=json.loads(manifest.read_text())
    if not report['verified']:raise RuntimeError('Archive not verified')
    # Verify every archived member before any network mutation.
    from unpack_release import unpack
    unpack(manifest,ROOT,verify_only=True)
    portability=json.loads((ROOT/'output/scrub_portability_validation.json').read_text())
    if not portability['passed'] or portability['scrub_manifest_sha256']!=digest(manifest):raise RuntimeError('Relocated archive validation missing or stale')
    for name in ['scrub_delivery_manifest.json','scrub_20261005/validation.json','scrub_20261005/replay_validation.json','scrub_media/video_validation.json','ui_scrub_smoke_validation.json']:
        if not json.loads((ROOT/'output'/name).read_text())['passed']:raise RuntimeError('Failed validation: '+name)
    delivery=json.loads((ROOT/'output/scrub_delivery_manifest.json').read_text())
    for row in delivery['files']:
        if digest(ROOT/'output'/row['path'])!=row['sha256']:raise RuntimeError('Delivery changed: '+row['path'])
    files=[manifest]+[ROOT/'dist'/p['name'] for p in report['parts']]
    files += [ROOT/'output/potato_factory_scrub.mp4',ROOT/'output/physics_debug/physics_debug_demo.mp4',ROOT/'output/scrub_media/poster.jpg']
    plan=[dict(name=p.name,path=str(p),bytes=p.stat().st_size,sha256=digest(p)) for p in files]
    if not args.publish:print(json.dumps(plan,indent=2));return
    if gh('repo','view',REPOSITORY,'--json','visibility','--jq','.visibility')!='PUBLIC':raise RuntimeError('Expected existing public repository')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise RuntimeError('Commit source before publication')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if gh('api',f'repos/{REPOSITORY}/commits/main','--jq','.sha')!=commit:raise RuntimeError('Remote source mismatch')
    base=json.loads(gh('api',f'repos/{REPOSITORY}/releases/tags/v3.0.0'))
    if base['draft']:raise RuntimeError('Base release unavailable')
    releases=json.loads(gh('api',f'repos/{REPOSITORY}/releases'))
    release=next((r for r in releases if r['tag_name']==TAG),None)
    if release and not release['draft']:raise RuntimeError('Release is already published')
    if not release:
        gh('release','create',TAG,'--repo',REPOSITORY,'--target',commit,'--title','FIELD / FLOW 3.1 — scrubbing and physics debug','--draft','--notes-file',str(ROOT/'docs/release_notes_3.1.md'))
        release=next(r for r in json.loads(gh('api',f'repos/{REPOSITORY}/releases')) if r['tag_name']==TAG)
    if release['target_commitish']!=commit:raise RuntimeError('Draft targets another commit')
    for row in plan:
        asset=next((a for a in remote_release(release['id'])['assets'] if a['name']==row['name']),None)
        if asset is None:
            print('UPLOADING',row['name'],row['bytes'],flush=True)
            gh('release','upload',TAG,row['path'],'--repo',REPOSITORY)
            asset=next(a for a in remote_release(release['id'])['assets'] if a['name']==row['name'])
        if asset['size']!=row['bytes'] or asset.get('digest')!='sha256:'+row['sha256']:raise RuntimeError('Upload mismatch: '+row['name'])
        print('UPLOAD_VERIFIED',row['name'],flush=True)
    gh('release','edit',TAG,'--repo',REPOSITORY,'--draft=false','--latest')
    latest=json.loads(gh('api',f'repos/{REPOSITORY}/releases/latest'))
    if latest['tag_name']!=TAG or latest['draft']:raise RuntimeError('Latest release verification failed')
    (ROOT/'output/publication_3.1_receipt.json').write_text(json.dumps(dict(passed=True,commit=commit,release=latest['html_url'],assets=latest['assets']),indent=2))
    print('PUBLISHED',latest['html_url'],flush=True)

if __name__=='__main__':main()
