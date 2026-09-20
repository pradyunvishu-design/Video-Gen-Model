import {TransitionSeries, linearTiming} from "@remotion/transitions";
import {fade} from "@remotion/transitions/fade";
import type {ReactNode} from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const colors = {
  black: "#0B0C0D",
  panel: "#151617",
  raised: "#1C1E20",
  line: "#34373A",
  white: "#F2F1ED",
  muted: "#86898D",
  yellow: "#EEE72B",
  minimax: "#FF6673",
  claude: "#D97757",
};

const smooth = Easing.bezier(0.22, 1, 0.36, 1);

const enter = (frame: number, start: number, end = start + 18) =>
  interpolate(frame, [start, end], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smooth,
  });

const Shell: React.FC<{
  children: ReactNode;
  chapter: string;
  caption: string;
  important?: boolean;
}> = ({children, chapter, caption, important = false}) => (
  <AbsoluteFill
    style={{
      overflow: "hidden",
      background: colors.black,
      color: colors.white,
      fontFamily: "Inter Variable, Inter, Arial, sans-serif",
    }}
  >
    <div
      style={{
        position: "absolute",
        left: 150,
        top: 92,
        display: "flex",
        alignItems: "center",
        gap: 22,
        color: colors.muted,
        fontSize: 25,
        fontWeight: 700,
        letterSpacing: 5,
      }}
    >
      <span style={{width: 10, height: 10, borderRadius: 20, background: important ? colors.yellow : colors.white}} />
      {chapter}
    </div>
    <AbsoluteFill style={{padding: "160px 150px 205px"}}>{children}</AbsoluteFill>
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 62,
        textAlign: "center",
        color: colors.white,
        fontSize: 31,
        fontWeight: 580,
        letterSpacing: -0.4,
      }}
    >
      {caption}
    </div>
  </AbsoluteFill>
);

const LogoBadge: React.FC<{
  logo: string;
  label: string;
  background?: string;
  active?: boolean;
  delay?: number;
  size?: number;
}> = ({logo, label, background = colors.white, active = false, delay = 0, size = 210}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const value = spring({
    frame: frame - delay,
    fps,
    config: {damping: 25, stiffness: 125, mass: 0.8},
  });
  return (
    <div
      style={{
        width: size,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 18,
        opacity: value * (active ? 1 : 0.72),
        transform: `translateY(${(1 - value) * 28}px) scale(${0.94 + value * 0.06})`,
      }}
    >
      <div
        style={{
          width: size,
          height: size,
          borderRadius: size * 0.22,
          background: active ? background : colors.raised,
          border: active ? "none" : `2px solid ${colors.line}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: active ? "0 18px 50px rgba(0,0,0,.3)" : "none",
        }}
      >
        <div
          style={{
            width: size * 0.48,
            height: size * 0.48,
            padding: active ? 0 : size * 0.07,
            borderRadius: size * 0.12,
            background: active ? "transparent" : colors.white,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Img src={staticFile(logo)} style={{width: "100%", height: "100%", objectFit: "contain"}} />
        </div>
      </div>
      <div style={{fontSize: 27, fontWeight: active ? 720 : 570, color: active ? colors.white : colors.muted}}>{label}</div>
    </div>
  );
};

const IntroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const title = enter(frame, 4, 28);
  return (
    <Shell chapter="THE LAUNCH" caption="MiniMax just released H3. Here's what actually matters.">
      <div style={{height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center"}}>
        <div style={{opacity: title, transform: `translateY(${(1 - title) * 24}px)`, fontSize: 86, fontWeight: 590, letterSpacing: -3}}>
          MiniMax H3
        </div>
        <div style={{display: "flex", alignItems: "flex-start", gap: 72, marginTop: 110}}>
          <LogoBadge logo="brands/minimax.svg" label="MiniMax" background={colors.minimax} active delay={18} />
          <LogoBadge logo="brands/claude.svg" label="Claude" delay={28} />
          <LogoBadge logo="brands/openai.svg" label="OpenAI" delay={38} />
          <LogoBadge logo="brands/github-brand/GitHub Logos/SVG/GitHub_Invertocat_Black.svg" label="GitHub" delay={48} />
        </div>
      </div>
    </Shell>
  );
};

const NetworkScene: React.FC = () => {
  const frame = useCurrentFrame();
  const draw = enter(frame, 10, 72);
  const travel = interpolate(frame, [40, 145], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic)});
  return (
    <Shell chapter="THE CLAIMS" caption="One model is being pitched as text, image, video, and audio in one system.">
      <div style={{position: "relative", width: 2580, height: 1080, margin: "70px auto 0"}}>
        <div style={{position: "absolute", left: 980, top: 300}}>
          <LogoBadge logo="brands/minimax.svg" label="H3" background={colors.minimax} active delay={6} size={260} />
        </div>
        <svg viewBox="0 0 2580 1080" style={{position: "absolute", inset: 0}}>
          {[
            "M1110 430 C810 260 540 235 320 235",
            "M1110 430 C800 610 560 765 320 790",
            "M1370 430 C1680 260 1915 235 2260 235",
            "M1370 430 C1670 610 1915 765 2260 790",
          ].map((path) => (
            <path key={path} d={path} fill="none" stroke={colors.line} strokeWidth="5" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - draw} />
          ))}
          <circle cx={320 + travel * 1940} cy={235} r="11" fill={colors.yellow} opacity={travel < 0.52 ? 1 : 0} />
          <circle cx={2260 - (travel - 0.52) * 1900} cy={790} r="11" fill={colors.yellow} opacity={travel >= 0.52 ? 1 : 0} />
        </svg>
        {[
          {label: "TEXT", left: 170, top: 130, delay: 22},
          {label: "IMAGE", left: 170, top: 690, delay: 32},
          {label: "VIDEO", left: 2110, top: 130, delay: 42},
          {label: "AUDIO", left: 2110, top: 690, delay: 52},
        ].map((item) => {
          const value = enter(frame, item.delay, item.delay + 16);
          return (
            <div key={item.label} style={{position: "absolute", left: item.left, top: item.top, opacity: value, transform: `scale(${0.94 + value * 0.06})`}}>
              <div style={{width: 300, height: 190, borderRadius: 28, background: colors.panel, border: `2px solid ${colors.line}`, display: "grid", placeItems: "center", fontSize: 29, fontWeight: 700, letterSpacing: 4}}>
                {item.label}
              </div>
            </div>
          );
        })}
      </div>
    </Shell>
  );
};

const ActivityScene: React.FC = () => {
  const frame = useCurrentFrame();
  const rows = [
    ["Official launch page opened", "SOURCE"],
    ["Repository and model card checked", "CODE"],
    ["Limits and dates extracted", "FACTS"],
    ["Community tests compared", "REVIEW"],
  ];
  return (
    <Shell chapter="THE CHECK" caption="The story starts with receipts, not a generated picture of a robot.">
      <div style={{width: 2200, margin: "135px auto 0", borderRadius: 34, background: colors.panel, border: `2px solid ${colors.line}`, padding: "55px 68px", boxShadow: "0 36px 90px rgba(0,0,0,.32)"}}>
        <div style={{display: "flex", alignItems: "center", justifyContent: "space-between", paddingBottom: 38, borderBottom: `2px solid ${colors.line}`}}>
          <div style={{display: "flex", alignItems: "center", gap: 22, fontSize: 35, fontWeight: 720}}>
            <span style={{width: 42, height: 42, borderRadius: 12, background: colors.minimax, display: "grid", placeItems: "center"}}>
              <Img src={staticFile("brands/minimax.svg")} style={{width: 25, height: 25}} />
            </span>
            Research activity
          </div>
          <div style={{fontSize: 26, color: colors.muted}}># evidence</div>
        </div>
        <div style={{marginTop: 25, display: "grid", gap: 16}}>
          {rows.map(([label, tag], index) => {
            const value = enter(frame, 16 + index * 24, 32 + index * 24);
            const active = frame >= 26 + index * 24 && frame < 50 + index * 24;
            return (
              <div
                key={label}
                style={{
                  height: 132,
                  padding: "0 34px",
                  borderRadius: 20,
                  background: active ? "rgba(242,241,237,.075)" : "transparent",
                  border: `2px solid ${active ? "rgba(242,241,237,.10)" : "transparent"}`,
                  display: "grid",
                  gridTemplateColumns: "1fr 180px 90px",
                  alignItems: "center",
                  opacity: 0.24 + value * 0.76,
                  transform: `translateY(${(1 - value) * 14}px)`,
                }}
              >
                <div style={{fontSize: 33, fontWeight: active ? 650 : 500}}>{label}</div>
                <div style={{color: colors.muted, fontSize: 23, fontWeight: 700, letterSpacing: 3}}>{tag}</div>
                <div style={{fontSize: 28, color: index === 3 && frame > 112 ? colors.yellow : colors.muted}}>✓</div>
              </div>
            );
          })}
        </div>
      </div>
    </Shell>
  );
};

const EvidenceScene: React.FC = () => {
  const frame = useCurrentFrame();
  const underline = enter(frame, 52, 92);
  const zoom = interpolate(frame, [0, 158], [1.0, 1.035], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic)});
  return (
    <Shell chapter="THE SOURCE" caption="The launch page makes the exact claim: native audiovisual output, up to 15 seconds at 2K." important>
      <div style={{position: "relative", height: 1460, marginTop: 4, overflow: "hidden", borderRadius: 28, background: colors.white, border: `3px solid ${colors.line}`}}>
        <div style={{height: 82, background: colors.panel, display: "flex", alignItems: "center", gap: 16, padding: "0 28px"}}>
          {[colors.claude, "#B8B4AA", "#73766F"].map((color) => <span key={color} style={{width: 20, height: 20, borderRadius: 30, background: color}} />)}
          <span style={{marginLeft: 20, color: colors.muted, fontSize: 25}}>minimax.io / official launch</span>
        </div>
        <Img
          src={staticFile("episode/h3-news/minimax_launch-minimax-h3-official-launch-viewport.png")}
          style={{position: "absolute", left: 0, top: 82, width: "100%", height: 1378, objectFit: "cover", objectPosition: "50% 14%", transform: `scale(${zoom})`}}
        />
        <svg viewBox="0 0 1000 90" preserveAspectRatio="none" style={{position: "absolute", left: 1040, top: 238, width: 1160, height: 120}}>
          <path d="M20 60 C280 52 620 70 980 54" fill="none" stroke={colors.yellow} strokeWidth="8" strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - underline} />
        </svg>
        <div style={{position: "absolute", left: 34, bottom: 30, padding: "13px 22px", borderRadius: 14, background: "rgba(11,12,13,.92)", color: colors.white, fontSize: 23, fontWeight: 680, letterSpacing: 2}}>SOURCE · MINIMAX</div>
      </div>
    </Shell>
  );
};

const InterfaceScene: React.FC = () => {
  const frame = useCurrentFrame();
  const zoom = interpolate(frame, [0, 158], [1.015, 1.075], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic)});
  const cursor = interpolate(frame, [22, 118], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic)});
  return (
    <Shell chapter="THE INTERFACE" caption="A slow crop and one deliberate cursor move are enough. No shake, no fake browser motion.">
      <div style={{position: "relative", height: 1460, overflow: "hidden", borderRadius: 30, border: `3px solid ${colors.line}`, background: colors.panel}}>
        <Img
          src={staticFile("episode/h3-news/minimax_repo-minimax-h3-official-repository-and-model-details-viewport.png")}
          style={{width: "100%", height: "100%", objectFit: "cover", objectPosition: "50% 28%", transform: `scale(${zoom})`, transformOrigin: "52% 42%"}}
        />
        <div style={{position: "absolute", left: 38, top: 34, padding: "14px 23px", borderRadius: 14, background: "rgba(11,12,13,.92)", fontSize: 23, fontWeight: 670, letterSpacing: 2}}>REAL UI · 1080P</div>
        <div style={{position: "absolute", left: `${33 + cursor * 27}%`, top: `${25 + cursor * 34}%`, filter: "drop-shadow(0 5px 6px rgba(0,0,0,.55))"}}>
          <svg width="62" height="82" viewBox="0 0 58 74"><path d="M5 4 L5 58 L19 45 L30 69 L42 63 L31 41 L51 40 Z" fill={colors.white} stroke={colors.black} strokeWidth="5" strokeLinejoin="round" /></svg>
        </div>
      </div>
    </Shell>
  );
};

const VerdictScene: React.FC = () => {
  const frame = useCurrentFrame();
  const claim = enter(frame, 8, 30);
  const evidence = enter(frame, 35, 58);
  const underline = enter(frame, 88, 126);
  return (
    <Shell chapter="THE VERDICT" caption="The useful takeaway isn't that everything changed. It's that the evidence got more interesting." important>
      <div style={{width: 2450, margin: "160px auto 0"}}>
        <div style={{display: "grid", gridTemplateColumns: "1fr 1fr", gap: 34}}>
          <div style={{height: 460, padding: 62, borderRadius: 30, background: colors.panel, border: `2px solid ${colors.line}`, opacity: 0.35 + claim * 0.45, transform: `translateY(${(1 - claim) * 22}px)`}}>
            <div style={{fontSize: 24, fontWeight: 730, color: colors.muted, letterSpacing: 4}}>THE CLAIM</div>
            <div style={{fontSize: 62, lineHeight: 1.1, fontWeight: 570, marginTop: 75}}>“The one model that replaces everything.”</div>
          </div>
          <div style={{height: 460, padding: 62, borderRadius: 30, background: colors.raised, border: `2px solid rgba(242,241,237,.18)`, opacity: evidence, transform: `translateY(${(1 - evidence) * 22}px)`}}>
            <div style={{fontSize: 24, fontWeight: 730, color: colors.white, letterSpacing: 4}}>THE EVIDENCE</div>
            <div style={{fontSize: 62, lineHeight: 1.1, fontWeight: 620, marginTop: 75}}>15-second output. 2K ceiling. Open weights planned.</div>
          </div>
        </div>
        <div style={{position: "relative", marginTop: 126, textAlign: "center", fontSize: 82, fontWeight: 650, letterSpacing: -3}}>
          Proof beats hype.
          <svg viewBox="0 0 1000 70" preserveAspectRatio="none" style={{position: "absolute", left: 760, top: 82, width: 930, height: 64}}>
            <path d="M15 30 C300 20 610 42 985 24" fill="none" stroke={colors.yellow} strokeWidth="7" strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - underline} />
          </svg>
        </div>
      </div>
    </Shell>
  );
};

export const EditorialProof30s: React.FC = () => (
  <TransitionSeries>
    <TransitionSeries.Sequence durationInFrames={159}><IntroScene /></TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: 10})} />
    <TransitionSeries.Sequence durationInFrames={159}><NetworkScene /></TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: 10})} />
    <TransitionSeries.Sequence durationInFrames={158}><ActivityScene /></TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: 10})} />
    <TransitionSeries.Sequence durationInFrames={158}><EvidenceScene /></TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: 10})} />
    <TransitionSeries.Sequence durationInFrames={158}><InterfaceScene /></TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: 10})} />
    <TransitionSeries.Sequence durationInFrames={158}><VerdictScene /></TransitionSeries.Sequence>
  </TransitionSeries>
);
