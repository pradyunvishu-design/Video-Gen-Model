import {createTikTokStyleCaptions} from "@remotion/captions";
import {Audio, Video} from "@remotion/media";
import {useEffect, useMemo, useState} from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  Sequence,
  continueRender,
  delayRender,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type {EpisodeBeat, EpisodeData, LoadedEpisode, SourceAssets} from "./types";

const C = {
  bg: "#05020D",
  ink: "#FAF9FF",
  muted: "#BEB8D8",
  purple: "#8A5CFF",
  pink: "#FF3B9D",
  blue: "#4F91FF",
  red: "#FF405A",
  mint: "#5CF2C7",
};

const ease = Easing.bezier(0.16, 1, 0.3, 1);

const useEpisode = (): LoadedEpisode | null => {
  const [data, setData] = useState<LoadedEpisode | null>(null);
  const [handle] = useState(() => delayRender("Loading six-minute episode data"));
  useEffect(() => {
    Promise.all([
      fetch(staticFile("episode/magic-hour/episode.json")).then((r) => r.json() as Promise<EpisodeData>),
      fetch(staticFile("episode/magic-hour/captions.json")).then((r) => r.json()),
    ])
      .then(([episode, captions]) => {
        setData({episode, captions});
        continueRender(handle);
      })
      .catch((error: unknown) => {
        throw error;
      });
  }, [handle]);
  return data;
};

const Backdrop: React.FC = () => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const drift = interpolate(frame, [0, durationInFrames], [-120, 140], {easing: ease});
  return (
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(circle at 10% 5%, rgba(99,63,255,.42), transparent 36%), radial-gradient(circle at 90% 90%, rgba(255,48,155,.32), transparent 40%), linear-gradient(135deg,#030108 0%,#140629 52%,#07020E 100%)",
      }}
    >
      <div
        style={{
          position: "absolute",
          width: 840,
          height: 840,
          left: -260 + drift,
          top: -360 + drift * 0.25,
          borderRadius: "50%",
          background: "radial-gradient(circle,rgba(69,139,255,.32),transparent 68%)",
          filter: "blur(35px)",
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 900,
          height: 900,
          right: -340 - drift * 0.4,
          bottom: -390,
          borderRadius: "50%",
          background: "radial-gradient(circle,rgba(255,59,157,.24),transparent 68%)",
          filter: "blur(45px)",
        }}
      />
      <AbsoluteFill
        style={{
          opacity: 0.13,
          backgroundImage:
            "linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px)",
          backgroundSize: "64px 64px",
          transform: `translateY(${drift * 0.15}px)`,
        }}
      />
    </AbsoluteFill>
  );
};

const BrandMark: React.FC<{label?: string}> = ({label = "MAGIC HOUR · FIELD GUIDE"}) => (
  <div
    style={{
      position: "absolute",
      top: 42,
      left: 62,
      display: "flex",
      alignItems: "center",
      gap: 14,
      color: C.ink,
      fontSize: 19,
      fontWeight: 780,
      letterSpacing: 4,
      zIndex: 30,
    }}
  >
    <span
      style={{
        width: 18,
        height: 18,
        borderRadius: 99,
        background: `linear-gradient(135deg,${C.blue},${C.pink})`,
        boxShadow: `0 0 26px ${C.pink}`,
      }}
    />
    {label}
  </div>
);

const Progress: React.FC<{beatIndex: number}> = ({beatIndex}) => (
  <div style={{position: "absolute", right: 60, top: 49, zIndex: 30, display: "flex", gap: 7}}>
    {Array.from({length: 17}, (_, index) => (
      <div
        key={index}
        style={{
          width: index === beatIndex ? 32 : 8,
          height: 8,
          borderRadius: 9,
          background: index <= beatIndex ? `linear-gradient(90deg,${C.blue},${C.pink})` : "rgba(255,255,255,.16)",
        }}
      />
    ))}
  </div>
);

const Glass: React.FC<React.PropsWithChildren<{style?: React.CSSProperties}>> = ({children, style}) => (
  <div
    style={{
      border: "1px solid rgba(255,255,255,.17)",
      background: "linear-gradient(145deg,rgba(255,255,255,.115),rgba(255,255,255,.045))",
      boxShadow: "0 30px 90px rgba(0,0,0,.42),inset 0 1px rgba(255,255,255,.16)",
      borderRadius: 34,
      ...style,
    }}
  >
    {children}
  </div>
);

const DrawUnderline: React.FC<{width?: number; color?: string}> = ({width = 310, color = C.red}) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [8, 24], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease});
  return (
    <svg width={width} height={25} viewBox="0 0 310 25" style={{overflow: "visible"}}>
      <path
        d="M4 13 C78 6, 190 20, 305 10"
        fill="none"
        stroke={color}
        strokeWidth="5"
        strokeLinecap="round"
        pathLength={1}
        strokeDasharray={1}
        strokeDashoffset={1 - p}
        style={{filter: `drop-shadow(0 0 7px ${color})`}}
      />
    </svg>
  );
};

const Arrow: React.FC<{style?: React.CSSProperties; flip?: boolean}> = ({style, flip = false}) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [16, 34], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease});
  return (
    <svg width="240" height="150" viewBox="0 0 240 150" style={{position: "absolute", transform: flip ? "scaleX(-1)" : undefined, ...style}}>
      <path d="M15 20 C65 18,120 48,194 113" fill="none" stroke={C.red} strokeWidth="6" strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p} />
      <path d="M165 108 L198 116 L188 82" fill="none" stroke={C.red} strokeWidth="6" strokeLinecap="round" opacity={p} />
    </svg>
  );
};

const Badge: React.FC<{children: React.ReactNode; accent?: string}> = ({children, accent = C.blue}) => (
  <div
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      borderRadius: 999,
      padding: "10px 17px",
      border: "1px solid rgba(255,255,255,.16)",
      background: "rgba(3,1,12,.72)",
      fontSize: 17,
      fontWeight: 760,
      letterSpacing: 2.4,
    }}
  >
    <span style={{width: 8, height: 8, borderRadius: 9, background: accent, boxShadow: `0 0 14px ${accent}`}} />
    {children}
  </div>
);

const SourcePanel: React.FC<{
  assets: SourceAssets;
  title: string;
  url: string;
  variant: number;
}> = ({assets, title, url, variant}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const entering = spring({frame, fps, config: {damping: 22, stiffness: 130, mass: 0.9}});
  const scale = interpolate(frame, [0, 155], [1.015, 1.06], {extrapolateRight: "clamp", easing: ease});
  const src = variant % 4 === 0
    ? (assets.screen_recording ?? assets.viewport ?? assets.full_page ?? "")
    : (assets.viewport ?? assets.full_page ?? assets.screen_recording ?? "");
  const isVideo = src.endsWith(".mp4");
  return (
    <Glass
      style={{
        position: "absolute",
        left: 76,
        right: 76,
        top: 112,
        bottom: 145,
        padding: 10,
        overflow: "hidden",
        opacity: entering,
        transform: `translateY(${(1 - entering) * 36}px) scale(${0.98 + entering * 0.02})`,
      }}
    >
      <div style={{height: 46, display: "flex", alignItems: "center", padding: "0 18px", gap: 10, background: "rgba(8,5,16,.96)", borderRadius: "25px 25px 0 0"}}>
        {[C.red, "#FFC84F", "#48D99B"].map((color) => <span key={color} style={{width: 11, height: 11, borderRadius: 20, background: color}} />)}
        <div style={{marginLeft: 16, color: "rgba(255,255,255,.54)", fontSize: 16, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis"}}>{url}</div>
      </div>
      <div style={{position: "absolute", left: 10, right: 10, top: 56, bottom: 10, overflow: "hidden", borderRadius: "0 0 25px 25px", background: "#0B0910"}}>
        {isVideo ? (
          <Video src={staticFile(src)} muted loop objectFit="cover" style={{width: "100%", height: "100%", transform: `scale(${scale})`}} />
        ) : (
          <Img src={staticFile(src)} style={{width: "100%", height: "100%", objectFit: "cover", transform: `scale(${scale})`}} />
        )}
        <div style={{position: "absolute", inset: 0, background: "linear-gradient(180deg,transparent 62%,rgba(0,0,0,.66))"}} />
        {variant % 2 === 0 ? <Arrow style={{right: 170, top: 105}} flip /> : null}
        {variant % 2 === 1 ? <div style={{position: "absolute", left: 310, bottom: 105}}><DrawUnderline width={390} /></div> : null}
        <div style={{position: "absolute", left: 28, bottom: 23, maxWidth: 980}}>
          <Badge accent={C.red}>PRIMARY SOURCE · MAGIC HOUR</Badge>
          <div style={{fontSize: 29, marginTop: 10, fontWeight: 760, textShadow: "0 5px 24px #000"}}>{title}</div>
        </div>
      </div>
    </Glass>
  );
};

const GeneratedMotionPanel: React.FC<{src: string; index: number}> = ({src, index}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame, fps, config: {damping: 22, stiffness: 120}});
  return (
    <Glass style={{position: "absolute", inset: "118px 76px 148px", padding: 10, overflow: "hidden", opacity: p, transform: `scale(${0.97 + p * 0.03})`}}>
      <div style={{position: "absolute", inset: 10, borderRadius: 25, overflow: "hidden", background: C.bg}}>
        <Video src={staticFile(src)} muted loop objectFit="cover" style={{width: "100%", height: "100%"}} />
        <div style={{position: "absolute", inset: 0, background: "linear-gradient(180deg,transparent 64%,rgba(5,2,13,.72))"}} />
        <div style={{position: "absolute", left: 30, bottom: 28}}>
          <Badge accent={C.mint}>MAGIC HOUR MOTION STUDY · 0{index + 1}</Badge>
        </div>
      </div>
    </Glass>
  );
};

const AnimatedNumber: React.FC<{value: string; label: string; accent?: string; delay?: number}> = ({value, label, accent = C.blue, delay = 0}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame: frame - delay, fps, config: {damping: 18, stiffness: 115}});
  return (
    <Glass style={{padding: "30px 34px", minWidth: 275, transform: `translateY(${(1 - p) * 42}px) scale(${0.94 + p * 0.06})`, opacity: p}}>
      <div style={{fontSize: 68, lineHeight: 1, fontWeight: 870, background: `linear-gradient(100deg,${accent},#fff)`, backgroundClip: "text", color: "transparent"}}>{value}</div>
      <div style={{fontSize: 20, color: C.muted, marginTop: 14, fontWeight: 650}}>{label}</div>
    </Glass>
  );
};

const ModelMatrix: React.FC<{compact?: boolean}> = ({compact = false}) => {
  const frame = useCurrentFrame();
  const rows = [
    ["Veo 3.1", "1080p", C.mint],
    ["Kling 3.0", "4K", C.pink],
    ["Seedance 1.5", "1080p", C.blue],
    ["Seedance 2.0", "720p", C.red],
  ] as const;
  return (
    <div style={{display: "grid", gap: compact ? 10 : 15, width: "100%"}}>
      {rows.map(([model, resolution, color], index) => {
        const p = interpolate(frame, [index * 5, index * 5 + 18], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease});
        return (
          <div key={model} style={{display: "grid", gridTemplateColumns: "1fr 230px", alignItems: "center", padding: compact ? "17px 22px" : "23px 28px", borderRadius: 20, background: index === 3 ? "rgba(255,64,90,.10)" : "rgba(255,255,255,.055)", border: `1px solid ${index === 3 ? "rgba(255,64,90,.38)" : "rgba(255,255,255,.12)"}`, opacity: p, transform: `translateX(${(1 - p) * 80}px)`}}>
            <div style={{fontSize: compact ? 27 : 34, fontWeight: 760}}>{model}</div>
            <div style={{fontSize: compact ? 31 : 42, fontWeight: 850, color, textAlign: "right"}}>{resolution}</div>
          </div>
        );
      })}
    </div>
  );
};

const Flow: React.FC<{items: string[]; active?: number}> = ({items, active = items.length - 1}) => {
  const frame = useCurrentFrame();
  return (
    <div style={{display: "flex", alignItems: "center", justifyContent: "center", gap: 14, width: "100%"}}>
      {items.map((item, index) => {
        const p = interpolate(frame, [index * 8, index * 8 + 16], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease});
        return (
          <div key={item} style={{display: "contents"}}>
            <Glass style={{padding: "24px 29px", minWidth: 205, textAlign: "center", borderColor: index === active ? `${C.pink}99` : "rgba(255,255,255,.16)", opacity: p, transform: `scale(${0.88 + 0.12 * p})`}}>
              <div style={{fontSize: 16, color: index === active ? C.pink : C.blue, letterSpacing: 2.5, fontWeight: 780}}>0{index + 1}</div>
              <div style={{fontSize: 25, fontWeight: 760, marginTop: 7}}>{item}</div>
            </Glass>
            {index < items.length - 1 ? <div style={{height: 2, width: 62 * p, background: `linear-gradient(90deg,${C.blue},${C.pink})`, position: "relative"}}><span style={{position: "absolute", right: -2, top: -5, borderLeft: `10px solid ${C.pink}`, borderTop: "6px solid transparent", borderBottom: "6px solid transparent"}} /></div> : null}
          </div>
        );
      })}
    </div>
  );
};

const InputQuality: React.FC = () => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [10, 36], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease});
  return (
    <div style={{display: "grid", gridTemplateColumns: "1fr 1fr", gap: 28}}>
      <Glass style={{padding: 30, borderColor: "rgba(92,242,199,.5)"}}>
        <Badge accent={C.mint}>STRONG INPUT</Badge>
        <div style={{height: 235, marginTop: 23, borderRadius: 22, background: "radial-gradient(circle at 50% 38%,#B7A7FF 0 11%,transparent 12%),linear-gradient(90deg,transparent 46%,rgba(255,255,255,.3) 47% 53%,transparent 54%),linear-gradient(145deg,#1B1232,#090612)", position: "relative", overflow: "hidden"}}>
          <div style={{position: "absolute", left: "50%", top: "62%", width: 160, height: 100, transform: "translate(-50%,-50%)", borderRadius: "80px 80px 24px 24px", background: "rgba(183,167,255,.62)"}} />
        </div>
        <div style={{fontSize: 28, fontWeight: 750, marginTop: 18}}>Front-facing · even light · clean frame</div>
      </Glass>
      <Glass style={{padding: 30, borderColor: "rgba(255,64,90,.48)", opacity: p}}>
        <Badge accent={C.red}>FRAGILE INPUT</Badge>
        <div style={{height: 235, marginTop: 23, borderRadius: 22, background: "repeating-linear-gradient(110deg,rgba(255,64,90,.18) 0 20px,transparent 20px 42px),linear-gradient(145deg,#29101D,#090612)", position: "relative", overflow: "hidden"}}>
          <div style={{position: "absolute", left: "61%", top: "52%", width: 105, height: 190, transform: "skewX(-18deg) rotate(17deg)", borderRadius: 75, background: "rgba(255,120,150,.42)", filter: "blur(4px)"}} />
        </div>
        <div style={{fontSize: 28, fontWeight: 750, marginTop: 18}}>Profile · fast motion · occlusion</div>
      </Glass>
    </div>
  );
};

const ConceptScene: React.FC<{beat: EpisodeBeat; beatIndex: number}> = ({beat, beatIndex}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 21, stiffness: 120}});
  const titleMap = [
    "ROUTE BEFORE YOU RENDER",
    "ONE SYSTEM · THREE JOBS",
    "THE WORKFLOW, NOT THE BUTTON",
    "MODELS ARE SPECIALISTS",
    "RESOLUTION IS A HARD LIMIT",
    "COST FOLLOWS THE CHOICE",
    "DURATION + AUDIO ARE ROUTE-SPECIFIC",
    "FOUR QUESTIONS BEFORE GENERATE",
    "INPUT QUALITY SETS THE CEILING",
    "DOCUMENTED LIMIT ≠ MYSTERY",
    "PROMPT THE MOTION",
    "DESCRIPTION → ACTION",
    "USE GENERATION SELECTIVELY",
    "GENERATE · TRANSFORM · FINISH",
    "AUDIO IS PART OF ROUTING",
    "KNOW THE PRODUCT BOUNDARY",
    "THE PRACTICAL PLAYBOOK",
  ];
  const title = titleMap[beatIndex] ?? beat.purpose.toUpperCase();
  let content: React.ReactNode;
  if ([0, 3, 4].includes(beatIndex)) {
    content = <ModelMatrix compact={beatIndex !== 4} />;
  } else if ([1, 2, 12, 13, 14].includes(beatIndex)) {
    const sets = [
      ["Choose", "Generate", "Refine"],
      ["Evidence", "Route", "Create", "Edit"],
      ["Real media", "Selective AI", "Normal edit"],
      ["Generate", "Transform", "Finish"],
      ["Narration", "Music", "Final mix"],
    ];
    const selected = [1, 2, 12, 13, 14].indexOf(beatIndex);
    content = <Flow items={sets[selected]} />;
  } else if ([8, 9].includes(beatIndex)) {
    content = <InputQuality />;
  } else if ([10, 11].includes(beatIndex)) {
    content = (
      <div style={{display: "grid", gridTemplateColumns: "1fr 100px 1fr", alignItems: "center", gap: 20}}>
        <Glass style={{padding: 34, minHeight: 230}}>
          <Badge accent={C.red}>SCENE DESCRIPTION</Badge>
          <div style={{fontSize: 35, lineHeight: 1.2, fontWeight: 740, marginTop: 28}}>“A cat beside a peaceful lake.”</div>
        </Glass>
        <div style={{fontSize: 63, textAlign: "center", color: C.pink}}>→</div>
        <Glass style={{padding: 34, minHeight: 230, borderColor: "rgba(92,242,199,.5)"}}>
          <Badge accent={C.mint}>MOTION INSTRUCTION</Badge>
          <div style={{fontSize: 35, lineHeight: 1.2, fontWeight: 740, marginTop: 28}}>“The cat drinks while the camera pushes in.”</div>
        </Glass>
      </div>
    );
  } else if (beatIndex === 5) {
    content = <div style={{display: "flex", gap: 22, justifyContent: "center"}}><AnimatedNumber value="MODEL" label="Different routes, different cost" /><AnimatedNumber value="TIME" label="Longer clips consume more" accent={C.pink} delay={7} /><AnimatedNumber value="SIZE" label="Resolution changes spend" accent={C.mint} delay={14} /></div>;
  } else if (beatIndex === 6) {
    content = <div style={{display: "flex", gap: 24, justifyContent: "center"}}><AnimatedNumber value="5–10s" label="Duration depends on model" /><AnimatedNumber value="AUDIO" label="Not every route supports it" accent={C.pink} delay={10} /></div>;
  } else if (beatIndex === 7) {
    content = <Flow items={["What job?", "What ceiling?", "What input?", "What finish?"]} />;
  } else if (beatIndex === 15) {
    content = <div style={{display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24}}><AnimatedNumber value="STRONG" label="Transformations and rapid creative iteration" accent={C.mint} /><AnimatedNumber value="LIMIT" label="Not a replacement for the full editing stack" accent={C.red} delay={9} /></div>;
  } else {
    content = <Flow items={["Match job", "Protect quality", "Generate", "Finish"]} active={3} />;
  }
  return (
    <div style={{position: "absolute", left: 110, right: 110, top: 145, bottom: 160, display: "flex", flexDirection: "column", justifyContent: "center", opacity: enter, transform: `translateY(${(1 - enter) * 38}px)`}}>
      <Badge accent={beatIndex === 16 ? C.mint : C.pink}>{beat.purpose.toUpperCase()} · {String(beatIndex + 1).padStart(2, "0")}</Badge>
      <div style={{fontSize: beatIndex === 16 ? 66 : 58, lineHeight: 1, fontWeight: 880, letterSpacing: -2.4, marginTop: 20, marginBottom: 33, maxWidth: 1550}}>{title}</div>
      {content}
      <div style={{marginTop: 24}}><DrawUnderline width={beatIndex === 16 ? 470 : 325} color={beatIndex === 16 ? C.mint : C.red} /></div>
    </div>
  );
};

const BeatScene: React.FC<{
  beat: EpisodeBeat;
  beatIndex: number;
  episode: EpisodeData;
}> = ({beat, beatIndex, episode}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const micro = Math.floor(frame / (fps * 5));
  const showSource = beat.source_ids.length > 0 && (micro + beatIndex) % 2 === 0;
  const motionIndex = [2, 7, 12].indexOf(beatIndex);
  const generatedSrc = motionIndex >= 0 ? episode.generatedMotion?.[motionIndex] : undefined;
  const showGenerated = Boolean(generatedSrc) && micro % 3 === 1;
  const sourceId = beat.source_ids[micro % Math.max(1, beat.source_ids.length)];
  const source = episode.sources[sourceId];
  const assets = episode.assets[sourceId] ?? {};
  return (
    <AbsoluteFill style={{color: C.ink, fontFamily: "Inter Variable,Inter,Arial,sans-serif"}}>
      <Backdrop />
      <BrandMark label={beatIndex === 16 ? "MAGIC HOUR · DECISION RULES" : undefined} />
      <Progress beatIndex={beatIndex} />
      {showGenerated && generatedSrc ? (
        <GeneratedMotionPanel src={generatedSrc} index={motionIndex} />
      ) : showSource && source ? (
        <SourcePanel assets={assets} title={source.title} url={source.url} variant={micro + beatIndex} />
      ) : (
        <ConceptScene beat={beat} beatIndex={beatIndex} />
      )}
    </AbsoluteFill>
  );
};

const Captions: React.FC<{loaded: LoadedEpisode}> = ({loaded}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const nowMs = (frame / fps) * 1000;
  const pages = useMemo(
    () => {
      const tokens = createTikTokStyleCaptions({captions: loaded.captions, combineTokensWithinMilliseconds: 1150}).pages.flatMap((page) => page.tokens);
      const result: Array<{startMs: number; durationMs: number; tokens: typeof tokens}> = [];
      let current: typeof tokens = [];
      for (const token of tokens) {
        const tooLong = current.length > 0 && token.toMs - current[0].fromMs > 1450;
        if (current.length >= 7 || tooLong) {
          result.push({startMs: current[0].fromMs, durationMs: current[current.length - 1].toMs - current[0].fromMs, tokens: current});
          current = [];
        }
        current.push(token);
      }
      if (current.length > 0) {
        result.push({startMs: current[0].fromMs, durationMs: current[current.length - 1].toMs - current[0].fromMs, tokens: current});
      }
      return result;
    },
    [loaded.captions],
  );
  const page = pages.find((candidate, index) => {
    const next = pages[index + 1];
    return nowMs >= candidate.startMs && (!next || nowMs < next.startMs);
  });
  if (!page || nowMs < page.startMs || nowMs > page.startMs + page.durationMs + 500) return null;
  return (
    <div style={{position: "absolute", zIndex: 60, left: 190, right: 190, bottom: 28, display: "flex", justifyContent: "center", pointerEvents: "none", fontFamily: "Inter Variable,Inter,Arial,sans-serif"}}>
      <div style={{maxWidth: 1480, padding: "13px 25px 15px", borderRadius: 21, background: "rgba(4,2,11,.90)", border: "1px solid rgba(255,255,255,.12)", boxShadow: "0 12px 45px rgba(0,0,0,.5)", textAlign: "center", whiteSpace: "pre-wrap", fontSize: 35, lineHeight: 1.2, fontWeight: 790, textShadow: "0 3px 12px #000"}}>
        {page.tokens.map((token, index) => {
          const active = nowMs >= token.fromMs && nowMs < token.toMs;
          return (
            <span key={`${token.fromMs}-${index}`} style={{color: active ? C.pink : C.ink}}>
              {token.text}
            </span>
          );
        })}
      </div>
    </div>
  );
};

export const MagicHourEducationalEpisode: React.FC = () => {
  const loaded = useEpisode();
  const {fps} = useVideoConfig();
  if (!loaded) return <AbsoluteFill style={{background: C.bg}} />;
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <Audio src={staticFile("episode/magic-hour/narration.wav")} />
      {loaded.episode.beats.map((beat, beatIndex) => {
        const start = Math.max(0, Math.floor((beat.startMs / 1000) * fps));
        const nextBeat = loaded.episode.beats[beatIndex + 1];
        const end = nextBeat ? Math.ceil((nextBeat.startMs / 1000) * fps) : loaded.episode.durationSeconds * fps;
        return (
          <Sequence key={beat.id} from={start} durationInFrames={Math.max(1, end - start)} premountFor={fps}>
            <BeatScene beat={beat} beatIndex={beatIndex} episode={loaded.episode} />
          </Sequence>
        );
      })}
      <Captions loaded={loaded} />
    </AbsoluteFill>
  );
};
