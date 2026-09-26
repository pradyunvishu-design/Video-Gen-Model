"""Build reusable graphic packages from JSON, or the multi-topic review gallery."""
import argparse
import json
import re
from pathlib import Path
from pipeline.motion_library import MotionSpec, write_package, stage_runtime

ROOT=Path(__file__).resolve().parents[1]


def build(input_path: Path, output: Path):
    raw=json.loads(input_path.read_text(encoding='utf-8'))
    entries=raw if isinstance(raw,list) else [raw]
    if not 1<=len(entries)<=40:
        raise ValueError('supply 1–40 scenes per package')
    specs=[MotionSpec.model_validate(item) for item in entries]
    output.mkdir(parents=True,exist_ok=True)
    stage_runtime(output)
    mounts=[]; timeline=[]; cursor=0
    for i,spec in enumerate(specs):
        key=f'graphic_{i+1:02d}'
        folder=output/key
        manifest=write_package(spec,folder)
        stage_runtime(folder,output/'assets/gsap.min.js')
        document=(folder/'index.html').read_text(encoding='utf-8')
        styles=re.search(r'<style>(.*?)</style>',document,re.S).group(1)
        body=re.search(r'<body>(.*?)</body>',document,re.S).group(1)
        styles=styles.replace('#root',f'#{key}')
        body=body.replace('id="root"',f'id="{key}"').replace("getElementById('root')",f"getElementById('{key}')")
        body=body.replace('data-composition-id="graphic"',f'data-composition-id="{key}"')
        body=body.replace('window.__timelines.graphic=',f'window.__timelines["{key}"]=')
        body=body.replace('<script>','<script>(()=>{').replace('</script>','})();</script>')
        (folder/'scene.html').write_text(f'<template><style>{styles}</style>{body}</template>',encoding='utf-8')
        mounts.append(f'<div id="host-{key}" data-composition-id="{key}" data-composition-src="{key}/scene.html" data-start="{cursor}" data-duration="{spec.duration_seconds}" data-track-index="{i}" data-width="1920" data-height="1080"></div>')
        timeline.append({'id':key,'kind':spec.kind,'theme':spec.theme,'start':cursor,'duration':spec.duration_seconds,**manifest})
        cursor+=spec.duration_seconds
    index='''<!doctype html><html><head><meta charset="utf-8"><script src="assets/gsap.min.js"></script>
<style>html,body{margin:0;width:100%;height:100%;overflow:hidden;font-family:system-ui,sans-serif}#gallery{position:relative;width:100%;height:100%}</style></head><body>'''
    index+=f'<div id="gallery" data-composition-id="gallery" data-width="1920" data-height="1080" data-duration="{cursor}">'+''.join(mounts)+'</div>'
    index+=f'<script>window.__timelines=window.__timelines||{{}};window.__timelines.gallery=gsap.timeline({{paused:true}}).to("#gallery",{{opacity:1,duration:{cursor},ease:"none"}});</script></body></html>'
    (output/'index.html').write_text(index,encoding='utf-8')
    (output/'hyperframes.json').write_text(json.dumps({'version':1,'entry':'index.html','width':1920,'height':1080,'fps':30}))
    (output/'gallery.json').write_text(json.dumps({'duration':cursor,'scenes':timeline,'review_required':True},indent=2))
    return {'directory':str(output),'scenes':len(specs),'duration_seconds':cursor}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',type=Path,default=ROOT/'configs/motion_library_examples.json')
    parser.add_argument('--output',type=Path,default=ROOT/'data/motion_expert_runs/library_v1/gallery')
    args=parser.parse_args()
    print(json.dumps(build(args.input,args.output)))
