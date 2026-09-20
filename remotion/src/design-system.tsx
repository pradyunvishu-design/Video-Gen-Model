import type {CSSProperties, ReactNode} from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type {MotionShotProps} from "./types";

export const magicHour = {
  ink: "#F4F3EE",
  muted: "#A7AAA5",
  surface: "rgba(24, 26, 26, 0.94)",
  surfaceStrong: "rgba(11, 12, 12, 0.98)",
  line: "rgba(244,243,238,0.14)",
  purple: "#5576C9",
  magenta: "#83938C",
  blue: "#5576C9",
  red: "#A66A4F",
};

export const editorialPalette = {
  black: "#0B0C0C",
  card: "#181A1A",
  paper: "#F4F3EE",
  muted: "#A7AAA5",
  yellow: "#83938C",
  moss: "#607457",
  mossDark: "#142019",
  clay: "#A66A4F",
  clayDark: "#211813",
  blue: "#5576C9",
};

export const smooth = Easing.bezier(0.16, 1, 0.3, 1);

type BackdropVariant =
  | "ui_stage"
  | "evidence_focus"
  | "orbit_map"
  | "step_flow"
  | "comparison"
  | "stat_reveal"
  | "chapter_title"
  | "news_intro";

const backdropLooks: Record<BackdropVariant, {base: string; glowA: string; glowB: string; line: string}> = {
  news_intro: {base: "#121513", glowA: "#18201C", glowB: "#211813", line: "#83938C"},
  ui_stage: {base: "#0B0C0C", glowA: "#142019", glowB: "#0B0C0C", line: "#607457"},
  evidence_focus: {base: "#121513", glowA: "#18201C", glowB: "#211813", line: "#83938C"},
  comparison: {base: "#0B0C0C", glowA: "#211813", glowB: "#0B0C0C", line: "#A66A4F"},
  stat_reveal: {base: "#121513", glowA: "#18201C", glowB: "#121513", line: "#83938C"},
  orbit_map: {base: "#0B0C0C", glowA: "#142019", glowB: "#0B0C0C", line: "#607457"},
  step_flow: {base: "#0B0C0C", glowA: "#142019", glowB: "#211813", line: "#607457"},
  chapter_title: {base: "#121513", glowA: "#18201C", glowB: "#211813", line: "#83938C"},
};

export const resolveAsset = (src: string): string => {
  if (!src || src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:")) {
    return src;
  }
  return staticFile(src.replace(/^\/+/, ""));
};

export const MagicHourBackdrop: React.FC<{children: ReactNode; variant?: BackdropVariant}> = ({
  children,
  variant = "orbit_map",
}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const look = backdropLooks[variant];
  return (
    <AbsoluteFill
      style={{
        overflow: "hidden",
        color: magicHour.ink,
        fontFamily: "Inter Variable, Inter, Arial, sans-serif",
        background: look.base,
      }}
    >
      <AbsoluteFill
        style={{
          opacity: 0.045,
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 180 180' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.3'/%3E%3C/svg%3E\")",
          mixBlendMode: "soft-light",
        }}
      />
      <AbsoluteFill style={{background: "radial-gradient(ellipse at center, transparent 58%, rgba(0,0,0,.34) 100%)"}} />
      <AbsoluteFill style={{padding: "180px 220px"}}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};

export const GlassPanel: React.FC<{children: ReactNode; style?: CSSProperties}> = ({children, style}) => (
  <div
    style={{
      background: "rgba(24,26,26,0.96)",
      border: `2px solid ${magicHour.line}`,
      boxShadow: "0 34px 90px rgba(0,0,0,0.42), inset 0 2px 0 rgba(255,255,255,0.08)",
      backdropFilter: "blur(18px)",
      borderRadius: 46,
      ...style,
    }}
  >
    {children}
  </div>
);

export const Kicker: React.FC<{children: ReactNode; accent: string}> = ({children, accent}) => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 22,
        padding: "18px 34px",
        borderRadius: 999,
        border: "2px solid rgba(255,255,255,0.16)",
        background: "rgba(11,12,12,0.86)",
        fontSize: 42,
        fontWeight: 750,
        letterSpacing: 7,
        opacity: interpolate(frame, [0, 16], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: smooth,
        }),
        translate: interpolate(frame, [0, 20], ["0px 34px", "0px 0px"], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: smooth,
        }),
      }}
    >
      <span style={{width: 18, height: 18, borderRadius: "50%", background: accent, boxShadow: `0 0 16px ${accent}88`}} />
      {children}
    </div>
  );
};

export const Headline: React.FC<{children: ReactNode; size?: number; align?: "left" | "center"}> = ({
  children,
  size = 170,
  align = "left",
}) => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        maxWidth: 3380,
        fontSize: size,
        lineHeight: 0.96,
        fontWeight: 850,
        letterSpacing: -8,
        textAlign: align,
        textWrap: "balance",
        opacity: interpolate(frame, [6, 24], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: smooth,
        }),
        translate: interpolate(frame, [6, 28], ["0px 70px", "0px 0px"], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: smooth,
        }),
      }}
    >
      {children}
    </div>
  );
};

export const SourceBadge: React.FC<{label: string}> = ({label}) => (
  <div
    style={{
      position: "absolute",
      left: 64,
      bottom: 54,
      padding: "18px 28px",
      borderRadius: 18,
        background: "rgba(4,4,8,0.82)",
      border: "1px solid rgba(255,255,255,0.22)",
      fontSize: 34,
      fontWeight: 720,
      letterSpacing: 2,
    }}
  >
    SOURCE · {label || "PRIMARY SOURCE"}
  </div>
);

export const RealSourceImage: React.FC<{src: string; label: string}> = ({src, label}) => {
  if (!src) {
    return (
      <AbsoluteFill style={{justifyContent: "center", alignItems: "center", background: "rgba(0,0,0,0.45)"}}>
        <div style={{fontSize: 54, fontWeight: 700, color: magicHour.muted}}>SOURCE CAPTURE REQUIRED</div>
      </AbsoluteFill>
    );
  }
  return (
    <>
      <Img src={resolveAsset(src)} style={{width: "100%", height: "100%", objectFit: "cover", objectPosition: "center", background: "#08070C"}} />
      <SourceBadge label={label} />
    </>
  );
};

export const EvidenceAnnotation: React.FC<{
  annotation: MotionShotProps["annotation"];
  accent?: string;
}> = ({annotation, accent = magicHour.red}) => {
  const frame = useCurrentFrame();
  if (!annotation) return null;
  if (annotation.style === "zoom") return null;
  const progress = interpolate(frame, [28, 48], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smooth,
  });
  const common: CSSProperties = {
    position: "absolute",
    left: `${annotation.x * 100}%`,
    top: `${annotation.y * 100}%`,
    width: `${annotation.width * 100}%`,
    height: `${annotation.height * 100}%`,
    pointerEvents: "none",
  };
  if (annotation.style === "underline") {
    return (
      <div style={common}>
        <svg width="100%" height="100%" viewBox="0 0 1000 120" preserveAspectRatio="none" style={{overflow: "visible"}}>
          <path
            d="M8 95 C245 80, 590 108, 992 88"
            fill="none"
            stroke={accent}
            strokeWidth="10"
            strokeLinecap="round"
            pathLength={1}
            strokeDasharray={1}
            strokeDashoffset={1 - progress}
            style={{filter: `drop-shadow(0 0 7px ${accent}99)`}}
          />
        </svg>
      </div>
    );
  }
  if (annotation.style === "arrow") {
    return (
      <div style={common}>
        <svg width="100%" height="100%" viewBox="0 0 800 600" preserveAspectRatio="none" style={{overflow: "visible"}}>
          <path
            d="M760 40 C570 80, 450 200, 150 470"
            fill="none"
            stroke={accent}
            strokeWidth="14"
            strokeLinecap="round"
            pathLength={1}
            strokeDasharray={1}
            strokeDashoffset={1 - progress}
          />
          <path d="M150 470 L235 448 L190 382" fill="none" stroke={accent} strokeWidth="14" strokeLinecap="round" opacity={progress} />
        </svg>
      </div>
    );
  }
  return (
    <div
      style={{
        ...common,
        border: `10px solid ${accent}`,
        borderRadius: 30,
        opacity: progress,
        boxShadow: `0 0 38px ${accent}88, inset 0 0 38px ${accent}30`,
      }}
    />
  );
};

export type MascotKind = "claude" | "codex" | "gemini" | "open_source";

const brandAvatarLooks: Record<MascotKind, {accent: string; label: string; logo?: string; fallback?: string}> = {
  claude: {accent: "#D77A57", label: "CLAUDE", logo: "brands/claude.svg"},
  codex: {accent: editorialPalette.blue, label: "CODEX", logo: "brands/openai.svg"},
  // No Gemini artwork is bundled. A neutral word tile avoids presenting an
  // invented symbol as an official Google mascot or mark.
  gemini: {accent: "#7768C9", label: "GEMINI", fallback: "GEMINI"},
  open_source: {
    accent: "#7D9A6B",
    label: "OPEN SOURCE",
    logo: "brands/github-brand/GitHub Logos/SVG/GitHub_Invertocat_Black.svg",
  },
};

/**
 * An original editorial character built around an unmodified product mark.
 * It is a channel-owned brand avatar, never an official company mascot.
 */
export const EditorialBrandAvatar: React.FC<{
  kind: MascotKind;
  size?: number;
  delay?: number;
  muted?: boolean;
}> = ({kind, size = 180, delay = 0, muted = false}) => {
  const frame = useCurrentFrame();
  const look = brandAvatarLooks[kind];
  const enter = interpolate(frame, [delay, delay + 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smooth,
  });
  const settle = interpolate(frame, [delay, delay + 12, delay + 24], [-2.5, 1.2, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smooth,
  });
  const iconSize = look.fallback ? size * 0.23 : size * 0.34;
  return (
    <div
      aria-label={`${look.label} editorial brand avatar`}
      style={{
        position: "relative",
        width: size,
        height: size,
        opacity: muted ? enter * 0.42 : enter,
        transform: `translateY(${(1 - enter) * 28}px) scale(${0.92 + enter * 0.08}) rotate(${settle}deg)`,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: size * 0.08,
          borderRadius: size * 0.24,
          background: "linear-gradient(145deg, rgba(244,243,238,.98), rgba(222,222,214,.94))",
          border: `${Math.max(3, size * 0.02)}px solid ${look.accent}`,
          boxShadow: `0 ${size * 0.12}px ${size * 0.3}px rgba(0,0,0,.42), inset 0 2px 0 rgba(255,255,255,.8)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          overflow: "hidden",
        }}
      >
        <div style={{position: "absolute", left: 0, right: 0, top: 0, height: size * 0.065, background: look.accent}} />
        {look.logo ? (
          <Img src={staticFile(look.logo)} style={{width: iconSize, height: iconSize, objectFit: "contain"}} />
        ) : (
          <div style={{fontSize: iconSize * 0.38, letterSpacing: 1.5, fontWeight: 900, color: editorialPalette.black}}>
            {look.fallback}
          </div>
        )}
        <div style={{position: "absolute", left: size * 0.09, right: size * 0.09, bottom: size * 0.07, textAlign: "center", color: editorialPalette.black, fontSize: Math.max(10, size * 0.075), fontWeight: 850, letterSpacing: size * 0.006}}>
          {look.label}
        </div>
      </div>
      <div style={{position: "absolute", left: size * 0.03, top: size * 0.48, width: size * 0.12, height: size * 0.035, borderRadius: 99, background: look.accent, rotate: "-14deg"}} />
      <div style={{position: "absolute", right: size * 0.03, top: size * 0.48, width: size * 0.12, height: size * 0.035, borderRadius: 99, background: look.accent, rotate: "14deg"}} />
      <div style={{position: "absolute", left: size * 0.25, bottom: size * 0.005, width: size * 0.13, height: size * 0.075, borderRadius: 99, background: look.accent}} />
      <div style={{position: "absolute", right: size * 0.25, bottom: size * 0.005, width: size * 0.13, height: size * 0.075, borderRadius: 99, background: look.accent}} />
    </div>
  );
};

// Backwards-compatible name for existing templates.
export const EditorialMascot = EditorialBrandAvatar;

export const EditorialCursor: React.FC<{cursor: MotionShotProps["cursor"]}> = ({cursor}) => {
  const frame = useCurrentFrame();
  if (!cursor) return null;
  const travel = interpolate(frame, [16, 38], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smooth,
  });
  const x = cursor.startX + (cursor.endX - cursor.startX) * travel;
  const y = cursor.startY + (cursor.endY - cursor.startY) * travel;
  const ripple = cursor.click
    ? interpolate(frame, [46, 54], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})
    : 0;
  return (
    <div style={{position: "absolute", left: `${x * 100}%`, top: `${y * 100}%`, zIndex: 20, pointerEvents: "none", translate: "-5px -5px"}}>
      {cursor.click ? <div style={{position: "absolute", left: 8, top: 8, width: 72, height: 72, borderRadius: 99, border: `4px solid ${editorialPalette.yellow}`, opacity: 1 - ripple, scale: 0.35 + ripple * 1.35}} /> : null}
      <svg width="58" height="74" viewBox="0 0 58 74" style={{filter: "drop-shadow(0 5px 7px rgba(0,0,0,.72))"}}>
        <path d="M5 4 L5 58 L19 45 L30 69 L42 63 L31 41 L51 40 Z" fill={editorialPalette.paper} stroke="#080909" strokeWidth="5" strokeLinejoin="round" />
      </svg>
    </div>
  );
};

export const EvidenceViewport: React.FC<{
  annotation: MotionShotProps["annotation"];
  cursor: MotionShotProps["cursor"];
  children: ReactNode;
  accent?: string;
}> = ({annotation, cursor, children, accent = editorialPalette.yellow}) => {
  const frame = useCurrentFrame();
  const shouldZoom = annotation?.style === "zoom";
  const zoom = shouldZoom
    ? interpolate(frame, [22, 42, 82, 104], [1, 1.42, 1.42, 1.08], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: smooth,
      })
    : 1;
  const originX = annotation ? (annotation.x + annotation.width / 2) * 100 : 50;
  const originY = annotation ? (annotation.y + annotation.height / 2) * 100 : 50;
  return (
    <div style={{position: "absolute", inset: 0, overflow: "hidden"}}>
      <div style={{position: "absolute", inset: 0, scale: zoom, transformOrigin: `${originX}% ${originY}%`}}>
        {children}
        <EvidenceAnnotation annotation={annotation} accent={accent} />
      </div>
      <EditorialCursor cursor={cursor} />
    </div>
  );
};
