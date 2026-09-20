import {interpolate, useCurrentFrame} from "remotion";
import {MagicHourBackdrop, editorialPalette, smooth} from "../design-system";
import type {MotionShotProps} from "../types";

export const PromptAnatomy: React.FC<MotionShotProps> = (props) => {
  const frame = useCurrentFrame();
  const labels = props.labels.slice(0, 4);
  const values = ["empty beach", "slow dolly-in", "warm side light", "calm, quiet frame"];
  return (
    <MagicHourBackdrop variant="comparison">
      <div style={{position: "absolute", left: 300, right: 300, top: 280}}>
        <div style={{fontSize: 54, color: editorialPalette.muted, letterSpacing: 5, fontWeight: 650}}>A USEFUL PROMPT HAS STRUCTURE</div>
        <div style={{fontSize: 142, fontWeight: 820, letterSpacing: -7, marginTop: 36}}>{props.title}</div>
      </div>
      <div style={{position: "absolute", left: 300, right: 300, top: 820, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 34}}>
        {labels.map((label, index) => {
          const enter = interpolate(frame, [10 + index * 14, 28 + index * 14], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: smooth});
          return (
            <div key={label} style={{minHeight: 650, padding: "64px 54px", background: index % 2 ? "#1A1D1B" : "#171A18", borderTop: `8px solid ${index === 2 ? "#A66A4F" : props.accent}`, opacity: enter, transform: `translateY(${(1-enter)*24}px)`}}>
              <div style={{fontSize: 32, letterSpacing: 5, color: editorialPalette.muted}}>0{index + 1}</div>
              <div style={{fontSize: 58, fontWeight: 800, marginTop: 44}}>{label}</div>
              <div style={{fontSize: 47, lineHeight: 1.3, color: "#C8CEC9", marginTop: 72}}>{values[index]}</div>
            </div>
          );
        })}
      </div>
      <div style={{position: "absolute", left: 300, bottom: 250, fontSize: 46, color: editorialPalette.muted}}>{props.body}</div>
    </MagicHourBackdrop>
  );
};
