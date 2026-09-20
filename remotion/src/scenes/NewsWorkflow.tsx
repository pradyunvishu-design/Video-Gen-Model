import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {editorialPalette, smooth} from "../design-system";
import type {MotionShotProps} from "../types";

const positions = [
  {x: 150, y: 500},
  {x: 585, y: 620},
  {x: 1035, y: 470},
  {x: 1490, y: 590},
];

const WorkflowIcon: React.FC<{index: number; active: boolean}> = ({index, active}) => {
  const ink = active ? editorialPalette.paper : editorialPalette.black;
  const accent = [editorialPalette.moss, editorialPalette.blue, editorialPalette.clay, editorialPalette.moss][index];
  return (
    <div style={{
      width: 142,
      height: 142,
      borderRadius: index === 1 ? 999 : 26,
      background: active ? accent : "transparent",
      border: `4px solid ${active ? accent : "#777B77"}`,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      boxShadow: active ? "0 18px 42px rgba(11,12,12,.16)" : "none",
    }}>
      <svg width="82" height="82" viewBox="0 0 82 82" fill="none" aria-hidden="true">
        {index === 0 ? <>
          <rect x="13" y="13" width="23" height="23" rx="3" fill={ink}/>
          <rect x="46" y="13" width="23" height="23" rx="3" fill={ink} opacity=".55"/>
          <rect x="13" y="46" width="23" height="23" rx="3" fill={ink} opacity=".55"/>
          <rect x="46" y="46" width="23" height="23" rx="3" fill={ink}/>
        </> : null}
        {index === 1 ? <>
          <path d="M8 42C17 25 28 17 41 17s24 8 33 25c-9 16-20 24-33 24S17 58 8 42Z" stroke={ink} strokeWidth="6"/>
          <circle cx="41" cy="42" r="11" fill={ink}/>
        </> : null}
        {index === 2 ? <>
          <path d="M18 61 23 44 54 13l15 15-31 31-20 2Z" stroke={ink} strokeWidth="6" strokeLinejoin="round"/>
          <path d="m49 18 15 15" stroke={ink} strokeWidth="6"/>
          <path d="M13 69h56" stroke={ink} strokeWidth="6" strokeLinecap="round"/>
        </> : null}
        {index === 3 ? <>
          <path d="M12 31V12h19M51 12h19v19M70 51v19H51M31 70H12V51" stroke={ink} strokeWidth="7" strokeLinecap="round"/>
          <path d="M27 41h28" stroke={ink} strokeWidth="7" strokeLinecap="round"/>
        </> : null}
      </svg>
    </div>
  );
};

export const NewsWorkflow: React.FC<MotionShotProps> = (props) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const labels = props.labels.slice(0, 4);
  const route = interpolate(frame, [14, Math.max(58, durationInFrames - 34)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smooth,
  });
  return (
    <AbsoluteFill style={{overflow: "hidden", background: editorialPalette.paper, color: editorialPalette.black, fontFamily: "Inter Variable, Inter, Arial, sans-serif"}}>
      <div style={{position: "absolute", left: 110, top: 92, fontSize: 25, fontWeight: 760, letterSpacing: 5, color: editorialPalette.clay}}>PRACTICAL WORKFLOW</div>
      <div style={{position: "absolute", left: 110, top: 142, width: 940, fontSize: 100, lineHeight: .94, fontWeight: 820, letterSpacing: -5, whiteSpace: "pre-line"}}>{props.title}</div>
      <div style={{position: "absolute", right: 120, top: 132, width: 560, fontSize: 36, lineHeight: 1.28, color: "#555955"}}>{props.body}</div>

      <svg width="1920" height="1080" viewBox="0 0 1920 1080" style={{position: "absolute", inset: 0}}>
        <path d="M220 570 C380 570 430 690 655 690 S850 540 1105 540 S1320 660 1560 660" fill="none" stroke="#C8CEC9" strokeWidth="5"/>
        <path d="M220 570 C380 570 430 690 655 690 S850 540 1105 540 S1320 660 1560 660" fill="none" stroke={editorialPalette.moss} strokeWidth="7" pathLength={1} strokeDasharray={1} strokeDashoffset={1-route}/>
      </svg>

      {labels.map((label, index) => {
        const threshold = index / Math.max(1, labels.length - 1);
        const active = route >= threshold - .035;
        const enter = interpolate(frame, [12 + index * 10, 28 + index * 10], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: smooth});
        const pos = positions[index];
        return <div key={label} style={{position: "absolute", left: pos.x, top: pos.y, width: 310, opacity: enter, transform: `translateY(${(1-enter)*14}px)`}}>
          <WorkflowIcon index={index} active={active}/>
          <div style={{marginTop: 24, fontSize: 22, fontWeight: 760, letterSpacing: 3, color: active ? editorialPalette.clay : "#777B77"}}>0{index + 1}</div>
          <div style={{marginTop: 9, fontSize: 42, lineHeight: 1.02, fontWeight: 790, letterSpacing: -1.5, maxWidth: 285}}>{label}</div>
        </div>;
      })}

      <div style={{position: "absolute", left: 110, right: 110, bottom: 76, height: 2, background: "#CFD2CE"}}/>
      <div style={{position: "absolute", left: 110, bottom: 34, fontSize: 20, fontWeight: 650, letterSpacing: 2.4, color: "#6D716D"}}>DRAFT → VERIFY → EDIT → FINISH</div>
    </AbsoluteFill>
  );
};
