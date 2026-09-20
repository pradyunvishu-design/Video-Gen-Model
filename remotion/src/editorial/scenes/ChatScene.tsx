import {Img, useCurrentFrame, useVideoConfig} from "remotion";
import {EditorialFrame} from "../EditorialFrame";
import type {EditorialScene} from "../schema";
import {editorial, enter, resolveEditorialAsset} from "../theme";

export const ChatScene: React.FC<{scene: EditorialScene; seriesName: string; footer: string}> = ({scene, seriesName, footer}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const shell = enter(frame, 3, 18);
  const dense = scene.messages.length > 5 || scene.messages.some((message) => message.text.length > 92);
  const dialogGrid = !dense && scene.messages.length >= 2 && scene.messages.length <= 4;
  return (
    <EditorialFrame scene={scene} seriesName={seriesName} footer={footer}>
      <div style={{position: "absolute", left: 72, right: 72, top: 54, bottom: 46, padding: "0 48px 40px", borderRadius: 32, background: editorial.board, border: `2px solid ${editorial.line}`, translate: `0px ${(1 - shell) * 18}px`}}>
        <div style={{height: 118, display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: `2px solid ${editorial.line}`}}>
          <div style={{display: "flex", alignItems: "center", gap: 22, fontSize: 46, fontWeight: 640}}>
            <span style={{width: 54, height: 54, borderRadius: 13, display: "grid", placeItems: "center", color: scene.accent, background: editorial.panelRaised, border: `2px solid ${scene.accent}`, fontSize: 25, fontWeight: 900}}>#</span>
            {scene.title}
          </div>
          <div style={{display: "flex", gap: 42, color: editorial.mutedDark, fontSize: 26, fontWeight: 560}}>
            {scene.messages.slice(0, 2).map((message) => (
              <div key={message.speaker} style={{display: "flex", alignItems: "center", gap: 13}}>
                <span style={{width: 30, height: 30, borderRadius: 8, background: message.color || scene.accent, padding: 6, display: "grid", placeItems: "center", color: editorial.black, fontSize: 12, fontWeight: 900}}>
                  {message.logo ? <Img src={resolveEditorialAsset(message.logo)} style={{width: "100%", height: "100%", objectFit: "contain"}} /> : message.speaker.slice(0, 2).toUpperCase()}
                </span>
                @{message.speaker.toLowerCase().replace(/\s+/g, "-")}
              </div>
            ))}
          </div>
        </div>
        <div style={{position: "absolute", left: 0, right: 0, top: 158, bottom: 18, display: "grid", gridTemplateColumns: dialogGrid ? "1fr 1fr" : "1fr", gridAutoRows: dialogGrid ? "minmax(260px, 1fr)" : "auto", alignContent: dialogGrid ? "stretch" : "start", gap: dense ? 20 : 28}}>
          {scene.messages.map((message, index) => {
            const value = enter(frame, 18 + index * Math.max(22, Math.floor((durationInFrames * .68) / Math.max(1, scene.messages.length))), 16);
            return (
              <div key={`${message.speaker}-${index}`} style={{display: "grid", gridTemplateColumns: dense ? "72px 1fr" : "82px 1fr", gap: 24, alignItems: dialogGrid ? "center" : "start", padding: dialogGrid ? "34px 38px" : 24, borderRadius: dialogGrid ? 26 : 18, background: editorial.panel, border: `2px solid ${index === scene.messages.length - 1 ? message.color : editorial.line}`, opacity: value, translate: `0px ${(1 - value) * 14}px`}}>
                <div style={{width: dense ? 62 : 72, height: dense ? 62 : 72, borderRadius: 18, background: editorial.panelRaised, border: `2px solid ${message.color || scene.accent}`, padding: dense ? 12 : 15, display: "grid", placeItems: "center", color: message.color || scene.accent, fontSize: dense ? 22 : 25, fontWeight: 900}}>
                  {message.logo ? <Img src={resolveEditorialAsset(message.logo)} style={{width: "100%", height: "100%", objectFit: "contain"}} /> : message.speaker.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <div style={{display: "flex", alignItems: "baseline", gap: 18}}><span style={{fontSize: dense ? 36 : 42, fontWeight: 680}}>{message.speaker}</span><span style={{fontSize: dense ? 24 : 28, color: editorial.muted}}>{message.time}</span></div>
                  <div style={{marginTop: 7, fontSize: dense ? 43 : 50, lineHeight: 1.2, fontWeight: 440, color: editorial.white}}>{message.text}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </EditorialFrame>
  );
};
