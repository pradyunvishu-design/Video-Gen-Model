import {interpolate, useCurrentFrame} from "remotion";
import {GlassPanel, Kicker, MagicHourBackdrop, editorialPalette, smooth} from "../design-system";
import type {MotionShotProps} from "../types";

export const ChapterTitle: React.FC<MotionShotProps> = (props) => {
  const frame = useCurrentFrame();
  return (
    <MagicHourBackdrop variant="chapter_title">
      <div style={{height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center"}}>
        {props.showEditorialHeading ? <Kicker accent={props.accentSecondary}>{props.kicker}</Kicker> : null}
        <GlassPanel style={{marginTop: props.showEditorialHeading ? 80 : 0, maxWidth: 3200, padding: "120px 170px", textAlign: "center"}}>
          <div style={{fontSize: 190, lineHeight: 0.98, fontWeight: 900, letterSpacing: -10, textWrap: "balance", opacity: interpolate(frame, [8, 26], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: smooth}), translate: interpolate(frame, [8, 32], ["0px 90px", "0px 0px"], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: smooth})}}>{props.title}</div>
          <div style={{height: 14, width: interpolate(frame, [24, 52], [0, 980], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: smooth}), margin: "80px auto 0", borderRadius: 20, background: props.accent}} />
          {props.body ? <div style={{fontSize: 64, lineHeight: 1.35, color: editorialPalette.muted, marginTop: 72}}>{props.body}</div> : null}
        </GlassPanel>
      </div>
    </MagicHourBackdrop>
  );
};
