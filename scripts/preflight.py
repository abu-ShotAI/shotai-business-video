#!/usr/bin/env python3
"""Read-only local readiness check. No install, secret discovery or network calls."""
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--script',type=Path,action='append',default=[])
    parser.add_argument('--provider',choices=['existing','edge','qwen-demo'],default='existing')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    checks=[]
    def add(name,ready,detail):checks.append({'check':name,'ready':bool(ready),'detail':detail})
    add('project_directory',args.project.is_dir(),str(args.project.resolve()))
    for tool in ['ffmpeg','ffprobe']:
        path=shutil.which(tool)
        ok=bool(path)
        if path:
            try:
                result=subprocess.run([path,'-version'],capture_output=True,text=True,timeout=10)
                detail=result.stdout.splitlines()[0] if result.stdout else 'Executable returned no version'
                ok=result.returncode==0
            except (OSError,subprocess.TimeoutExpired):ok=False;detail='Executable failed or timed out'
        else:detail='Missing from PATH'
        add(tool,ok,detail)
    for module in ['PIL','numpy','soundfile']+(['edge_tts'] if args.provider=='edge' else []):
        add(module,importlib.util.find_spec(module) is not None,'Python module availability')
    for path in args.script:
        try:
            text=path.read_text(encoding='utf-8-sig')
            add('script',bool(text.strip()),{'file':str(path.resolve()),'characters':len(text),'nonempty':bool(text.strip())})
        except (OSError,UnicodeError):add('script',False,{'file':str(path),'error':'Missing or not UTF-8'})
    result={'checks':checks,'local_ready':all(x['ready'] for x in checks),
        'shotai':{'native_mcp':'Discover and call actual ShotAI tools in the agent environment',
            'sse_token_environment_present':bool(os.getenv('SHOTAI_TOKEN')),
            'live_connection_verified':False},
        'tts_provider':args.provider,'tts_online_availability_verified':False,
        'note':'Local dependencies only. Native MCP can be available without SHOTAI_TOKEN. ASR requires provider word timestamps or a separately available ASR service/model.'}
    encoded=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(encoded,encoding='utf-8')
    print(encoded)
    return 0 if result['local_ready'] else 2

if __name__=='__main__':raise SystemExit(main())
