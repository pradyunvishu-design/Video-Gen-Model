import {useCurrentFrame} from "remotion";
import {EditorialFrame} from "../EditorialFrame";
import {LogoMark} from "../LogoMark";
import type {EditorialScene} from "../schema";
import {editorial, enter} from "../theme";

export const TitleScene: React.FC<{scene: EditorialScene; seriesName: string; footer: string}> = ({scene, seriesName, footer}) => {
  const frame = useCurrentFrame();
  const title = enter(frame, 5, 22);
  const body = enter(frame, 20, 22);
  return (
    <EditorialFrame scene={scene} seriesName={seriesName} footer={footer}>
      <div style={{position: "absolute", inset: 0, display: "grid", gridTemplateColumns: "1.45fr .9fr", alignItems: "center", gap: 180}}>
        <div style={{paddingLeft: 120, maxWidth: 2020}}>
          <div style={{fontSize: 160, lineHeight: .98, letterSpacing: -6, fontWeight: 650, opacity: title, translate: `0px ${(1 - title) * 24}px`}}>{scene.title}</div>
          <div style={{marginTop: 54, maxWidth: 1620, fontSize: 48, lineHeight: 1.38, color: editorial.muted, fontWeight: 480, opacity: body, translate: `0px ${(1 - body) * 18}px`}}>{scene.subtitle}</div>
        </div>
        <div style={{display: "grid", gridTemplateColumns: "repeat(2, 190px)", gap: "70px 74px", alignItems: "center", justifyContent: "center"}}>
          {scene.logos.map((logo, index) => <LogoMark key={logo.name} logo={logo} delay={18 + index * 10} size={190} />)}
        </div>
      </div>
    </EditorialFrame>
  );
};
