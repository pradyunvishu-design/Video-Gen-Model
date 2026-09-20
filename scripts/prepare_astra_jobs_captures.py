"""Readable centered crops from authentic browser captures; never fabricate webpages."""
from pathlib import Path
from scripts.produce_astra_jobs_episode import EP,SOURCES
from scripts.produce_astra_episode import read,dump,sha,run,probe

SPECS=[
 ('finance_benchmark_source','finance_benchmark_complete.png',[535,158,1020,770],'F','Complete OfficeQA Pro source chart; original40-to100 axis visible; narration uses separate zero-based comparison'),
 ('finance_data','finance_data.png',[655,122,835,395],'F','Built-in financial data and provider context'),
 ('finance_governance','finance_governance.png',[655,124,835,470],'F','Enterprise controls and business-data training default'),
 ('finance_templates','finance_templates.png',[625,120,950,535],'F','Research and models turned into firm-template work'),
 ('law_research','law_research.png',[655,124,835,375],'L','Legal index and relevant authorities'),
 ('law_research_benchmark','law_research.png',[655,545,835,316],'L','Two-hundred-question benchmark and exact54/38.7 result'),
 ('law_firms','law_firms.png',[655,410,835,385],'L','Contract analysis and acquisition diligence examples'),
 ('law_controls','law_controls.png',[655,119,835,355],'L','Eligible law firms and specific privacy controls'),
 ('law_workflow','law_workflow.png',[655,124,835,470],'L','Applying research to facts and identifying uncertainty'),
 ('ilo_title','ilo_title.png',[380,340,1140,642],'I','2025 ILO/NASK exposure study with date'),
 ('ilo_caveat','ilo_caveat.png',[452,567,810,456],'I','Potential exposure is not actual job losses'),
]
def main():
 folder=EP/'captures';out=folder/'normalized';out.mkdir(exist_ok=True)
 rows=[]
 for ident,name,crop,evidence,caption in SPECS:
  source=folder/name;meta=probe(source);v=next(x for x in meta['streams'] if x['codec_type']=='video')
  # Browser's measured content region excludes its shell despite requested1080pviewport.
  # These coordinates were inspected against actual1823x1072 screenshots.
  if (v['width'],v['height'])!=(1823,1072): raise RuntimeError(f'{name}: unexpectedcapture {v["width"]}x{v["height"]}')
  x,y,w,h=crop;dest=out/f'{ident}.png';receipt=dest.with_suffix('.json')
  digest=sha(source)+str(crop)+sha(Path(__file__))
  if not dest.exists() or not receipt.exists() or read(receipt).get('input_hash')!=digest:
   label='Source - ILO / NASK, May 2025' if evidence=='I' else 'Source - OpenAI, September 2026'
   vf=f"crop={w}:{h}:{x}:{y},scale=1920:990:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,drawbox=x=0:y=1018:w=1920:h=62:color=black@0.75:t=fill,drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='{label}':fontsize=23:fontcolor=white:x=45:y=1038"
   run(['ffmpeg','-y','-v','error','-i',str(source),'-vf',vf,'-frames:v','1',str(dest)])
   dump(receipt,{'input_hash':digest,'sha256':sha(dest),'source_sha256':sha(source),'crop':crop})
  rows.append({'id':ident,'path':str(dest),'source_url':SOURCES[evidence],'kind':'article','caption':caption,'evidence_id':evidence,'capture_type':'authentic_browser_capture_centered_readable_crop','source_path':str(source),'source_sha256':sha(source),'sha256':sha(dest),'crop':crop,'native_dimensions':[1823,1072],'publishing_enabled':False,'rights_basis':'Limited source passage for direct explanatory commentary; publication review pending','annotation':'Precise crop to relevant passage; no guessed underline or fakecursor','max_editorial_uses':2})
 dump(folder/'ledger.json',rows)
 print('Prepared',len(rows),'authentic readable source views',flush=True)
if __name__=='__main__':main()
