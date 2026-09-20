import React from 'react';
import {AbsoluteFill,Composition,Easing,Img,interpolate,registerRoot,staticFile,useCurrentFrame} from 'remotion';
import '@fontsource-variable/inter';

type Kind='latency'|'edit'|'continuity'|'sketch'|'tradeoff'|'check';
type Props={kind:Kind;seconds:number};
const C={paper:'#F3F2ED',ink:'#131313',muted:'#646464',line:'#B7B7B2',soft:'#DEDED8',red:'#B5322D'};
const p=(f:number,s:number,d=24)=>interpolate(f,[s,s+d],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp',easing:Easing.bezier(.22,.7,.25,1)});
const T=({x,y,size=38,children,fill=C.ink,weight=500,anchor='start'}:{x:number;y:number;size?:number;children:React.ReactNode;fill?:string;weight?:number;anchor?:'start'|'middle'|'end'})=><text x={x} y={y} fontSize={size} fill={fill} fontWeight={weight} textAnchor={anchor}>{children}</text>;
const Line=({d,progress=1,color=C.ink,width=4}:{d:string;progress?:number;color?:string;width?:number})=><path d={d} fill="none" stroke={color} strokeWidth={width} pathLength={1} strokeDasharray={1} strokeDashoffset={1-progress}/>;
const Credit=({children}:{children:React.ReactNode})=><div style={{position:'absolute',left:108,bottom:54,fontSize:23,color:C.muted,display:'flex',gap:15,alignItems:'center'}}><span style={{width:25,height:2,background:C.muted}}/>{children}</div>;
const Poster=({x=0,y=0,w=570,h=530,red=0,background=0,crop=0}:{x?:number;y?:number;w?:number;h?:number;red?:number;background?:number;crop?:number})=><g transform={`translate(${x} ${y})`}>
 <rect width={w} height={h} fill={C.paper} stroke={C.ink} strokeWidth={3}/>
 <rect x={20} y={20} width={w-40} height={h-40} fill={C.soft} opacity={background}/>
 <T x={45} y={75} size={w*.076} weight={670}>FORM / STUDY</T>
 <path d={`M${w*.13} ${h*.78}H${w*.88}`} stroke={C.line} strokeWidth={3}/>
 <ellipse cx={w*.51} cy={h*.77} rx={w*.23} ry={h*.035} fill={C.line}/>
 <path d={`M${w*.43} ${h*.26}H${w*.59}V${h*.35}Q${w*.72} ${h*.41} ${w*.70} ${h*.62}L${w*.65} ${h*.75}H${w*.37}L${w*.32} ${h*.62}Q${w*.30} ${h*.41} ${w*.43} ${h*.35}Z`} fill={C.ink}/>
 <path d={`M${w*.43} ${h*.26}H${w*.59}V${h*.35}Q${w*.72} ${h*.41} ${w*.70} ${h*.62}L${w*.65} ${h*.75}H${w*.37}L${w*.32} ${h*.62}Q${w*.30} ${h*.41} ${w*.43} ${h*.35}Z`} fill={C.red} opacity={red}/>
 <Line d={`M${w*.46} ${h*.42}Q${w*.40} ${h*.50} ${w*.43} ${h*.61}`} color={C.paper} width={5}/>
 <T x={45} y={h-34} size={w*.041}>CERAMIC / NO. 04</T>
 <rect x={-2} y={-2} width={38*crop} height={h+4} fill={C.paper}/><rect x={w-36*crop} y={-2} width={38*crop} height={h+4} fill={C.paper}/>
 <g opacity={crop}><path d={`M${18+18*crop} 18h60m-60 0v60M${w-18-18*crop} 18h-60m60 0v60M${18+18*crop} ${h-18}h60m-60 0v-60M${w-18-18*crop} ${h-18}h-60m60 0v-60`} stroke={C.ink} fill="none" strokeWidth={8}/></g>
</g>;
const Latency=({f}:{f:number})=>{
 const a=p(f,20,48),b=p(f,84,55),note=p(f,162,32);
 return <>
 <T x={110} y={302} size={31} fill={C.muted}>Normalized latency index</T>
 <T x={110} y={403} size={41}>Images 2.0</T><rect x={432} y={352} width={1190*a} height={72} fill={C.ink}/><T x={1665} y={408} size={62} weight={670}>100</T>
 <T x={110} y={568} size={41}>Images 2.5</T><rect x={432} y={517} width={595*b} height={72} fill={C.muted}/><T x={1070} y={574} size={62} weight={670} fill={C.muted}>{Math.round(50*b)}</T>
 <Line d="M432 653H1622" color={C.line}/>{[0,25,50,75,100].map((n,i)=><g key={n}><path d={`M${432+i*297.5} 642v22`} stroke={C.line} strokeWidth={2}/><T x={432+i*297.5} y={702} size={27} fill={C.muted} anchor="middle">{n}</T></g>)}
 <g opacity={note}><T x={432} y={811} size={40} weight={650}>Illustration — not seconds.</T><T x={432} y={866} size={32}>Not our benchmark. “Up to” is a ceiling, not a guarantee.</T></g>
 </>;
};
const Edit=({f}:{f:number})=><>
 <rect x={170} y={280} width={590} height={550} fill={C.paper} stroke={C.ink} strokeWidth={3}/>
 <T x={218} y={380} size={76} weight={760}>NIGHT</T><T x={218} y={460} size={76} weight={760}>MARKET</T>
 <path d="M216 637h493M240 637v48m52-48v48m52-48v48m52-48v48m52-48v48m52-48v48m52-48v48m52-48v48m52-48v48M224 685h475" fill="none" stroke={C.ink} strokeWidth={4}/>
 <T x={218} y={758} size={31} weight={550}>7 PM / RIVER SQUARE</T>
 <g opacity={1-p(f,95,20)}><T x={218} y={579} size={64} weight={660}>Friday</T></g>
 <g opacity={p(f,115,25)}><T x={218} y={579} size={64} weight={660}>Saturday</T></g>
 <g opacity={p(f,28,20)}><T x={966} y={527} size={45} weight={640}>Friday → Saturday.</T><T x={966} y={585} size={32} fill={C.muted}>Change only the requested date.</T></g>
 <g opacity={p(f,155,32)}><T x={966} y={720} size={43} weight={620}>Keep the rest of the poster.</T><T x={966} y={775} size={32} fill={C.muted}>Layout · artwork · other lettering</T></g>
 </>;
const Continuity=({f}:{f:number})=>{
 const state=Math.min(3,Math.floor(Math.max(0,f-25)/48));
 const color=p(f,65,24),bg=p(f,113,24),crop=p(f,161,24);
 return <>
 <Poster x={235} y={278} w={560} h={540} red={color} background={bg} crop={crop}/>
 <Line d="M917 334V809" color={C.line}/>
 {[['01','Original'],['02','Change color'],['03','Change background'],['04','Adjust crop']].map(([n,label],i)=><g key={n} opacity={p(f,i*48,18)}><circle cx={917} cy={348+i*135} r={i===state?11:5} fill={C.ink}/><T x={968} y={358+i*135} size={27} fill={C.muted}>{n}</T><T x={1050} y={365+i*135} size={i===state?46:40} weight={i===state?660:450}>{label}</T></g>)}
 <g opacity={p(f,183,20)}><T x={235} y={899} size={35}>Same object. Selected changes. Earlier decisions retained.</T></g>
 </>;
};
const Sketch=({f}:{f:number})=>{
 const structure=p(f,10,35),brief=p(f,55,25),out=p(f,115,40),details=p(f,171,28);
 return <>
 <g opacity={structure}><T x={130} y={308} size={31}>01 / Rough structure</T><rect x={130} y={349} width={440} height={390} fill="none" stroke={C.line} strokeWidth={3}/><path d="M165 391h112v158H165ZM221 391v158M165 470h112M130 681h440M303 589h84v35h-84ZM356 589v-89h31v89M314 624v56M376 624v56" fill="none" stroke={C.ink} strokeWidth={4}/></g>
 <Line d="M598 535H688" progress={p(f,43,20)}/>
 <g opacity={brief}><T x={723} y={447} size={31}>02 / Layout brief</T><T x={723} y={510} size={44} weight={650}>Window left</T><T x={723} y={565} size={34}>Chair beside</T><T x={723} y={613} size={34}>Clear wall</T></g>
 <Line d="M1120 535H1200" progress={p(f,98,20)}/>
 <g opacity={out}><T x={1240} y={308} size={31}>03 / Visual direction</T><rect x={1240} y={349} width={540} height={390} fill={C.soft}/><rect x={1240} y={681} width={540} height={58} fill={C.line}/><rect x={1275} y={391} width={130} height={158} fill={C.paper} stroke={C.ink} strokeWidth={4}/><path d="M1340 391v158M1275 470h130M1263 556h154" fill="none" stroke={C.ink} strokeWidth={4}/><g opacity={details}><path d="M1430 589h95v35h-95ZM1491 589v-89h34v89" fill={C.ink}/><path d="M1442 624v57M1514 624v57" stroke={C.ink} strokeWidth={8}/><path d="M1420 685h120" stroke={C.muted} strokeWidth={3}/></g></g>
 <g opacity={p(f,185,18)}><T x={130} y={864} size={38}>Window left. Chair beside it. Space for the headline.</T></g>
 </>;
};
const Tradeoff=({f}:{f:number})=><>
 <g opacity={p(f,0,24)}><T x={122} y={317} size={30} fill={C.muted}>Choose by the job, not a universal winner.</T><circle cx={355} cy={542} r={127} fill="none" stroke={C.ink} strokeWidth={4}/><path d="M355 440V542L416 504M313 390h84" stroke={C.ink} strokeWidth={5} fill="none"/><T x={554} y={497} size={65} weight={650}>Flare</T><T x={554} y={558} size={38}>Everyday work</T><T x={554} y={610} size={31} fill={C.muted}>Prioritize speed</T></g>
 <Line d="M941 376V784" color={C.line} progress={p(f,45,30)}/>
 <g opacity={p(f,75,32)}><path d="M1070 466h170v170h-170zM1091 487h128v128h-128zM1070 551h170M1155 466v170" fill="none" stroke={C.ink} strokeWidth={3}/><circle cx={1155} cy={551} r={48} fill="none" stroke={C.ink} strokeWidth={4}/><T x={1290} y={497} size={65} weight={650}>Sunburst</T><T x={1290} y={558} size={38}>Detailed work</T><T x={1290} y={610} size={31} fill={C.muted}>Prioritize precision</T></g>
 <g opacity={p(f,155,40)}><T x={1042} y={853} size={39} anchor="middle">Precision can mean a longer wait.</T></g>
 </>;
const Check=({f}:{f:number})=>{
 const region=f<82?0:f<145?1:2;
 return <>
 <Poster x={180} y={280} w={610} h={540} red={1}/>
 <g opacity={p(f,48,25)}><circle cx={1235} cy={530} r={191} fill={C.paper} stroke={C.ink} strokeWidth={5}/><path d="M1370 665l112 112" stroke={C.ink} strokeWidth={25}/>{region===0?<><T x={1235} y={514} size={37} anchor="middle" weight={650}>FORM / STUDY</T><T x={1235} y={568} size={28} anchor="middle">Did the layout shift?</T></>:region===1?<><T x={1235} y={510} size={38} anchor="middle" weight={650}>CERAMIC</T><T x={1235} y={568} size={31} anchor="middle">Is spelling intact?</T></>:<><Line d="M1210 422Q1150 482 1200 574" progress={p(f,145,53)} width={12}/><T x={1235} y={630} size={28} anchor="middle">Edges + small details</T></>}</g>
 <T x={1010} y={871} size={40} weight={620}>{region===0?'Inspect unchanged regions.':region===1?'Read the lettering.':'Check details at full size.'}</T>
 </>;
};
const titles:Record<Kind,string>={latency:'Less waiting — according to OpenAI',edit:'The edit has a boundary',continuity:'Every edit inherits the last',sketch:'From a rough idea to a direction',tradeoff:'Speed or precision?',check:'Check what was not supposed to change'};
const credits:Record<Kind,string>={latency:'OpenAI • launch claim • up to 50% lower latency',edit:'Illustration • Friday → Saturday; not product output',continuity:'Illustration • multi-turn continuity concept; not product output',sketch:'Original workflow illustration • not model-generated output',tradeoff:'OpenAI launch positioning • qualitative; no scores or timing measurements',check:'Suggested viewer check • original illustration; not a reported test'};
const Graphic:React.FC<Props>=({kind})=>{const f=useCurrentFrame();return <AbsoluteFill style={{background:C.paper,fontFamily:'Inter Variable, Arial',color:C.ink}}>
 <div style={{position:'absolute',left:108,top:107,fontSize:kind==='check'?65:72,fontWeight:650,letterSpacing:-2.5,maxWidth:1570,lineHeight:1.08}}>{titles[kind]}</div>
 <Img src={staticFile('brands/openai.svg')} style={{position:'absolute',right:110,top:106,width:68,height:69,objectFit:'contain'}}/>
 <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{position:'absolute',inset:0}}>{kind==='latency'?<Latency f={f}/>:kind==='edit'?<Edit f={f}/>:kind==='continuity'?<Continuity f={f}/>:kind==='sketch'?<Sketch f={f}/>:kind==='tradeoff'?<Tradeoff f={f}/>:<Check f={f}/>}</svg>
 <Credit>{credits[kind]}</Credit>
 </AbsoluteFill>};
registerRoot(()=><Composition id="Images25Graphic" component={Graphic} width={1920} height={1080} fps={30} durationInFrames={300} defaultProps={{kind:'latency' as Kind,seconds:10}} calculateMetadata={({props})=>({durationInFrames:Math.round(props.seconds*30)})}/>);
