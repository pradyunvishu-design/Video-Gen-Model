import React from 'react';
import {AbsoluteFill, Composition, Easing, Img, interpolate, registerRoot, staticFile, useCurrentFrame} from 'remotion';
import '@fontsource-variable/inter';

type Props={kind:string;seconds:number};
const C={paper:'#F2F0E9',ink:'#17221F',muted:'#68726B',sage:'#9CAD9D',clay:'#AB6450',line:'#CAD0C5'};
const p=(f:number,s:number,d=24)=>interpolate(f,[s,s+d],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp',easing:Easing.bezier(.22,.7,.25,1)});
const Text=({x,y,size=44,children,fill=C.ink,weight=500,anchor='start'}:{x:number;y:number;size?:number;children:React.ReactNode;fill?:string;weight?:number;anchor?:'start'|'middle'|'end'})=><text x={x} y={y} fontSize={size} fill={fill} fontWeight={weight} textAnchor={anchor}>{children}</text>;
const Draw=({d,progress,color=C.ink,width=4}:{d:string;progress:number;color?:string;width?:number})=><path d={d} fill="none" stroke={color} strokeWidth={width} pathLength={1} strokeDasharray={1} strokeDashoffset={1-progress}/>;
const Pic=({name,x,y,w,h,style={}}:{name:string;x:number;y:number;w:number;h:number;style?:React.CSSProperties})=><Img src={staticFile('qwen21/'+name)} style={{position:'absolute',left:x,top:y,width:w,height:h,objectFit:'contain',...style}}/>;
const titles:Record<string,string>={opaque:'White is still part of the image.',alpha_channel:'Alpha means visibility.',alpha:'The background is not the picture.',edit:'The change has a boundary.',references:'Give each reference a job.',components:'7B is not the whole workflow.',workflow:'Measure the finished asset.',permission:'Available ≠ unrestricted.',checks:'Three things worth checking.',outro:'Less work after Generate?'};
const Graphic:React.FC<Props>=({kind})=>{
 const f=useCurrentFrame();
 const credit=kind==='alpha'?'Source: Qwen · official transparent PNG; backgrounds added for inspection':kind==='edit'?'Source: Qwen · official annotated input and edited output':kind==='components'?'Source: Qwen repository · component sizes, not a memory benchmark':'Original explanatory diagram · not a measured model test';
 return <AbsoluteFill style={{background:C.paper,fontFamily:'Inter Variable, Arial',color:C.ink}}>
  <div style={{position:'absolute',left:104,top:86,fontSize:69,fontWeight:650,letterSpacing:-2.5,maxWidth:1560}}>{titles[kind]}</div>
  {kind==='opaque'&&<svg width={1920} height={1080}>
   <rect x={140} y={279} width={710} height={550} fill={C.ink}/><rect x={1070} y={279} width={710} height={550} fill={C.ink}/>
   <g transform={`translate(${140+120*p(f,10,38)} 335)`}><rect width={380} height={430} fill="white"/><path d="M159 76h62v96q99 32 72 149l-16 43H103l-16-43q-27-117 72-149z" fill={C.sage}/></g>
   <g opacity={p(f,65,25)} transform="translate(1235 335)"><path d="M159 76h62v96q99 32 72 149l-16 43H103l-16-43q-27-117 72-149z" fill={C.sage}/></g>
   <Text x={145} y={910} size={39}>Opaque rectangle</Text><Text x={1075} y={910} size={39}>Transparent surround</Text>
  </svg>}
  {kind==='alpha_channel'&&<svg width={1920} height={1080}>
   {[0,.5,1].map((a,i)=><g key={a} opacity={p(f,i*38,25)}>
    {Array.from({length:36},(_,k)=><rect key={k} x={225+i*560+(k%6)*52} y={328+Math.floor(k/6)*52} width={52} height={52} fill={(k+Math.floor(k/6))%2?C.line:'#FFFFFF'}/>)}
    <circle cx={381+i*560} cy={484} r={119} fill={C.clay} opacity={a}/>
    <Text x={381+i*560} y={751} size={70} weight={650} anchor="middle">{a*100}%</Text><Text x={381+i*560} y={812} size={33} anchor="middle">visible</Text>
   </g>)}
  </svg>}
  {kind==='alpha'&&<>
   <div style={{position:'absolute',left:140,top:270,width:710,height:570,background:'#fff'}}/>
   <div style={{position:'absolute',left:1070,top:270,width:710,height:570,background:C.ink}}/>
   <Pic name="example-06.png" x={215} y={292} w={560} h={520}/>
   <Pic name="example-06.png" x={1145} y={292} w={560} h={520} style={{opacity:p(f,55,30)}}/>
   <svg width={1920} height={1080}><Text x={145} y={903} size={36}>Light background</Text><Text x={1075} y={903} size={36}>Dark background</Text><Draw d="M890 554H1020m-28-23 28 23-28 23" progress={p(f,18,30)}/></svg>
  </>}
  {kind==='edit'&&<>
   <Pic name="example-18.png" x={140} y={255} w={725} h={640}/>
   <Pic name="example-19.png" x={1070} y={255} w={725} h={640} style={{opacity:p(f,65,25)}}/>
   <svg width={1920} height={1080}><Text x={140} y={947} size={32}>Annotated input</Text><Text x={1070} y={947} size={32}>Published result</Text><Draw d="M900 559H1030m-28-23 28 23-28 23" progress={p(f,25,25)}/></svg>
  </>}
  {kind==='references'&&<svg width={1920} height={1080}>
    {[['SUBJECT','Who or what?',275],['SETTING','Where?',820],['STYLE','How should it look?',1365]].map(([a,b,x],i)=><g key={String(a)} opacity={p(f,i*42,28)}>
     <circle cx={Number(x)+110} cy={510} r={128} fill={i===1?C.sage:'none'} stroke={C.ink} strokeWidth={3}/>
     {i===0?<><circle cx={Number(x)+110} cy={476} r={39} fill={C.ink}/><path d={`M${Number(x)+44} 582q0-95 66-95t66 95`} fill={C.ink}/></>:i===1?<><path d={`M${Number(x)+35} 565l68-115 39 62 34-36 38 89z`} fill={C.ink}/><circle cx={Number(x)+159} cy={442} r={18} fill={C.paper}/></>:<><path d={`M${Number(x)+41} 566l61-124h48l-61 124z`} fill={C.clay}/><path d={`M${Number(x)+110} 566l61-124h18l-61 124z`} fill={C.ink}/></>}
     <Text x={Number(x)+110} y={724} size={40} weight={650} anchor="middle">{a}</Text><Text x={Number(x)+110} y={788} size={31} anchor="middle" fill={C.muted}>{b}</Text>
    </g>)}
    <Draw d="M541 510H653M1090 510H1200" progress={p(f,100,30)} color={C.line}/>
  </svg>}
  {kind==='components'&&<svg width={1920} height={1080}>
    <g opacity={p(f,0,24)}><rect x={180} y={320} width={525} height={345} rx={12} fill={C.ink}/><Text x={440} y={507} size={133} fill={C.paper} weight={650} anchor="middle">7B</Text><Text x={442} y={739} size={40} anchor="middle">Visual generator</Text></g>
    <g opacity={p(f,72,30)}><Text x={881} y={514} size={100} fill={C.muted}>+</Text><rect x={1120} y={320} width={600} height={345} rx={12} fill={C.sage}/><Text x={1420} y={477} size={65} weight={650} anchor="middle">Qwen3-VL</Text><Text x={1420} y={568} size={73} weight={650} anchor="middle">8B</Text><Text x={1420} y={739} size={40} anchor="middle">Text encoder</Text></g>
    <g opacity={p(f,160,25)}><Text x={960} y={879} size={38} anchor="middle">Plus the image autoencoder and runtime settings.</Text></g>
  </svg>}
  {kind==='workflow'&&<svg width={1920} height={1080}>
    <Draw d="M260 567H1620" progress={p(f,10,110)} color={C.line} width={5}/>
    {[['Generate',320],['Inspect',740],['Repair',1160],['Use',1580]].map(([name,x],i)=><g key={String(name)} opacity={p(f,15+i*38,23)}><circle cx={Number(x)} cy={565} r={i===3?24:15} fill={i===3?C.clay:C.ink}/><Text x={Number(x)} y={454} size={46} weight={600} anchor="middle">{name}</Text></g>)}
    <g opacity={p(f,154,32)}><path d="M320 648v26h1260v-26" fill="none" stroke={C.ink} strokeWidth={3}/><Text x={960} y={782} size={44} anchor="middle">Count retries and cleanup, too.</Text><Text x={960} y={841} size={31} anchor="middle" fill={C.muted}>A proposed comparison — no timing result claimed.</Text></g>
  </svg>}
  {kind==='permission'&&<svg width={1920} height={1080}>
    <g opacity={p(f,0,25)}><path d="M247 340h280l84 84v330H247zM527 340v84h84M301 500h232M301 550h232M301 600h172" fill="none" stroke={C.ink} strokeWidth={6}/><Text x={743} y={455} size={66} weight={650}>Research license</Text><Text x={743} y={537} size={41}>Non-commercial purposes</Text></g>
    <g opacity={p(f,100,28)}><path d="M743 609h923" stroke={C.line} strokeWidth={3}/><Text x={743} y={711} size={44} weight={600} fill={C.clay}>Commercial use?</Text><Text x={743} y={780} size={38}>Separate permission required.</Text></g>
  </svg>}
  {kind==='checks'&&<svg width={1920} height={1080}>
    {['Clean edges','Unchanged details','Reference accuracy'].map((name,i)=><g key={name} opacity={p(f,i*55,26)}><Text x={165} y={376+i*185} size={76} fill={C.sage} weight={650}>0{i+1}</Text><Text x={365} y={376+i*185} size={63} weight={600}>{name}</Text><Draw d={`M365 ${425+i*185}H1690`} progress={p(f,i*55+12,30)} color={C.line} width={2}/></g>)}
  </svg>}
  {kind==='outro'&&<><Pic name="logo.png" x={130} y={335} w={1190} h={326}/><svg width={1920} height={1080}><g opacity={p(f,65,35)}><Text x={147} y={786} size={44}>The output matters.</Text><Text x={147} y={858} size={44} fill={C.muted}>So does everything you do with it.</Text></g></svg></>}
  <div style={{position:'absolute',left:104,bottom:38,fontSize:22,color:C.muted}}>{credit}</div>
 </AbsoluteFill>;
};
registerRoot(()=><Composition id="Qwen21Graphic" component={Graphic} width={1920} height={1080} fps={30} durationInFrames={330} defaultProps={{kind:'alpha',seconds:11}} calculateMetadata={({props})=>({durationInFrames:Math.round(props.seconds*30)})}/>);
