import React from 'react';
import {AbsoluteFill, Composition, Easing, interpolate, registerRoot, useCurrentFrame} from 'remotion';
import '@fontsource-variable/inter';

type Props = {kind: 'together' | 'stages' | 'timing' | 'protocol' | 'runtime'; seconds: number};
const C = {paper:'#F3F2ED', ink:'#24312E', moss:'#647E6A', slate:'#667780', pale:'#D6DDD5', muted:'#53625B'};
const p = (f:number, start:number, duration=20) => interpolate(f,[start,start+duration],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp',easing:Easing.bezier(.22,.7,.25,1)});
const Text = ({x,y,size=38,children,fill=C.ink,weight=500,anchor='start'}:{x:number;y:number;size?:number;children:React.ReactNode;fill?:string;weight?:number;anchor?:'start'|'middle'|'end'}) => <text x={x} y={y} fontSize={size} fill={fill} fontWeight={weight} textAnchor={anchor}>{children}</text>;
const Credit=({text}:{text:string})=><div style={{position:'absolute',left:110,bottom:58,fontSize:22,color:C.muted,display:'flex',gap:15,alignItems:'center'}}><span style={{width:28,height:2,background:C.muted}}/>{text}</div>;
const Film=({x,y,w=460,h=280,refiner=false}:{x:number;y:number;w?:number;h?:number;refiner?:boolean})=><g transform={`translate(${x} ${y})`}>
  <rect width={w} height={h} rx={8} fill="none" stroke={C.ink} strokeWidth={5}/>
  {[0,1,2,3,4,5,6].map(i=><g key={i}><rect x={18+i*(w-50)/7} y={14} width={23} height={13} fill={C.pale}/><rect x={18+i*(w-50)/7} y={h-27} width={23} height={13} fill={C.pale}/></g>)}
  {refiner?<><path d={`M30 67h30m-30 0v30M${w-30} 67h-30m30 0v30M30 ${h-67}h30m-30 0v-30M${w-30} ${h-67}h-30m30 0v-30`} stroke={C.moss} strokeWidth={4} fill="none"/><Text x={w/2} y={h/2+28} anchor="middle" size={88} weight={650}>2K</Text></>:<><path d={`M${w*.1} ${h*.77}L${w*.39} ${h*.4}L${w*.57} ${h*.64}L${w*.72} ${h*.49}L${w*.9} ${h*.77}Z`} fill={C.pale}/><circle cx={w*.73} cy={h*.3} r={h*.09} fill={C.moss}/></>}
</g>;
const Wave=({x,y,w=460,spike=false,amplitude=1}:{x:number;y:number;w?:number;spike?:boolean;amplitude?:number})=><g transform={`translate(${x} ${y}) scale(1 ${amplitude})`}>
  <line x1={0} y1={0} x2={w} y2={0} stroke={C.pale} strokeWidth={3}/>
  {Array.from({length:35},(_,i)=>{const height=spike?12+110*Math.exp(-Math.pow((i-17)/2.0,2)):18+88*Math.pow(Math.sin(i*.67),2)*Math.pow(Math.sin((i+4)*.21),2);return <line key={i} x1={i*w/34} x2={i*w/34} y1={-height} y2={height} stroke={C.moss} strokeWidth={Math.min(8,w/55)} strokeLinecap="round"/>;})}
</g>;
const Together=({f}:{f:number})=>{
  const connection=p(f,35,30), shared=p(f,98,20), scan=p(f,119,35);
  return <>
    <g opacity={p(f,-8,16)}><Film x={225} y={320}/><Text x={225} y={660} size={43}>Picture</Text></g>
    <g opacity={p(f,14,16)}><Wave x={1160} y={462} w={460}/><Text x={1160} y={660} size={43}>Sound</Text></g>
    <path d="M745 462H1090" stroke={C.slate} strokeWidth={5} strokeDasharray={345} strokeDashoffset={345*(1-connection)}/>
    <g opacity={connection}><path d="M756 451l-12 11 12 11M1078 451l12 11-12 11" stroke={C.slate} strokeWidth={4} fill="none"/></g>
    <g opacity={p(f,65,8)*(1-p(f,91,8))}><circle cx={760+310*p(f,65,30)} cy={462} r={11} fill={C.moss}/></g>
    <g opacity={shared}>
      <Text x={225} y={818} size={38}>One shared clock</Text>
      {[0,1,2,3,4,5,6,7,8].map(i=><g key={i}><rect x={690+i*102} y={738} width={78} height={54} fill={i===5?C.moss:C.pale}/><line x1={729+i*102} x2={729+i*102} y1={838-(i===5?27:8)} y2={838+(i===5?27:8)} stroke={C.moss} strokeWidth={7}/></g>)}
      <path d={`M${710+529*scan} 710V895`} stroke={C.ink} strokeWidth={5}/>
    </g>
  </>;
};
const Stages=({f}:{f:number})=>{
 const video=p(f,34,26), audio=p(f,88,42), finish=p(f,134,16);
 return <>
  <g opacity={p(f,-8,16)}>
    <circle cx={365} cy={474} r={136} fill={C.pale}/><Text x={365} y={493} size={106} weight={650} anchor="middle">7B</Text>
    <Text x={365} y={654} size={39} anchor="middle">Joint generator</Text>
  </g>
  <path d="M524 456H872" stroke={C.slate} strokeWidth={5} strokeDasharray={348} strokeDashoffset={348*(1-video)}/>
  <path d="M858 444l14 12-14 12" fill="none" stroke={C.slate} strokeWidth={4} opacity={video}/>
  <Text x={683} y={420} size={31} fill={C.muted} anchor="middle">Video</Text>
  <g opacity={p(f,53,15)}><Film x={919} y={338} w={360} h={240} refiner/><Text x={1099} y={637} size={39} anchor="middle">Video refiner</Text></g>
  <path d="M1314 456H1570" stroke={C.slate} strokeWidth={5} strokeDasharray={256} strokeDashoffset={256*(1-p(f,70,20))}/>
  <g opacity={p(f,84,15)}><path d="M1558 444l14 12-14 12" stroke={C.slate} strokeWidth={4} fill="none"/><Film x={1590} y={375} w={210} h={158}/></g>
  <path d="M365 690V771Q365 799 397 799H1643Q1683 799 1683 758V693" stroke={C.moss} fill="none" strokeWidth={6} pathLength={1} strokeDasharray={1} strokeDashoffset={1-audio}/>
  <g opacity={p(f,89,16)}><rect x={770} y={758} width={480} height={81} fill={C.paper}/><Text x={1010} y={808} size={40} fill={C.moss} anchor="middle">Original audio retained</Text></g>
  <g opacity={finish}><Wave x={1598} y={636} w={194} amplitude={.48}/><Text x={1695} y={575} size={29} anchor="middle" fill={C.muted}>Final picture</Text></g>
 </>;
};
const Timing=({f}:{f:number})=>{
 const shift=p(f,78,44), spikeX=850+310*shift, marker=p(f,134,18);
 return <>
  <Text x={120} y={435} size={35}>Picture</Text><Text x={120} y={700} size={35}>Sound</Text>
  <g opacity={p(f,-8,16)}>
    <path d="M355 423H1720M355 686H1720" stroke={C.pale} strokeWidth={4}/>
    {[0,1,2,3,4,5,6].map(i=><g key={i}><path d={`M${400+i*205} 411v24M${400+i*205} 674v24`} stroke={C.pale} strokeWidth={3}/></g>)}
    <path d="M1104 435H1216" stroke={C.ink} strokeWidth={7}/>
    <path d="M1160 286V329" stroke={C.slate} strokeWidth={3} strokeDasharray="5 8"/>
    <circle cx={1160} cy={344+53*p(f,12,20)} r={32} fill={C.moss}/>
    <g opacity={p(f,32,10)}><path d="M1090 399l20 9M1210 408l20-9" stroke={C.slate} strokeWidth={4}/></g>
  </g>
  <g opacity={p(f,16,18)}><Wave x={spikeX-200} y={686} w={400} spike/></g>
  <g opacity={p(f,42,14)*(1-shift)}><path d="M850 847H1160M850 834v26M1160 834v26" stroke={C.slate} strokeWidth={3}/><Text x={1005} y={906} size={38} fill={C.muted} anchor="middle">Sound arrives early</Text></g>
  <g opacity={marker}><path d="M1160 340V820" stroke={C.moss} strokeWidth={3} strokeDasharray="7 9"/><Text x={1160} y={906} size={38} fill={C.moss} anchor="middle">Same moment</Text></g>
 </>;
};
const Protocol=({f}:{f:number})=><>
 <g opacity={p(f,-8,16)}><Film x={185} y={372} w={260} h={175}/><path d="M225 589h190M225 617h142" stroke={C.slate} strokeWidth={8}/><Text x={315} y={715} size={42} anchor="middle">Same input</Text></g>
 <path d="M495 511H699" stroke={C.slate} strokeWidth={5} strokeDasharray={204} strokeDashoffset={204*(1-p(f,32,28))}/>
 <g opacity={p(f,58,18)}>
   {[2,1,0].map(i=><g key={i} transform={`translate(${i*23} ${-i*24})`}><rect x={746} y={391} width={256} height={212} fill={C.paper} stroke={C.slate} strokeWidth={3}/><path d="M792 452h135M792 481h100" stroke={C.pale} strokeWidth={9}/></g>)}
   <path d="M734 515H833L856 543H1045L1021 650H752Z" fill={C.pale} stroke={C.ink} strokeWidth={4}/>
   <Text x={889} y={715} size={42} anchor="middle">Save every output</Text>
 </g>
 {[{label:'Picture',y:386},{label:'Sound',y:558},{label:'Timing',y:730}].map((row,i)=><g key={row.label} opacity={p(f,88+i*20,18)}>
   <path d={`M1086 550H1174V${row.y-12}H1291`} stroke={C.slate} strokeWidth={4} fill="none"/>
   <circle cx={1340} cy={row.y-14} r={25} fill="none" stroke={C.moss} strokeWidth={4}/>
   {i===0?<rect x={1327} y={row.y-23} width={26} height={18} fill={C.pale}/>:i===1?<path d={`M1329 ${row.y-14}v-7m11 16v-23m11 17v-10`} stroke={C.moss} strokeWidth={4}/>:<path d={`M1340 ${row.y-29}v17l10 6`} stroke={C.moss} strokeWidth={3} fill="none"/>}
   <Text x={1400} y={row.y} size={48}>{row.label}</Text>
 </g>)}
 <g opacity={p(f,150,16)}><Text x={1370} y={841} size={34} fill={C.muted}>Assess separately</Text></g>
</>;
const Runtime=({f}:{f:number})=><>
 <g opacity={p(f,-8,16)}><circle cx={345} cy={522} r={134} fill="none" stroke={C.ink} strokeWidth={6}/><path d="M316 345H374M345 347V386M441 404l25-24M345 428V522H415" fill="none" stroke={C.ink} strokeWidth={6}/><Text x={345} y={743} size={42} anchor="middle">The full wait</Text></g>
 <g opacity={p(f,30,20)}><Text x={706} y={427} size={57} weight={600}>Generate picture + sound</Text><Text x={706} y={484} size={33} fill={C.muted}>Joint generation stage</Text></g>
 <path d="M747 536V589" stroke={C.slate} strokeWidth={5} strokeDasharray={53} strokeDashoffset={53*(1-p(f,71,24))}/>
 <path d="M735 578l12 13 12-13" fill="none" stroke={C.slate} strokeWidth={4} opacity={p(f,82,14)}/>
 <g opacity={p(f,96,18)}><Text x={706} y={664} size={57} weight={600}>Then refine the video</Text><Text x={706} y={721} size={33} fill={C.muted}>Separate refinement stage</Text></g>
 <g opacity={p(f,139,18)}><path d="M650 374H620V764H650" fill="none" stroke={C.moss} strokeWidth={4}/><Text x={706} y={873} size={42} fill={C.moss}>Measure the complete workflow</Text></g>
</>;
const Graphic:React.FC<Props>=({kind})=>{const f=useCurrentFrame();const title={together:'Picture and sound, together',stages:'Two different steps',timing:'Match the moment',protocol:'Keep the test honest',runtime:'Generation is not the whole wait'}[kind];const credit=kind==='timing'?'Illustration':kind==='protocol'?'Suggested test · not a reported experiment':kind==='runtime'?'Process illustration · no timing measurements':'DreamX-Creator technical report';return <AbsoluteFill style={{background:C.paper,color:C.ink,fontFamily:'Inter Variable, Arial'}}>
 <div style={{position:'absolute',top:111,left:110,fontSize:76,lineHeight:1.08,fontWeight:620,letterSpacing:-2.7}}>{title}</div>
 <svg viewBox="0 0 1920 1080" width={1920} height={1080} style={{position:'absolute',inset:0}}>{kind==='together'?<Together f={f}/>:kind==='stages'?<Stages f={f}/>:kind==='timing'?<Timing f={f}/>:kind==='protocol'?<Protocol f={f}/>:<Runtime f={f}/>}</svg>
 <Credit text={credit}/>
 </AbsoluteFill>};
registerRoot(()=><Composition id="DreamXGraphic" component={Graphic} width={1920} height={1080} fps={30} durationInFrames={240} defaultProps={{kind:'together' as const,seconds:8}} calculateMetadata={({props})=>({durationInFrames:Math.round(props.seconds*30)})}/>);
