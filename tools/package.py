#!/usr/bin/env python3
"""Build the English-default skill and an optional Chinese-entry edition."""
import hashlib
import json
from pathlib import Path
import re
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
    for lang in ('en', 'zh'):
        content = dict(payload)
        if lang == 'zh':
            body = (ROOT/'references/workflow.zh.md').read_text(encoding='utf-8')
            body = body.replace('(../SKILL.md)', '(workflow.en.md)')
            def resolve_link(match):
                target = match.group(1)
                if '://' in target or target.startswith(('#', '/')):
                    return match.group(0)
                path = (ROOT/'references'/target.split('#', 1)[0]).resolve()
                fragment = '#'+target.split('#', 1)[1] if '#' in target else ''
                return ']('+path.relative_to(ROOT).as_posix()+fragment+')'
            body = re.sub(r'][(]([^)]*)[)]', resolve_link, body)
            header = NL.join(['---','name: shotai-business-video',
                'description: 基于固定文案与已索引的自有素材，使用 ShotAI MCP 实时选镜，搭配可选配音、字幕和授权音乐，制作本地商家抖音或 TikTok 视频；支持中文、英文或分别两版，以及局部修订。',
                'metadata:','  short-description: 固定文案、实时素材、可选声音音乐，制作商家短视频','---',''])
            content['SKILL.md'] = (header + NL + body).encode('utf-8')
            canonical = (ROOT/'SKILL.md').read_text(encoding='utf-8').split('---', 2)[2].lstrip()
            def reference_link(match):
                target = match.group(1)
                if '://' in target or target.startswith(('#', '/')):
                    return match.group(0)
                if target.startswith('references/'):
                    target = target[len('references/'):]
                else:
                    target = '../' + target
                return ']('+target+')'
            content['references/workflow.en.md'] = re.sub(r'][(]([^)]*)[)]', reference_link, canonical).encode('utf-8')
            content['references/workflow.zh.md'] = payload['references/workflow.zh.md'].decode('utf-8').replace('(../SKILL.md)', '(workflow.en.md)').encode('utf-8')
            for key in list(content):
                if key.startswith('references/zh-CN/') and key.endswith('.md'):
                    content[key] = content[key].decode('utf-8').replace('(../../SKILL.md)', '(../workflow.en.md)').encode('utf-8')
            content['agents/openai.yaml'] = NL.join(['interface:',
                '  display_name: "ShotAI 商家短视频"',
                '  short_description: "基于固定文案匹配自有素材，选配音与音乐，制作商家中英文信息流视频"',
                '  default_prompt: "用 $shotai-business-video，根据我的固定文案与已入库素材制作短视频，由我选择声音和配乐。"','']).encode('utf-8')
        for extension in ('zip', 'skill'):
            target = dist/f'{PREFIX}-{lang}.{extension}'
            with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
                for name, data in sorted(content.items()):
                    info = zipfile.ZipInfo(f'{PREFIX}/{name}', date_time=(2026,9,24,0,0,0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, data)
            with zipfile.ZipFile(target) as archive:
                assert archive.testzip() is None
            records.append({'file':target.name,'language':lang,'bytes':target.stat().st_size,
                            'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
            if lang == 'en':
                default = dist/f'{PREFIX}.{extension}'
                default.write_bytes(target.read_bytes())
                records.append({'file':default.name,'language':'en','default':True,
                                'bytes':default.stat().st_size,'sha256':hashlib.sha256(default.read_bytes()).hexdigest()})
    (dist/'manifest.json').write_text(json.dumps({'version':(ROOT/'VERSION').read_text().strip(),
        'default_language':'en','video_language_options':['en','zh','both'],
        'packages':records,'install_one_language_package':True},ensure_ascii=False,indent=2)+NL,encoding='utf-8')
    print(json.dumps(records,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
