#!/usr/bin/env python3
"""Move an explicit allowlist of job caches into recoverable job-local trash."""
import argparse
import hashlib
import json
import shutil
from datetime import datetime,timezone
from pathlib import Path

def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
    return value.hexdigest()

def contained(job,value):
    raw=Path(value)
    if raw.is_absolute():raise ValueError('Manifest paths must be job-relative')
    path=job/raw
    current=job
    for part in raw.parts:
        current=current/part
        if current.is_symlink():raise ValueError('Symlink paths are not eligible for cleanup')
    resolved=path.resolve()
    if not resolved.is_relative_to(job) or resolved==job:raise ValueError('Path leaves job root')
    return resolved

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--apply',action='store_true',help='Default is dry-run')
    args=parser.parse_args();job=args.job.resolve()
    if not job.is_dir():raise ValueError('Job directory does not exist')
    if job==Path.home() or job==Path(job.anchor):raise ValueError('Use a specific job directory')
    data=json.loads(args.manifest.read_text(encoding='utf-8'))
    if not data.get('cache_roots'):raise ValueError('cache_roots allowlist is required')
    roots=[contained(job,x) for x in data['cache_roots']]
    for root in roots:
        if root.name not in {'render_work','cache','frames','temp','tmp','intermediates'} and not root.name.endswith('_render_work'):
            raise ValueError('Cache root must have an explicit temporary-directory name')
    preserve=[contained(job,x) for x in data.get('preserve',[])]
    manifest_path=args.manifest.resolve();entries=[];seen=set()
    for item in data.get('files',[]):
        if item.get('rebuildable') is not True or not item.get('reason'):
            raise ValueError('Each candidate needs rebuildable:true and a reason')
        path=contained(job,item['path'])
        if path in seen:raise ValueError('Duplicate candidate')
        seen.add(path)
        if not path.is_file() or not any(path.is_relative_to(root) for root in roots):
            raise ValueError('Candidate is not a file beneath an allowed cache root')
        if path==manifest_path or any(path==p or path.is_relative_to(p) for p in preserve):
            raise ValueError('Candidate is preserved')
        if path.suffix.lower() not in {'.mp4','.mov','.mkv','.webm','.png','.jpg','.jpeg','.wav','.tmp','.pyc'}:
            raise ValueError('Only generated media/temporary cache files are eligible')
        dependencies=item.get('dependencies',[])
        if not dependencies:raise ValueError('At least one existing job-relative rebuild dependency is required')
        for dep in dependencies:
            dep_path=contained(job,dep)
            if not dep_path.is_file():raise ValueError('Missing rebuild dependency')
            if dep_path in seen:raise ValueError('Rebuild dependency is also a cleanup candidate')
        actual=digest(path)
        if item.get('sha256') and item['sha256']!=actual:raise ValueError('Candidate changed since review')
        entries.append({'path':path,'sha256':actual,'bytes':path.stat().st_size,'reason':item['reason'],'dependencies':dependencies})
    for row in entries:
        if any(contained(job,x) in seen for x in row['dependencies']):raise ValueError('Rebuild dependency is also being removed')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    trash=job/'.trash'/stamp
    report={'mode':'apply' if args.apply else 'dry_run','job':str(job),'recoverable':True,'bytes':sum(x['bytes'] for x in entries),'files':[]}
    if args.apply:trash.mkdir(parents=True,exist_ok=False)
    for row in entries:
        source=row['path'];dest=trash/source.relative_to(job)
        item={**row,'path':str(source),'restore_from':str(dest)}
        if args.apply:
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(source),str(dest))
        report['files'].append(item)
        if args.apply:(trash/'restore_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,json.JSONDecodeError) as exc:
        raise SystemExit('Cleanup blocked: '+str(exc))
