import {useCurrentFrame, useVideoConfig} from "remotion";
import {EditorialFrame} from "../EditorialFrame";
import type {EditorialScene} from "../schema";
import {bodyTextPx, labelTextPx, semanticStateFrame, useVisualStyle} from "../styleProfile";
import {editorial, enter} from "../theme";

export const CompareScene: React.FC<{scene: EditorialScene; seriesName: string; footer: string}> = ({scene, seriesName, footer}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const profile = useVisualStyle();
  const bodyPx = bodyTextPx(scene, 36, profile);
  const labelPx = labelTextPx(scene, 34, profile);
  const left = enter(frame, 5, 20);
  const right = enter(frame, Math.min(Math.floor(durationInFrames * .34), semanticStateFrame(scene, 1, 30)), 20);
  const conclusion = enter(frame, Math.min(Math.floor(durationInFrames * .67), semanticStateFrame(scene, 2, 30)), 18);
  return (
    <EditorialFrame scene={scene} seriesName={seriesName} footer={footer}>
      <div style={{position: "absolute", left: 60, right: 60, top: 60, bottom: 250, display: "grid", gridTemplateColumns: "1fr 1.08fr", gap: 100, alignItems: "center"}}>
        <div style={{height: "100%", boxSizing: "border-box", padding: "62px 70px", borderRadius: 32, background: editorial.board, border: `2px solid ${editorial.line}`, display: "flex", alignItems: "center"}}>
          <div style={{opacity: left, translate: `${(1 - left) * -20}px 0px`}}>
            <div style={{fontSize: labelPx, color: editorial.muted, letterSpacing: 6, fontWeight: 720}}>THE CLAIM</div>
            <div style={{marginTop: 36, fontSize: 78, lineHeight: 1.12, fontWeight: 520}}>{scene.claim}</div>
          </div>
        </div>
        <div style={{height: "100%", boxSizing: "border-box", padding: "62px 70px", borderRadius: 32, background: editorial.boardRaised, border: `2px solid ${scene.accent}`, boxShadow: "0 30px 90px rgba(0,0,0,.42)", display: "flex", alignItems: "center"}}>
          <div style={{opacity: right, translate: `${(1 - right) * 20}px 0px`}}>
            <div style={{fontSize: labelPx, color: editorial.white, letterSpacing: 6, fontWeight: 720}}>THE EVIDENCE</div>
            <div style={{marginTop: 36, fontSize: 62, lineHeight: 1.17, fontWeight: 540}}>{scene.evidence}</div>
          </div>
        </div>
      </div>
      <div style={{position: "absolute", left: 60, right: 60, bottom: 70, height: 230, display: "grid", gridTemplateColumns: "1.05fr .95fr", gap: 90, alignItems: "center", opacity: conclusion}}>
        <div style={{fontSize: 92, lineHeight: 1.02, letterSpacing: -3.5, fontWeight: 640}}>{scene.title}</div>
        <div style={{color: editorial.muted, fontSize: bodyPx, lineHeight: 1.32}}>{scene.subtitle}</div>
      </div>
    </EditorialFrame>
  );
};
