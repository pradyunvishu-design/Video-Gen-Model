import {Img, useCurrentFrame} from "remotion";
import {EditorialFrame} from "../EditorialFrame";
import {patternForScene} from "../motionCatalog";
import {motionProgress, staggerDelay, typewriterCount} from "../motionSystem";
import type {EditorialScene} from "../schema";
import {editorial, enter, resolveEditorialAsset} from "../theme";

const statusColor = (mode: string, index: number) => {
  if (mode === "diff-apply") return index % 2 ? "#7FA589" : "#B96D63";
  if (mode === "test-suite") return "#7FA589";
  return index === 0 ? editorial.white : editorial.muted;
};

export const TerminalScene: React.FC<{scene: EditorialScene; seriesName: string; footer: string}> = ({scene, seriesName, footer}) => {
  const frame = useCurrentFrame();
  const panel = enter(frame, 2, 16);
  const pattern = patternForScene(scene);
  const mode = pattern.id.replace("terminal-", "");
  const toolCall = mode === "tool-call";
  const firstLogo = scene.logos[0];

  return (
    <EditorialFrame scene={scene} seriesName={seriesName} footer={footer}>
      <div style={{position: "absolute", inset: "38px 34px 44px", borderRadius: 30, overflow: "hidden", background: "#0C0D0D", border: `2px solid ${editorial.line}`, boxShadow: "0 42px 120px rgba(0,0,0,.5)", opacity: panel, translate: `0px ${(1 - panel) * 14}px`}}>
        <div style={{height: 112, display: "flex", alignItems: "center", padding: "0 36px", background: editorial.panel, borderBottom: `2px solid ${editorial.line}`}}>
          <div style={{display: "flex", gap: 15}}>{["#6C6F6D", "#8A8D8A", "#B9BAB6"].map((color) => <span key={color} style={{width: 17, height: 17, borderRadius: 20, background: color}} />)}</div>
          {firstLogo ? <div style={{marginLeft: 36, width: 58, height: 58, borderRadius: 15, background: firstLogo.color, padding: 10, display: "grid", placeItems: "center"}}><Img src={resolveEditorialAsset(firstLogo.src)} style={{width: "100%", height: "100%", objectFit: "contain"}} /></div> : null}
          <div style={{marginLeft: 22, color: editorial.white, fontSize: 36, fontWeight: 680}}>{scene.title}</div>
          <div style={{marginLeft: "auto", color: editorial.muted, fontSize: 24, letterSpacing: 3, textTransform: "uppercase"}}>{mode.replace(/-/g, " ")}</div>
        </div>

        <div style={{position: "absolute", left: 0, right: 0, top: 112, bottom: 0, display: toolCall ? "grid" : "block", gridTemplateColumns: toolCall ? "1fr 1fr" : undefined}}>
          <div style={{padding: "58px 66px", borderRight: toolCall ? `2px solid ${editorial.line}` : undefined, fontFamily: "ui-monospace, SFMono-Regular, Consolas, monospace"}}>
            {scene.items.slice(0, 7).map((item, index) => {
              const delay = 14 + staggerDelay(index, mode === "streaming-output" ? "tight" : "normal");
              const value = motionProgress(frame, "micro", delay, 10);
              const typed = mode === "command-run" || mode === "streaming-output";
              const visible = typed ? item.slice(0, typewriterCount(frame, item, delay, 58)) : item;
              const isTyping = typed && visible.length < item.length;
              const prefix = mode === "file-tree" ? `${"  ".repeat(Math.min(index, 3))}${index === scene.items.length - 1 ? "└─" : "├─"}` : mode === "diff-apply" ? (index % 2 ? "+" : "-") : mode === "test-suite" ? "PASS" : index === 0 ? ">" : "·";
              return (
                <div key={`${item}-${index}`} style={{minHeight: 118, display: "grid", gridTemplateColumns: mode === "test-suite" ? "150px 1fr" : "82px 1fr", alignItems: "center", borderBottom: `1px solid ${editorial.line}`, opacity: value, translate: `0px ${(1 - value) * 10}px`, fontSize: 50, lineHeight: 1.28}}>
                  <span style={{color: statusColor(mode, index), fontSize: mode === "test-suite" ? 28 : 46, fontWeight: 720}}>{prefix}</span>
                  <span style={{color: mode === "diff-apply" ? statusColor(mode, index) : editorial.white}}>{visible}{isTyping ? <span style={{opacity: frame % 24 < 12 ? .9 : .2}}>▌</span> : null}</span>
                </div>
              );
            })}
          </div>

          {toolCall ? (
            <div style={{padding: "64px 72px", display: "flex", flexDirection: "column", justifyContent: "space-between"}}>
              <div>
                <div style={{fontSize: 26, letterSpacing: 4, color: editorial.muted, fontWeight: 720}}>STRUCTURED RESULT</div>
                <div style={{marginTop: 34, fontSize: 58, lineHeight: 1.2, fontWeight: 580}}>{scene.evidence || scene.subtitle}</div>
              </div>
              <div style={{padding: "30px 34px", borderRadius: 18, background: editorial.panelRaised, border: `2px solid ${editorial.line}`, fontSize: 30, color: editorial.muted}}>One request. One result. No decorative motion.</div>
            </div>
          ) : (
            <div style={{position: "absolute", right: 54, bottom: 42, maxWidth: 1500, padding: "20px 28px", borderRadius: 14, background: "rgba(12,13,13,.94)", border: `2px solid ${editorial.line}`, color: editorial.muted, fontSize: 30, lineHeight: 1.35}}>{scene.subtitle}</div>
          )}
        </div>
      </div>
    </EditorialFrame>
  );
};
