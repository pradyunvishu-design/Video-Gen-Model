import {AbsoluteFill} from "remotion";
import {EvidenceViewport, Kicker, RealSourceImage} from "../design-system";
import type {MotionShotProps} from "../types";

export const EvidenceFocus: React.FC<MotionShotProps> = (props) => {
  return (
    <AbsoluteFill style={{background: "#08070C", color: "white"}}>
      <EvidenceViewport annotation={props.annotation} cursor={props.cursor} accent={props.accent}>
        <RealSourceImage src={props.sourceImage} label={props.sourceLabel} />
      </EvidenceViewport>
      <div style={{position: "absolute", inset: 0, pointerEvents: "none", background: "linear-gradient(180deg,rgba(0,0,0,.62),transparent 27%,transparent 73%,rgba(0,0,0,.24))"}} />
      {props.showEditorialHeading ? (
        <>
          <Kicker accent={props.accent}>{props.kicker || "SOURCE EVIDENCE"}</Kicker>
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
