import {interpolate, spring, useCurrentFrame, useVideoConfig} from "remotion";
import {EditorialMascot, GlassPanel, Headline, Kicker, MagicHourBackdrop, editorialPalette, smooth} from "../design-system";
import type {MotionShotProps} from "../types";

export const StepFlow: React.FC<MotionShotProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <MagicHourBackdrop variant="step_flow">
      {props.showEditorialHeading ? <><Kicker accent={props.accent}>{props.kicker}</Kicker><div style={{marginTop: 58}}><Headline size={150}>{props.title}</Headline></div></> : null}
      <div style={{position: "absolute", left: 220, right: 220, top: props.showEditorialHeading ? 690 : 540, bottom: props.showEditorialHeading ? 280 : 420, display: "flex", alignItems: "center", gap: 70}}>
        {props.labels.slice(0, 3).map((label, index) => {
          const entrance = spring({frame: frame - 10 - index * 10, fps, config: {damping: 200, stiffness: 170}});
          return (
            <div key={`${label}-${index}`} style={{display: "contents"}}>
              <GlassPanel style={{width: 920, minHeight: 600, padding: 72, opacity: entrance, translate: `0px ${90 * (1 - entrance)}px`}}>
                <div style={{position: "absolute", right: 42, top: 30}}><EditorialMascot kind={props.mascots[index % Math.max(1, props.mascots.length)] || "codex"} size={145} delay={14 + index * 8} muted={index !== 0} /></div>
                <div style={{fontSize: 42, fontWeight: 800, color: index === 1 ? props.accentSecondary : props.accent}}>0{index + 1}</div>
                <div style={{fontSize: 82, lineHeight: 1.04, fontWeight: 850, marginTop: 48}}>{label}</div>
                <div style={{fontSize: 48, lineHeight: 1.35, color: editorialPalette.muted, marginTop: 42}}>{index === 2 ? props.body : "Show the evidence before explaining the conclusion."}</div>
              </GlassPanel>
              {index < 2 ? (
                <svg width="160" height="100" viewBox="0 0 160 100" style={{overflow: "visible"}}>
                  <path d="M5 50 H135" stroke={props.accentSecondary} strokeWidth="10" strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - interpolate(frame, [30 + index * 10, 52 + index * 10], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: smooth})} />
                  <path d="M115 20 L150 50 L115 80" fill="none" stroke={props.accentSecondary} strokeWidth="10" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : null}
            </div>
          );
        })}
      </div>
    </MagicHourBackdrop>
  );
};
