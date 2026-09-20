import {TransitionSeries, linearTiming} from "@remotion/transitions";
import {fade} from "@remotion/transitions/fade";
import type {ReactNode} from "react";
import {AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig} from "remotion";
import {eased, quadraticPoint, smoothValue, softEnter} from "./aiLabsMotion";

const palette = {
  black: "#090A0B",
  panel: "#151719",
  raised: "#1C1F21",
  line: "#34383C",
  white: "#F4F3EF",
  muted: "#858A8F",
  yellow: "#EEE72B",
  minimax: "#FF6673",
  claude: "#D97757",
  green: "#72B889",
};

const Stage: React.FC<{label: string; children: ReactNode}> = ({label, children}) => (
  <AbsoluteFill style={{background: palette.black, color: palette.white, fontFamily: "Inter Variable, Inter, Arial, sans-serif", overflow: "hidden"}}>
    <div style={{position: "absolute", left: 126, top: 86, fontSize: 22, color: palette.muted, letterSpacing: 4.5, fontWeight: 720}}>
      <span style={{display: "inline-block", width: 10, height: 10, borderRadius: 20, background: palette.white, marginRight: 18}} />
      {label}
    </div>
    <div style={{position: "absolute", right: 126, bottom: 78, fontSize: 18, color: "#5F656B", letterSpacing: 3, fontWeight: 650}}>AI NEWS / REFERENCE SYSTEM</div>
    {children}
  </AbsoluteFill>
);

const Mark: React.FC<{logo: string; label: string; active?: boolean; color?: string; delay?: number; size?: number}> = ({
  logo,
  label,
  active = false,
  color = palette.white,
  delay = 0,
  size = 150,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const value = softEnter(frame, fps, delay);
  return (
    <div style={{width: size, opacity: value * (active ? 1 : 0.7), transform: `translateY(${(1 - value) * 16}px)`, textAlign: "center"}}>
      <div style={{width: size, height: size, borderRadius: 25, display: "grid", placeItems: "center", background: active ? color : palette.raised, border: active ? "none" : `2px solid ${palette.line}`}}>
        <div style={{width: active ? size * 0.54 : size * 0.42, height: active ? size * 0.54 : size * 0.42, padding: active ? 0 : 11, borderRadius: 15, background: active ? "transparent" : palette.white, display: "grid", placeItems: "center"}}>
          <Img src={staticFile(logo)} style={{width: "100%", height: "100%", objectFit: "contain"}} />
        </div>
      </div>
      <div style={{marginTop: 14, fontSize: 21, color: active ? palette.white : palette.muted, fontWeight: active ? 700 : 560}}>{label}</div>
    </div>
  );
};

const Intro: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const title = softEnter(frame, fps, 4);
  const sub = softEnter(frame, fps, 20);
  return (
    <Stage label="01 / THE LAUNCH">
      <div style={{position: "absolute", left: 300, top: 660, opacity: title, transform: `translateY(${(1 - title) * 24}px)`}}>
        <div style={{fontSize: 112, fontWeight: 610, letterSpacing: -5}}>MiniMax H3</div>
        <div style={{marginTop: 38, fontSize: 31, lineHeight: 1.35, color: palette.muted, maxWidth: 900, opacity: sub}}>A multimodal launch with a lot of claims.</div>
      </div>
      <div style={{position: "absolute", left: 2450, top: 410, display: "grid", gridTemplateColumns: "repeat(2, 150px)", gap: "48px 54px"}}>
        <Mark logo="brands/minimax.svg" label="MiniMax" active color={palette.minimax} delay={16} />
        <Mark logo="brands/claude.svg" label="Claude" delay={28} />
        <Mark logo="brands/openai.svg" label="OpenAI" delay={40} />
        <Mark logo="brands/github-brand/GitHub Logos/SVG/GitHub_Invertocat_Black.svg" label="GitHub" delay={52} />
      </div>
      <svg viewBox="0 0 3840 2160" style={{position: "absolute", inset: 0}}>
        <path d="M1750 930 C2050 720 2230 650 2460 620" fill="none" stroke={palette.line} strokeWidth="4" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - eased(frame, 36, 78)} />
      </svg>
    </Stage>
  );
};

const Network: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const draw = eased(frame, 8, 62);
  const value = softEnter(frame, fps, 6);
  const dotProgress = smoothValue(frame, 62, 142, 0, 1);
  const point = quadraticPoint([740, 1010], [1100, 710], [1530, 730], dotProgress);
  const nodes = [
    {label: "TEXT", x: 1480, y: 560, delay: 28},
    {label: "IMAGE", x: 1480, y: 860, delay: 38},
    {label: "VIDEO", x: 1480, y: 1160, delay: 48},
    {label: "AUDIO", x: 1480, y: 1460, delay: 58},
  ];
  return (
    <Stage label="02 / THE CLAIMS">
      <div style={{position: "absolute", left: 270, top: 440, width: 1880, height: 1260, borderRadius: 34, background: palette.panel, border: `2px solid ${palette.line}`, opacity: value}}>
        <div style={{position: "absolute", left: 145, top: 478}}><Mark logo="brands/minimax.svg" label="H3" active color={palette.minimax} size={190} delay={4} /></div>
        <svg viewBox="0 0 1880 1260" style={{position: "absolute", inset: 0}}>
          {[[340, 573, 900, 240], [340, 573, 900, 520], [340, 573, 900, 810], [340, 573, 900, 1090]].map(([x1, y1, x2, y2]) => (
            <path key={`${x2}-${y2}`} d={`M ${x1} ${y1} C 575 ${y1}, 670 ${y2}, ${x2} ${y2}`} fill="none" stroke={palette.line} strokeWidth="4" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - draw} />
          ))}
          <circle cx={point.x - 270} cy={point.y - 440} r="8" fill={palette.yellow} opacity={frame > 65 && frame < 146 ? 1 : 0} />
        </svg>
        {nodes.map((node) => {
          const nodeEnter = softEnter(frame, fps, node.delay);
          return <div key={node.label} style={{position: "absolute", left: node.x - 270, top: node.y - 440, width: 260, height: 118, borderRadius: 18, display: "grid", placeItems: "center", background: palette.raised, border: `2px solid ${palette.line}`, fontSize: 22, fontWeight: 730, letterSpacing: 3, opacity: nodeEnter, transform: `translateY(${(1 - nodeEnter) * 12}px)`}}>{node.label}</div>;
        })}
      </div>
      <div style={{position: "absolute", left: 2360, top: 790, width: 700}}>
        <div style={{fontSize: 29, color: palette.muted, letterSpacing: 3, fontWeight: 700}}>WHY IT'S INTERESTING</div>
        <div style={{marginTop: 34, fontSize: 55, lineHeight: 1.1, fontWeight: 570}}>One model, four output modes.</div>
      </div>
    </Stage>
  );
};

const Activity: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const rows = [["Official launch page", "SOURCE"], ["Model card and repo", "CODE"], ["Dates and limits", "FACTS"], ["Community test", "REVIEW"]];
  return (
    <Stage label="03 / THE CHECK">
      <div style={{position: "absolute", left: 340, top: 490, width: 1780, borderRadius: 30, background: palette.panel, border: `2px solid ${palette.line}`, padding: "44px 48px 46px"}}>
        <div style={{display: "flex", alignItems: "center", gap: 17, fontSize: 29, fontWeight: 700, paddingBottom: 30, borderBottom: `2px solid ${palette.line}`}}>
          <span style={{width: 27, height: 27, borderRadius: 8, background: palette.minimax, display: "grid", placeItems: "center"}}><Img src={staticFile("brands/minimax.svg")} style={{width: 16, height: 16}} /></span>
          Research activity
        </div>
        <div style={{marginTop: 24, display: "grid", gap: 10}}>
          {rows.map(([label, tag], index) => {
            const value = softEnter(frame, fps, 15 + index * 23);
            const active = frame >= 38 + index * 23 && frame < 62 + index * 23;
            return <div key={label} style={{height: 104, padding: "0 28px", display: "grid", gridTemplateColumns: "1fr 160px 35px", alignItems: "center", borderRadius: 14, background: active ? "rgba(244,243,239,.07)" : "transparent", opacity: value, transform: `translateY(${(1 - value) * 12}px)`}}>
              <span style={{fontSize: 29, fontWeight: active ? 650 : 520}}>{label}</span><span style={{fontSize: 18, color: palette.muted, fontWeight: 700, letterSpacing: 3}}>{tag}</span><span style={{fontSize: 23, color: index === 3 && frame > 106 ? palette.green : palette.muted}}>✓</span>
            </div>;
          })}
        </div>
      </div>
      <div style={{position: "absolute", left: 2390, top: 720, width: 820, paddingLeft: 40, borderLeft: `3px solid ${palette.line}`}}>
        <div style={{fontSize: 28, color: palette.muted, letterSpacing: 3, fontWeight: 700}}>EDITORIAL RULE</div>
        <div style={{fontSize: 53, lineHeight: 1.14, marginTop: 30, fontWeight: 560}}>Show the receipt before the opinion.</div>
      </div>
    </Stage>
  );
};

const Evidence: React.FC = () => {
  const frame = useCurrentFrame();
  const underline = eased(frame, 55, 104);
  const zoom = smoothValue(frame, 0, 158, 1, 1.025);
  return (
    <Stage label="04 / THE SOURCE">
      <div style={{position: "absolute", left: 270, top: 305, width: 2070, height: 1260, borderRadius: 26, overflow: "hidden", border: `3px solid ${palette.minimax}`, background: palette.white}}>
        <div style={{height: 68, background: palette.panel, display: "flex", alignItems: "center", gap: 14, padding: "0 24px"}}>{[palette.minimax, "#B1ACA4", "#6E746F"].map((color) => <span key={color} style={{width: 16, height: 16, borderRadius: 20, background: color}} />)}<span style={{fontSize: 20, color: palette.muted, marginLeft: 14}}>minimax.io / official launch</span></div>
        <Img src={staticFile("episode/h3-news/minimax_launch-minimax-h3-official-launch-viewport.png")} style={{width: "100%", height: 1192, objectFit: "cover", objectPosition: "50% 15%", transform: `scale(${zoom})`, transformOrigin: "51% 26%"}} />
        <svg viewBox="0 0 1000 100" preserveAspectRatio="none" style={{position: "absolute", left: 620, top: 205, width: 1050, height: 86}}><path d="M 18 52 C 320 40, 650 64, 980 45" fill="none" stroke={palette.yellow} strokeWidth="8" strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - underline} /></svg>
      </div>
      <div style={{position: "absolute", left: 2580, top: 630, width: 870}}>
        <div style={{fontSize: 24, color: palette.muted, letterSpacing: 3, fontWeight: 700}}>ON THE PAGE</div>
        <div style={{fontSize: 53, lineHeight: 1.12, marginTop: 30, fontWeight: 570}}>Native audiovisual output, up to 15 seconds at 2K.</div>
      </div>
    </Stage>
  );
};

const Interface: React.FC = () => {
  const frame = useCurrentFrame();
  const zoom = smoothValue(frame, 0, 158, 1.0, 1.026);
  const x = smoothValue(frame, 26, 130, 2180, 2800);
  const y = smoothValue(frame, 26, 130, 840, 1140);
  return (
    <Stage label="05 / THE INTERFACE">
      <div style={{position: "absolute", left: 310, top: 700, width: 970}}>
        <div style={{fontSize: 27, color: palette.muted, letterSpacing: 3, fontWeight: 700}}>WHAT WE SHOW</div>
        <div style={{fontSize: 63, lineHeight: 1.08, marginTop: 32, fontWeight: 570}}>Real product pages. A slow crop. One deliberate action.</div>
      </div>
      <div style={{position: "absolute", left: 1620, top: 300, width: 1940, height: 1280, borderRadius: 25, overflow: "hidden", border: `3px solid ${palette.line}`, background: palette.panel}}>
        <Img src={staticFile("episode/h3-news/minimax_repo-minimax-h3-official-repository-and-model-details-viewport.png")} style={{width: "100%", height: "100%", objectFit: "cover", objectPosition: "50% 28%", transform: `scale(${zoom})`, transformOrigin: "55% 44%"}} />
        <div style={{position: "absolute", left: 25, top: 23, padding: "11px 18px", borderRadius: 11, background: "rgba(9,10,11,.92)", fontSize: 18, letterSpacing: 2, fontWeight: 700}}>REAL UI · 1080P</div>
      </div>
      <div style={{position: "absolute", left: x, top: y, filter: "drop-shadow(0 6px 6px rgba(0,0,0,.5))"}}><svg width="54" height="72" viewBox="0 0 58 74"><path d="M5 4 L5 58 L19 45 L30 69 L42 63 L31 41 L51 40 Z" fill={palette.white} stroke={palette.black} strokeWidth="5" strokeLinejoin="round" /></svg></div>
    </Stage>
  );
};

const Verdict: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const left = softEnter(frame, fps, 10);
  const right = softEnter(frame, fps, 34);
  const underline = eased(frame, 86, 136);
  return (
    <Stage label="06 / THE VERDICT">
      <div style={{position: "absolute", left: 330, top: 560, width: 1190, opacity: left, transform: `translateY(${(1 - left) * 16}px)`}}>
        <div style={{fontSize: 22, color: palette.muted, letterSpacing: 4, fontWeight: 700}}>THE CLAIM</div>
        <div style={{fontSize: 67, lineHeight: 1.08, marginTop: 38, fontWeight: 540}}>“One model replaces everything.”</div>
      </div>
      <div style={{position: "absolute", left: 2040, top: 520, width: 1350, padding: "64px 70px", borderRadius: 28, background: palette.raised, border: `2px solid ${palette.line}`, opacity: right, transform: `translateY(${(1 - right) * 16}px)`}}>
        <div style={{fontSize: 22, color: palette.white, letterSpacing: 4, fontWeight: 700}}>THE EVIDENCE</div>
        <div style={{fontSize: 60, lineHeight: 1.1, marginTop: 38, fontWeight: 580}}>15-second output. 2K ceiling. Open weights planned.</div>
      </div>
      <div style={{position: "absolute", left: 330, top: 1260, fontSize: 83, letterSpacing: -3, fontWeight: 610}}>Proof beats hype.</div>
      <svg viewBox="0 0 1000 90" preserveAspectRatio="none" style={{position: "absolute", left: 320, top: 1380, width: 935, height: 72}}><path d="M 18 35 C 300 24, 620 48, 980 30" fill="none" stroke={palette.yellow} strokeWidth="7" strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - underline} /></svg>
    </Stage>
  );
};

export const EditorialProof30sV4: React.FC = () => (
  <TransitionSeries>
    <TransitionSeries.Sequence durationInFrames={159}><Intro /></TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: 6})} />
    <TransitionSeries.Sequence durationInFrames={159}><Network /></TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: 6})} />
    <TransitionSeries.Sequence durationInFrames={158}><Activity /></TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: 6})} />
    <TransitionSeries.Sequence durationInFrames={158}><Evidence /></TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: 6})} />
    <TransitionSeries.Sequence durationInFrames={158}><Interface /></TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: 6})} />
    <TransitionSeries.Sequence durationInFrames={158}><Verdict /></TransitionSeries.Sequence>
  </TransitionSeries>
);
