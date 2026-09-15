"""Verify release parts and safely extract into a cloned project folder."""
from pathlib import Path
import argparse,hashlib,json,zipfile,shutil,stat,os

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def unpack(manifest,destination,verify_only=False):
    manifest=Path(manifest).resolve();destination=Path(destination).resolve();report=json.loads(manifest.read_text());base=manifest.parent
    for group in report.get('groups',[report]):
        for part in group['parts']:
            if Path(part['name']).name!=part['name']:raise ValueError('Invalid part filename')
            path=base/part['name']
            if path.stat().st_size!=part['bytes'] or digest(path)!=part['sha256']:raise RuntimeError('Part checksum mismatch: '+path.name)
        if Path(group['archive']).name!=group['archive']:raise ValueError('Invalid archive filename')
        archive=base/group['archive']
        if len(group['parts'])>1:
            if not archive.exists():
                temporary=archive.with_suffix('.joining')
                with temporary.open('wb') as output:
                    for part in group['parts']:
                        with (base/part['name']).open('rb') as source:shutil.copyfileobj(source,output,8*1024*1024)
                os.replace(temporary,archive)
        if digest(archive)!=group['archive_sha256']:raise RuntimeError('Joined archive checksum mismatch')
        entries={row['path']:row for row in group['files']}
        with zipfile.ZipFile(archive) as zipped:
            if set(zipped.namelist())!=set(entries):raise RuntimeError('Archive membership differs from manifest')
            for info in zipped.infolist():
                target=(destination/info.filename).resolve()
                if not target.is_relative_to(destination) or stat.S_ISLNK(info.external_attr>>16):raise ValueError('Unsafe archive member')
                if verify_only:
                    h=hashlib.sha256()
                    with zipped.open(info) as stream:
                        for chunk in iter(lambda:stream.read(8*1024*1024),b''):h.update(chunk)
                    if h.hexdigest()!=entries[info.filename]['sha256']:raise RuntimeError('Archived member checksum mismatch')
                    continue
                if target.exists():
                    if digest(target)!=entries[info.filename]['sha256']:raise RuntimeError('Existing file differs; preserve it before extracting: '+str(target))
                    continue
                target.parent.mkdir(parents=True,exist_ok=True);temporary=target.with_name(target.name+'.extracting')
                with zipped.open(info) as source,temporary.open('wb') as output:shutil.copyfileobj(source,output,8*1024*1024)
                if digest(temporary)!=entries[info.filename]['sha256']:raise RuntimeError('Extracted member checksum mismatch')
                os.replace(temporary,target)
        print('VERIFIED' if verify_only else 'EXTRACTED',group['group'],len(entries),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('manifest');parser.add_argument('--destination',default='.');parser.add_argument('--verify-only',action='store_true');args=parser.parse_args()
    unpack(args.manifest,args.destination,args.verify_only)
