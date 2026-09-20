import {interpolate, useCurrentFrame} from "remotion";
import {GlassPanel, Headline, Kicker, MagicHourBackdrop, smooth} from "../design-system";
import type {MotionShotProps} from "../types";

export const StatReveal: React.FC<MotionShotProps> = (props) => {
  const frame = useCurrentFrame();
  const progress = interpolate(frame, [12, 46], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: smooth});
  const radius = 420;
  const circumference = 2 * Math.PI * radius;
  return (
    <MagicHourBackdrop variant="stat_reveal">
      {props.showEditorialHeading ? <><Kicker accent={props.accent}>{props.kicker}</Kicker><div style={{marginTop: 58}}><Headline size={142}>{props.title}</Headline></div></> : null}
      <GlassPanel style={{position: "absolute", left: 300, right: 300, top: props.showEditorialHeading ? 850 : 510, height: 950, display: "grid", gridTemplateColumns: "1100px 1fr", alignItems: "center", padding: "0 130px"}}>
        <div style={{position: "relative", width: 920, height: 920, display: "flex", alignItems: "center", justifyContent: "center"}}>
          <svg width="920" height="920" viewBox="0 0 920 920" style={{position: "absolute"}}>
            <circle cx="460" cy="460" r={radius} fill="none" stroke="rgba(255,255,255,0.10)" strokeWidth="42" />
            <circle cx="460" cy="460" r={radius} fill="none" stroke={props.accentSecondary} strokeWidth="42" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={circumference * (1 - progress)} transform="rotate(-90 460 460)" style={{filter: `drop-shadow(0 0 28px ${props.accentSecondary})`}} />
          </svg>
          <div style={{fontSize: 190, fontWeight: 900, letterSpacing: -10, scale: interpolate(frame, [8, 38], [0.75, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: smooth, output: "perceptual-scale"})}}>{props.metric || "PROOF"}</div>
        </div>
        <div>
          <div style={{fontSize: 82, lineHeight: 1.08, fontWeight: 820}}>{props.body}</div>
          <div style={{marginTop: 72, width: `${progress * 100}%`, height: 14, borderRadius: 20, background: props.accent}} />
        </div>
      </GlassPanel>
    </MagicHourBackdrop>
  );
};
