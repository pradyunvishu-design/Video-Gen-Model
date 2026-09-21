"""Deterministic public-source evidence for the Qwen Image 2.1 private review.

No login state, paid planner, publishing, or generated substitute screenshots.
The source DOM supplies both the screenshot and any exact phrase annotation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.capture import _assert_capture_is_clean, _load_page

OUTPUT = ROOT / "data/episodes/episode_20260920_qwen_image21/captures"
URLS = {
    "repo": "https://github.com/QwenLM/Qwen-Image-2.1",
    "model": "https://huggingface.co/Qwen/Qwen-Image-2.1",
    "license": "https://github.com/QwenLM/Qwen-Image-2.1?tab=License-1-ov-file",
    "comfy": "https://blog.comfy.org/p/qwen-image-21-in-comfyui-open-weight",
}

# Every target is a literal source phrase, not a fabricated evidence headline.
SPECS = [
    ("repo_unified_creation", "repo", "Introduction", "unified text-to-image generation and image editing", "One model for creation and editing", 1.45),
    ("repo_ten_references", "repo", "Versatile Editing", "10 reference images", "Up to ten reference images", 1.55),
    ("repo_local_masks", "repo", "Versatile Editing", "circles", "Specify local edits with circles or masks", 1.4),
    ("repo_native_rgba", "repo", "Native Transparency, Unified Creation and Editing", "transparent (RGBA) images", "Native transparency and transparent-layer editing", 1.5),
    ("repo_day_zero_support", "repo", "News", "ComfyUI", "ComfyUI support announced by Qwen", 1.35),
    ("repo_multireference_code", "repo", "Image Editing (Multiple Reference Images)", "10 reference images", "Multiple-reference editing API", 1.3),
    ("repo_single_edit_code", "repo", "Image Editing (Single Image)", "Change the background to a sunset beach", "Single-image editing with a specific instruction", 1.3),
    ("repo_product_fidelity", "repo", "Portrait and Product Fidelity", "Portrait and Product Fidelity", "Qwen's published identity and product examples", 1.0),
    ("repo_resolution_settings", "repo", "Supported Aspect Ratios", "2K resolution", "Official supported resolution settings", 1.4),
    ("repo_rgba_prompt", "repo", "Transparent Image Generation (RGBA)", "RGBA image with transparency", "Transparency requires an alpha channel", 1.3),
    ("repo_memory_offload", "repo", "For GPUs with limited memory, use model offloading:", "model offloading", "Model offloading for limited GPU memory", 1.45),
    ("repo_architecture_7b", "repo", "Architecture", "7B parameters", "Seven-billion parameter visual transformer", 1.45),
    ("repo_architecture_encoder", "repo", "Text Encoder", "Qwen3-VL 8B", "Separate Qwen3-VL eight-billion text encoder", 1.6),
    ("repo_native_transparency_examples", "repo", "Native Transparency", "Native Transparency", "Qwen's published transparency examples", 1.1),
    ("repo_multireference_example", "repo", "Multi-Reference Editing", "Multi-Reference Editing", "Qwen's published multi-reference example", 1.0),
    ("repo_local_editing_example", "repo", "Local Editing", "Local Editing", "Qwen's published local-editing example", 1.0),
    ("model_card_overview", "model", "Introduction", "Qwen-Image-2.1", "Official downloadable model card", 1.4),
    ("model_cpu_offload", "model", "Memory Optimization", "enable_model_cpu_offload", "Official model card memory optimization", 1.45),
    ("model_license_notice", "model", "This model is licensed under", "Qwen Research License Agreement", "Official model card license notice", 1.6),
    ("license_research_definition", "license", '"Non-Commercial" shall mean', "research or evaluation purposes only", "Non-commercial means research or evaluation", 1.65),
    ("license_noncommercial_grant", "license", "2. Grant of Rights", "NON-COMMERCIAL", "Research license non-commercial grant", 1.65),
    ("license_commercial_permission", "license", "You shall not use the Materials for any commercial purpose", "commercial purpose", "Commercial use requires separate permission", 1.65),
    ("comfy_native_support", "comfy", "Qwen-Image-2.1 in ComfyUI:", "Qwen-Image-2.1", "Comfy's native support announcement", 1.25),
    ("comfy_alpha_channel", "comfy", "Model Highlights", "Four channels, alpha included.", "RGBA includes a real alpha channel", 1.35),
    ("comfy_getting_started", "comfy", "Getting Started", "Templates panel", "Comfy model and template setup", 1.4),
]

REJECTED = {
    "comfy_alpha_channel": "Visual QC: sticky publication header crosses body text; excluded from accepted ledger.",
    "comfy_getting_started": "Visual QC: sticky publication header crosses body text; excluded from accepted ledger.",
}

FIND_TARGET = r"""({phrase, position}) => {
  const matches = [...document.querySelectorAll('h1,h2,h3,h4,p,li,strong,td,div,span')]
    .filter(el => {const r=el.getBoundingClientRect(); return r.width>0 && r.height>0 &&
      getComputedStyle(el).visibility!=='hidden' && (el.innerText||'').includes(phrase);})
    .sort((a,b)=>(a.innerText||'').length-(b.innerText||'').length);
  if(!matches.length) throw new Error('No visible source element: '+phrase);
  const el=matches[0];
  let anchor=el.getBoundingClientRect();
  if(anchor.height>innerHeight/2){
    const w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);
    while(w.nextNode()){
      const n=w.currentNode;const i=n.textContent.indexOf(phrase);if(i<0)continue;
      const range=document.createRange();range.setStart(n,i);range.setEnd(n,i+phrase.length);
      const r=range.getBoundingClientRect();if(r.width&&r.height){anchor=r;break;}
    }
  }
  window.scrollTo(0, Math.max(0,window.scrollY+anchor.top-position));
  const column=el.closest('article,.markdown-body,.prose,.available-content')||el.closest('p,li')||el;
  const r=column.getBoundingClientRect();
  return {tag:el.tagName,text:el.innerText,column:{x:r.x,width:r.width}};
}"""

EXACT_RANGE = r"""phrase => {
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  const results=[];
  while(walker.nextNode()){
    const node=walker.currentNode; const i=node.textContent.indexOf(phrase); if(i<0) continue;
    const el=node.parentElement; if(!el || ['SCRIPT','STYLE'].includes(el.tagName)) continue;
    const style=getComputedStyle(el); if(style.visibility==='hidden'||style.display==='none') continue;
    const range=document.createRange();range.setStart(node,i);range.setEnd(node,i+phrase.length);
    const rects=[...range.getClientRects()].filter(r=>r.width>1 && r.height>1);
    if(rects.length!==1) continue;
    const r=rects[0]; if(r.x<20||r.y<90||r.right>innerWidth-20||r.bottom>innerHeight-35)continue;
    results.push({x:r.x,y:r.y,width:r.width,height:r.height,units:'pixels'});
  }
  return results.sort((a,b)=>Math.abs(a.y-400)-Math.abs(b.y-400))[0]||null;
}"""

VISIBLE_TEXT = r"""() => {
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT); const rows=[];
  while(walker.nextNode()){
    const n=walker.currentNode; if(!n.textContent.trim())continue;
    const e=n.parentElement;if(!e||['STYLE','SCRIPT'].includes(e.tagName))continue;
    const s=getComputedStyle(e);if(s.display==='none'||s.visibility==='hidden')continue;
    const r=document.createRange();r.selectNodeContents(n);const b=r.getBoundingClientRect();
    if(b.width<=0||b.height<=0||b.bottom<0||b.top>innerHeight)continue;
    if(b.top>=0&&b.bottom<=innerHeight&&b.left>=0&&b.right<=innerWidth){rows.push(n.textContent.trim());continue;}
    for(const match of n.textContent.matchAll(/\S+/g)){
      const wr=document.createRange();wr.setStart(n,match.index);wr.setEnd(n,match.index+match[0].length);
      const q=wr.getBoundingClientRect();if(q.width>0&&q.top>=0&&q.bottom<=innerHeight&&q.left>=0&&q.right<=innerWidth)rows.push(match[0]);
    }
  }return rows.join(' ');
}"""


def contact_sheet(records: list[dict]) -> None:
    tile_w, tile_h = 480, 296
    sheet = Image.new("RGB", (tile_w * 4, tile_h * ((len(records) + 3) // 4)), "#e6e6e6")
    draw = ImageDraw.Draw(sheet)
    for index, row in enumerate(records):
        with Image.open(row["path"]) as im:
            im = im.convert("RGB")
            im.thumbnail((480, 270))
            x, y = index % 4 * tile_w, index // 4 * tile_h
            sheet.paste(im, (x, y))
            draw.text((x + 6, y + 274), row["id"], fill="black")
    if records:
        sheet.save(OUTPUT / "contact_sheet.jpg", quality=92)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--only", default="")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        args.only = "__verify_only__"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records, failures, probes = [], [{"id":key,"error":value,"status":"rejected_visual_qc"} for key,value in REJECTED.items()], {}
    if args.only and (OUTPUT / "ledger.json").exists():
        records = [r for r in json.loads((OUTPUT / "ledger.json").read_text()) if r["id"] not in args.only.split(",") and r["id"] not in REJECTED]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        try:
            for key, url in URLS.items():
                specs = [r for r in SPECS if r[1] == key and r[0] not in REJECTED and (not args.only or r[0] in args.only.split(","))]
                if not specs and not args.probe:
                    continue
                context = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1, color_scheme="light")
                page = context.new_page()
                try:
                    _load_page(page, url)
                    if key == "comfy":
                        # The generic loader's newsletter selector also matches
                        # Substack's public article container. Restore it; never
                        # suppress a paywall or replace the source article.
                        page.evaluate("""() => {for(const e of [...document.querySelectorAll('style')]) if(e.textContent.includes(\"[class*='newsletter']\")) e.remove();}""")
                        for label in ("No thanks", "Maybe later"):
                            dismiss = page.get_by_role("button", name=label, exact=True).first
                            if dismiss.is_visible():
                                dismiss.click()
                        _assert_capture_is_clean(page, moment="restored public article")
                    probes[key] = {"url":page.url,"title":page.title(),"headings":page.locator("h1,h2,h3,h4").all_text_contents(),"text":page.locator("body").inner_text()}
                    if args.probe:
                        print(key, json.dumps(probes[key], ensure_ascii=True), flush=True)
                        continue
                    for ident, _, target, phrase, subject, zoom in specs:
                        try:
                            page.evaluate("zoom => {document.body.style.zoom=zoom;window.scrollTo(0,0);}", zoom)
                            target_info = page.evaluate(FIND_TARGET, {"phrase":target,"position":230})
                            page.wait_for_timeout(800)
                            page.evaluate("async()=>{await document.fonts.ready;await Promise.race([Promise.all([...document.images].filter(i=>{const r=i.getBoundingClientRect();return r.bottom>0&&r.top<innerHeight}).map(i=>i.complete?Promise.resolve():new Promise(r=>{i.onload=r;i.onerror=r}))),new Promise(r=>setTimeout(r,5000))]);}")
                            page.evaluate(FIND_TARGET, {"phrase":target,"position":230})
                            page.wait_for_timeout(200)
                            _assert_capture_is_clean(page, moment=ident)
                            text = page.evaluate(VISIBLE_TEXT)
                            if target not in text:
                                raise ValueError(f"Target not fully within viewport: {target}")
                            path = OUTPUT / f"{ident}.png"
                            annotation = page.evaluate(EXACT_RANGE, phrase)
                            page.screenshot(path=str(path), full_page=False, animations="disabled")
                            with Image.open(path) as image:
                                if image.size != (1920,1080):
                                    raise ValueError(f"Wrong dimensions {image.size}")
                            column = target_info["column"]
                            crop_x = max(0, min(480, round(column["x"] + column["width"] / 2 - 720)))
                            crop_y = 0
                            if annotation:
                                crop_x = min(crop_x, max(0, int(annotation["x"])-25))
                                crop_x = max(crop_x, min(480, int(annotation["x"]+annotation["width"]+25-1440)))
                                crop_y = max(0, min(270, round(annotation["y"]+annotation["height"]+40-810)))
                            framing = {"x":crop_x,"y":crop_y,"width":1440,"height":810,"units":"pixels","measurement":"measured source column and exact target phrase; 16:9 nondistorting crop"}
                            row = {"id":ident,"path":str(path),"url":page.url,"page_title":page.title(),"visible_text":text,"subject":subject,"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"viewport":[1920,1080],"framing":framing,"captured_at":datetime.now(timezone.utc).isoformat(),"capture_plan":{"target_phrase":target,"target_y":230,"browser_zoom":zoom},"rights_note":"Public source-page screenshot for private editorial review only; publication rights not cleared.","annotations":[]}
                            if annotation:
                                row["annotations"].append({"measurement":"exact single-line browser DOM Range","phrase":phrase,"narration_cue":subject,"region":annotation,"start":0.8,"end":6.0})
                            records.append(row)
                            print(f"CAPTURED {ident} exact_annotation={bool(annotation)}", flush=True)
                        except Exception as exc:
                            failures.append({"id":ident,"url":url,"error":str(exc)})
                            print(f"FAILED {ident}: {exc}", flush=True)
                except Exception as exc:
                    failures.append({"source":key,"url":url,"error":str(exc)})
                    print(f"FAILED SOURCE {key}: {exc}", flush=True)
                finally:
                    context.close()
        finally:
            browser.close()
    if probes:
        (OUTPUT / "discovery.json").write_text(json.dumps(probes, indent=2), encoding="utf-8")
    if not args.probe:
        for row in records:
            if row.get("annotations"):
                r = row["annotations"][0]["region"]
                row["framing"]["y"] = max(0, min(270, round(r["y"]+r["height"]+40-810)))
            path = Path(row["path"])
            assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"], row["id"]
            with Image.open(path) as image:
                assert image.size == (1920, 1080), row["id"]
            f = row["framing"]
            assert 0 <= f["x"] <= 480 and 0 <= f["y"] <= 270
            assert (f["width"], f["height"]) == (1440, 810)
            for ann in row.get("annotations", []):
                r = ann["region"]
                assert f["x"] <= r["x"] and r["x"]+r["width"] <= f["x"]+f["width"], row["id"]
                assert f["y"] <= r["y"] and r["y"]+r["height"] <= f["y"]+f["height"], row["id"]
        (OUTPUT / "ledger.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
        (OUTPUT / "failures.json").write_text(json.dumps(failures, indent=2), encoding="utf-8")
        contact_sheet(records)
    print(f"Captured {len(records)}; failures {len(failures)}", flush=True)


if __name__ == "__main__":
    main()
