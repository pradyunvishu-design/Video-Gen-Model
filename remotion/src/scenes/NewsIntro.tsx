import {interpolate, spring, useCurrentFrame, useVideoConfig} from "remotion";
import {EditorialMascot, MagicHourBackdrop, editorialPalette, smooth} from "../design-system";
import type {MotionShotProps} from "../types";

export const NewsIntro: React.FC<MotionShotProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 20, stiffness: 120, mass: 0.8}});
  const wipe = interpolate(frame, [10, 34], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smooth,
  });
  return (
    <MagicHourBackdrop variant="news_intro">
      <div style={{height: "100%", display: "grid", gridTemplateColumns: "1.42fr .92fr", gap: 110, alignItems: "center"}}>
        <div>
          <div style={{display: "inline-flex", alignItems: "center", gap: 22, opacity: enter, translate: `0px ${(1 - enter) * 36}px`}}>
            <div style={{width: 18, height: 18, borderRadius: 99, background: editorialPalette.yellow}} />
            <div style={{fontSize: 42, fontWeight: 820, letterSpacing: 9, color: editorialPalette.muted}}>THE WEEK IN AI</div>
          </div>
          <div style={{marginTop: 48, fontSize: 265, lineHeight: .83, fontWeight: 940, letterSpacing: -20, opacity: enter}}>
            WEEKLY
          </div>
          <div style={{display: "inline-block", marginTop: 20, padding: "14px 34px 20px", color: editorialPalette.black, background: editorialPalette.yellow, fontSize: 220, lineHeight: .86, fontWeight: 940, letterSpacing: -16, clipPath: `inset(0 ${(1 - wipe) * 100}% 0 0)`}}>
            RECAP
          </div>
          <div style={{marginTop: 60, maxWidth: 2050, color: editorialPalette.muted, fontSize: 48, lineHeight: 1.25, fontWeight: 620, opacity: interpolate(frame, [28, 50], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: smooth})}}>
            {props.body || "The AI and tech news that actually mattered, in under ten minutes."}
          </div>
        </div>
        <div style={{display: "flex", flexDirection: "column", gap: 28}}>
          <div style={{display: "flex", justifyContent: "center", alignItems: "end", minHeight: 330}}>
            {props.mascots.slice(0, 3).map((mascot, index) => (
              <EditorialMascot key={`${mascot}-${index}`} kind={mascot} size={250} delay={10 + index * 5} muted={false} />
            ))}
          </div>
          {props.labels.slice(0, 3).map((label, index) => {
            const card = spring({frame: frame - 18 - index * 6, fps, config: {damping: 21, stiffness: 132}});
            return (
              <div key={`${label}-${index}`} style={{display: "grid", gridTemplateColumns: "92px 1fr", alignItems: "center", minHeight: 150, padding: "24px 32px", borderRadius: 28, border: `2px solid ${index === 0 ? editorialPalette.yellow : "rgba(244,243,238,.13)"}`, background: editorialPalette.card, boxShadow: "0 24px 55px rgba(0,0,0,.32)", opacity: card, translate: `${(1 - card) * 55}px 0px`}}>
                <div style={{fontSize: 36, fontWeight: 900, color: index === 0 ? editorialPalette.yellow : editorialPalette.moss}}>0{index + 1}</div>
                <div style={{fontSize: 39, lineHeight: 1.08, fontWeight: 760}}>{label}</div>
              </div>
            );
          })}
          <div style={{textAlign: "right", color: editorialPalette.muted, fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: 30, letterSpacing: 3}}>
            {props.metric || "UNDER 10 MIN"}
          </div>
        </div>
      </div>
    </MagicHourBackdrop>
  );
};
