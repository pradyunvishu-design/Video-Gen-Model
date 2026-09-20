import type {ReactNode} from "react";
import {AbsoluteFill} from "remotion";
import type {EditorialScene} from "./schema";
import {editorial} from "./theme";
import {patternForScene} from "./motionCatalog";
import {labelTextPx, useVisualStyle} from "./styleProfile";

export const EditorialFrame: React.FC<{scene: EditorialScene; seriesName: string; footer: string; children: ReactNode}> = ({scene, seriesName, footer, children}) => {
  const profile = useVisualStyle();
  const pattern = patternForScene(scene);
  const dominance = Math.max(pattern.dominance, scene.proofDominance ?? 0);
  const patternInset = pattern.stage === "full"
    ? Math.max(52, Math.round(130 * (1 - dominance))) + 52
    : pattern.stage === "wide"
      ? 96
      : 132;
  const sideInset = Math.max(patternInset, (profile?.canvas.safeInsetPx ?? 70) / (profile?.canvas.renderScale ?? 1));
  const labelPx = labelTextPx(scene, 22, profile);
  const canvas = profile?.canvas.background ?? editorial.black;
  return (
    <AbsoluteFill style={{background: canvas, color: profile?.canvas.paper ?? editorial.white, fontFamily: "Inter Variable, Inter, Arial, sans-serif", overflow: "hidden"}}>
      <AbsoluteFill style={{background: `radial-gradient(circle at 50% 42%, rgba(255,255,255,.018) 0%, transparent 42%), ${canvas}`}} />
      <div style={{position: "absolute", left: sideInset, top: 64, display: "flex", alignItems: "center", gap: 18, fontSize: labelPx, color: editorial.muted, letterSpacing: 4.5, fontWeight: 700}}>
        <span style={{width: 10, height: 10, borderRadius: 3, background: scene.accent}} />
        {scene.chapter}
      </div>
      <div style={{position: "absolute", right: sideInset, top: 66, fontSize: labelPx, color: editorial.mutedDark, letterSpacing: 3.5, fontWeight: 650}}>{seriesName}</div>
      <AbsoluteFill style={{left: sideInset, right: sideInset, top: 148, bottom: 76, width: "auto", height: "auto"}}>
        {children}
      </AbsoluteFill>
      <div style={{position: "absolute", right: sideInset, bottom: 30, fontSize: labelPx, color: editorial.mutedDark, letterSpacing: 2.8, fontWeight: 620}}>{footer}</div>
    </AbsoluteFill>
  );
};
