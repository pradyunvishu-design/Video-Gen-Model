import {useCurrentFrame} from "remotion";
import {EditorialFrame} from "../EditorialFrame";
import type {EditorialScene} from "../schema";
import {editorial, progress} from "../theme";
import {motionProgress, staggerDelay} from "../motionSystem";

export const TimelineScene: React.FC<{scene: EditorialScene; seriesName: string; footer: string}> = ({scene, seriesName, footer}) => {
  const frame = useCurrentFrame();
  const draw = progress(frame, 12, 72);
  const items = scene.items.slice(0, 5);
  return (
    <EditorialFrame scene={scene} seriesName={seriesName} footer={footer}>
      <div style={{position: "absolute", left: 140, right: 140, top: 190}}>
        <div style={{fontSize: 94, letterSpacing: -3, fontWeight: 630}}>{scene.title}</div>
        <div style={{marginTop: 28, fontSize: 42, color: editorial.muted}}>{scene.subtitle}</div>
      </div>
      <div style={{position: "absolute", left: 170, right: 170, top: 760, height: 420}}>
        <div style={{position: "absolute", left: 0, right: 0, top: 96, height: 4, background: editorial.line}} />
        <div style={{position: "absolute", left: 0, top: 96, width: `${draw * 100}%`, height: 4, background: scene.accent}} />
        <div style={{display: "grid", gridTemplateColumns: `repeat(${Math.max(1, items.length)}, 1fr)`, gap: 38}}>
          {items.map((item, index) => {
            const value = motionProgress(frame, "enter", 20 + staggerDelay(index, "normal"), 18);
            return <div key={item} style={{position: "relative", opacity: value, translate: `0px ${(1 - value) * 18}px`}}>
              <div style={{width: 34, height: 34, margin: "80px auto 0", borderRadius: 99, background: editorial.white, border: `8px solid ${editorial.black}`, boxShadow: `0 0 0 3px ${scene.accent}`}} />
              <div style={{marginTop: 42, textAlign: "center", fontSize: 36, lineHeight: 1.25, fontWeight: 570}}>{item}</div>
            </div>;
          })}
        </div>
      </div>
    </EditorialFrame>
  );
};
