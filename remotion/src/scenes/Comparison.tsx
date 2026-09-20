import {interpolate, useCurrentFrame} from "remotion";
import {GlassPanel, Headline, Kicker, MagicHourBackdrop, smooth} from "../design-system";
import type {MotionShotProps} from "../types";

export const Comparison: React.FC<MotionShotProps> = (props) => {
  const frame = useCurrentFrame();
  const parts = props.body.split(/\b(?:versus|vs\.?|but|while)\b/i);
  const bodies = parts.length >= 2 ? parts.slice(0, 2) : ["What the claim suggests", "What the evidence actually supports"];
  return (
    <MagicHourBackdrop variant="comparison">
      {props.showEditorialHeading ? <><Kicker accent={props.accentSecondary}>{props.kicker}</Kicker><div style={{marginTop: 54}}><Headline size={142}>{props.title}</Headline></div></> : null}
      <div style={{position: "absolute", left: 220, right: 220, top: props.showEditorialHeading ? 660 : 390, bottom: 210, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 100}}>
        {bodies.map((body, index) => (
          <GlassPanel
            key={`${body}-${index}`}
            style={{
              minHeight: 850,
              padding: 90,
              opacity: interpolate(frame, [10 + index * 10, 30 + index * 10], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: smooth}),
              translate: interpolate(frame, [8 + index * 10, 34 + index * 10], [index === 0 ? "-120px 0px" : "120px 0px", "0px 0px"], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: smooth}),
            }}
          >
            <div style={{fontSize: 44, fontWeight: 820, letterSpacing: 6, color: index === 0 ? props.accentSecondary : props.accent}}>{props.labels[index] || (index === 0 ? "CLAIM" : "EVIDENCE")}</div>
            <div style={{height: 10, width: interpolate(frame, [30 + index * 8, 55 + index * 8], [0, 520], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: smooth}), borderRadius: 10, background: index === 0 ? props.accentSecondary : props.accent, marginTop: 38}} />
            <div style={{fontSize: 76, lineHeight: 1.18, fontWeight: 760, marginTop: 80}}>{body.trim()}</div>
          </GlassPanel>
        ))}
      </div>
    </MagicHourBackdrop>
  );
};
