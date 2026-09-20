import {Img, useCurrentFrame, useVideoConfig} from "remotion";
import {EditorialFrame} from "../EditorialFrame";
import type {EditorialScene} from "../schema";
import {bodyTextPx, labelTextPx, semanticStateFrame, useVisualStyle} from "../styleProfile";
import {editorial, enter, progress, resolveEditorialAsset} from "../theme";

const graphWidth = 3400;
const graphHeight = 1600;

export const GraphScene: React.FC<{scene: EditorialScene; seriesName: string; footer: string}> = ({scene, seriesName, footer}) => {
  const frame = useCurrentFrame();
  const {durationInFrames, fps} = useVideoConfig();
  const profile = useVisualStyle();
  const bodyPx = bodyTextPx(scene, 40, profile);
  const labelPx = labelTextPx(scene, 34, profile);
  const draw = progress(frame, 7, 48);
  const byId = new Map(scene.nodes.map((node) => [node.id, node]));
  return (
    <EditorialFrame scene={scene} seriesName={seriesName} footer={footer}>
      <div style={{position: "absolute", left: 38, top: 120, width: graphWidth, height: graphHeight, borderRadius: 34, background: frame >= semanticStateFrame(scene, 1, fps) ? "#493F31" : editorial.board, border: `2px solid ${editorial.line}`, overflow: "hidden"}}>
        <svg viewBox={`0 0 ${graphWidth} ${graphHeight}`} style={{position: "absolute", inset: 0, overflow: "visible"}}>
          {scene.edges.map(([fromId, toId], index) => {
            const from = byId.get(fromId); const to = byId.get(toId);
            if (!from || !to) return null;
            const x1 = from.x * graphWidth; const y1 = from.y * graphHeight; const x2 = to.x * graphWidth; const y2 = to.y * graphHeight;
            return <path key={`${fromId}-${toId}`} d={`M ${x1} ${y1} C ${(x1 + x2) / 2} ${y1}, ${(x1 + x2) / 2} ${y2}, ${x2} ${y2}`} fill="none" stroke={editorial.line} strokeWidth="5" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - Math.max(0, Math.min(1, draw - index * .06))} />;
          })}
        </svg>
        {scene.nodes.map((node, index) => {
          const revealWindow = Math.max(36, Math.floor(durationInFrames * .68));
          const value = enter(frame, 8 + index * Math.max(12, Math.floor(revealWindow / Math.max(1, scene.nodes.length))), 18);
          const featured = node.color !== "#F2F1ED";
          return (
            <div key={node.id} style={{position: "absolute", left: `${node.x * 100}%`, top: `${node.y * 100}%`, translate: "-50% -50%", opacity: value}}>
              <div style={{minWidth: node.logo ? 240 : featured ? 430 : 340, height: node.logo ? 240 : featured ? 184 : 154, padding: node.logo ? 42 : "0 52px", borderRadius: node.logo ? 46 : 24, display: "grid", placeItems: "center", overflow: "hidden", background: node.logo ? node.color : featured ? editorial.clay : editorial.panelRaised, border: `2px solid ${featured ? node.color : editorial.line}`, boxShadow: featured ? "0 30px 95px rgba(0,0,0,.55)" : "0 24px 70px rgba(0,0,0,.35)", color: editorial.white, fontSize: bodyPx, fontWeight: 740, letterSpacing: 3}}>
                {node.logo ? <Img src={resolveEditorialAsset(node.logo)} style={{width: "78%", height: "78%", objectFit: "contain"}} /> : node.label}
              </div>
              {featured && !node.logo ? <div style={{position: "absolute", right: 18, top: 14, width: 12, height: 12, borderRadius: 20, background: node.color, boxShadow: `0 0 20px ${node.color}`}} /> : null}
              {node.logo ? <div style={{marginTop: 18, textAlign: "center", fontSize: labelPx, color: editorial.muted, fontWeight: 650}}>{node.label}</div> : null}
            </div>
          );
        })}
      </div>
      <div style={{position: "absolute", left: 72, right: 72, top: 30, display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 120}}>
        <div style={{fontSize: 56, color: editorial.white, letterSpacing: 1, fontWeight: 720}}>{scene.title}</div>
        <div style={{maxWidth: 1500, color: editorial.muted, fontSize: bodyPx, lineHeight: 1.28, textAlign: "right", fontWeight: 510}}>{scene.subtitle}</div>
      </div>
    </EditorialFrame>
  );
};
