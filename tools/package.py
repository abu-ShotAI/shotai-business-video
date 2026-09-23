#!/usr/bin/env python3
"""Build Chinese and English skill archives from the repository sources."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'shotai-business-video'
ALLOWED_DIRS = ('agents', 'assets', 'references', 'scripts')
NL = chr(10)

def main():
    files = [ROOT/'SKILL.md', ROOT/'requirements.txt']
    for directory in ALLOWED_DIRS:
        files.extend(p for p in (ROOT/directory).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix != '.pyc' and p.name != '.DS_Store')
    payload = {str(p.relative_to(ROOT)): p.read_bytes() for p in sorted(files)}
    dist = ROOT/'dist'
    dist.mkdir(exist_ok=True)
    records = []
    for lang in ('zh', 'en'):
        content = dict(payload)
        if lang == 'en':
            body = (ROOT/'references/workflow.en.md').read_text(encoding='utf-8')
            for reference in (ROOT/'references').glob('*.md'):
                body = body.replace(']('+reference.name+')', '](references/'+reference.name+')')
            header = NL.join(['---','name: shotai-business-video',
                'description: Create script-led Douyin and TikTok videos for local businesses using live ShotAI MCP footage selection, selectable narration, synchronized captions and licensed music. Use with indexed owner footage, approved copy, Chinese or English delivery, and targeted revisions.',
                'metadata:','  short-description: Approved copy to ShotAI footage, selectable voice and music','---',''])
            content['SKILL.md'] = (header + NL + body).encode('utf-8')
            content['agents/openai.yaml'] = NL.join(['interface:',
                '  display_name: "ShotAI Business Video"',
                '  short_description: "Turn approved copy into narrated business feed videos"',
                '  default_prompt: "Use $shotai-business-video to turn my approved script and indexed ShotAI footage into a vertical video with selectable voice and music."','']).encode('utf-8')
        for extension in ('zip', 'skill'):
            target = dist/f'{PREFIX}-{lang}.{extension}'
            with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
                for name, data in sorted(content.items()):
                    info = zipfile.ZipInfo(f'{PREFIX}/{name}', date_time=(2026,9,23,0,0,0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, data)
            with zipfile.ZipFile(target) as archive:
                assert archive.testzip() is None
            records.append({'file':target.name,'language':lang,'bytes':target.stat().st_size,
                            'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
    (dist/'manifest.json').write_text(json.dumps({'version':(ROOT/'VERSION').read_text().strip(),
        'packages':records,'install_one_language_package':True},ensure_ascii=False,indent=2)+NL,encoding='utf-8')
    print(json.dumps(records,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
