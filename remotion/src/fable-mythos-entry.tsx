import React from 'react';
import {AbsoluteFill, Composition, Easing, Img, interpolate, registerRoot, staticFile, useCurrentFrame} from 'remotion';
import {ExplanationGraphic} from './fable-explanation-graphics';

type Props={kind:string; title:string; subtitle:string; labels:string[]; values:number[]; images:string[]; logo:string; source:string; seconds:number; dark?:boolean; revealTimes?:number[]};
const paper='#F3F0E9', ink='#1E2925', clay='#D97757', sage='#768775';
const ease=Easing.bezier(.22,1,.36,1);
const Reveal:React.FC<{at:number;children:React.ReactNode}>=({at,children})=>{
  const f=useCurrentFrame();
  return <div style={{opacity:interpolate(f,[at,at+18],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}),translate:interpolate(f,[at,at+22],['0px 14px','0px 0px'],{extrapolateLeft:'clamp',extrapolateRight:'clamp',easing:ease})}}>{children}</div>;
};
const Mark:React.FC<{src:string,size?:number}>=({src,size=90})=><Img src={staticFile(src)} style={{width:size,height:size,objectFit:'contain'}}/>;
const Icon:React.FC<{type:number;size?:number;color?:string}>=({type,size=100,color=ink})=><svg width={size} height={size} viewBox="0 0 100 100" fill="none" stroke={color} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round">
  {type===0?<><path d="M22 17h56v66H22z"/><path d="M34 34h32M34 48h26M34 62h18"/></>:null}
  {type===1?<><circle cx="44" cy="44" r="25"/><path d="m63 63 23 23M35 44l7 7 13-16"/></>:null}
  {type===2?<><path d="M19 76h64M29 73V37M50 73V22M71 73V46"/></>:null}
  {type===3?<><rect x="24" y="43" width="53" height="40" rx="6"/><path d="M34 43V29a17 17 0 0 1 34 0v14"/><circle cx="50" cy="61" r="3"/></>:null}
  {type===4?<><path d="m35 22-18 28 18 28M65 22l18 28-18 28M55 17 44 83"/></>:null}
  {type===5?<><path d="M36 15h28M42 15v33L22 79q-4 7 7 7h42q11 0 7-7L58 48V15M34 65h31"/><circle cx="46" cy="71" r="2"/><circle cx="57" cy="78" r="2"/></>:null}
  {type===6?<><circle cx="50" cy="50" r="34"/><path d="M16 50h68M50 16c-27 26-27 42 0 68M50 16c27 26 27 42 0 68M25 29h50M25 71h50"/></>:null}
  {type===7?<><path d="M17 25h66v44H17zM37 84h26M50 69v15"/><path d="m34 48 10 10 22-25"/></>:null}
</svg>;

const Graphic:React.FC<Props>=(p)=>{
 const f=useCurrentFrame(), fg=p.dark?paper:ink, bg=p.dark?ink:paper;
 if(p.kind.startsWith('learn-')) return <ExplanationGraphic {...p}/>;
 const header=<div style={{position:'absolute',left:110,top:100,right:110,display:'flex',alignItems:'center',gap:34}}><Mark src={p.logo} size={78}/><div style={{fontSize:62,fontWeight:750,letterSpacing:-2,lineHeight:1.04,maxWidth:1370}}>{p.title}</div></div>;
 return <AbsoluteFill style={{background:bg,color:fg,fontFamily:'Arial, sans-serif',overflow:'hidden'}}>
  {p.kind==='intro-roadmap'?<>
    <div style={{position:'absolute',left:110,top:86,right:110,display:'flex',alignItems:'center',justifyContent:'space-between'}}>
      <Mark src={p.logo} size={76}/>
      <div style={{fontSize:22,letterSpacing:3.2,textTransform:'uppercase',color:'#A8B2AA'}}>Claude Fable 5.1 + Mythos 5.1</div>
    </div>
    <div style={{position:'absolute',left:112,top:214,width:1500}}>
      <Reveal at={0}><div style={{fontSize:91,fontWeight:780,letterSpacing:-4.2,lineHeight:1.02}}>Same model. <span style={{color:clay}}>Different rules.</span></div></Reveal>
      <Reveal at={8}><div style={{fontSize:35,lineHeight:1.35,marginTop:30,color:'#C8CEC8',maxWidth:1220}}>The access split changes how the benchmarks—and the launch itself—should be read.</div></Reveal>
    </div>
    <div style={{position:'absolute',left:130,right:130,top:585,height:6,background:'#334139'}}>
      <div style={{height:'100%',width:`${interpolate(f,[20,80],[0,100],{extrapolateLeft:'clamp',extrapolateRight:'clamp',easing:ease})}%`,background:sage}}/>
    </div>
    <div style={{position:'absolute',left:120,right:120,top:535,display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:72}}>
      {[
        ['01','THE SPLIT','Who can use each version'],
        ['02','THE EVIDENCE','What the scores actually show'],
        ['03','THE VERDICT','Science, price, and the real tradeoff'],
      ].map((item,i)=><Reveal key={item[0]} at={18+i*22}>
        <div style={{paddingTop:78}}>
          <div style={{width:23,height:23,borderRadius:12,background:i===0?clay:sage,border:`5px solid ${ink}`,boxShadow:`0 0 0 2px ${i===0?clay:sage}`,marginBottom:28}}/>
          <div style={{fontSize:20,letterSpacing:2.6,color:'#9FAAA2'}}>{item[0]} · {item[1]}</div>
          <div style={{fontSize:34,fontWeight:700,lineHeight:1.18,marginTop:15,maxWidth:440}}>{item[2]}</div>
        </div>
      </Reveal>)}
    </div>
  </>:null}
  {p.kind==='hero'||p.kind==='thumb-access'?<>
    <div style={{position:'absolute',left:100,top:105,width:1050}}>
      <Mark src={p.logo} size={150}/><div style={{fontSize:114,lineHeight:.98,letterSpacing:-5,fontWeight:800,marginTop:45}}>One model.<br/><span style={{color:clay}}>Two rulebooks.</span></div>
      <div style={{fontSize:35,marginTop:45,lineHeight:1.3,color:p.dark?'#CBD0C7':'#626A61'}}>Claude Fable 5.1 + Mythos 5.1</div>
    </div>
    <div style={{position:'absolute',left:1180,top:180,width:580,height:730,borderLeft:`2px solid ${p.dark?'#647267':'#BBC1B6'}`,paddingLeft:70}}>
      {['Fable 5.1','Mythos 5.1'].map((x,i)=><Reveal key={x} at={18+i*40}><div style={{padding:'44px 0',borderBottom:`2px solid ${p.dark?'#647267':'#BBC1B6'}`}}><Icon type={i===0?7:3} size={100} color={i===0?sage:clay}/><div style={{fontSize:49,fontWeight:750,marginTop:25}}>{x}</div><div style={{fontSize:29,marginTop:16}}>{i===0?'General access':'Restricted access'}</div></div></Reveal>)}
    </div>
  </>:null}
  {p.kind==='branch'?<>{header}<div style={{position:'absolute',left:120,top:440,width:390,textAlign:'center'}}><Mark src={p.logo} size={190}/><div style={{fontSize:43,fontWeight:700,marginTop:30}}>Same model</div></div><svg style={{position:'absolute',inset:0}} width="1920" height="1080"><path d="M540 550H760V365H1010M760 550V785H1010" fill="none" stroke={sage} strokeWidth="5" pathLength="1" strokeDasharray="1" strokeDashoffset={1-interpolate(f,[15,55],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp',easing:ease})}/></svg><div style={{position:'absolute',left:1070,top:265,width:680}}>{p.labels.map((x,i)=><Reveal key={x} at={25+i*50}><div style={{height:360,display:'flex',gap:30,alignItems:'center'}}><Icon type={i===0?4:3} color={i===0?sage:clay}/><div style={{fontSize:50,fontWeight:700,lineHeight:1.18}}>{x}<div style={{fontSize:29,fontWeight:400,marginTop:20}}>{i===0?'Broad availability':'Verify exact eligibility'}</div></div></div></Reveal>)}</div></>:null}
  {p.kind==='bars'?<>{header}<div style={{position:'absolute',left:130,right:180,top:330}}>{p.labels.map((label,i)=><div key={label} style={{marginBottom:66}}><div style={{display:'flex',justifyContent:'space-between',fontSize:39,marginBottom:22}}><span>{label}</span><strong>{p.values[i]}%</strong></div><div style={{height:68,background:p.dark?'#344139':'#DADCD2'}}><div style={{height:'100%',width:`${interpolate(f,[15+i*18,55+i*18],[0,p.values[i]],{extrapolateLeft:'clamp',extrapolateRight:'clamp',easing:ease})}%`,background:i===0?sage:clay}}/></div></div>)}<div style={{fontSize:26,color:p.dark?'#C4CBBF':'#5F695F'}}>0–100% axis · Anthropic-reported results · Not an independent test</div></div></>:null}
  {p.kind==='sequence'||p.kind==='checks'?<>{header}<div style={{position:'absolute',left:110,right:110,top:385,display:'flex',gap:50}}>{p.labels.map((label,i)=><div key={label} style={{flex:1}}><Reveal at={12+i*43}><div style={{borderTop:`3px solid ${i===1?clay:sage}`,paddingTop:40}}><Icon type={p.values[i]??i} size={118} color={i===1?clay:fg}/><div style={{fontSize:48,fontWeight:750,marginTop:44,lineHeight:1.15}}>{label}</div></div></Reveal></div>)}</div><div style={{position:'absolute',left:110,bottom:160,fontSize:31,maxWidth:1540,lineHeight:1.3}}>{p.subtitle}</div></>:null}
  {p.kind==='cost'?<>{header}<div style={{position:'absolute',left:100,right:100,top:345,display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:65}}>{['Cached read','Base input','Output'].map((x,i)=><Reveal at={10+i*35} key={x}><div style={{borderTop:`3px solid ${i===0?clay:sage}`,paddingTop:42}}><div style={{fontSize:35}}>{x}</div><div style={{fontSize:i===0?130:145,fontWeight:780,letterSpacing:-7,marginTop:40,color:i===0?clay:fg}}>{['$0.25','$10','$50'][i]}</div><div style={{fontSize:28,marginTop:22}}>per million tokens</div></div></Reveal>)}</div><div style={{position:'absolute',left:100,bottom:160,fontSize:36}}>Cached reads are not the price of the whole request.</div></>:null}
  {p.kind==='venus'||p.kind==='thumb-venus'?<>{header}<div style={{position:'absolute',left:110,right:110,top:290,display:'flex',gap:40}}>{p.images.map((src,i)=><div key={src} style={{flex:1}}><Reveal at={10+i*28}><Img src={staticFile(src)} style={{width:'100%',height:510,objectFit:'cover'}}/><div style={{fontSize:33,marginTop:28,fontWeight:650}}>{p.labels[i]}</div></Reveal></div>)}</div><div style={{position:'absolute',left:110,bottom:112,fontSize:29}}>{p.subtitle}</div></>:null}
  {p.kind==='study'?<>{header}<div style={{position:'absolute',left:120,right:120,top:360,display:'grid',gridTemplateColumns:'1fr 1fr',gap:100}}>{p.labels.map((x,i)=><Reveal key={x} at={14+i*35}><div style={{borderTop:`4px solid ${i===0?sage:clay}`,paddingTop:38}}><div style={{fontSize:33}}>{i===0?'August 18 research':'September 1 launch'}</div><div style={{fontSize:65,fontWeight:750,lineHeight:1.08,marginTop:30}}>{x}</div><div style={{fontSize:43,marginTop:55}}>{i===0?'15 targets':'12 targets'}</div></div></Reveal>)}</div><div style={{position:'absolute',left:120,bottom:150,fontSize:35}}>Different experiments. Not a controlled model comparison.</div></>:null}
  {p.kind==='quote'?<>{header}<div style={{position:'absolute',left:130,right:130,top:370,fontSize:88,fontWeight:730,letterSpacing:-3,lineHeight:1.14}}><Reveal at={12}>{p.labels[0]}</Reveal></div><div style={{position:'absolute',left:135,right:135,bottom:180,fontSize:34,lineHeight:1.35}}>{p.subtitle}</div></>:null}
  {p.kind==='thumb-cost'?<><div style={{position:'absolute',left:110,top:100}}><Mark src={p.logo} size={170}/><div style={{fontSize:134,fontWeight:800,letterSpacing:-5,marginTop:45}}>The price<br/><span style={{color:clay}}>has a catch.</span></div></div><div style={{position:'absolute',left:1230,top:220,fontSize:170,fontWeight:780,color:clay}}>$0.25<div style={{fontSize:43,fontWeight:600,color:fg,marginTop:55}}>CACHED READS<br/>≠ WHOLE BILL</div></div></>:null}
  {p.kind==='thumb-evidence'?<><div style={{position:'absolute',left:110,top:120}}><Mark src={p.logo} size={170}/><div style={{fontSize:125,fontWeight:800,letterSpacing:-5,lineHeight:1.01,marginTop:45}}>Beyond<br/>the <span style={{color:clay}}>chatbot.</span></div></div><div style={{position:'absolute',right:110,top:150,width:770}}><Img src={staticFile(p.images[0])} style={{width:670,height:670,objectFit:'cover',borderRadius:335}}/><div style={{fontSize:35,textAlign:'center',marginTop:20}}>CLAUDE → VENUS MAPPING</div></div></>:null}
  {!p.kind.startsWith('thumb')?<div style={{position:'absolute',left:110,bottom:48,fontSize:23,color:p.dark?'#ABB6A8':'#606C62'}}>{p.source}</div>:null}
 </AbsoluteFill>;
};
const defaults:Props={kind:'hero',title:'One model. Two rulebooks.',subtitle:'',labels:[],values:[],images:[],logo:'fable-mythos/Claude Spark - Clay.png',source:'Anthropic · September 1, 2026',seconds:9};
const Root=()=> <Composition id="FableMythosGraphic" component={Graphic} width={1920} height={1080} fps={30} durationInFrames={270} defaultProps={defaults} calculateMetadata={({props})=>({durationInFrames:Math.round(props.seconds*30)})}/>;
registerRoot(Root);
