import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import {EvidenceViewport, Kicker, RealSourceImage, smooth} from "../design-system";
import type {MotionShotProps} from "../types";

export const UiStage: React.FC<MotionShotProps> = (props) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{background: "#08070C", color: "white"}}>
      <div style={{position: "absolute", inset: 0, opacity: interpolate(frame, [8, 24], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: smooth}), scale: interpolate(frame, [8, 90], [1.015, 1.045], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: smooth, output: "perceptual-scale"})}}>
        <EvidenceViewport annotation={props.annotation} cursor={props.cursor} accent={props.accent}>
          <RealSourceImage src={props.sourceImage} label={props.sourceLabel} />
        </EvidenceViewport>
      </div>
      <div style={{position: "absolute", inset: 0, pointerEvents: "none", background: "linear-gradient(180deg,rgba(0,0,0,.68),transparent 31%,transparent 78%,rgba(0,0,0,.25))"}} />
      {props.showEditorialHeading ? (
        <>
          <Kicker accent={props.accent}>{props.kicker}</Kicker>
          <div
            style={{
              position: "absolute",
              right: 100,
              top: 100,
              maxWidth: 2480,
              fontSize: 116,
              lineHeight: 1.02,
              fontWeight: 850,
              letterSpacing: -3,
              textAlign: "right",
              textWrap: "balance",
              textShadow: "0 10px 42px rgba(0,0,0,.92)",
            }}
          >
            {props.title}
          </div>
        </>
      ) : null}
    </AbsoluteFill>
  );
};
