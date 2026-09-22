import React from 'react';
import {AbsoluteFill,Composition,Easing,Img,interpolate,registerRoot,staticFile,useCurrentFrame} from 'remotion';
import '@fontsource-variable/inter';

type Props={seconds:number;editStart:number;questionStart:number};
const C={paper:'#F2F0E9',ink:'#17221F',sage:'#9CAD9D',muted:'#68726B'};
const ease=(f:number,a:number,b:number)=>interpolate(f,[a,b],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp',easing:Easing.bezier(.22,.7,.25,1)});
const pic=(name:string)=>staticFile('qwen21/'+name);
const Hook:React.FC<Props>=({editStart,questionStart})=>{
 const f=useCurrentFrame(),t=f/30;
 const stage=t<editStart?0:t<questionStart?1:2;
 const local=f-(stage===1?Math.round(editStart*30):stage===2?Math.round(questionStart*30):0);
 return <AbsoluteFill style={{background:C.paper,fontFamily:'Inter Variable, Arial',color:C.ink}}>
  {stage===0&&<>
   <div style={{position:'absolute',left:778,top:72,width:1038,height:882,background:C.ink,overflow:'hidden'}}>
    <div style={{position:'absolute',inset:0,background:'#fff',clipPath:`inset(0 ${ease(f,36,88)*100}% 0 0)`}}/>
    <Img src={pic('example-04.png')} style={{position:'absolute',left:90,top:28,width:858,height:820,objectFit:'contain'}}/>
   </div>
   <div style={{position:'absolute',left:106,top:190,width:610,fontSize:84,lineHeight:1.1,fontWeight:650,letterSpacing:-3}}>
    {t<2.95?<>Not a white<br/>background.</>:<>A transparent<br/>image.</>}
   </div>
   <Img src={pic('logo.png')} style={{position:'absolute',left:106,top:502,width:596,height:165,objectFit:'contain',opacity:ease(f,90,108)}}/>
   <div style={{position:'absolute',left:106,top:729,fontSize:36,lineHeight:1.4,opacity:ease(f,183,200)}}>Generate the subject.<br/>Keep the transparency.</div>
  </>}
  {stage===1&&<>
   <div style={{position:'absolute',left:106,top:128,fontSize:81,fontWeight:620,letterSpacing:-2}}>Choose what changes.</div>
   <div style={{position:'absolute',left:107,top:408,width:1706,height:112,overflow:'hidden',background:'white'}}>
    <Img src={pic('repo_local_masks.png')} style={{position:'absolute',width:2729,height:1535,left:-213,top:-320}}/>
    {/* Exact stored DOM range for 'circles', transformed with this source crop. */}
    <svg width={1706} height={112} style={{position:'absolute'}}><path d="M1163 51H1249" stroke="#B04438" strokeWidth={4} fill="none" pathLength={1} strokeDasharray={1} strokeDashoffset={1-ease(local,52,70)}/></svg>
   </div>
   <div style={{position:'absolute',left:112,top:673,fontSize:44,color:C.muted,opacity:ease(local,73,88)}}>Local edits, not a fresh start.</div>
  </>}
  {stage===2&&<>
   <div style={{position:'absolute',left:104,top:105,fontSize:87,fontWeight:650,lineHeight:1.05,letterSpacing:-3,width:940}}>Can you skip<br/>the cleanup?</div>
   <svg width={1920} height={1080} style={{position:'absolute'}}><path d="M1220 181h339l166 166v393h-505zM1559 181v166h166" stroke={C.sage} strokeWidth={5} fill="none"/><text x={1465} y={593} textAnchor="middle" fontSize={186} fontWeight={400} fill={C.ink}>?</text></svg>
   {['What the examples show','What still needs checking','The license limit'].map((label,i)=><div key={label} style={{position:'absolute',left:112,top:481+i*114,opacity:ease(local,60+i*54,75+i*54),fontSize:43,fontWeight:500}}><span style={{color:C.muted,marginRight:28,fontSize:28}}>0{i+1}</span>{label}</div>)}
  </>}
  <div style={{position:'absolute',bottom:34,left:106,fontSize:24,color:C.muted}}>{stage===0?'Source: Qwen · official transparent PNG; backgrounds added for inspection':stage===1?'Source: Qwen repository · exact source excerpt':'Source: Qwen repository and research license'}</div>
 </AbsoluteFill>;
};
registerRoot(()=><Composition id="QwenHook" component={Hook} width={1920} height={1080} fps={30} durationInFrames={900} defaultProps={{seconds:30,editStart:10,questionStart:19}} calculateMetadata={({props})=>({durationInFrames:Math.round(props.seconds*30)})}/>);
