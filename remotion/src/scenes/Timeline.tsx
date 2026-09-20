import {interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {MagicHourBackdrop, editorialPalette, smooth} from "../design-system";
import type {MotionShotProps} from "../types";

export const Timeline: React.FC<MotionShotProps> = (props) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const labels = props.labels.slice(0, 4);
  const progress = interpolate(frame, [12, durationInFrames - 18], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: smooth});
  return (
    <MagicHourBackdrop variant="step_flow">
      <div style={{position: "absolute", left: 300, right: 300, top: 360}}>
        <div style={{fontSize: 58, color: editorialPalette.muted, letterSpacing: 5, fontWeight: 650}}>WORKFLOW</div>
        <div style={{fontSize: 150, fontWeight: 820, letterSpacing: -7, marginTop: 38}}>{props.title}</div>
      </div>
      <div style={{position: "absolute", left: 330, right: 330, top: 1040, height: 8, background: "#343936"}}>
        <div style={{height: "100%", width: `${progress*100}%`, background: props.accent, borderRadius: 99}} />
      </div>
      <div style={{position: "absolute", left: 300, right: 300, top: 930, display: "grid", gridTemplateColumns: `repeat(${labels.length}, 1fr)`, gap: 36}}>
        {labels.map((label, index) => {
          const threshold = index / Math.max(1, labels.length - 1);
          const on = progress >= threshold - 0.04;
          return (
            <div key={label}>
              <div style={{width: 54, height: 54, borderRadius: 99, background: on ? props.accentSecondary : "#121513", border: `5px solid ${on ? props.accentSecondary : "#59605C"}`, boxShadow: "0 0 0 12px #121513"}} />
              <div style={{fontSize: 56, fontWeight: 780, marginTop: 90, maxWidth: 620, color: on ? editorialPalette.paper : editorialPalette.muted}}>{label}</div>
              <div style={{fontSize: 34, color: editorialPalette.muted, marginTop: 24}}>STEP {index + 1}</div>
            </div>
          );
        })}
      </div>
      <div style={{position: "absolute", left: 300, bottom: 250, fontSize: 52, color: editorialPalette.muted, maxWidth: 1800}}>{props.body}</div>
    </MagicHourBackdrop>
  );
};
