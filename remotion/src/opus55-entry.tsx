import React from 'react';
import {AbsoluteFill,Composition,Easing,interpolate,registerRoot,useCurrentFrame} from 'remotion';
import '@fontsource-variable/inter';

type Kind='cost_layers'|'token_price'|'cache_price'|'benchmark_axes'|'verification_loop'|'effort_tradeoff'|'migration'|'decision';
const C={paper:'#F2F0E9',ink:'#17221F',clay:'#B56F55',sage:'#809689',muted:'#68726B',line:'#CCCFC6'};
const p=(f:number,a:number,d=24)=>interpolate(f,[a,a+d],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp',easing:Easing.bezier(.22,.7,.25,1)});
const Text:React.FC<{x:number;y:number;size?:number;children:React.ReactNode;fill?:string;weight?:number;opacity?:number}>=({x,y,size=42,children,fill=C.ink,weight=500,opacity=1})=><text x={x} y={y} fontSize={size} fill={fill} fontWeight={weight} opacity={opacity}>{children}</text>;
const Line:React.FC<{x1:number;y1:number;x2:number;y2:number;amount?:number;color?:string;width?:number}>=({x1,y1,x2,y2,amount=1,color=C.line,width=3})=><line x1={x1} y1={y1} x2={x1+(x2-x1)*amount} y2={y1+(y2-y1)*amount} stroke={color} strokeWidth={width}/>;
const source=(kind:Kind)=>kind==='migration'?'Anthropic · Claude Opus 5.5 migration documentation':kind==='decision'?'Editorial evaluation framework · use your own measured results':'Anthropic · Claude Opus 5.5 launch';
const titles:Record<Kind,string>={cost_layers:'A cheaper token is only half the story.',token_price:'The price of one million tokens.',cache_price:'Repeated context costs less.',benchmark_axes:'How to read this kind of chart.',verification_loop:'The answer is not the finish line.',effort_tradeoff:'Spend effort where it matters.',migration:'Changing a model means checking the workflow.',decision:'Try one real task first.'};

const Scene:React.FC<{kind:Kind}>=({kind})=>{const f=useCurrentFrame();
return <AbsoluteFill style={{background:C.paper,fontFamily:'Inter Variable, Arial',color:C.ink}}><svg viewBox="0 0 1920 1080" width={1920} height={1080}>
<Text x={104} y={143} size={64} weight={620}>{titles[kind]}</Text>
{kind==='cost_layers'&&<>
 <Text x={108} y={350} size={31} fill={C.muted}>Your bill depends on two things</Text>
 <g opacity={p(f,20)}><Text x={108} y={489} size={77}>Token price</Text><Text x={112} y={552} size={29} fill={C.muted}>What each unit costs</Text></g>
 <Text x={687} y={491} size={88} opacity={p(f,82)} fill={C.clay}>×</Text>
 <g opacity={p(f,96)}><Text x={823} y={489} size={77}>Work performed</Text><Text x={827} y={552} size={29} fill={C.muted}>How much the model uses</Text></g>
 <Line x1={108} y1={645} x2={1738} y2={645} amount={p(f,156,35)}/>
 <g opacity={p(f,204)}><Text x={108} y={759} size={59} fill={C.clay}>~40%</Text><Text x={363} y={756} size={38}>lower cost on typical workloads</Text><Text x={363} y={809} size={28} fill={C.muted}>Anthropic's claim · not a guarantee for every task</Text></g>
 </>}
{kind==='token_price'&&<>
 <Text x={108} y={238} size={29} fill={C.muted}>USD per 1M tokens · each pair normalized to its Opus 5 price</Text>
 <rect x={1390} y={216} width={22} height={22} fill={C.line}/><Text x={1425} y={237} size={25} fill={C.muted}>Opus 5</Text><rect x={1580} y={216} width={22} height={22} fill={C.clay}/><Text x={1615} y={237} size={25} fill={C.muted}>Opus 5.5</Text>
 {[{label:'Input',old:5,new:4,y:390},{label:'Output',old:25,new:20,y:675}].map((r,i)=><g key={r.label} opacity={p(f,12+i*95)}>
 <Text x={110} y={r.y} size={45}>{r.label}</Text>
 <rect x={390} y={r.y-65} width={1080*p(f,25+i*95,42)} height={47} fill={C.line}/>
 <rect x={390} y={r.y+6} width={864*p(f,65+i*95,42)} height={62} fill={C.clay}/>
 <Text x={1516} y={r.y-27} size={41} fill={C.muted}>${r.old}</Text><Text x={1300} y={r.y+54} size={50}>${r.new}</Text>
 </g>)}
 <Text x={108} y={885} size={38} opacity={p(f,250)}>20% lower price per token.</Text>
 </>}
{kind==='cache_price'&&<>
 <Text x={111} y={274} size={32} fill={C.muted}>Cache reads · USD per 1M tokens</Text>
 <g opacity={p(f,10)}><Text x={112} y={497} size={134} fill={C.muted}>$0.50</Text><Text x={118} y={562} size={31}>Opus 5</Text></g>
 <Line x1={662} y1={450} x2={944} y2={450} amount={p(f,82,42)} color={C.clay} width={5}/><path d="M915 429L944 450L915 471" fill="none" stroke={C.clay} strokeWidth={5} opacity={p(f,113)}/>
 <g opacity={p(f,140)}><Text x={1052} y={497} size={134} fill={C.clay}>$0.20</Text><Text x={1060} y={562} size={31}>Opus 5.5</Text></g>
 <Text x={112} y={745} size={48} opacity={p(f,210)}>60% lower cache-read price.</Text><Text x={116} y={815} size={30} fill={C.muted} opacity={p(f,269)}>The rest of your request still has its own costs.</Text>
 </>}
{kind==='benchmark_axes'&&<>
 <Text x={108} y={230} size={28} fill={C.muted}>Illustration of the axes · no model scores plotted</Text>
 <Line x1={310} y1={827} x2={1590} y2={827} amount={p(f,15,35)} color={C.ink} width={4}/><Line x1={310} y1={827} x2={310} y2={325} amount={p(f,45,35)} color={C.ink} width={4}/>
 <Text x={1050} y={896} size={36} opacity={p(f,65)}>Cost per task →</Text><Text x={104} y={365} size={30} opacity={p(f,95)}>Higher</Text><Text x={104} y={407} size={30} opacity={p(f,95)}>score ↑</Text>
 <path d="M1300 680Q890 610 541 426" fill="none" stroke={C.clay} strokeWidth={8} pathLength={1} strokeDasharray={1} strokeDashoffset={1-p(f,142,70)}/><path d="M547 460L537 423L578 419" fill="none" stroke={C.clay} strokeWidth={7} opacity={p(f,207)}/>
 <Text x={680} y={390} size={45} opacity={p(f,239)}>Up and left is the goal.</Text><Text x={680} y={448} size={30} fill={C.muted} opacity={p(f,273)}>Better results. Lower cost.</Text>
 </>}
{kind==='verification_loop'&&<>
 <Text x={108} y={257} size={31} fill={C.muted}>An agent can act. The workflow still needs checks.</Text>
 {[{label:'Task',sub:'Define success',x:113},{label:'Tools',sub:'Do the work',x:563},{label:'Checks',sub:'Test the result',x:1000},{label:'Review',sub:'A person decides',x:1436}].map((v,i)=><g key={v.label} opacity={p(f,12+i*63)}>
 <text x={v.x} y={426} fill={i===2?C.clay:C.sage} fontSize={64} fontWeight={500}>0{i+1}</text><Text x={v.x} y={522} size={48}>{v.label}</Text><Text x={v.x} y={582} size={28} fill={C.muted}>{v.sub}</Text>
 {i<3&&<Line x1={v.x+234} y1={484} x2={v.x+382} y2={484} amount={p(f,42+i*63)} color={C.line} width={3}/>}</g>)}
 <path d="M1250 673V755H582V673" fill="none" stroke={C.clay} strokeWidth={4} pathLength={1} strokeDasharray={1} strokeDashoffset={1-p(f,242,42)}/><Text x={693} y={822} size={31} opacity={p(f,283)}>If a check fails, revise.</Text>
 </>}
{kind==='effort_tradeoff'&&<>
 <Text x={111} y={278} size={31} fill={C.muted}>Qualitative decision guide · not a latency benchmark</Text>
 <Line x1={140} y1={501} x2={1710} y2={501} amount={p(f,15,40)} color={C.line} width={8}/>
 <circle cx={550} cy={501} r={18} fill={C.sage}/><circle cx={1400} cy={501} r={18} fill={C.clay} opacity={p(f,120)}/>
 <Text x={360} y={414} size={58} opacity={p(f,25)}>Medium</Text><Text x={375} y={584} size={30} fill={C.muted} opacity={p(f,58)}>Start here</Text>
 <Text x={1270} y={414} size={58} opacity={p(f,142)}>Higher</Text><Text x={1240} y={584} size={30} fill={C.muted} opacity={p(f,168)}>For harder tasks</Text>
 <path d="M580 501H1368" stroke={C.clay} strokeWidth={8} pathLength={1} strokeDasharray={1} strokeDashoffset={1-p(f,190,55)}/>
 <Text x={111} y={781} size={44} opacity={p(f,260)}>Increase effort when the task earns it.</Text>
 </>}
{kind==='migration'&&<>
 <Text x={109} y={265} size={31} fill={C.muted}>Before moving a production workflow</Text>
 {[['01','Thinking behavior','Read the current model guidance.'],['02','Tool calling','Check supported options and tool results.'],['03','Conversation context','Test the switch with a clean task.']].map((v,i)=><g key={v[0]} opacity={p(f,15+i*82)}><Text x={108} y={397+i*168} size={39} fill={C.clay}>{v[0]}</Text><Text x={249} y={397+i*168} size={48}>{v[1]}</Text><Text x={920} y={397+i*168} size={29} fill={C.muted}>{v[2]}</Text>{i<2&&<Line x1={249} y1={449+i*168} x2={1746} y2={449+i*168}/>}</g>)}
 <Text x={249} y={913} size={30} opacity={p(f,288)}>A model-name change is the beginning of the test.</Text>
 </>}
{kind==='decision'&&<>
 <Text x={113} y={343} size={34} fill={C.muted}>Pick a task your team actually repeats.</Text>
 <g opacity={p(f,12)}><path d="M127 423H405L467 485V742H127ZM405 423V485H467" fill="none" stroke={C.ink} strokeWidth={4}/><Text x={164} y={596} size={50}>One task</Text></g>
 <Line x1={510} y1={580} x2={716} y2={580} amount={p(f,65,32)} color={C.clay} width={4}/>
 {['Accuracy','Time','Cost'].map((label,i)=><g key={label} opacity={p(f,102+i*54)}><Text x={800} y={458+i*132} size={48}>{label}</Text><Line x1={1110} y1={449+i*132} x2={1518} y2={449+i*132} color={C.line}/><Text x={1540} y={459+i*132} size={31} fill={C.muted}>Measure</Text></g>)}
 <Text x={795} y={881} size={42} opacity={p(f,280)}>Choose from evidence.</Text>
 </>}
<Text x={105} y={1020} size={23} fill={C.muted}>{source(kind)}</Text></svg></AbsoluteFill>};
registerRoot(()=><Composition id="Opus55Graphic" component={Scene} width={1920} height={1080} fps={30} durationInFrames={360} defaultProps={{kind:'cost_layers' as Kind}}/>);
