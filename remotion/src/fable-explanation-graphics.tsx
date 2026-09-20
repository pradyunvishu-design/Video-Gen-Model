import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';

// Original teaching diagrams, not scientific reconstructions or model predictions.
const paper='#F3F0E9', ink='#1E2925', muted='#58655E', sage='#768775', red='#B84D45';
const clamp={extrapolateLeft:'clamp' as const,extrapolateRight:'clamp' as const,easing:Easing.bezier(.22,1,.36,1)};
export const ExplanationGraphic:React.FC<{kind:string;seconds:number;source:string;phase?:string;revealTimes?:number[]}>=(p)=>{
 const f=useCurrentFrame(), t=f/30;
 const show=(n:number)=>interpolate(t,[n,n+.4],[0,1],clamp);
 const a=p.revealTimes||[0,2.4,5,7.5];
 const title=p.kind==='learn-log'?'Read the axes first':p.kind==='learn-radar'?'How do you see through the clouds?':p.kind==='learn-height'?'An elevation map describes height':p.kind==='learn-resolution'?'Smaller features ≠ smaller pixels':p.kind==='learn-binder'?'A binder attaches to a target':p.kind==='learn-hit'?'What does “50% hit rate” mean?':'Add the three parts of the bill';
 return <AbsoluteFill style={{background:paper,color:ink,fontFamily:'Arial, sans-serif',overflow:'hidden'}}>
  <div style={{position:'absolute',left:110,top:92,right:100,fontSize:74,fontWeight:750,letterSpacing:-2,lineHeight:1.08}}>{title}</div>
  {p.kind==='learn-log'?<>
    <svg width="1920" height="1080" style={{position:'absolute',inset:0}}>
      <path d="M370 300V780H1740" stroke={ink} strokeWidth="5" fill="none"/>
      {[500,1080,1660].map((x,i)=><g key={x} opacity={show(a[i]??i*2)}><path d={`M${x} 766v28`} stroke={ink} strokeWidth="4"/><text x={x} y="855" textAnchor="middle" fontSize="56" fontWeight="700" fill={ink}>{['$1','$10','$100'][i]}</text></g>)}
      {[0,1].map(i=><g key={i} opacity={show((a[i+1]??3)-.1)}><path d={`M${550+i*580} 701Q${790+i*580} 622 ${1030+i*580} 701`} stroke={red} strokeWidth="5" fill="none"/><text x={790+i*580} y="623" textAnchor="middle" fill={red} fontSize="56" fontWeight="700">×10</text></g>)}
      <text x="225" y="540" textAnchor="middle" fontSize="36" fill={muted} transform="rotate(-90 225 540)">Higher test score</text>
      <text x="1060" y="936" textAnchor="middle" fill={muted} fontSize="34">More expensive →</text>
    </svg>
    <div style={{position:'absolute',left:500,top:330,fontSize:44,maxWidth:1110,lineHeight:1.3}}>Equal spacing.<br/><strong style={{color:red}}>Multiplying cost, not adding equal dollars.</strong></div>
  </>:null}
  {p.kind==='learn-radar'?<>
    <svg width="1920" height="1080" style={{position:'absolute',inset:0}}>
      <g transform="translate(600 260)"><rect x="-42" y="-25" width="84" height="84" rx="10" fill={ink}/><path d="M-200-10h142v56h-142zM60-10h142v56H60z" fill={sage}/><path d="m-15 60 45 45 45-45" fill="none" stroke={ink} strokeWidth="7"/></g>
      <path d="M140 463Q240 391 350 452Q470 387 580 452Q710 383 835 452Q930 386 1060 452Q1170 389 1290 452Q1430 390 1580 452Q1710 400 1790 463V530H140Z" fill="#C8CEC9" opacity=".65"/>
      <path d="M140 803 380 760 530 800 770 651 980 760 1220 690 1430 774 1780 734V894H140Z" fill={sage}/>
      <path d="M610 372 770 651 653 372" fill="none" stroke={red} strokeWidth="6" strokeDasharray="660" strokeDashoffset={interpolate(t,[a[1],a[1]+2],[660,0],clamp)}/>
      <text x="1440" y="410" fill={muted} fontSize="34">Cloud layer</text><text x="1490" y="856" fill={paper} fontSize="34">Surface</text>
    </svg>
    <div style={{position:'absolute',left:1120,top:270,fontSize:39,lineHeight:1.4,opacity:show(a[1])}}>Radio signal goes down.<br/>An echo comes back.</div>
    <div style={{position:'absolute',left:160,top:575,fontSize:35,opacity:show(a[2])}}>Magellan radar</div>
  </>:null}
  {p.kind==='learn-height'||p.kind==='learn-resolution'?<>
    <svg width="1920" height="1080" style={{position:'absolute',inset:0}}>
     <path d="M160 766H1750" stroke="#B7BFB8" strokeWidth="2" strokeDasharray="10 12"/>
     <path d="M160 744 320 724 485 580 615 720 840 368 1010 690 1170 444 1350 690 1520 596 1750 744V820H160Z" fill={sage} opacity=".35"/>
     <path d="M160 744 320 724 485 580 615 720 840 368 1010 690 1170 444 1350 690 1520 596 1750 744" stroke={ink} strokeWidth="6" fill="none"/>
     {p.kind==='learn-height'?<g opacity={show(a[1])}><path d="M876 766h66M910 766V368M876 368h66" stroke={red} strokeWidth="5"/><text x="1300" y="390" fontSize="57" fontWeight="700" fill={red}>Height</text><text x="1300" y="446" fontSize="31" fill={muted}>above a reference level</text></g>:<>
      <path d="M160 744Q960 348 1750 744" stroke={red} strokeWidth="6" fill="none" strokeDasharray="13 11" opacity={show(a[1])}/>
      <text x="170" y="330" fill={red} fontSize="38" opacity={show(a[1])}>Coarse estimate: nearby features merge</text>
      <text x="1080" y="325" fill={ink} fontSize="38">Finer estimate: ridges separate</text>
     </>}
    </svg>
    <div style={{position:'absolute',left:170,bottom:160,fontSize:36,color:muted}}>{p.kind==='learn-height'?'Height data—not a photograph of rock colors.':'Illustrative cross-section—not a measured slice of Venus.'}</div>
  </>:null}
  {p.kind==='learn-binder'?<>
    <svg width="1920" height="1080" style={{position:'absolute',inset:0}}>
     <path d="M1080 365C1280 290 1500 375 1540 525C1600 755 1410 859 1250 783C1140 743 1120 690 1080 670L1190 615 1110 540 1190 465Z" fill="#B8C0B9" stroke={ink} strokeWidth="4"/>
     <g style={{translate:`${interpolate(t,[a[1],a[1]+1.8],[0,395],clamp)}px 0px`}}><path d="M620 378C478 370 405 443 420 559C425 693 554 728 685 685L795 615 715 540 795 465Z" fill="#D97757" stroke="#AC5139" strokeWidth="4"/></g>
     <text x={510+interpolate(t,[a[1],a[1]+1.8],[0,395],clamp)} y="820" fontSize="46" fontWeight="700" fill={ink}>Binder</text><text x="1310" y="880" textAnchor="middle" fontSize="46" fontWeight="700" fill={ink}>Target</text>
    </svg>
    <div style={{position:'absolute',left:170,top:235,fontSize:37,color:muted}}>Simplified shape analogy · not a molecular structure</div>
  </>:null}
  {p.kind==='learn-hit'?<>
    <div style={{position:'absolute',left:160,top:305,fontSize:36,color:muted}}>A made-up example: 10 candidate designs</div>
    <svg width="1250" height="500" style={{position:'absolute',left:130,top:400}}>
     {Array.from({length:10},(_,i)=>{const active=i<5&&t>a[1]+i*.45;return <g key={i}><circle cx={90+(i%5)*205} cy={95+Math.floor(i/5)*205} r="69" fill={active?sage:'none'} stroke={active?ink:'#929F95'} strokeWidth="4"/>{active?<path d={`m${60+(i%5)*205} ${95+Math.floor(i/5)*205} 20 21 42-46`} fill="none" stroke={paper} strokeWidth="7"/>:null}</g>})}
    </svg>
    <div style={{position:'absolute',left:1350,top:390,opacity:show(a[2]),fontSize:118,fontWeight:750,lineHeight:1.2}}>5 / 10<div style={{fontSize:100,color:sage}}>= 50%</div><div style={{fontSize:30,fontWeight:400,marginTop:25}}>meet the test criterion</div></div>
    <div style={{position:'absolute',left:160,bottom:145,fontSize:38,opacity:show(a[3])}}>A binder hit rate is not a patient success rate.</div>
  </>:null}
  {p.kind==='learn-bill'?<>
    <div style={{position:'absolute',left:120,top:245,fontSize:33,color:muted}}>Hypothetical usage · cache already exists</div>
    <div style={{position:'absolute',left:140,top:335,right:155}}>
    {[
      ['1M fresh input tokens','$10'],['1M cached-read tokens','$0.25'],['100k output tokens','$5']
    ].map(([label,cost],i)=><div key={label} style={{display:'flex',justifyContent:'space-between',alignItems:'center',height:115,borderBottom:'2px solid #BAC2B9',opacity:show(a[i]),fontSize:49}}><span>{label}</span><strong>{cost}</strong></div>)}
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginTop:30,opacity:show(a[3]),fontSize:67,fontWeight:750}}><span>These items total</span><span style={{color:red}}>$15.25</span></div>
    </div>
    <div style={{position:'absolute',left:140,bottom:150,fontSize:31,color:muted}}>Excludes cache-write charges and any other fees.</div>
  </>:null}
  <div style={{position:'absolute',left:110,bottom:48,fontSize:23,color:muted}}>{p.source}</div>
 </AbsoluteFill>;
};
