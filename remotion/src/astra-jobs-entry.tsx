import React from 'react';
import {AbsoluteFill,Composition,Easing,Img,interpolate,registerRoot,staticFile,useCurrentFrame} from 'remotion';
import '@fontsource-variable/inter';

type Kind='job_tasks'|'finance_flow'|'financial_model'|'finance_benchmark'|'law_research'|'law_benchmark'|'permission_layers'|'work_handoff'|'automation_boundary'|'practical_check';
const C={paper:'#F2F1ED',ink:'#202624',muted:'#666D6A',line:'#B7BFBA',soft:'#E0E5E1',blue:'#577A91',moss:'#647B6A'};
const p=(f:number,s:number,d=24)=>interpolate(f,[s,s+d],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp',easing:Easing.bezier(.22,.7,.25,1)});
const T=({x,y,size=38,children,fill=C.ink,weight=500,anchor='start'}:{x:number;y:number;size?:number;children:React.ReactNode;fill?:string;weight?:number;anchor?:'start'|'middle'|'end'})=><text x={x} y={y} fontSize={size} fill={fill} fontWeight={weight} textAnchor={anchor}>{children}</text>;
const Reveal=({f,at,children}:{f:number;at:number;children:React.ReactNode})=><g opacity={p(f,at)} transform={`translate(0 ${12*(1-p(f,at))})`}>{children}</g>;
const Route=({d,f,at,color=C.line}:{d:string;f:number;at:number;color?:string})=><path d={d} stroke={color} strokeWidth={4} fill="none" pathLength={1} strokeDasharray={1} strokeDashoffset={1-p(f,at,32)}/>;
const Doc=({x,y,w=280,h=330,children}:{x:number;y:number;w?:number;h?:number;children?:React.ReactNode})=><g transform={`translate(${x} ${y})`}><path d={`M0 0H${w-48}L${w} 48V${h}H0Z`} fill={C.paper} stroke={C.ink} strokeWidth={3}/><path d={`M${w-48} 0V48H${w}`} fill="none" stroke={C.ink} strokeWidth={3}/>{children}</g>;
const Check=({x,y,f,at,size=34}:{x:number;y:number;f:number;at:number;size?:number})=><g transform={`translate(${x} ${y})`}><rect width={size} height={size} fill="none" stroke={C.line} strokeWidth={2}/><path d={`M${size*.2} ${size*.52}l${size*.23} ${size*.24}L${size*.83} ${size*.2}`} stroke={C.moss} strokeWidth={4} fill="none" pathLength={1} strokeDasharray={1} strokeDashoffset={1-p(f,at,18)}/></g>;
const titles:Record<Kind,string>={job_tasks:'A job is a bundle of tasks',finance_flow:'From financial data to a reviewed answer',financial_model:'The assumption changes the answer',finance_benchmark:'A task benchmark — not a hiring forecast',law_research:'An answer still needs legal judgment',law_benchmark:'Context changes the result',permission_layers:'Access is not a blank check',work_handoff:'The handoff matters',automation_boundary:'Time saved is not the same as jobs lost',practical_check:'Four checks before you trust the output'};
const credits:Record<Kind,string>={job_tasks:'Editorial illustration · task structure, not measured proportions',finance_flow:'OpenAI · ChatGPT for Financial Services · workflow illustration',financial_model:'Hypothetical example · index values, not financial advice or a real company',finance_benchmark:'OpenAI · OfficeQA Pro · reported benchmark, not our independent test',law_research:'OpenAI · Astra for Law · editorial workflow illustration',law_benchmark:'OpenAI · highest reasoning setting · reported legal benchmark',permission_layers:'OpenAI · Astra for Law · permissions concept, not product UI',work_handoff:'Editorial illustration · human review and accountability',automation_boundary:'Editorial distinction · no employment projection shown',practical_check:'Editorial review checklist · not an observed product screen'};

const Tasks=({f}:{f:number})=><>
 <T x={130} y={312} size={31} fill={C.muted}>One role. Different kinds of work.</T>
 <Doc x={170} y={367} w={430} h={427}><T x={40} y={76} size={37} weight={650}>Analyst / lawyer</T>{['Research','Draft','Check','Decide'].map((v,i)=><Reveal f={f} at={15+i*35} key={v}><T x={40} y={155+i*70} size={40}>{v}</T><circle cx={357} cy={142+i*70} r={8} fill={i<2?C.blue:C.moss}/></Reveal>)}</Doc>
 <Route d="M639 488H808V402H924" f={f} at={142} color={C.blue}/><Reveal f={f} at={158}><T x={970} y={405} size={49} weight={650}>Speed up the first draft</T><T x={970} y={463} size={33} fill={C.muted}>Gather, organize, summarize</T></Reveal>
 <Route d="M639 691H808V727H924" f={f} at={196} color={C.moss}/><Reveal f={f} at={217}><T x={970} y={731} size={49} weight={650}>Keep someone accountable</T><T x={970} y={789} size={33} fill={C.muted}>Verify, approve, take responsibility</T></Reveal>
</>;
const Finance=({f}:{f:number})=><>
 <Reveal f={f} at={0}><g transform="translate(140 390)"><ellipse cx={135} cy={32} rx={130} ry={31} fill={C.soft} stroke={C.ink} strokeWidth={3}/><path d="M5 32v235c0 42 260 42 260 0V32M5 147c0 42 260 42 260 0" fill="none" stroke={C.ink} strokeWidth={3}/></g><T x={275} y={774} size={37} anchor="middle" weight={600}>Connected data</T><T x={275} y={824} size={29} anchor="middle" fill={C.muted}>Licensed sources + firm files</T></Reveal>
 <Route d="M449 560H672" f={f} at={44}/><Reveal f={f} at={73}><Doc x={717} y={350} w={445} h={379}><T x={34} y={85} size={33} weight={650}>Research workbook</T>{[0,1,2].map(i=><g key={i}><rect x={35} y={122+i*67} width={365} height={45} fill={i===1?C.soft:'none'}/><T x={48} y={155+i*67} size={26}>{['Claim','Input','Calculation'][i]}</T><T x={291} y={155+i*67} size={26} fill={C.blue}>[{i+1}]</T></g>)}</Doc><T x={940} y={805} size={33} anchor="middle">Citations travel with the answer</T></Reveal>
 <Route d="M1200 560H1394" f={f} at={153}/><Reveal f={f} at={181}><circle cx={1566} cy={525} r={104} stroke={C.moss} strokeWidth={4} fill="none"/><Check x={1537} y={495} f={f} at={205} size={58}/><T x={1566} y={717} size={40} anchor="middle" weight={650}>Analyst approval</T><T x={1566} y={772} size={29} anchor="middle" fill={C.muted}>Check before client use</T></Reveal>
</>;
const Model=({f}:{f:number})=>{const changed=f>=126;return <>
 <T x={133} y={310} size={30} fill={C.muted}>Simplified hypothetical model · revenue 100 · other costs 60</T>
 <T x={133} y={456} size={38}>Fuel-cost assumption</T><T x={133} y={580} size={98} weight={650} fill={C.blue}>{changed?'30':'20'}</T><T x={133} y={655} size={31} fill={C.muted}>Illustrative units — not a forecast</T>
 <Route d="M572 545H776" f={f} at={49}/><Reveal f={f} at={71}><T x={820} y={431} size={33} fill={C.muted}>Profit after these costs</T><T x={820} y={580} size={124} weight={650}>{changed?'10':'20'}</T><T x={820} y={649} size={38}>100 − {changed?'30':'20'} − 60</T></Reveal>
 <Reveal f={f} at={173}><Doc x={1410} y={375} w={320} h={340}><T x={30} y={96} size={32} weight={650}>Before approval</T><T x={30} y={165} size={28}>Check the formula</T><T x={30} y={222} size={28}>Test the assumption</T><T x={30} y={279} size={28}>Trace the source</T></Doc></Reveal>
 <Reveal f={f} at={233}><T x={133} y={863} size={43} weight={600}>A polished spreadsheet can still start from the wrong premise.</T></Reveal>
</>};
const Chart=({f,law=false}:{f:number;law?:boolean})=>{const values=law?[38.7,54]:[60.2,69.9];const names=law?['Astra · web only','Astra for Law']:['Sol','Astra'];return <>
 <T x={135} y={305} size={32} fill={C.muted}>{law?'Legal benchmark · highest reasoning setting':'OfficeQA Pro · score as reported by OpenAI'}</T>
 {values.map((v,i)=><g key={i}><T x={135} y={423+i*158} size={law?37:42} weight={570}>{names[i]}</T><rect x={575} y={369+i*158} width={v*10.7*p(f,20+i*63,46)} height={83} fill={i?C.blue:C.line}/><Reveal f={f} at={63+i*63}><T x={575+v*10.7+24} y={432+i*158} size={58} weight={660}>{v.toFixed(1)}</T></Reveal></g>)}
 <path d="M575 672H1645" stroke={C.line} strokeWidth={2}/>{[0,25,50,75,100].map(v=><g key={v}><path d={`M${575+v*10.7} 661v22`} stroke={C.line} strokeWidth={2}/><T x={575+v*10.7} y={723} size={27} anchor="middle" fill={C.muted}>{v}</T></g>)}
 <Reveal f={f} at={174}><T x={575} y={817} size={47} weight={650}>{law?'+15.3 percentage points':'Not “69.9% of an analyst’s job.”'}</T><T x={575} y={874} size={31} fill={C.muted}>{law?'About 40% relative improvement — not cases won.':'A measured task score does not measure job replacement.'}</T></Reveal>
</>};
const Law=({f}:{f:number})=><>
 <Doc x={140} y={354} w={391} h={432}><T x={35} y={92} size={40} weight={650}>Case facts</T>{['People','Events','Documents'].map((s,i)=><Reveal key={s} f={f} at={12+i*25}><T x={35} y={180+i*80} size={34}>{s}</T></Reveal>)}</Doc>
 <Route d="M574 559H696" f={f} at={67}/><Reveal f={f} at={90}><T x={740} y={401} size={43} weight={650}>Relevant authority</T><T x={740} y={478} size={33}>What does the source say?</T><Check x={740} y={556} f={f} at={147}/><T x={799} y={585} size={36}>Right jurisdiction?</T><Check x={740} y={652} f={f} at={181}/><T x={799} y={681} size={36}>Still current?</T></Reveal>
 <Route d="M1231 559H1371" f={f} at={205}/><Reveal f={f} at={228}><circle cx={1557} cy={506} r={95} fill={C.soft}/><path d="M1507 491h100m-50-39v129m-81 0h162M1487 491l-30 67h60zM1627 491l-30 67h60z" fill="none" stroke={C.ink} strokeWidth={4}/><T x={1557} y={698} size={46} anchor="middle" weight={650}>Lawyer</T><T x={1557} y={756} size={31} anchor="middle">Judgment + responsibility</T></Reveal>
</>;
const Permissions=({f}:{f:number})=><>
 <T x={135} y={326} size={34} fill={C.muted}>Three different questions — three different boundaries.</T>
 {[['Approved data','What may the system read?'],['Matter / team scope','Whose work may it access?'],['Action approval','What may happen next?']].map(([a,b],i)=><Reveal f={f} at={i*78} key={a}><path d={`M${140+i*120} ${395+i*158}H${1735-i*85}V${506+i*158}H${140+i*120}Z`} fill={i===2?C.soft:'none'} stroke={i===2?C.moss:C.line} strokeWidth={3}/><T x={181+i*120} y={467+i*158} size={43} weight={610}>{a}</T><T x={795+i*44} y={466+i*158} size={32}>{b}</T></Reveal>)}
 <Reveal f={f} at={249}><T x={380} y={947} size={32} fill={C.muted}>Permission to retrieve information is not permission to act on it.</T></Reveal>
</>;
const Handoff=({f}:{f:number})=><>
 <Doc x={140} y={334} w={492} h={500}><T x={36} y={89} size={39} weight={650}>Working draft</T><T x={36} y={174} size={31}>Findings</T><T x={36} y={245} size={31}>Sources</T><T x={36} y={316} size={31}>Assumptions</T><Reveal f={f} at={37}><T x={36} y={422} size={30} fill={C.blue}>Ready for review — not final</T></Reveal></Doc>
 <Route d="M674 550H800" f={f} at={76}/><Reveal f={f} at={99}><Check x={854} y={421} f={f} at={123} size={40}/><T x={918} y={456} size={40}>Check the source</T><Check x={854} y={546} f={f} at={160} size={40}/><T x={918} y={580} size={40}>Check the reasoning</T><Check x={854} y={671} f={f} at={197} size={40}/><T x={918} y={706} size={40}>Resolve the uncertainty</T></Reveal>
 <Reveal f={f} at={236}><T x={854} y={845} size={53} weight={650} fill={C.moss}>Then a person decides.</T></Reveal>
</>;
const Boundary=({f}:{f:number})=><>
 <Reveal f={f} at={0}><circle cx={346} cy={506} r={138} fill="none" stroke={C.ink} strokeWidth={5}/><path d="M346 407V506L413 466" stroke={C.ink} strokeWidth={7} fill="none"/><T x={346} y={734} size={50} weight={650} anchor="middle">Time saved</T></Reveal>
 <Reveal f={f} at={64}><T x={827} y={590} size={161} weight={450} anchor="middle">≠</T></Reveal>
 <Reveal f={f} at={116}><g transform="translate(1371 465)" fill="none" stroke={C.ink} strokeWidth={5}><circle cx={0} cy={-65} r={51}/><path d="M-110 168V83c0-99 220-99 220 0v85"/></g><T x={1371} y={734} size={50} weight={650} anchor="middle">Jobs lost</T></Reveal>
 <Reveal f={f} at={204}><T x={133} y={876} size={36}>Hiring also depends on demand, costs, trust and how work is reorganized.</T></Reveal>
</>;
const Practical=({f}:{f:number})=><>
 <Doc x={190} y={280} w={1170} h={646}><T x={51} y={84} size={43} weight={650}>Review record</T>{[['Source','Can you open the original?'],['Date','Is it current?'],['Assumptions','What did the model assume?'],['Reviewer','Who signs off?']].map(([a,b],i)=><g key={a}><Check x={52} y={148+i*113} f={f} at={33+i*56} size={39}/><Reveal f={f} at={12+i*56}><T x={120} y={181+i*113} size={38} weight={650}>{a}</T><T x={440} y={181+i*113} size={34}>{b}</T></Reveal></g>)}</Doc>
 <Reveal f={f} at={241}><T x={1446} y={559} size={42} weight={650}>Useful output.</T><T x={1446} y={622} size={42} weight={650}>Clear owner.</T></Reveal>
</>;
const Graphic=({kind}:{kind:Kind;seconds:number})=>{const f=useCurrentFrame();return <AbsoluteFill style={{background:C.paper,fontFamily:'Inter Variable, Arial',color:C.ink}}>
 <div style={{position:'absolute',left:108,top:105,fontSize:kind==='finance_benchmark'||kind==='automation_boundary'?65:71,fontWeight:650,letterSpacing:-2.4,maxWidth:1570,lineHeight:1.1}}>{titles[kind]}</div>
 <Img src={staticFile('brands/openai.svg')} style={{position:'absolute',right:108,top:105,width:68,height:69,objectFit:'contain'}}/>
 <svg width={1920} height={1080} style={{position:'absolute',inset:0}}>{kind==='job_tasks'?<Tasks f={f}/>:kind==='finance_flow'?<Finance f={f}/>:kind==='financial_model'?<Model f={f}/>:kind==='finance_benchmark'?<Chart f={f}/>:kind==='law_research'?<Law f={f}/>:kind==='law_benchmark'?<Chart f={f} law/>:kind==='permission_layers'?<Permissions f={f}/>:kind==='work_handoff'?<Handoff f={f}/>:kind==='automation_boundary'?<Boundary f={f}/>:<Practical f={f}/>}</svg>
 <div style={{position:'absolute',left:108,bottom:44,fontSize:23,color:C.muted}}>{credits[kind]}</div>
 </AbsoluteFill>};
registerRoot(()=><Composition id="AstraJobsGraphic" component={Graphic} width={1920} height={1080} fps={30} durationInFrames={360} defaultProps={{kind:'job_tasks' as Kind,seconds:12}} calculateMetadata={({props})=>({durationInFrames:Math.round(props.seconds*30)})}/>);
