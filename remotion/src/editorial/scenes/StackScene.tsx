import {useCurrentFrame, useVideoConfig} from "remotion";
import {EditorialFrame} from "../EditorialFrame";
import type {EditorialScene} from "../schema";
import {editorial} from "../theme";
import {motionProgress, staggerDelay} from "../motionSystem";
import {bodyTextPx, labelTextPx, useVisualStyle} from "../styleProfile";

export const StackScene: React.FC<{scene: EditorialScene; seriesName: string; footer: string}> = ({scene, seriesName, footer}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const profile = useVisualStyle();
  const bodyPx = bodyTextPx(scene, 43, profile);
  const labelPx = labelTextPx(scene, 29, profile);
  const activeIndex = Math.max(0, Math.min(4, Math.floor(Math.max(0, frame - 18) / Math.max(24, (durationInFrames - 36) / 5))));
  return (
    <EditorialFrame scene={scene} seriesName={seriesName} footer={footer}>
      <div style={{position: "absolute", left: 90, top: 150, bottom: 110, width: 1260, padding: "120px 70px", borderRadius: 32, background: editorial.board, border: `2px solid ${editorial.line}`}}>
        <div style={{fontSize: 105, lineHeight: 1.02, letterSpacing: -4, fontWeight: 630}}>{scene.title}</div>
        <div style={{marginTop: 44, fontSize: bodyPx, lineHeight: 1.35, color: editorial.muted}}>{scene.subtitle}</div>
      </div>
      <div style={{position: "absolute", right: 170, top: 150, width: 1940, height: 1330, padding: "60px 50px", borderRadius: 32, background: editorial.board, border: `2px solid ${editorial.line}`}}>
        {scene.items.slice(0, 5).map((item, index) => {
          const value = motionProgress(frame, "enter", 12 + staggerDelay(index, "normal"), 34);
          const active = index === activeIndex;
          return (
            <div key={item} style={{position: "absolute", left: index * 72, right: (4 - index) * 72, top: index * 210, height: 178, display: "grid", gridTemplateColumns: "110px 1fr 90px", alignItems: "center", padding: "0 42px", borderRadius: 24, background: active ? editorial.clay : editorial.boardRaised, border: `2px solid ${active ? scene.accent : editorial.line}`, boxShadow: active ? "0 30px 80px rgba(0,0,0,.48)" : "0 24px 65px rgba(0,0,0,.34)", opacity: value, translate: `${(1 - value) * 34}px 0px`}}>
              <span style={{fontSize: labelPx, color: editorial.muted, fontWeight: 760}}>{String(index + 1).padStart(2, "0")}</span>
              <span style={{fontSize: bodyPx, fontWeight: 590}}>{item}</span>
              <span style={{width: 22, height: 22, borderRadius: 99, background: active ? scene.accent : editorial.mutedDark}} />
            </div>
          );
        })}
      </div>
    </EditorialFrame>
  );
};
