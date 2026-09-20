import {interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {MagicHourBackdrop, editorialPalette, smooth} from "../design-system";
import type {MotionShotProps} from "../types";

const glyphs = ["01", "02", "03", "04", "05"];

export const ListReveal: React.FC<MotionShotProps> = (props) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const labels = props.labels.slice(0, 5);
  const active = Math.min(labels.length - 1, Math.floor((frame / Math.max(1, durationInFrames - 1)) * labels.length));
  return (
    <MagicHourBackdrop variant="step_flow">
      <div style={{position: "absolute", inset: "260px 300px", display: "grid", gridTemplateColumns: "0.8fr 1.2fr", gap: 170, alignItems: "center"}}>
        <div>
          <div style={{fontSize: 48, color: editorialPalette.muted, letterSpacing: 5, fontWeight: 650}}>THE CHECKLIST</div>
          <div style={{fontSize: 180, lineHeight: 0.92, fontWeight: 820, letterSpacing: -8, marginTop: 42}}>{props.title}</div>
          <div style={{fontSize: 52, lineHeight: 1.35, color: editorialPalette.muted, marginTop: 56, maxWidth: 1050}}>{props.body}</div>
        </div>
        <div style={{display: "grid", gap: 28}}>
          {labels.map((label, index) => {
            const start = 10 + index * 10;
            const enter = interpolate(frame, [start, start + 18], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: smooth});
            const selected = index === active;
            return (
              <div key={label} style={{height: 150, borderBottom: `2px solid ${selected ? props.accent : "rgba(240,242,240,.14)"}`, display: "grid", gridTemplateColumns: "120px 1fr 48px", alignItems: "center", opacity: enter, transform: `translateY(${(1-enter)*18}px)`}}>
                <div style={{fontSize: 34, letterSpacing: 4, color: selected ? props.accent : editorialPalette.muted}}>{glyphs[index]}</div>
                <div style={{fontSize: 68, fontWeight: 760, color: selected ? editorialPalette.paper : "#C8CEC9"}}>{label}</div>
                <div style={{width: 24, height: 24, borderRadius: 99, background: selected ? props.accentSecondary : "transparent", border: `2px solid ${selected ? props.accentSecondary : "#4A4F4B"}`}} />
              </div>
            );
          })}
        </div>
      </div>
    </MagicHourBackdrop>
  );
};
