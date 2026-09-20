"""Resumable, source-first production for the September 2 Fable/Mythos episode.

Uses the project's approved Gemini narrator and FFmpeg assembly utilities.
No publishing, unapproved source-video acquisition, or credential logging is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
import shutil
from urllib.parse import urlparse, parse_qs, urljoin
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EP = ROOT / "data/episodes/episode_20260902_fable_mythos"
LAUNCH = "https://www.anthropic.com/claude-fable-and-mythos-5-1"
SOURCES = {
    "launch": LAUNCH,
    "docs": "https://platform.claude.com/docs/en/models/fable-5-1/whats-new-fable-5-1",
    "protein_research": "https://www.anthropic.com/research/Claude-accelerates-protein-design",
    "efs": "https://www.anthropic.com/news/enterprise-frontier-safeguards",
    "venus_dataset": "https://zenodo.org/records/22164484",
    "nasa": "https://science.nasa.gov/mission/magellan/",
    "nasa_svs": "https://svs.gsfc.nasa.gov/3728/",
}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=lambda x: x.model_dump(mode="json") if hasattr(x,"model_dump") else str(x)), encoding="utf-8")


def acquire():
    soup = BeautifulSoup((EP / "research/launch.html").read_text(encoding="utf-8"), "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    (EP / "research/launch.txt").write_text(soup.get_text("\n", strip=True), encoding="utf-8")
    links = [{"text": a.get_text(" ", strip=True)[:100], "url": a.get("href")} for a in soup.find_all("a") if a.get("href")]
    media = [{"tag": t.name, "src": t.get("src"), "poster": t.get("poster")} for t in soup.find_all(["video", "source", "iframe"])]
    dump(EP / "research/links.json", links)
    dump(EP / "research/embedded_media.json", media)
    print("Relevant links:", json.dumps([a for a in links if any(s in str(a).lower() for s in ("zenodo", "protein", "agu", "science", "safeguard", "cost", "model"))], indent=2))
    print("Embeds:", json.dumps(media, indent=2)[:4500])
    z = zipfile.ZipFile(EP / "research/anthropic_press_kit.zip")
    selected = [n for n in z.namelist() if not n.startswith("__MACOSX") and ("3 Claude Spark" in n or "4 Claude icon" in n) and n.lower().endswith((".svg", ".png"))]
    print("Identity options:", selected)
    for n in selected:
        target = EP / "media/brand" / Path(n).name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(z.read(n))
    for name, uid in {
        "venus_radar": "4d8f06a743ecfc6ec87ccde0b1964e48175a141e-800x800.png",
        "venus_old_map": "e374c070fc1a84872dcb1343b5bb0ed540ca3770-800x800.png",
        "venus_new_map": "3dd626b47b88feb72082646cdea87944d49a3c7f-800x800.png",
        "benchmark_table": "a0ec790d784db6dab9e05a7cfe2664e31aec1681-2160x1996.png",
    }.items():
        target = EP / "media" / f"{name}.png"
        if not target.exists():
            r = requests.get("https://www-cdn.anthropic.com/images/4zrzovbb/website/" + uid, timeout=60)
            r.raise_for_status()
            target.write_bytes(r.content)
    try:
        from pypdf import PdfReader
        pdf = PdfReader(EP / "research/system_card.pdf")
        text = "\n".join(f"\n--- PAGE {i+1} ---\n" + p.extract_text() for i, p in enumerate(pdf.pages))
        (EP / "research/system_card.txt").write_text(text, encoding="utf-8")
        print("System card pages:", len(pdf.pages))
    except ImportError:
        print("PDF text extraction requires pypdf")


def review():
    """One independently authored factual/editorial pass, with a durable spend receipt."""
    from pipeline.editorial import call_openrouter, capture_openrouter_usage
    import pipeline.editorial as editorial
    editorial.OPENROUTER_API_KEY = dotenv_values(ROOT / ".env").get("OPENROUTER_API_KEY", "")
    script = json.loads((EP / "script.json").read_text(encoding="utf-8"))
    receipt = EP / "script_review.json"
    digest = hashlib.sha256((EP / "script.json").read_bytes()).hexdigest()
    if receipt.exists() and json.loads(receipt.read_text()).get("script_hash") == digest:
        print("Reusing independently reviewed script", flush=True)
        return
    sources = {}
    for sid, url in SOURCES.items():
        target = EP / "research" / f"{sid}.html"
        if not target.exists():
            try:
                r = requests.get(url, timeout=35)
                r.raise_for_status()
                target.write_text(r.text, encoding="utf-8")
            except requests.RequestException:
                continue
        soup = BeautifulSoup(target.read_text(encoding="utf-8"), "html.parser")
        for t in soup(["script", "style", "nav", "footer"]):
            t.decompose()
        txt = soup.get_text(" ", strip=True)
        (EP / "research" / f"{sid}.txt").write_text(txt, encoding="utf-8")
        sources[sid] = {"url": url, "text": txt[:42000]}
    dump(EP / "source_ledger.json", {"sources": sources, "youtube": {"ROF2Nv_KjOM": {"url": "https://www.youtube.com/watch?v=ROF2Nv_KjOM", "publisher": "Anthropic", "title": "Introducing Claude Fable 5.1", "reuse": "not included: standard YouTube license; no reuse clearance confirmed"}}, "publishing_enabled": False})
    spend_path = EP / "provider_usage.json"
    spend = json.loads(spend_path.read_text()) if spend_path.exists() else {"openrouter_usd": 0, "calls": [], "maximum_episode_usd": 1.5, "magichour_credits": 0}
    def usage(event):
        if event["phase"] == "before":
            if spend["openrouter_usd"] + .75 > 1.5:
                raise RuntimeError("Episode review budget exhausted; no paid request started")
            spend["reserved_usd"] = .75
            dump(spend_path, spend)
            return {"max_tokens": 3500}
        u = event.get("usage", {})
        cost = u.get("cost")
        if cost is None:
            raise RuntimeError("Missing provider cost: reserve retained, stop further requests")
        spend["openrouter_usd"] += float(cost)
        spend["reserved_usd"] = 0
        spend["calls"].append(event)
        dump(spend_path, spend)
    schema = {"type":"json_schema","json_schema":{"name":"review","strict":True,"schema":{"type":"object","additionalProperties":False,"properties":{"passed":{"type":"boolean"},"issues":{"type":"array","items":{"type":"string"}},"naturalness":{"type":"number"},"clarity":{"type":"number"},"evidence_notes":{"type":"array","items":{"type":"string"}}},"required":["passed","issues","naturalness","clarity","evidence_notes"]}}}
    if receipt.exists():
        previous = json.loads(receipt.read_text())
        dump(EP / "research" / ("review_" + previous["script_hash"][:12] + ".json"), previous)
    reviewer_model = os.environ.get("EPISODE_REVIEW_MODEL", "openai/gpt-5.4")
    with capture_openrouter_usage(usage):
        result = call_openrouter(reviewer_model, "You are an independent factual and spoken-script reviewer. Review the supplied draft against primary sources. Do not reward the author's intentions. Flag unsupported claims, temporal confusion between Aug18 research and Sept1 release, exaggerated claims, mismatched numbers, jargon, forced humor, repetitive phrasing. Scores 1-10. Pass only if no material factual issues and understandable conversational narration. Fail for actual contradictions or misleading assertions, not for omitting additional facts the narration does not claim to cover. Identify soft style notes separately in evidence_notes. Do not demand every source detail be read aloud. This is reporting, not hands-on testing. Ignore source names absent from the excerpts if their facts are supported by another supplied primary source. Return strict JSON.", json.dumps({"script":script,"sources":sources}), schema, temperature=.1)
    result["reviewer_model"] = reviewer_model
    result["script_hash"] = digest
    dump(receipt, result)
    print(json.dumps(result, indent=2), flush=True)


def narrate():
    from pipeline.gemini_tts import GeminiTTSClient
    from pipeline.render_v2 import concat_audio, duration, make_silence, run_command
    from scripts.refine_measured_tech_host_delivery import DIRECTOR
    reviewed = json.loads((EP / "script_review.json").read_text())
    if not reviewed["passed"] or reviewed["script_hash"] != hashlib.sha256((EP / "script.json").read_bytes()).hexdigest():
        raise RuntimeError("Current script has not cleared independent review")
    script = json.loads((EP / "script.json").read_text(encoding="utf-8"))
    env = dotenv_values(r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\.env.worker")
    director = script.get('delivery_direction') or DIRECTOR.replace("after testing it yourself", "after researching the published release")
    key = env.get("GEMINI_API_KEY")
    model = "gemini-3.1-flash-tts-preview"
    voice = "Zubenelgenubi"
    def one(chapter):
        transcript = "\n\n".join(chapter["paragraphs"])
        chapter_director = director
        if chapter['id'] == 'cost_verdict' and not script.get('delivery_direction'):
            chapter_director += "\nMaintain exactly the same relaxed adult male timbre across the entire passage. Keep the price explanation and closing conversational and matter-of-fact, at a steady 145 words per minute. No whispering, gravelly emphasis, breathy endings, or performed character changes. Finish every word clearly."
        h = hashlib.sha256((model+voice+chapter_director+transcript).encode()).hexdigest()[:12]
        raw = EP / "audio" / f"{chapter['id']}_{h}_raw.wav"
        clean = raw.with_name(raw.stem.replace("_raw", "_master") + ".wav")
        print("Narrating", chapter["id"], flush=True)
        result = GeminiTTSClient(key, model=model, voice=voice, timeout_seconds=240).synthesize(transcript, raw, director_prompt=chapter_director, retries=2)
        if not clean.exists():
            run_command(["ffmpeg","-y","-i",str(raw),"-af","highpass=f=65,loudnorm=I=-17:TP=-1.5:LRA=5","-ar","48000","-ac","1","-c:a","pcm_s16le",str(clean)])
        info = {"id":chapter["id"],"path":str(clean),"raw":str(raw),"duration":duration(clean),"voice":voice,"hash":h,"usage":result.usage}
        dump(EP / "audio" / f"{chapter['id']}_receipt.json", info)
        print("Narration complete", chapter["id"], round(info["duration"],1), "seconds", flush=True)
        return info
    with ThreadPoolExecutor(max_workers=2) as pool:
        audio = list(pool.map(one, script["chapters"]))
    silence = make_silence(EP / "audio/pause.wav", 220)
    paths = []
    cursor = 0.
    for i, ch in enumerate(audio):
        ch["start"] = cursor
        paths.append(Path(ch["path"]))
        cursor += ch["duration"]
        if i < len(audio)-1:
            paths.append(silence)
            cursor += .22
    master = concat_audio(paths, EP / "narration_zubenelgenubi.wav")
    dump(EP / "narration.json", {"chapters":audio,"path":str(master),"duration":duration(master),"voice":voice,"model":model})
    print("FULL NARRATION", duration(master), flush=True)


def capture():
    from pipeline.capture import capture_source
    from pipeline.models import Source
    def one(pair):
        sid, url = pair
        print("Capturing", sid, flush=True)
        source = Source(id=sid, url=url, title={"launch":"Introducing Claude Fable 5.1 and Mythos 5.1","docs":"Fable 5.1 model documentation","protein_research":"Claude protein design research","efs":"Enterprise safeguards","nasa":"Magellan at Venus"}.get(sid,sid), publisher="NASA" if sid=="nasa" else "Anthropic",source_type="primary")
        try:
            result = capture_source(source, EP / "captures" / sid, record=False)
            dump(EP / "captures" / f"{sid}.json", result)
            print("Capture saved",sid,flush=True)
        except Exception as exc:
            dump(EP / "captures" / f"{sid}_failure.json", {"source":url,"error":str(exc)[:700]})
            print("Capture rejected",sid,type(exc).__name__,flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(one, [(s,u) for s,u in SOURCES.items() if s != "venus_dataset"]))


def details():
    """Capture observed source regions, already centered on the relevant evidence."""
    from playwright.sync_api import sync_playwright
    from pipeline.capture import _load_page, _assert_capture_is_clean, _blocked_page_reason
    targets = {
        "launch": ["same model", "Price.", "Safeguards.", "A new performance frontier", "Terminal-Bench-Science", "Here, you can see", "Scientific research", "Molecular design.", "Planetary science.", "Safety, security", "Trusted access", "Cost and availability"],
        "docs": ["What's new", "Project Glasswing", "Pricing", "Cache", "effort", "data retention"],
        "protein_research": ["How Claude", "Claude designs proteins", "external evaluators", "The campaign", "Claude's performance", "Claude struggled", "wet lab"],
        "efs": ["Developing Enterprise", "zero data retention", "customer", "privacy"],
        "nasa": ["Magellan", "radar", "Venus"],
    }
    output = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        for sid, phrases in targets.items():
            page = browser.new_page(viewport={"width":1920,"height":1080}, device_scale_factor=1)
            try:
                _load_page(page, SOURCES[sid])
                # Browser-native text enlargement, not raster enlargement.
                page.add_style_tag(content="body{zoom:1.25} video{visibility:hidden}")
                for idx, phrase in enumerate(phrases):
                    path = EP / "captures/details" / f"{sid}_{idx:02d}.png"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    matches = page.locator("h1,h2,h3,p,td,li").filter(has_text=re.compile(re.escape(phrase),re.I))
                    if not matches.count():
                        continue
                    # Prefer the shortest visible block matching the requested phrase.
                    observed = []
                    for j in range(min(matches.count(),25)):
                        loc = matches.nth(j)
                        if loc.is_visible():
                            tag=loc.evaluate("el=>el.tagName.toLowerCase()")
                            content=loc.inner_text()
                            if content.strip().casefold() in {"customer support","privacy policy"}:
                                continue
                            observed.append((0 if tag in {"h1","h2","h3"} else 1, len(content), j))
                    if not observed:
                        continue
                    loc = matches.nth(min(observed)[2])
                    visible_text = loc.inner_text()
                    loc.evaluate("el => el.scrollIntoView({block:'center',behavior:'instant'})")
                    page.wait_for_timeout(250)
                    _assert_capture_is_clean(page,moment="evidence detail")
                    if _blocked_page_reason(page):
                        raise RuntimeError("blocked page")
                    box = loc.bounding_box()
                    page.screenshot(path=str(path),animations="disabled")
                    output.append({"id":f"{sid}_{idx:02d}","source":sid,"url":page.url,"phrase":phrase,"text":visible_text,"bounds":box,"path":str(path),"qc":"clean DOM and exact observed text"})
                print("Evidence regions",sid,len([x for x in output if x["source"]==sid]),flush=True)
            except Exception as exc:
                print("Evidence capture failed",sid,type(exc).__name__,flush=True)
            finally:
                page.close()
        browser.close()
    dump(EP / "captures/details.json",output)


def graphics():
    """Original, native-1080p compositions in the existing Remotion project."""
    from pipeline.render_v2 import run_command
    public = ROOT / "remotion/public/fable-mythos"
    public.mkdir(parents=True, exist_ok=True)
    for source in [EP / "media/brand/Claude Spark - Clay.png", *[EP / "media" / f"{n}.png" for n in ("venus_radar","venus_old_map","venus_new_map")]]:
        shutil.copy2(source, public / source.name)
    base={"title":"", "subtitle":"", "labels":[], "values":[], "images":[], "logo":"fable-mythos/Claude Spark - Clay.png", "source":"Anthropic · September 1, 2026", "seconds":9}
    specs={
      "opening":dict(kind="hero",dark=True),
      "access_split":dict(kind="branch",title="Capability is not the same as access",labels=["Fable 5.1","Mythos 5.1"]),
      "science_scores":dict(kind="bars",title="Terminal-Bench-Science 0.1",labels=["Fable 5","Fable 5.1"],values=[24.7,52.6]),
      "coding_scores":dict(kind="bars",title="Terminal-Bench 4.0",labels=["Fable 5.1","Mythos 5.1"],values=[55.8,60.9],dark=True),
      "test_setup":dict(kind="sequence",title="Compare the work, not the confidence",labels=["Same task","Same inputs","Check the result"],values=[0,4,1],subtitle="Keep the success criteria fixed. Include retries in the cost.",source="Editorial testing framework"),
      "venus_maps":dict(kind="venus",title="New work on old measurements",images=["fable-mythos/venus_radar.png","fable-mythos/venus_old_map.png","fable-mythos/venus_new_map.png"],labels=["Magellan radar","Earlier elevation map","New elevation map"],subtitle="Anthropic-reported research · Not new spacecraft imagery"),
      "research_roles":dict(kind="sequence",title="The ingredients of the Venus result",labels=["Measured radar","Existing map","New analysis"],values=[6,0,2],subtitle="A general-purpose agent coordinating a scientific workflow.",source="Anthropic · NASA Magellan"),
      "study_split":dict(kind="study",title="Do not combine these studies",labels=["Mythos Preview\n+ Opus 4.8","Mythos 5.1"],source="Anthropic · August 18 and September 1, 2026"),
      "evidence_ladder":dict(kind="checks",title="What did the experiment actually prove?",labels=["Predicted?","Physically tested?","What was established?"],values=[7,5,1],subtitle="A binder is an early research result, not a finished medicine.",source="Editorial reading guide · Anthropic research"),
      "token_prices":dict(kind="cost",title="Three prices. Three different things."),
      "verdict":dict(kind="quote",title="The useful test",labels=["Does it do your real task better?"],subtitle="Keep the old result. Compare quality, time, cost, and mistakes.",source="Editorial conclusion",dark=True),
    }
    thumbnail_specs={
      "one_model_two_rulebooks":dict(kind="thumb-access",dark=True),
      "claude_mapped_venus":dict(kind="thumb-venus",title="Claude mapped Venus",images=["fable-mythos/venus_old_map.png","fable-mythos/venus_new_map.png"],labels=["Earlier map","New result"],subtitle=""),
      "the_price_has_a_catch":dict(kind="thumb-cost",dark=False),
      "beyond_the_chatbot":dict(kind="thumb-evidence",images=["fable-mythos/venus_new_map.png"]),
    }
    source_hash=hashlib.sha256((ROOT / "remotion/src/fable-mythos-entry.tsx").read_bytes()).hexdigest()
    executable=ROOT / "remotion/node_modules/.bin/remotion.cmd"
    def render(item):
        name, spec, still=item
        props=base|spec
        dest=(EP / "thumbnails" if still else EP / "motion") / f"{name}.{'png' if still else 'mp4'}"
        pp=dest.with_suffix('.props.json')
        sig=hashlib.sha256((source_hash+json.dumps(props,sort_keys=True)).encode()).hexdigest()
        receipt=dest.with_suffix('.render.json')
        if dest.exists() and receipt.exists() and json.loads(receipt.read_text()).get("input_hash")==sig:
            return str(dest)
        dump(pp,props)
        frames=EP / "motion/frames" / name
        frames.mkdir(parents=True,exist_ok=True)
        cmd=[str(executable),"still" if still else "render","src/fable-mythos-entry.tsx","FableMythosGraphic",str(dest.resolve() if still else frames.resolve()),f"--props={pp.resolve()}","--browser-executable=C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"]
        if still:
            cmd += ["--frame=180","--image-format=png"]
        else:
            cmd += ["--sequence","--image-format=png","--concurrency=3","--muted"]
        print("Rendering",name,flush=True)
        if still or len(list(frames.glob('*.png'))) != round(props['seconds']*30):
            process=subprocess.run(cmd,cwd=ROOT / "remotion",capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=1200)
            (dest.with_suffix('.render.log')).write_text(process.stdout+process.stderr,encoding='utf-8')
            if process.returncode:
                raise RuntimeError((process.stdout+process.stderr)[-2200:])
        if not still:
            pics=sorted(frames.glob('*.png'))
            if len(pics)!=round(props['seconds']*30):
                raise RuntimeError(f"Incomplete frames for {name}: {len(pics)}")
            # Use the installed, working FFmpeg rather than Remotion's failed bundled encoder.
            listing=frames / 'sequence.txt'
            listing.write_text(''.join("file '"+x.resolve().as_posix()+"'\nduration 0.033333333333\n" for x in pics),encoding='utf-8')
            run_command(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-an','-r','30','-t',str(props['seconds']),'-c:v','libx264','-preset','fast','-crf','17','-threads','2','-pix_fmt','yuv420p',str(dest)])
        dump(receipt,{"input_hash":sig,"asset":str(dest),"width":1920,"height":1080,"original_composition":True})
        if still:
            from PIL import Image
            image=Image.open(dest)
            image.resize((320,180),Image.Resampling.LANCZOS).save(dest.with_name(dest.stem+"_preview.png"))
            image.convert("L").resize((320,180)).save(dest.with_name(dest.stem+"_grayscale.png"))
        print("Rendered",name,flush=True)
        return str(dest)
    work=[(n,s,True) for n,s in thumbnail_specs.items()]+[(n,s,False) for n,s in specs.items()]
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(render,work))
    dump(EP / "motion/catalog.json",specs)
    dump(EP / "thumbnails/concepts.json",{"hook_angles":["One model. Two rulebooks.","Who gets Mythos?","The price has a catch","Claude mapped Venus","Beyond the chatbot","Same model, different access","Read the chart carefully","The upgrade worth testing"],"candidates":thumbnail_specs,"recommended":"one_model_two_rulebooks.png","brand_source":"https://www.anthropic.com/press-kit","brand_hash":hashlib.sha256((public/'Claude Spark - Clay.png').read_bytes()).hexdigest(),"generation":"Original deterministic composition; official logo and authentic source maps; no generated stills","forbidden_implications":["Mythos is unrestricted","New spacecraft images","Independent benchmarks","Clinical efficacy"],"human_approval":"pending"})


def audio_review():
    from pipeline.captions import transcribe_words, align_script_words, TimedWord
    from pipeline.audio_qc import review_narration
    from dataclasses import asdict
    script=json.loads((EP / "script.json").read_text(encoding="utf-8"))
    narration=json.loads((EP / "narration.json").read_text())
    reference=ROOT / "output/voice_canary/measured_original_tech_host_v4_round2/zubenelgenubi_connected_master.wav"
    paragraphs=[]
    reports=[]
    for chapter,aud in zip(script["chapters"],narration["chapters"]):
        cache=EP / "audio" / f"{chapter['id']}_{aud['hash']}_words.json"
        if cache.exists():
            words=[TimedWord(**x) for x in json.loads(cache.read_text())]
        else:
            print("Transcribing",chapter["id"],flush=True)
            words=transcribe_words(Path(aud["path"]),model_size="small.en")
            dump(cache,[asdict(x) for x in words])
        approved="\n\n".join(chapter["paragraphs"])
        recognized=" ".join(x.text for x in words)
        report=review_narration(Path(aud["path"]),approved,reference,recognized_text=recognized,min_intelligibility=.9)
        report["chapter"]=chapter["id"]
        dump(EP / "audio" / f"{chapter['id']}_qc.json",report)
        reports.append(report)
        aligned=align_script_words(approved,words)
        n=0
        for i,text in enumerate(chapter["paragraphs"]):
            count=len(re.findall(r"\S+",text))
            pwords=aligned[n:n+count]
            n+=count
            start=pwords[0].start+aud["start"] if i else aud["start"]
            end=(aligned[n].start if n<len(aligned) else aud["duration"])+aud["start"]
            paragraphs.append({"id":f"{chapter['id']}_{i}","chapter":chapter["id"],"index":i,"text":text,"start":start,"end":end,"duration":end-start,"sources":chapter["sources"]})
        print("Audio QC",chapter["id"],report["passed"],report["metrics"]["intelligibility"],flush=True)
    dump(EP / "audio_qc.json",{"passed":all(x["passed"] for x in reports),"chapters":reports,"method":"Independent local Whisper recognition plus waveform/spectral metrics and approved-voice feature comparison; not a human listening certification"})
    # Place exact paragraph changes at speech-aligned boundaries, including inter-chapter pauses.
    for i,p in enumerate(paragraphs[:-1]):
        p["end"]=paragraphs[i+1]["start"]
        p["duration"]=p["end"]-p["start"]
    paragraphs[-1]["end"]=narration["duration"]+1.2
    paragraphs[-1]["duration"]=paragraphs[-1]["end"]-paragraphs[-1]["start"]
    dump(EP / "paragraph_timing.json",paragraphs)


def source_media():
    """Acquire original article figures and the explicitly reusable NASA visualization."""
    records=[]
    soup=BeautifulSoup((EP / 'research/protein_research.html').read_text(encoding='utf-8'),'html.parser')
    for i,img in enumerate([x for x in soup.find_all('img') if x.get('alt')][:6]):
        src=img.get('src','')
        src=parse_qs(urlparse(src).query).get('url',[src])[0]
        url=urljoin(SOURCES['protein_research'],src)
        target=EP / 'media' / f'protein_figure_{i}.png'
        if not target.exists():
            r=requests.get(url,timeout=45);r.raise_for_status();target.write_bytes(r.content)
        records.append({'id':target.stem,'path':str(target),'url':url,'source_url':SOURCES['protein_research'],'description':img.get('alt'),'rights_basis':'Limited figure excerpt for direct research commentary; human rights review pending'})
    nasa_page='https://svs.gsfc.nasa.gov/3728/'
    r=requests.get(nasa_page,timeout=45);r.raise_for_status()
    ns=BeautifulSoup(r.text,'html.parser')
    link=next(a['href'] for a in ns.find_all('a',href=True) if a['href'].endswith('/venus_topo_1080p30.mp4'))
    movie_url=urljoin(nasa_page,link)
    target=EP / 'media/nasa_venus_topography.mp4'
    if not target.exists():
        r=requests.get(movie_url,timeout=90);r.raise_for_status();target.write_bytes(r.content)
    youtube=next((a['href'] for a in ns.find_all('a',href=True) if 'youtube.com/watch' in a['href']),None)
    records.append({'id':'nasa_venus_topography','path':str(target),'url':movie_url,'source_url':nasa_page,'youtube_url':youtube,'description':'NASA 2010 Magellan false-color terrain visualization; historical context, not output of Claude','credit':'NASA/Goddard Space Flight Center Scientific Visualization Studio; clouds courtesy NASA/JPL-Caltech','rights_basis':'NASA media made available for informational/educational use with credit; no endorsement; original audio excluded','rights_url':'https://www.nasa.gov/nasa-brand-center/images-and-media/'})
    for name,url in {
        'magellan_deployment':'https://assets.science.nasa.gov/dynamicimage/assets/science/psd/solar/2023/07/Magellan_deploy.jpg',
        'venus_radar_overview':'https://assets.science.nasa.gov/dynamicimage/assets/science/psd/solar/internal_resources/3536/Radar_view_of_Venus_surface.jpeg',
    }.items():
        target=EP / 'media' / f'{name}.jpg'
        if not target.exists():
            r=requests.get(url,timeout=45);r.raise_for_status();target.write_bytes(r.content)
        records.append({'id':name,'path':str(target),'url':url,'source_url':SOURCES['nasa'],'credit':'NASA/JPL','rights_basis':'NASA informational use guidelines; no endorsement'})
    for rec in records:
        rec['sha256']=hashlib.sha256(Path(rec['path']).read_bytes()).hexdigest()
    dump(EP / 'media/source_media.json',records)
    print('Source media ready',len(records),flush=True)


def cards():
    from PIL import Image,ImageOps,ImageDraw,ImageFont
    directory=EP / 'cards'
    directory.mkdir(exist_ok=True)
    result={}
    font=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',23)
    def save(name,image,source,description,original):
        image=image.convert('RGB')
        canvas=Image.new('RGB',(1920,1080),'#F3F0E9')
        fitted=ImageOps.contain(image,(1800,950),Image.Resampling.LANCZOS)
        canvas.paste(fitted,((1920-fitted.width)//2,(1020-fitted.height)//2))
        draw=ImageDraw.Draw(canvas)
        draw.text((70,1035),source,font=font,fill='#47554C')
        target=directory / f'{name}.png'
        canvas.save(target)
        result[name]={'path':str(target),'source':source,'description':description,'original':str(original),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    details=json.loads((EP / 'captures/details.json').read_text(encoding='utf-8'))
    for x in details:
        if x['id'] in {'launch_02','efs_02','efs_03','docs_03','docs_04'}:
            continue
        source=Path(x['path'])
        im=Image.open(source)
        label={'nasa':'NASA · Magellan','protein_research':'Anthropic · August 18, 2026 research','docs':'Claude Platform Docs · September 2, 2026'}.get(x['source'],'Anthropic · September 2026')
        save(x['id'],im,label,x['text'],source)
        b=x['bounds']
        width=1320 if x['source']=='docs' else 1440
        cx=945 if x['source']=='docs' else 960
        cy=max(400,min(670,b['y']+b['height']/2))
        h=round(width*9/16)
        left=max(0,min(1920-width,cx-width/2));top=max(0,min(1080-h,cy-h/2))
        close=im.crop((round(left),round(top),round(left+width),round(top+h)))
        save(x['id']+'_detail',close,label,x['text'],source)
    hero=next((EP/'captures/launch').glob('*-viewport.png'))
    save('launch_hero',Image.open(hero),'Anthropic · September 1, 2026','Official Fable/Mythos launch page',hero)
    for name in ['venus_radar','venus_old_map','venus_new_map','magellan_deployment','venus_radar_overview',*[f'protein_figure_{i}' for i in range(6)]]:
        src=next((EP/'media').glob(name+'.*'))
        image=Image.open(src)
        label='NASA/JPL · Magellan' if name in {'magellan_deployment','venus_radar_overview'} else ('Anthropic · August 18 research' if name.startswith('protein') else 'Anthropic · September 1, 2026 research')
        save(name,image,label,name.replace('_',' '),src)
    table=Image.open(EP/'media/benchmark_table.png')
    for name,box in {
        'table_science':(50,50,2110,430),
        'table_coding':(50,50,2110,660),
        'table_overview':(0,0,2160,1996),
    }.items():
        save(name,table.crop(box),'Anthropic · September 1, 2026 benchmarks',name,EP/'media/benchmark_table.png')
    dump(EP/'cards/catalog.json',result)
    print('Prepared',len(result),'evidence views',flush=True)


def assemble():
    """Speech-aligned hard cuts; no camera drift, subtitle track, or truncated tail."""
    from pipeline.render_v2 import duration,run_command,write_concat
    from pipeline.models import EpisodeProject,Source,Claim,Script,ScriptBeat,Shot
    from collections import Counter
    import math
    timings=json.loads((EP/'paragraph_timing.json').read_text(encoding='utf-8'))
    audio=json.loads((EP/'audio_qc.json').read_text())
    if not audio['passed']:
        raise RuntimeError('Audio QC has unresolved failures; assembly stopped')
    card=json.loads((EP/'cards/catalog.json').read_text())
    # Each row refers to one spoken paragraph. Source views are selected editorially,
    # not by random pools or an unrelated fallback. Motion assets appear once only.
    plan={
      'intro_0':['@opening','launch_hero','launch_00'],
      'intro_1':['docs_01','launch_10','launch_00_detail'],
      'intro_2':['table_overview','venus_new_map','protein_figure_1'],
      'intro_3':['launch_05','docs_00','launch_04'],
      'intro_4':['launch_hero','docs_01_detail','launch_10_detail'],
      'access_0':['@access_split','docs_00_detail','launch_00_detail'],
      'access_1':['launch_09','launch_09_detail','docs_01'],
      'access_2':['docs_01_detail','launch_10','launch_10_detail'],
      'access_3':['table_coding','launch_05_detail','launch_04_detail'],
      'access_4':['docs_00','launch_00','launch_01_detail'],
      'benchmarks_0':['@science_scores','table_science','launch_04'],
      'benchmarks_1':['@coding_scores','table_coding','launch_05'],
      'benchmarks_2':['launch_04_detail','launch_05_detail','table_overview'],
      'benchmarks_3':['docs_00_detail','table_science','launch_03_detail'],
      'benchmarks_4':['@test_setup','docs_02_detail','launch_03'],
      'venus_0':['magellan_deployment','#nasa:4','venus_radar_overview'],
      'venus_1':['@venus_maps','venus_old_map','venus_new_map'],
      'venus_2':['venus_radar','venus_old_map','launch_06_detail'],
      'venus_3':['@research_roles','magellan_deployment','venus_radar_overview'],
      'venus_4':['#nasa:27','#nasa:45','venus_radar'],
      'biology_0':['protein_research_01','protein_figure_2','launch_07_detail'],
      'biology_1':['protein_research_00','protein_figure_1','protein_research_02'],
      'biology_2':['@study_split','launch_07','protein_figure_0'],
      'biology_3':['protein_figure_5','protein_figure_3','protein_figure_5'],
      'biology_4':['@evidence_ladder','protein_research_02_detail','protein_figure_4'],
      'cost_verdict_0':['docs_02','docs_02_detail','launch_01'],
      'cost_verdict_1':['@token_prices','docs_02','launch_11_detail'],
      'cost_verdict_2':['launch_01_detail','launch_01','launch_11'],
      'cost_verdict_3':['docs_05','efs_00','efs_01_detail'],
      'cost_verdict_4':['docs_05_detail','efs_01','@verdict'],
    }
    overrides=EP/'edit_plan_overrides.json'
    if overrides.exists(): plan.update(json.loads(overrides.read_text(encoding='utf-8')))
    broll_path=EP/'broll/approved_clips.json'
    broll=json.loads(broll_path.read_text(encoding='utf-8')) if broll_path.exists() else {}
    # Every render intermediate is fixed 1080p/30 fps, high-quality H.264.
    segment_dir=EP/'timeline_segments/fable-v1'
    segment_dir.mkdir(parents=True,exist_ok=True)
    rows=[]
    counts=Counter()
    for p in timings:
        names=plan[p['id']]
        for j,name in enumerate(names):
            counts[name]+=1
            if counts[name]>2 or (name.startswith('@') and counts[name]>1):
                raise RuntimeError('Repeated visual exceeds limit: '+name)
            begin=p['start']+p['duration']*j/len(names)
            end=p['start']+p['duration']*(j+1)/len(names)
            # Frame-rounded boundaries are cumulative, so no drift can build up.
            start_frame=round(begin*30);end_frame=round(end*30)
            length=(end_frame-start_frame)/30
            if length>12.0:
                raise RuntimeError(f'Visual hold exceeds 12s: {p["id"]} {length}')
            clip=None
            local_in=0.
            if name.startswith('!'):
                clip_id,_,offset=name[1:].partition(':')
                clip=broll[clip_id]
                local_in=float(offset or 0)
                ledger=json.loads(Path(clip['ledger']).read_text(encoding='utf-8'))
                if not clip.get('visual_approved') or ledger.get('rights',{}).get('basis') not in ('creative_commons','public_domain','owned','written_permission') or ledger.get('quality',{}).get('status')!='accepted':
                    raise RuntimeError('Source clip missing verified rights or visual acceptance: '+clip_id)
                if local_in+length>ledger['end_seconds']-ledger['start_seconds']+.04:
                    raise RuntimeError('Source excerpt is shorter than its shot: '+name)
                if clip.get('visible_range') and (local_in < clip['visible_range'][0] or local_in+length > clip['visible_range'][1]):
                    raise RuntimeError('Source excerpt enters an unapproved presenter/cutaway range: '+name)
                if hashlib.sha256(Path(clip['path']).read_bytes()).hexdigest()!=ledger['output_sha256']:
                    raise RuntimeError('Clip bytes no longer match the accepted ledger: '+name)
            kind='motion_graphic' if name.startswith('@') else 'official_demo' if name.startswith('#') else 'screen_recording' if clip else 'screenshot'
            src=Path(clip['path']) if clip else EP/'motion'/f'{name[1:]}.mp4' if name.startswith('@') else EP/'media/nasa_venus_topography.mp4' if name.startswith('#') else Path(card[name]['path'])
            if not src.exists() or src.stat().st_size<100:
                raise RuntimeError('Missing accepted asset: '+str(src))
            origin = ('nasa_svs' if name.startswith('#') else 'docs' if name.startswith('docs_') else 'efs' if name.startswith('efs_') else 'protein_research' if name.startswith('protein_') else 'nasa' if name in ('magellan_deployment','venus_radar_overview') else p['sources'][0] if name.startswith('@') else 'launch')
            rows.append({'id':f's{len(rows):03d}','beat_id':p['id'],'asset_key':name,'kind':kind,'source':str(src),'start':start_frame/30,'duration':length,'source_in':float(name.split(':')[1]) if name.startswith('#') else 0,'semantic_text':p['text'],'source_ids':p['sources'],'asset_source_id':origin,'asset_source_url':SOURCES.get(origin,LAUNCH)})
            if clip:
                rows[-1].update({'source_in':local_in,'asset_source_id':clip['source_id'],'asset_source_url':ledger['source_url'],'source_reference_in':ledger['start_seconds']+local_in,'source_credit':clip['credit'],'rights_basis':ledger['rights']['basis'],'rights_ledger':clip['ledger']})
                if clip.get('editorial_filter'):
                    rows[-1]['editorial_filter']=clip['editorial_filter']
                    rows[-1]['edit_note']=clip.get('edit_note','')
                SOURCES[clip['source_id']]=ledger['source_url']
    dump(EP/'storyboard.json',rows)
    def segment(row):
        dest=segment_dir/(row['id']+'.mp4')
        digest=hashlib.sha256((json.dumps(row,sort_keys=True)+hashlib.sha256(Path(row['source']).read_bytes()).hexdigest()).encode()).hexdigest()
        receipt=dest.with_suffix('.json')
        if dest.exists() and receipt.exists() and json.loads(receipt.read_text()).get('hash')==digest:
            return dest
        cmd=['ffmpeg','-y','-v','error']
        if row['kind']=='screenshot':
            cmd += ['-loop','1','-framerate','30','-i',row['source']]
            vf='scale=1920:1080:flags=lanczos,setsar=1,format=yuv420p'
        else:
            cmd += ['-ss',str(row['source_in']),'-i',row['source']]
            # Keep animation speed; append a final hold only when the paragraph is longer.
            vf='scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x1E2925,setsar=1,tpad=stop_mode=clone:stop_duration=4,format=yuv420p'
            if row.get('editorial_filter'):
                vf=row['editorial_filter'].replace('{source_in}',str(row['source_in']))+','+vf
            if row['kind']=='official_demo':
                vf += ",drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='NASA/Goddard SVS - Magellan data (2010)':fontcolor=white:fontsize=24:box=1:boxcolor=black@0.65:boxborderw=10:x=65:y=h-65"
            if row.get('source_credit'):
                credit=re.sub(r"[^A-Za-z0-9 .|/-]",'',row['source_credit'])
                vf += ",drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='"+credit+"':fontcolor=white:fontsize=23:box=1:boxcolor=black@0.70:boxborderw=9:x=w-tw-40:y=34"
        cmd += ['-an','-vf',vf,'-t',str(row['duration']),'-r','30','-c:v','libx264','-preset','fast','-crf','17','-threads','2','-pix_fmt','yuv420p','-video_track_timescale','15360',str(dest)]
        run_command(cmd)
        dump(receipt,{'hash':digest})
        if int(row['id'][1:])%10==0: print('Assembled shot',row['id'],flush=True)
        return dest
    with ThreadPoolExecutor(max_workers=3) as pool:
        paths=list(pool.map(segment,rows))
    listing=write_concat(paths,EP/'timeline_segments/fable-v1.txt')
    silent=EP/'timeline_fable_mythos_1080p.mp4'
    run_command(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-c','copy',str(silent)])
    total=sum(x['duration'] for x in rows)
    final=EP/'Claude_Fable_51_and_Mythos_1080p.mp4'
    run_command(['ffmpeg','-y','-v','error','-i',str(silent),'-i',str(EP/'narration_zubenelgenubi.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-af','apad=pad_dur=1.3','-t',str(total),'-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart',str(final)])
    narration=json.loads((EP/'narration.json').read_text())
    payload=json.loads((EP/'script.json').read_text(encoding='utf-8'))
    source_objs=[Source(id=sid,title=sid.replace('_',' ').title(),url=url,publisher='NASA' if sid.startswith('nasa') else 'Anthropic',source_type='primary') for sid,url in SOURCES.items()]
    source_objs.append(Source(id='system_card',title='Fable/Mythos 5.1 System Card',url='https://www.anthropic.com/system-cards',publisher='Anthropic',source_type='primary'))
    claims=[];beats=[]
    for p in timings:
        cid='claim_'+p['id']
        claims.append(Claim(id=cid,text=p['text'],source_ids=p['sources']))
        beats.append(ScriptBeat(id=p['id'],narration=p['text'],claim_ids=[cid],purpose='analysis',visual_direction='Source-matched evidence and original explanatory graphics',source_ids=p['sources']))
    project=EpisodeProject(episode_id=EP.name,scheduled_date='2026-09-02',status='review_required',episode={'target_minutes':10,'publishing_enabled':False,'captions_enabled':False},sources=source_objs,claims=claims,script=Script(title=payload['title'],description='Evidence-backed Fable 5.1/Mythos explainer. Source URLs in source ledger. Synthetic narration. Not a hands-on reproduction.',tags=['Claude','Fable 5.1','Mythos 5.1'],thumbnail_text='One model. Two rulebooks.',beats=beats),narration={'path':narration['path'],'duration_seconds':narration['duration'],'voice':'Zubenelgenubi'},shots=[Shot(id=r['id'],beat_id=r['beat_id'],asset_type=r['kind'],asset_path=r['source'],source_id=r['source_ids'][0],duration_seconds=r['duration'],start_seconds=r['start'],motion_style='locked',transition='cut') for r in rows],rights=[{'shot_id':r['id'],'source_url':SOURCES.get(r['source_ids'][0],LAUNCH),'basis':'original graphics' if r['kind']=='motion_graphic' else 'NASA informational reuse' if r['kind']=='official_demo' else 'source excerpt for direct commentary; final human rights review pending','status':'human_review_pending'} for r in rows],artifacts={'video':str(final),'thumbnail':str(EP/'thumbnails/one_model_two_rulebooks.png'),'script':str(EP/'script.json'),'source_ledger':str(EP/'source_ledger.json')},qc={'audio':audio,'script':json.loads((EP/'script_review.json').read_text())})
    for shot, row in zip(project.shots, rows):
        shot.source_id = row['asset_source_id']
        shot.source_in_seconds = row.get('source_reference_in',row['source_in'])
        shot.semantic_target = row['semantic_text']
    for right, row in zip(project.rights, rows):
        right['source_url'] = row['asset_source_url']
        right['source_in_seconds'] = row.get('source_reference_in',row['source_in'])
        right['source_out_seconds'] = right['source_in_seconds'] + row['duration']
        if row.get('rights_ledger'):
            right.update({'basis':row['rights_basis'],'status':'license_verified_human_editorial_review_pending','ledger':row['rights_ledger']})
            if row.get('editorial_filter'):
                right['editorial_transform']=row['editorial_filter']
                right['edit_note']=row.get('edit_note','')
    for source in project.sources:
        if source.id.startswith('youtube_'):
            source.source_type='secondary'
            source.publisher=next((c['publisher'] for c in broll.values() if c['source_id']==source.id),'YouTube creator')
    dump(EP/'episode_project.json',project.model_dump(mode='json'))
    print('DELIVERY',str(final),'seconds',duration(final),flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["acquire", "review", "narrate", "capture", "details", "graphics", "audio_review", "source_media", "cards", "assemble"])
    args = parser.parse_args()
    globals()[args.stage]()
