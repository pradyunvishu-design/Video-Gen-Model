import {Img, useCurrentFrame} from "remotion";
import type {EditorialLogo} from "./schema";
import {editorial, enter, resolveEditorialAsset} from "./theme";

export const LogoMark: React.FC<{logo: EditorialLogo; delay?: number; size?: number; showLabel?: boolean}> = ({logo, delay = 0, size = 180, showLabel = true}) => {
  const frame = useCurrentFrame();
  const value = enter(frame, delay, 18);
  return (
    <div style={{width: size, display: "flex", flexDirection: "column", alignItems: "center", gap: 18, opacity: value, translate: `0px ${(1 - value) * 16}px`}}>
      <div style={{width: size, height: size, borderRadius: size * 0.2, display: "grid", placeItems: "center", background: logo.color, border: `2px solid ${editorial.line}`, boxShadow: "0 24px 60px rgba(0,0,0,.34)"}}>
        <div style={{width: size * 0.56, height: size * 0.56, borderRadius: size * 0.12, background: "rgba(255,255,255,.94)", padding: size * 0.08, display: "grid", placeItems: "center"}}>
          <Img src={resolveEditorialAsset(logo.src)} style={{width: "100%", height: "100%", objectFit: "contain"}} />
        </div>
      </div>
      {showLabel ? <div style={{fontSize: 24, color: editorial.muted, fontWeight: 650}}>{logo.name}</div> : null}
    </div>
  );
};
