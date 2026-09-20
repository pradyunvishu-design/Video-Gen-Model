import {useCurrentFrame, useVideoConfig} from "remotion";
import {EditorialFrame} from "../EditorialFrame";
import type {EditorialScene} from "../schema";
import {editorial, enter} from "../theme";
import {bodyTextPx, labelTextPx, semanticStateFrame, useVisualStyle} from "../styleProfile";

export const ActivityScene: React.FC<{scene: EditorialScene; seriesName: string; footer: string}> = ({scene, seriesName, footer}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const profile = useVisualStyle();
  const bodyPx = bodyTextPx(scene, 44, profile);
  const labelPx = labelTextPx(scene, 25, profile);
  const shell = enter(frame, 3, 18);
  return (
    <EditorialFrame scene={scene} seriesName={seriesName} footer={footer}>
      <div style={{position: "absolute", left: 72, top: 70, bottom: 70, width: 2480, padding: "52px 54px 48px", borderRadius: 30, background: editorial.board, border: `2px solid ${editorial.line}`, translate: `0px ${(1 - shell) * 16}px`}}>
        <div style={{display: "flex", alignItems: "center", gap: 18, paddingBottom: 30, fontSize: 42, fontWeight: 680}}><span style={{width: 30, height: 30, borderRadius: 7, background: scene.accent}} />{scene.title}</div>
        <div style={{marginTop: 22, display: "grid", gap: 12}}>
          {scene.items.map((item, index) => {
            const step = Math.max(24, Math.floor((durationInFrames - 44) / Math.max(1, scene.items.length)));
            const revealAt = Math.min(18 + index * step, semanticStateFrame(scene, index, 30));
            const value = enter(frame, revealAt, 16);
            const active = frame >= revealAt && frame < revealAt + step;
            const failed = /FAIL(?:ED|URE)?/i.test(item);
            const queued = scene.motionPattern === "activity-task-queue";
            return (
              <div key={item} style={{height: 156, display: "grid", gridTemplateColumns: "76px 1fr 110px", alignItems: "center", padding: "0 26px", borderRadius: 14, background: active ? editorial.clay : editorial.boardRaised, border: `2px solid ${active ? scene.accent : editorial.line}`, opacity: value, translate: `0px ${(1 - value) * 12}px`}}>
                <span style={{width: 38, height: 38, borderRadius: 9, display: "grid", placeItems: "center", background: editorial.panelRaised, border: `2px solid ${active ? editorial.white : editorial.line}`, color: editorial.white, fontSize: labelPx, fontWeight: 900}}>{index + 1}</span>
                <span style={{fontSize: bodyPx, fontWeight: active ? 650 : 480}}>{item}</span>
                <span style={{color: frame > revealAt + 18 ? (failed ? "#D66A5E" : queued ? editorial.yellow : "#75AA83") : editorial.mutedDark, fontSize: labelPx, fontWeight: 760}}>{failed ? "FAILED" : queued ? "NEXT" : "PASS"}</span>
              </div>
            );
          })}
        </div>
        <div style={{position: "absolute", left: 54, bottom: 76, fontSize: 72, lineHeight: 1, letterSpacing: -2, fontWeight: 760, color: editorial.white}}>{scene.claim || "REPLICATION BEFORE VERDICT"}</div>
      </div>
      <div style={{position: "absolute", right: 72, top: 70, bottom: 70, width: 850, padding: "250px 54px 60px", borderRadius: 30, background: editorial.boardRaised, border: `2px solid ${editorial.line}`}}>
        <div style={{fontSize: labelPx, color: editorial.muted, letterSpacing: 3.5, fontWeight: 720}}>EDITORIAL RULE</div>
        <div style={{marginTop: 30, fontSize: bodyPx, lineHeight: 1.24, fontWeight: 520}}>{scene.subtitle}</div>
      </div>
    </EditorialFrame>
  );
};
