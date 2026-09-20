import {Video} from "@remotion/media";
import {Img, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {EditorialFrame} from "../EditorialFrame";
import {patternForScene} from "../motionCatalog";
import type {EditorialScene} from "../schema";
import {bodyTextPx, labelTextPx, semanticStateFrame, useVisualStyle} from "../styleProfile";
import {editorial, editorialEase, enter, resolveEditorialAsset} from "../theme";

export const SourceScene: React.FC<{scene: EditorialScene; seriesName: string; footer: string}> = ({scene, seriesName, footer}) => {
  const frame = useCurrentFrame();
  const {durationInFrames, fps} = useVideoConfig();
  const profile = useVisualStyle();
  const bodyPx = bodyTextPx(scene, 34, profile);
  const labelPx = labelTextPx(scene, 25, profile);
  const value = enter(frame, 3, 20);
  const pattern = patternForScene(scene);
  const lockedForReading = Boolean(scene.sourceFocus) || pattern.id === "source-ui-focus-corridor";
  const mediaScale = lockedForReading ? 1 : interpolate(frame, [0, durationInFrames - 1], [1, 1.012], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: editorialEase});
  const src = resolveEditorialAsset(scene.sourceAsset);
  const isVideo = /\.(mp4|webm|mov)(\?|$)/i.test(scene.sourceAsset);
  const showBrowserBar = Boolean(scene.sourceUrl) && pattern.id !== "source-demo-crop";
  const showEvidenceRail = pattern.id === "source-repo-metrics" || pattern.id === "source-ui-feature";
  const evidenceRailWidth = pattern.id === "source-repo-metrics" ? "34%" : "28%";
  const chromeHeight = showBrowserBar ? 84 : 0;
  return (
    <EditorialFrame scene={scene} seriesName={seriesName} footer={footer}>
      <div style={{position: "absolute", inset: pattern.stage === "full" ? 28 : 46, borderRadius: pattern.stage === "full" ? 24 : 34, overflow: "hidden", background: editorial.panel, border: `2px solid ${editorial.line}`, boxShadow: "0 58px 150px rgba(0,0,0,.42)", translate: `0px ${(1 - value) * 14}px`}}>
        {showBrowserBar ? <div style={{height: chromeHeight, display: "flex", alignItems: "center", gap: 16, padding: "0 32px", background: editorial.blackSoft, borderBottom: `2px solid ${editorial.line}`}}>
          {["#D66A5E", "#B49B54", "#637F6A"].map((color) => <span key={color} style={{width: 16, height: 16, borderRadius: 18, background: color}} />)}
          <div style={{marginLeft: 18, maxWidth: "78%", overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis", color: editorial.muted, fontSize: labelPx}}>{scene.sourceUrl}</div>
        </div> : null}
        <div style={{position: "absolute", left: 0, right: 0, top: chromeHeight, bottom: 0, overflow: "hidden", background: "#111"}}>
          {isVideo ? <Video src={src} muted trimBefore={Math.round((scene.sourceStartSeconds ?? 0) * fps)} objectFit="cover" style={{width: "100%", height: "100%", scale: mediaScale}} /> : <Img src={src} style={{width: "100%", height: "100%", objectFit: "cover", objectPosition: scene.sourceObjectPosition ?? "50% 16%", scale: mediaScale}} />}
          {pattern.id === "source-repo-metrics" ? <div style={{position: "absolute", inset: 0, background: "rgba(0,0,0,.12)", pointerEvents: "none"}} /> : null}
          <div style={{position: "absolute", left: 0, right: 0, bottom: 0, height: 150, background: "linear-gradient(transparent, rgba(9,10,10,.86))", pointerEvents: "none"}} />
          <div style={{position: "absolute", left: 36, bottom: 28, padding: "14px 21px", borderRadius: 12, background: "rgba(9,10,10,.92)", border: `2px solid ${editorial.line}`, color: editorial.white, fontSize: labelPx, letterSpacing: 2.5, fontWeight: 700}}>SOURCE / {scene.sourceLabel}</div>
          {scene.sourceFocus ? (
            <div style={{position: "absolute", left: `${scene.sourceFocus.x * 100}%`, top: `${scene.sourceFocus.y * 100}%`, width: `${scene.sourceFocus.width * 100}%`, height: `${scene.sourceFocus.height * 100}%`, border: `3px solid ${scene.accent}`, borderRadius: 14, boxShadow: "0 0 0 9999px rgba(7,8,8,.38)", opacity: enter(frame, semanticStateFrame(scene, 1, fps), 18)}}>
              <div style={{position: "absolute", right: 12, top: 12, color: editorial.black, background: scene.accent, padding: "10px 15px", borderRadius: 8, fontSize: labelPx, fontWeight: 800, letterSpacing: 1.5}}>{scene.sourceFocus.label}</div>
            </div>
          ) : null}
          {showEvidenceRail ? (
            <div style={{position: "absolute", right: 0, top: 0, bottom: 0, width: evidenceRailWidth, padding: "86px 54px", background: editorial.boardRaised, borderLeft: `2px solid ${editorial.line}`, display: "flex", flexDirection: "column", justifyContent: "space-between"}}>
              <div>
                <div style={{fontSize: labelPx, color: editorial.muted, letterSpacing: 5, fontWeight: 760}}>VERIFIED SOURCE</div>
                <div style={{marginTop: 34, fontSize: 54, lineHeight: 1.08, color: editorial.white, fontWeight: 720}}>{scene.title}</div>
                <div style={{marginTop: 32, fontSize: bodyPx, lineHeight: 1.34, color: editorial.white, fontWeight: 470}}>{scene.subtitle}</div>
              </div>
              <div style={{fontSize: labelPx, lineHeight: 1.35, color: editorial.muted, letterSpacing: 2}}>EVIDENCE ON SCREEN<br />{scene.sourceLabel}</div>
            </div>
          ) : null}
        </div>
      </div>
    </EditorialFrame>
  );
};
