const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const sharp = require('C:/Users/kanag/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const root = 'C:/Youtube Automation for Magic hour';
const out = path.join(root, 'data/episodes/episode_20260919_astra_jobs/thumbnails');
const plate = path.join(out, 'jobs_space_board_plate_v2.png');
const logo = path.join(root, 'remotion/public/brands/openai.svg');
const withIs = process.argv.includes('--with-is');
const version = withIs ? 'v3' : 'v2';
const stem = withIs ? 'Astra_Your_Job_Is_Next_v3' : 'Astra_Your_Job_Next_v2';
const headline = withIs ? 'YOUR JOB IS NEXT?' : 'YOUR JOB NEXT?';
const name = `${stem}_1080p.jpg`;
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');

(async () => {
  const background = await sharp(plate).resize(1920,1080,{fit:'fill'}).toBuffer();
  const typography = Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">
    <defs><linearGradient id="shade" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".5"/></linearGradient></defs>
    <rect x="1000" y="470" width="920" height="610" fill="url(#shade)"/>
    <g font-family="Arial Black, Arial" font-weight="900" fill="#15191C" letter-spacing="-5">
      <g transform="matrix(1 .06 0 .94 162 225)"><text x="0" y="115" font-size="139" textLength="655" lengthAdjust="spacingAndGlyphs">LAWYER</text><path d="M-14 70 L675 53" fill="none" stroke="#D32D35" stroke-width="15" stroke-linecap="round"/></g>
      <g transform="translate(164 484)"><text x="0" y="111" font-size="141" textLength="660" lengthAdjust="spacingAndGlyphs">BANKER</text><path d="M-12 68 L677 52" fill="none" stroke="#D32D35" stroke-width="15" stroke-linecap="round"/></g>
      <g transform="matrix(1 -.05 0 1 155 739)"><text x="0" y="108" font-size="137" textLength="685" lengthAdjust="spacingAndGlyphs">ANALYST</text><path d="M-8 67 L701 55" fill="none" stroke="#D32D35" stroke-width="15" stroke-linecap="round"/></g>
    </g>
    <g font-family="Arial Black, Arial" font-weight="900" fill="#fff">
      <text x="1065" y="248" font-family="Arial" font-size="56" letter-spacing="4">ASTRA</text>
      <text x="1051" y="520" font-size="164" letter-spacing="-5">YOUR</text>
      ${withIs ? '<text x="1048" y="714" font-size="184" letter-spacing="-5" textLength="751" lengthAdjust="spacingAndGlyphs">JOB IS</text>' : '<text x="1043" y="718" font-size="238" letter-spacing="-7">JOB</text>'}
      <rect x="1054" y="753" width="762" height="199" fill="#CF303B"/>
      <text x="1084" y="910" font-size="181" textLength="690" lengthAdjust="spacingAndGlyphs" letter-spacing="-5">NEXT?</text>
    </g>
  </svg>`);
  const mark = await sharp(logo).resize(224,224,{fit:'contain',background:{r:0,g:0,b:0,alpha:0}}).png().toBuffer();
  const final = await sharp(background).composite([{input:typography},{input:mark,left:1582,top:132}]).png().toBuffer();
  await sharp(final).png().toFile(path.join(out, `${stem}_master.png`));
  await sharp(final).jpeg({quality:94,chromaSubsampling:'4:4:4'}).toFile(path.join(out,name));
  await sharp(final).resize(320,180).png().toFile(path.join(out,`preview_${version}.png`));
  await sharp(final).resize(320,180).grayscale().png().toFile(path.join(out,`grayscale_${version}.png`));
  const manifest = {
    headline, context:'ASTRA', represented_companies:['openai'],
    hooks_considered:['YOUR JOB NEXT?','OUR JOBS NEXT?','WHO STILL GETS HIRED?','YOUR NEW COWORKER?','CAN ASTRA DO THIS?','THE WORK JUST CHANGED','WHO CHECKS THE AI?','ASTRA GOES TO WORK'],
    concepts_considered:[{name:'Job-list tension',selected:true,reason:'Matches requested list grammar; paired with a question and Astra visual continuity'},{name:'Briefcase consequence',selected:false,reason:'User requested a stronger alternative to v1'},{name:'Real workflow receipt',selected:false,reason:'Too much small interface detail'},{name:'Task handoff map',selected:false,reason:'Better suited to an explanatory video graphic'}],
    visual_metaphor:true, claim_scope:'Question about potential effects on occupations, not a report of eliminated jobs',
    forbidden_claims:['Only five jobs survive','Confirmed layoffs','All these occupations have already been replaced','OpenAI endorsement'],
    resolved_brand_assets:[{key:'openai',asset_path:logo,official_source_url:'https://openai.com/brand/',sha256:hash(logo),generated:false}],
    candidates:[{path:path.join(out,name),brand_placements:[{key:'openai',x:1582,y:132,width:224,height:224}]}],
    evidence:['../script.json','https://openai.com/index/introducing-chatgpt-financial-services/','https://openai.com/index/astra-for-law/'],
    generation_mode:'Built-in imagegen identity-free plate; existing native Sharp/SVG composition for exact typography and official logo',
    originality:'Reference used for bold job-list visual grammar only; no faces, original badges, or survival count copied',
    width:1920,height:1080,sha256:hash(path.join(out,name)),publishing_enabled:false
  };
  fs.writeFileSync(path.join(out,`manifest_${version}.json`),JSON.stringify(manifest,null,2));
  console.log(JSON.stringify({image:path.join(out,name),bytes:fs.statSync(path.join(out,name)).size,sha256:manifest.sha256}));
})().catch(error => {console.error(error.message);process.exitCode=1;});
