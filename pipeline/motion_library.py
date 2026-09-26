"""Topic-independent, validated SVG/HyperFrames graphics. No generated facts or media."""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

VERSION = 'motion-library-1.0'
GSAP_SHA256 = 'c174bfce53a729418d57a8ad8625e7247c793a22fef8e2851e3cfa3de9cd8280'
Kind = Literal['process','timeline','comparison','bars','layers','hub_spoke','checklist','quote','metric']
Theme = Literal['charcoal','paper','slate']
THEMES = {
    'charcoal': ('#131614','#f2f0e9','#aab3ac','#b6cdbb','#39483d'),
    'paper': ('#f2f0e9','#202722','#535d56','#3e654e','#d7dfd7'),
    'slate': ('#141b22','#f1f2ef','#abb8c2','#9fbacb','#354957'),
}
STYLE_PURPOSES = {
    'process': 'An ordered mechanism or workflow', 'timeline': 'Labeled events in sequence',
    'comparison': 'Two or three options with explicit tradeoffs', 'bars': 'Comparable nonnegative quantities with one unit',
    'layers': 'Layers or a hierarchy', 'hub_spoke': 'One subject connected to several related parts',
    'checklist': 'Requirements or a set of takeaways', 'quote': 'A short sourced quotation or clearly illustrative statement',
    'metric': 'One sourced quantity with its unit and context',
}


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False)


class MotionItem(Strict):
    label: str = Field(min_length=1, max_length=40)
    detail: str = Field(default='', max_length=96)
    tag: str = Field(default='', max_length=20)
    value: float | None = Field(default=None, ge=0, le=1e12)


class MotionSpec(Strict):
    kind: Kind
    title: str = Field(min_length=1, max_length=64)
    theme: Theme = 'charcoal'
    duration_seconds: float = Field(default=10, ge=4, le=20)
    items: list[MotionItem] = Field(min_length=1, max_length=5)
    unit: str = Field(default='', max_length=16)
    source_label: str = Field(default='', max_length=110)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    illustrative: bool = False

    @model_validator(mode='after')
    def validate_content(self):
        bounds = {'process':(2,5),'timeline':(2,5),'comparison':(2,3),'bars':(2,5),
                  'layers':(2,5),'hub_spoke':(3,5),'checklist':(2,5),'quote':(1,1),'metric':(1,1)}
        low, high = bounds[self.kind]
        if not low <= len(self.items) <= high:
            raise ValueError(f'{self.kind} needs {low}–{high} items; split larger content into scenes')
        if self.kind in {'bars','metric'} and any(i.value is None for i in self.items):
            raise ValueError('numeric graphics require supplied values; values are never invented')
        if self.kind not in {'bars','metric'} and (self.unit or any(i.value is not None for i in self.items)):
            raise ValueError('values and units are supported only by bars and metric')
        if self.kind not in {'timeline','comparison'} and any(i.tag for i in self.items):
            raise ValueError('tags are supported only by timeline and comparison')
        if self.kind == 'bars' and any(i.detail for i in self.items):
            raise ValueError('bars use labels, values and a unit; put explanation in narration')
        if self.kind == 'hub_spoke' and self.items[0].detail:
            raise ValueError('hub center supports a label only; place details on branches')
        if not self.illustrative and (not self.source_label or not self.evidence_ids):
            raise ValueError('factual graphics require source_label and evidence_ids')
        if any(not re.fullmatch(r'[A-Za-z0-9_-]{1,120}', e) for e in self.evidence_ids):
            raise ValueError('invalid evidence ID')
        strings = [self.title] + [s for i in self.items for s in (i.label,i.detail,i.tag)]
        if any(len(word)>26 for s in strings for word in s.split()):
            raise ValueError('unbroken text is too long; shorten labels for readability')
        if self.duration_seconds < self.minimum_seconds():
            raise ValueError(f'allow at least {self.minimum_seconds():g}s reading time or shorten/split the scene')
        return self

    def minimum_seconds(self):
        words = len((' '.join([self.title]+[i.label+' '+i.detail+' '+i.tag for i in self.items])).split())
        return round(max(4, 2+words/4), 2)


def catalog():
    return {'version': VERSION, 'width':1920, 'height':1080, 'themes':list(THEMES),
            'styles':[{'id':key,'purpose':value} for key,value in STYLE_PURPOSES.items()],
            'schema':MotionSpec.model_json_schema(), 'review_required':True, 'publishing_enabled':False}


def choose_style(description: str, *, strong_footage=False, previous: str | None=None):
    if strong_footage:
        return None
    routes = [('timeline',r'\btimeline\b|chronolog|milestone'),('comparison',r'compar|trade.?off|versus'),
              ('bars',r'bar chart|quantities|measurements'),('layers',r'layers|hierarchy|stack'),
              ('hub_spoke',r'ecosystem|hub|branches'),('checklist',r'checklist|requirements|takeaways|\blist\b'),
              ('quote',r'quotation|\bquote\b'),('metric',r'\bmetric\b|single statistic'),
              ('process',r'process|mechanism|steps|workflow|diagram')]
    for kind, pattern in routes:
        if re.search(pattern,description,re.I):
            # Prefer footage over immediately repeating a diagram; never choose an unrelated style.
            return None if kind == previous else kind
    return None


def _text(x, y, value, *, size=32, width=38, fill='var(--ink)', weight=400):
    lines = textwrap.wrap(value, width, break_long_words=False, break_on_hyphens=False) or ['']
    spans=''.join(f'<tspan x="{x}" dy="{0 if n==0 else size*1.28}">{html.escape(s)}</tspan>' for n,s in enumerate(lines))
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}">{spans}</text>'


def _group(content):
    return '<g class="reveal">'+content+'</g>'


def _body(spec):
    items=spec.items; out=[]; n=len(items)
    if spec.kind == 'process':
        for i,item in enumerate(items):
            x=150+i*1620/n
            if i<n-1:
                out.append(f'<path class="route" d="M{x+76} 448H{x+1620/n-36}"/>')
            out.append(_group(f'<circle cx="{x+26}" cy="448" r="26" fill="var(--accent)"/>'+
                _text(x+16,458,str(i+1),size=28,fill='var(--bg)')+
                _text(x,540,item.label,size=34,width=15,weight=550)+_text(x,690,item.detail,size=28,width=19,fill='var(--muted)')))
    elif spec.kind == 'timeline':
        out.append('<path class="route" d="M190 362V846"/>')
        for i,item in enumerate(items):
            y=370+i*480/max(1,n-1)
            out.append(_group(f'<circle cx="190" cy="{y}" r="8" fill="var(--accent)"/>'+
                _text(240,y+9,item.tag or str(i+1),size=26,fill='var(--accent)')+
                _text(590,y+9,item.label,size=34,width=40,weight=550)+
                _text(590,y+50,item.detail,size=28,width=63,fill='var(--muted)')))
    elif spec.kind == 'comparison':
        for i,item in enumerate(items):
            x=148+i*1640/n; w=1640/n-60
            out.append(_group(f'<path d="M{x} 357h{w}" stroke="var(--accent)" stroke-width="3"/>'+
                _text(x,420,item.tag or f'Option {i+1}',size=26,fill='var(--muted)')+
                _text(x,509,item.label,size=44,width=18,weight=550)+
                _text(x,680,item.detail,size=32,width=27,fill='var(--ink)')))
    elif spec.kind == 'bars':
        maximum=max([i.value for i in items]+[1])
        for i,item in enumerate(items):
            y=386+i*106; w=950*item.value/maximum
            out.append(_group(_text(148,y+31,item.label,size=30,width=21)+
                f'<rect class="bar" x="574" y="{y}" width="{w:.3f}" height="48" fill="var(--accent)"/>'+
                _text(1580,y+32,f'{item.value:g} {spec.unit}'.strip(),size=30,width=18)))
        out.append(_text(574,929,'0 • common scale',size=24,fill='var(--muted)'))
    elif spec.kind == 'layers':
        for i,item in enumerate(items):
            y=354+i*108; x=170+i*48
            out.append(_group(f'<rect x="{x}" y="{y}" width="{1570-i*48}" height="90" fill="var(--surface)"/>'+
                _text(x+30,y+33,item.label,size=32,width=25,weight=550)+
                _text(880,y+40,item.detail,size=26,width=50,fill='var(--muted)')))
    elif spec.kind == 'hub_spoke':
        out.append(_group(f'<circle cx="460" cy="581" r="132" fill="var(--surface)"/>'+
            _text(354,555,items[0].label,size=34,width=13,weight=550)))
        for i,item in enumerate(items[1:]):
            y=340+i*140
            out.append(f'<path class="route" d="M603 581C850 581 836 {y} 1035 {y}"/>')
            out.append(_group(_text(1090,y+10,item.label,size=34,width=32,weight=550)+
                _text(1090,y+56,item.detail,size=26,width=39,fill='var(--muted)')))
    elif spec.kind == 'checklist':
        for i,item in enumerate(items):
            y=364+i*114
            out.append(_group(f'<path d="M158 {y+12}l13 13 23-28" stroke="var(--accent)" stroke-width="4" fill="none"/>'+
                _text(252,y+23,item.label,size=34,width=35,weight=550)+
                _text(1000,y+9,item.detail,size=28,width=44,fill='var(--muted)')))
    elif spec.kind == 'quote':
        out.append(_group(_text(160,489,items[0].detail or items[0].label,size=58,width=40,weight=450)+
            _text(165,820,items[0].label,size=28,fill='var(--muted)')))
    elif spec.kind == 'metric':
        item=items[0]
        out.append(_group(_text(150,620,f'{item.value:g}',size=152,width=14,weight=550)+
            _text(156,697,spec.unit,size=34,fill='var(--accent)')+
            _text(910,490,item.label,size=48,width=25,weight=550)+
            _text(910,657,item.detail,size=32,width=32,fill='var(--muted)')))
    return ''.join(out)


def render_html(spec: MotionSpec):
    bg,ink,muted,accent,surface=THEMES[spec.theme]
    credit='Illustrative example • not a measured result' if spec.illustrative else spec.source_label
    duration=spec.duration_seconds
    body=_body(spec)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(spec.title)}</title>
<script src="assets/gsap.min.js"></script><style>
html,body{{margin:0;width:100%;height:100%;overflow:hidden;font-family:system-ui,sans-serif;background:{bg}}}
#root{{--bg:{bg};--ink:{ink};--muted:{muted};--accent:{accent};--surface:{surface};position:relative;width:100%;height:100%;overflow:hidden;background:var(--bg)}}
svg{{width:100%;height:100%}}.route{{stroke:var(--muted);stroke-width:3;fill:none}}
</style></head><body><div id="root" data-composition-id="graphic" data-kind="{spec.kind}" data-width="1920" data-height="1080" data-duration="{duration}">
<svg viewBox="0 0 1920 1080" role="img" aria-label="{html.escape(spec.title,quote=True)}">
{_text(145,164,spec.title,size=64,width=47,weight=550)}{body}
<path d="M145 968H1775" stroke="var(--muted)" stroke-width="1"/>{_text(145,1018,credit,size=22,width=110,fill='var(--muted)')}
</svg></div><script>
const tl=gsap.timeline({{paused:true}});
const scope=document.getElementById('root');
const groups=scope.querySelectorAll('.reveal');
groups.forEach((g,i)=>tl.fromTo(g,{{opacity:0,y:14}},{{opacity:1,y:0,duration:.45,ease:'power2.out'}},.35+i*{min(.8,(duration-3)/max(1,len(spec.items))):.3f}));
scope.querySelectorAll('.route').forEach((p,i)=>{{const len=p.getTotalLength();tl.fromTo(p,{{strokeDasharray:len,strokeDashoffset:len}},{{strokeDashoffset:0,duration:.65,ease:'power2.inOut'}},.6+i*.35)}});
scope.querySelectorAll('.bar').forEach((p,i)=>tl.fromTo(p,{{scaleX:0,transformOrigin:'left center'}},{{scaleX:1,duration:.7,ease:'power2.out'}},.7+i*.6));
window.__timelines=window.__timelines||{{}};window.__timelines.graphic=tl;
</script></body></html>'''


def write_package(spec: MotionSpec, destination: Path):
    destination=Path(destination)
    output=render_html(spec)
    digest=hashlib.sha256((VERSION+spec.model_dump_json()+output).encode()).hexdigest()
    destination.mkdir(parents=True,exist_ok=True)
    index=destination/'index.html'
    if not index.is_file() or index.read_text(encoding='utf-8') != output:
        index.write_text(output,encoding='utf-8')
    manifest={'version':VERSION,'input_hash':digest,'review_required':True,'publishing_enabled':False,
              'renderer':'hyperframes','dependency':'gsap@3.14.2 (assets/gsap.min.js)','video_rendered':False}
    for name,data in [('motion_spec.json',spec.model_dump(mode='json')),('manifest.json',manifest),
                      ('hyperframes.json',{'version':1,'entry':'index.html','width':1920,'height':1080,'fps':30})]:
        (destination/name).write_text(json.dumps(data,indent=2),encoding='utf-8')
    return manifest


def stage_runtime(destination: Path, source: Path | None=None):
    """Install one hash-pinned runtime; no provider credit use."""
    target=Path(destination)/'assets/gsap.min.js'
    if target.is_file():
        payload=target.read_bytes()
    elif source:
        payload=Path(source).read_bytes()
    else:
        import requests
        response=requests.get('https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js',timeout=30)
        response.raise_for_status()
        payload=response.content
    if hashlib.sha256(payload).hexdigest()!=GSAP_SHA256:
        raise ValueError('GSAP runtime integrity mismatch')
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists(): target.write_bytes(payload)


def package_hash(directory: Path):
    directory=Path(directory)
    spec=MotionSpec.model_validate_json((directory/'motion_spec.json').read_text(encoding='utf-8'))
    expected=render_html(spec)
    if (directory/'index.html').read_text(encoding='utf-8')!=expected:
        raise ValueError('motion package changed; rebuild and review it')
    return hashlib.sha256((VERSION+spec.model_dump_json()+expected).encode()).hexdigest()


def render_approved_package(directory: Path, destination: Path, approved_hash: str | None, seconds: float):
    digest=package_hash(directory)
    if approved_hash!=digest:
        raise ValueError('review and approve the current motion preview before rendering')
    spec=MotionSpec.model_validate_json((directory/'motion_spec.json').read_text(encoding='utf-8'))
    if abs(spec.duration_seconds-seconds)>.001:
        raise ValueError('motion duration changed; rebuild and review')
    npx=shutil.which('npx.cmd') or shutil.which('npx')
    if not npx: raise RuntimeError('Node.js / npx is required for HyperFrames')
    stage_runtime(directory)
    destination=Path(destination).resolve()
    destination.parent.mkdir(parents=True,exist_ok=True)
    environment={**os.environ,'HYPERFRAMES_NO_TELEMETRY':'1'}
    subprocess.run([npx,'--yes','hyperframes@0.8.77','check','--json'],cwd=directory,
                   check=True,capture_output=True,text=True,timeout=180,env=environment)
    subprocess.run([npx,'--yes','hyperframes@0.8.77','render','--quality','looks','--fps','30',
                    '--resolution','1080p','--output',str(destination)],cwd=directory,
                   check=True,capture_output=True,text=True,timeout=900,env=environment)
    from .remotion_renderer import _video_dimensions
    if not destination.is_file() or destination.stat().st_size<1024 or _video_dimensions(destination)!=(1920,1080):
        raise RuntimeError('HyperFrames did not produce a usable 1080p video')
    return destination
