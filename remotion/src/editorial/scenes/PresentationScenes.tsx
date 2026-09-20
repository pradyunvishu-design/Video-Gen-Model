import {Easing, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {EditorialFrame} from "../EditorialFrame";
import type {EditorialScene} from "../schema";
import {bodyTextPx, labelTextPx, semanticStateFrame, useVisualStyle} from "../styleProfile";
import {editorial} from "../theme";

const reveal = (frame: number, start: number, duration = 12) => interpolate(
  frame,
  [start, start + duration],
  [0, 1],
  {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(.16, 1, .3, 1)},
);

const Person = ({side, active, label}: {side: "left" | "right"; active: number; label: string}) => (
  <div style={{display: "grid", justifyItems: "center", gap: 22, opacity: .7 + active * .3}}>
    <div style={{width: 190, height: 190, borderRadius: "50%", background: editorial.panelRaised, border: `3px solid ${active > .5 ? editorial.yellow : editorial.line}`, position: "relative"}}>
      <div style={{position: "absolute", left: 54, top: 40, width: 82, height: 82, borderRadius: "50%", background: editorial.white}} />
      <div style={{position: "absolute", left: 31, bottom: 22, width: 128, height: 66, borderRadius: "64px 64px 24px 24px", background: editorial.white}} />
    </div>
    <div style={{fontSize: 34, fontWeight: 720, letterSpacing: 2, color: active > .5 ? editorial.white : editorial.muted}}>{label}</div>
    <div style={{height: 150, width: 250, borderRadius: side === "left" ? "26px 26px 80px 26px" : "26px 26px 26px 80px", background: editorial.panel, border: `2px solid ${editorial.line}`}} />
  </div>
);

export const StudioPodcastScene: React.FC<{scene: EditorialScene; seriesName: string; footer: string}> = ({scene, seriesName, footer}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const profile = useVisualStyle();
  const second = semanticStateFrame(scene, 1, fps);
  const activeLeft = reveal(frame, 10);
  const activeRight = reveal(frame, second);
  return (
    <EditorialFrame scene={scene} seriesName={seriesName} footer={footer}>
      <div style={{position: "absolute", inset: "18px 54px 44px", borderRadius: 38, background: frame >= second ? "#303332" : "#2A2D2C", border: `2px solid ${editorial.line}`, overflow: "hidden"}}>
        <div style={{position: "absolute", inset: "0 0 auto", height: 150, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 72px", borderBottom: `2px solid ${editorial.line}`}}>
          <div style={{fontSize: labelTextPx(scene, 36, profile), fontWeight: 760, letterSpacing: 3}}>BUZZ / STUDIO CONVERSATION</div>
          <div style={{fontSize: labelTextPx(scene, 34, profile), color: editorial.muted}}>SYNTHETIC PRESENTERS · EDITORIAL CONCEPT</div>
        </div>
        <div style={{position: "absolute", left: 120, right: 120, top: 210, bottom: 140, display: "grid", gridTemplateColumns: "1fr 1.35fr 1fr", alignItems: "center", gap: 70}}>
          <Person side="left" active={activeLeft} label={scene.messages[0]?.speaker ?? "HOST"} />
          <div style={{alignSelf: "stretch", display: "grid", alignContent: "center", gap: 38, opacity: reveal(frame, 16)}}>
            <div style={{justifySelf: "center", width: 178, height: 178, borderRadius: 38, display: "grid", placeItems: "center", background: editorial.white, color: editorial.black, fontSize: 52, fontWeight: 900, letterSpacing: -2}}>BUZZ</div>
            <div style={{fontSize: bodyTextPx(scene, 58, profile), lineHeight: 1.14, fontWeight: 680, textAlign: "center"}}>{scene.title}</div>
            <div style={{fontSize: bodyTextPx(scene, 42, profile), lineHeight: 1.34, color: editorial.muted, textAlign: "center"}}>{scene.subtitle}</div>
          </div>
          <Person side="right" active={activeRight} label={scene.messages[1]?.speaker ?? "GUEST"} />
        </div>
        <div style={{position: "absolute", left: 0, right: 0, bottom: 0, height: 28, background: `linear-gradient(90deg, transparent, ${editorial.yellow}, transparent)`, opacity: .75}} />
      </div>
    </EditorialFrame>
  );
};

export const KeynoteStageScene: React.FC<{scene: EditorialScene; seriesName: string; footer: string}> = ({scene, seriesName, footer}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const profile = useVisualStyle();
  const screen = reveal(frame, 4, 16);
  const presenter = reveal(frame, semanticStateFrame(scene, 1, fps), 12);
  return (
    <EditorialFrame scene={scene} seriesName={seriesName} footer={footer}>
      <div style={{position: "absolute", inset: "18px 48px 42px", borderRadius: 38, overflow: "hidden", background: presenter > .5 ? "#303332" : "#2A2D2C", border: `2px solid ${editorial.line}`}}>
        <div style={{position: "absolute", left: 250, right: 250, top: 105, height: 620, padding: "88px 110px", borderRadius: 30, background: editorial.board, border: `3px solid ${editorial.line}`, opacity: screen, translate: `0px ${(1 - screen) * 18}px`}}>
          <div style={{fontSize: labelTextPx(scene, 35, profile), color: editorial.muted, letterSpacing: 4}}>BUZZ · PRODUCT STORY</div>
          <div style={{marginTop: 48, fontSize: bodyTextPx(scene, 108, profile), lineHeight: 1, fontWeight: 720, letterSpacing: -4}}>{scene.title}</div>
          <div style={{marginTop: 42, maxWidth: 2200, fontSize: bodyTextPx(scene, 46, profile), lineHeight: 1.32, color: editorial.muted}}>{scene.subtitle}</div>
          <div style={{position: "absolute", left: 110, right: 110, bottom: 74, height: 9, background: editorial.line}}><div style={{width: `${42 + presenter * 42}%`, height: "100%", background: editorial.yellow}} /></div>
        </div>
        <div style={{position: "absolute", left: 210, right: 210, bottom: 88, height: 120, background: "linear-gradient(180deg,#161818,#080909)", transform: "perspective(700px) rotateX(55deg)", transformOrigin: "bottom"}} />
        <div style={{position: "absolute", left: 300, bottom: 76, opacity: presenter, translate: `${(1 - presenter) * -14}px 0px`}}>
          <div style={{width: 116, height: 116, borderRadius: "50%", background: editorial.white}} />
          <div style={{marginLeft: -22, marginTop: -4, width: 160, height: 190, borderRadius: "76px 76px 22px 22px", background: editorial.white}} />
          <div style={{marginTop: 18, fontSize: 27, fontWeight: 700, letterSpacing: 2}}>SYNTHETIC PRESENTER</div>
        </div>
        <div style={{position: "absolute", left: 0, right: 0, bottom: 0, height: 24, background: `linear-gradient(90deg, transparent, ${editorial.yellow}, transparent)`}} />
      </div>
    </EditorialFrame>
  );
};
