import {Audio} from "@remotion/media";
import {
  AbsoluteFill,
  Easing,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import episodeJson from "../../public/episode/h3-10m/episode.json";
import {SourceCredit} from "./SourceCredit";

type Beat = {
  id: string;
  purpose: string;
  narration: string;
  source_ids: string[];
  broll: string[];
  overlay: string;
  accent: string;
  startMs: number;
  endMs: number;
};

type Episode = {
  episodeId: string;
  title: string;
  durationSeconds: number;
  beats: Beat[];
  sources: Record<string, {title: string; url: string; publisher: string}>;
  assets: Record<string, {viewport?: string; screen_recording?: string}>;
  broll: Record<string, string>;
};

type Cue = {
  kind: "underline" | "arrow" | "spotlight";
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
};

type VisualEntry =
  | {kind: "image"; src: string; publisher: string; sourceId: string}
  | {kind: "video"; src: string; publisher: string; assetId: string};

const palette = {
  black: "#050505",
  white: "#f7f5ef",
  gray: "#b8b8b8",
  slate: "#8E9B95",
  red: "#ef4a52",
  coral: "#ff665e",
};
const ease = Easing.bezier(0.16, 1, 0.3, 1);
const SHOT_SECONDS = 5;

const SemanticOverlay: React.FC<{beat: Beat}> = ({beat}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [7, 17], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease});
  const underline = interpolate(frame, [24, 40], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease});
  const underlineIsMeaningful = ["hardware", "resolution", "not_fully_local", "license"].includes(beat.purpose);
  return (
    <div style={{position: "absolute", left: 58, bottom: 58, zIndex: 30, width: 1120, opacity, fontFamily: "Inter Variable,Inter,Arial,sans-serif"}}>
      <div style={{display: "inline-block", padding: "18px 24px 16px", background: "rgba(4,4,4,.87)", borderLeft: `3px solid ${palette.slate}`, boxShadow: "0 16px 50px rgba(0,0,0,.38)"}}>
        <div style={{fontSize: 43, lineHeight: 1.02, letterSpacing: -1.6, fontWeight: 900, color: palette.white}}>{beat.overlay}</div>
        <div style={{position: "relative", marginTop: 11, display: "inline-block", color: palette.gray, fontSize: 19, fontWeight: 730, letterSpacing: 2.2}}>
          {beat.accent}
          {underlineIsMeaningful ? <div style={{position: "absolute", left: 0, right: 0, bottom: -8, height: 3, borderRadius: 2, background: palette.red, transformOrigin: "left center", transform: `scaleX(${underline})`}} /> : null}
        </div>
      </div>
    </div>
  );
};

const sourceCueFor = (beat: Beat, sourceId?: string): Cue | null => {
  if (sourceId === "minimax_launch" && beat.purpose === "open_release") {
    return {kind: "underline", x: .288, y: .205, width: .405, height: .035, label: "OPEN SOURCE ANNOUNCEMENT"};
  }
  if (sourceId === "minimax_launch" && beat.purpose === "resolution") {
    return {kind: "spotlight", x: .29, y: .72, width: .47, height: .205, label: "PUBLISHED OUTPUT SPECIFICATION"};
  }
  if (sourceId === "comfy_workflow" && beat.purpose === "comfyui") {
    return {kind: "arrow", x: .46, y: .31, width: .12, height: .12, label: "OFFICIAL WORKFLOW FILE"};
  }
  return null;
};

const videoCueFor = (beat: Beat, assetId?: string): Cue | null => {
  if (beat.purpose === "quality" && assetId === "t2va_2k") {
    return {kind: "arrow", x: .49, y: .31, width: .09, height: .16, label: "SUBJECT DETAILS HOLD ACROSS THE DEMO EDIT"};
  }
  if (beat.purpose === "quality" && assetId === "i2va_2k") {
    return {kind: "spotlight", x: .36, y: .55, width: .28, height: .25, label: "FOREGROUND BOWL AND TABLE LAYOUT"};
  }
  return null;
};

const DirectionalCue: React.FC<{cue: Cue}> = ({cue}) => {
  const frame = useCurrentFrame();
  const reveal = interpolate(frame, [34, 50], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease});
  const left = cue.x * 1920;
  const top = cue.y * 1080;
  const width = cue.width * 1920;
  const height = cue.height * 1080;
  if (cue.kind === "underline") {
    return <div style={{position: "absolute", zIndex: 26, left, top: top + height + 6, width, height: 4, borderRadius: 3, background: palette.red, transformOrigin: "left center", transform: `scaleX(${reveal})`}} />;
  }
  if (cue.kind === "spotlight") {
    return (
      <div style={{position: "absolute", inset: 0, zIndex: 24, pointerEvents: "none", opacity: reveal}}>
        <div style={{position: "absolute", inset: 0, background: "rgba(0,0,0,.44)", clipPath: `polygon(0 0,100% 0,100% 100%,0 100%,0 ${top}px,${left}px ${top}px,${left}px ${top + height}px,${left + width}px ${top + height}px,${left + width}px ${top}px,0 ${top}px)`}} />
        <div style={{position: "absolute", left, top, width, height, border: `3px solid ${palette.red}`, borderRadius: 10, boxShadow: "0 0 0 1px rgba(255,255,255,.15) inset"}} />
        <div style={{position: "absolute", left, top: Math.max(24, top - 42), padding: "8px 11px", background: "rgba(0,0,0,.86)", color: palette.white, fontSize: 16, fontWeight: 800, letterSpacing: 1.1}}>{cue.label}</div>
      </div>
    );
  }
  const startX = Math.max(90, left - 250);
  const startY = Math.max(100, top - 125);
  const endX = left + width / 2;
  const endY = top + height / 2;
  return (
    <svg width="1920" height="1080" viewBox="0 0 1920 1080" style={{position: "absolute", inset: 0, zIndex: 26, overflow: "visible", pointerEvents: "none", opacity: reveal}}>
      <defs>
        <marker id="semantic-arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto"><path d="M0,0 L12,6 L0,12 z" fill={palette.red} /></marker>
      </defs>
      <path d={`M ${startX} ${startY} Q ${(startX + endX) / 2} ${Math.min(startY, endY) - 60} ${endX} ${endY}`} fill="none" stroke={palette.red} strokeWidth="5" strokeLinecap="round" markerEnd="url(#semantic-arrow)" pathLength="1" strokeDasharray="1" strokeDashoffset={1 - reveal} />
      <g transform={`translate(${startX - 8} ${startY - 45})`}>
        <rect width="390" height="39" rx="6" fill="rgba(0,0,0,.86)" />
        <text x="12" y="26" fill={palette.white} fontSize="16" fontWeight="800" letterSpacing="1">{cue.label}</text>
      </g>
    </svg>
  );
};

const VideoFrame: React.FC<{src: string; beat: Beat; assetId: string}> = ({src, beat, assetId}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const opacity = interpolate(frame, [0, 7, fps * SHOT_SECONDS - 7, fps * SHOT_SECONDS], [0, 1, 1, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  const scale = interpolate(frame, [0, fps * SHOT_SECONDS], [1, 1.018], {extrapolateRight: "clamp", easing: ease});
  return (
    <AbsoluteFill style={{background: palette.black, opacity, overflow: "hidden"}}>
      <OffthreadVideo src={staticFile(src)} muted style={{width: "100%", height: "100%", objectFit: "cover", transform: `scale(${scale})`}} />
      <AbsoluteFill style={{background: "linear-gradient(180deg,rgba(0,0,0,.05),transparent 52%,rgba(0,0,0,.48))"}} />
      <SourceCredit label="Official MiniMax H3 sample" placement="topRight" />
      {videoCueFor(beat, assetId) ? <DirectionalCue cue={videoCueFor(beat, assetId)!} /> : null}
      <SemanticOverlay beat={beat} />
    </AbsoluteFill>
  );
};

const SourceFrame: React.FC<{src: string; beat: Beat; publisher: string; sourceId: string}> = ({src, beat, publisher, sourceId}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const opacity = interpolate(frame, [0, 7, fps * SHOT_SECONDS - 7, fps * SHOT_SECONDS], [0, 1, 1, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  const scale = interpolate(frame, [0, fps * SHOT_SECONDS], [1, 1.014], {extrapolateRight: "clamp", easing: ease});
  return (
    <AbsoluteFill style={{background: "#0a0a0a", opacity, overflow: "hidden"}}>
      <Img src={staticFile(src)} style={{width: "100%", height: "100%", objectFit: "contain", transform: `scale(${scale})`}} />
      <AbsoluteFill style={{background: "linear-gradient(90deg,transparent 62%,rgba(0,0,0,.17)),linear-gradient(180deg,transparent 58%,rgba(0,0,0,.52))"}} />
      <SourceCredit label={publisher} placement="topRight" />
      {sourceCueFor(beat, sourceId) ? <DirectionalCue cue={sourceCueFor(beat, sourceId)!} /> : null}
      <SemanticOverlay beat={beat} />
    </AbsoluteFill>
  );
};

const facts: Record<string, [string, string, string]> = {
  hook: ["OPEN WEIGHTS", "NATIVE AUDIO", "COMFYUI DAY ZERO"],
  what_it_is: ["4–15 SEC", "UP TO 12 REFERENCES", "24 FPS"],
  native_audio: ["VIDEO", "+", "STEREO AUDIO"],
  open_release: ["DOWNLOAD", "FINE-TUNE", "BUILD AROUND IT"],
  comfyui: ["TEXT", "KEYFRAMES", "REFERENCES"],
  hardware: ["123.6 GB", "66% LESS", "42.5 GB"],
  quality: ["COHERENT MOTION", "STRONG REFERENCES", "REAL CAVEATS"],
  resolution: ["768P BASE", "CONTEXT", "2K REGEN"],
  not_fully_local: ["BASE: LOCAL", "CONTEXT IR: HOSTED", "2K REGEN: HOSTED"],
  community: ["KEYFRAMES", "PREVIEWS", "LoRAs"],
  workflow: ["PREVIEW", "LOCK", "FINISH"],
  who_for: ["BUILDERS", "STUDIOS", "RESEARCHERS"],
  why_now: ["MODEL", "TOOLS", "INFRASTRUCTURE"],
  verdict: ["POWERFUL", "OPEN BASE", "HYBRID SYSTEM"],
};

const EvidenceFrame: React.FC<{beat: Beat}> = ({beat}) => {
  const frame = useCurrentFrame();
  const items = facts[beat.purpose] ?? ["WHAT SHIPPED", "WHAT WORKS", "WHAT REMAINS"];
  return (
    <AbsoluteFill style={{background: palette.black, color: palette.white, padding: "120px 126px", fontFamily: "Inter Variable,Inter,Arial,sans-serif"}}>
      <div style={{fontSize: 19, letterSpacing: 3.5, fontWeight: 800, color: palette.slate}}>MINIMAX H3 · EVIDENCE CHECK</div>
      <div style={{marginTop: 22, maxWidth: 1500, fontSize: 84, lineHeight: .96, letterSpacing: -4.5, fontWeight: 920}}>{beat.overlay}</div>
      <div style={{display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 22, marginTop: 80}}>
        {items.map((item, index) => {
          const progress = interpolate(frame, [9 + index * 7, 22 + index * 7], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease});
          return <div key={item} style={{height: 250, padding: 28, display: "flex", alignItems: "flex-end", borderTop: `4px solid ${index === 1 ? palette.red : "#333"}`, background: index === 1 ? "#15110a" : "#101010", opacity: progress, transform: `translateY(${(1-progress)*14}px)`}}><div style={{fontSize: item.length > 18 ? 31 : 40, lineHeight: 1.02, fontWeight: 850}}>{item}</div></div>;
        })}
      </div>
      <div style={{position: "absolute", left: 126, bottom: 72, color: palette.gray, fontSize: 21, fontWeight: 650}}>{beat.accent}</div>
    </AbsoluteFill>
  );
};

const MetricFrame: React.FC<{beat: Beat}> = ({beat}) => {
  const frame = useCurrentFrame();
  const reduction = interpolate(frame, [16, 50], [0, 66], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease});
  const line = interpolate(frame, [24, 54], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease});
  return (
    <AbsoluteFill style={{background: palette.black, color: palette.white, padding: "116px 132px", fontFamily: "Inter Variable,Inter,Arial,sans-serif"}}>
      <div style={{fontSize: 18, letterSpacing: 3.4, fontWeight: 820, color: palette.slate}}>{beat.overlay} · PUBLISHED COMFYUI FIGURES · NOT INDEPENDENTLY VERIFIED</div>
      <div style={{display: "grid", gridTemplateColumns: "1fr 240px 1fr", alignItems: "center", marginTop: 126}}>
        <div><div style={{fontSize: 28, color: palette.gray}}>ORIGINAL FOOTPRINT</div><div style={{fontSize: 132, letterSpacing: -8, fontWeight: 920}}>123.6<span style={{fontSize: 50, letterSpacing: -2}}> GB</span></div></div>
        <svg width="240" height="120"><path d="M15 60 H210" stroke={palette.red} strokeWidth="7" pathLength="1" strokeDasharray="1" strokeDashoffset={1 - line} markerEnd="url(#metric-arrow)"/><defs><marker id="metric-arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto"><path d="M0,0 L12,6 L0,12 z" fill={palette.red}/></marker></defs></svg>
        <div><div style={{fontSize: 28, color: palette.gray}}>OPTIMIZED CLAIM</div><div style={{fontSize: 132, letterSpacing: -8, fontWeight: 920}}>42.5<span style={{fontSize: 50, letterSpacing: -2}}> GB</span></div></div>
      </div>
      <div style={{position: "absolute", left: 132, bottom: 102, fontSize: 56, fontWeight: 900, color: palette.white}}><span style={{color: palette.red}}>{Math.round(reduction)}%</span> reported reduction</div>
    </AbsoluteFill>
  );
};

const FlowFrame: React.FC<{beat: Beat}> = ({beat}) => {
  const frame = useCurrentFrame();
  const steps = beat.purpose === "creator_test" ? ["ONE SUBJECT", "ONE CAMERA MOVE", "ONE SOUND CUE"] : beat.purpose === "decision" ? ["PRIVACY", "CONTROL", "SPEED"] : ["PREVIEW LOW", "LOCK REFERENCES", "FINISH HIGH"];
  return (
    <AbsoluteFill style={{background: palette.black, color: palette.white, padding: "112px 128px", fontFamily: "Inter Variable,Inter,Arial,sans-serif"}}>
      <div style={{fontSize: 19, letterSpacing: 3.4, fontWeight: 820, color: palette.slate}}>WORKFLOW · DERIVED FROM THE OFFICIAL TEMPLATE</div>
      <div style={{fontSize: 76, letterSpacing: -4, lineHeight: .96, fontWeight: 920, marginTop: 22}}>{beat.overlay}</div>
      <div style={{display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 70, marginTop: 126, position: "relative"}}>
        <div style={{position: "absolute", top: 82, left: 170, right: 170, height: 3, background: "#343636"}} />
        {steps.map((step, index) => {
          const enter = interpolate(frame, [10 + index * 12, 24 + index * 12], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease});
          return <div key={step} style={{position: "relative", minHeight: 250, padding: "32px 28px", border: `1px solid ${index === 1 ? palette.red : "#343636"}`, background: "#111212", opacity: enter, transform: `translateY(${(1 - enter) * 14}px)`}}><div style={{width: 48, height: 48, borderRadius: 30, display: "grid", placeItems: "center", background: index === 1 ? palette.red : "#242626", fontSize: 22, fontWeight: 900}}>{index + 1}</div><div style={{position: "absolute", left: 28, bottom: 28, fontSize: 36, fontWeight: 880}}>{step}</div></div>;
        })}
      </div>
    </AbsoluteFill>
  );
};

const BoundaryFrame: React.FC<{beat: Beat}> = ({beat}) => {
  const frame = useCurrentFrame();
  const split = interpolate(frame, [12, 34], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease});
  const resolution = beat.purpose === "resolution";
  const leftTitle = resolution ? "LOCAL BASE PASS" : "LOCAL WEIGHTS";
  const rightTitle = resolution ? "HOSTED 2K REGEN" : "HOSTED HELPERS";
  return (
    <AbsoluteFill style={{background: palette.black, color: palette.white, padding: "112px 128px", fontFamily: "Inter Variable,Inter,Arial,sans-serif"}}>
      <div style={{fontSize: 19, letterSpacing: 3.4, fontWeight: 820, color: palette.slate}}>PROMISE / REALITY</div>
      <div style={{fontSize: 78, letterSpacing: -4.5, lineHeight: .96, fontWeight: 920, marginTop: 22}}>{beat.overlay}</div>
      <div style={{display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, marginTop: 90}}>
        <div style={{height: 360, padding: 36, border: "1px solid #333", background: "#111212", transform: `translateX(${(1 - split) * -18}px)`, opacity: split}}><div style={{fontSize: 23, color: palette.gray}}>ON YOUR MACHINE</div><div style={{marginTop: 170, fontSize: 45, fontWeight: 900}}>{leftTitle}</div></div>
        <div style={{height: 360, padding: 36, border: `1px solid ${palette.red}`, background: "#151010", transform: `translateX(${(1 - split) * 18}px)`, opacity: split}}><div style={{fontSize: 23, color: palette.red}}>STILL ONLINE</div><div style={{marginTop: 170, fontSize: 45, fontWeight: 900}}>{rightTitle}</div></div>
      </div>
    </AbsoluteFill>
  );
};

const SyncFrame: React.FC<{beat: Beat}> = ({beat}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{background: palette.black, color: palette.white, padding: "118px 132px", fontFamily: "Inter Variable,Inter,Arial,sans-serif"}}>
      <div style={{fontSize: 19, letterSpacing: 3.4, fontWeight: 820, color: palette.slate}}>PICTURE AND SOUND · SAME GENERATION</div>
      <div style={{fontSize: 82, letterSpacing: -4.5, fontWeight: 920, marginTop: 24}}>{beat.overlay}</div>
      <div style={{display: "flex", alignItems: "center", gap: 12, height: 280, marginTop: 88, borderTop: "1px solid #333", borderBottom: "1px solid #333", overflow: "hidden"}}>
        {Array.from({length: 54}).map((_, index) => {
          const height = 38 + Math.abs(Math.sin(index * .64 + frame * .12)) * 150;
          const active = index < (frame % 70);
          return <div key={index} style={{flex: 1, height, borderRadius: 4, background: active ? palette.red : "#3b3d3d"}} />;
        })}
      </div>
      <div style={{display: "flex", justifyContent: "space-between", marginTop: 24, fontSize: 25, color: palette.gray}}><span>24 FPS VIDEO</span><span>32 kHz STEREO AUDIO</span></div>
    </AbsoluteFill>
  );
};

const ProofFrame: React.FC<{beat: Beat}> = ({beat}) => {
  const frame = useCurrentFrame();
  const rows = beat.purpose === "sample_limits" ? ["VISIBLE CONTINUITY", "COMPANY-PICKED EXAMPLES", "UNKNOWN FAILURE RATE"] : ["SUBJECT DETAIL", "LIGHTING DIRECTION", "SCENE LAYOUT"];
  return (
    <AbsoluteFill style={{background: palette.black, color: palette.white, padding: "112px 132px", fontFamily: "Inter Variable,Inter,Arial,sans-serif"}}>
      <div style={{fontSize: 19, letterSpacing: 3.4, fontWeight: 820, color: palette.slate}}>WHAT THE VISUAL EVIDENCE SUPPORTS</div>
      <div style={{fontSize: 78, letterSpacing: -4.5, fontWeight: 920, marginTop: 22}}>{beat.overlay}</div>
      <div style={{marginTop: 86, borderTop: "1px solid #333"}}>{rows.map((row, index) => {const enter = interpolate(frame, [12 + index * 11, 25 + index * 11], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease}); return <div key={row} style={{height: 128, display: "grid", gridTemplateColumns: "90px 1fr 230px", alignItems: "center", borderBottom: "1px solid #333", opacity: enter, transform: `translateX(${(1 - enter) * 12}px)`}}><div style={{fontSize: 21, color: palette.gray}}>0{index + 1}</div><div style={{fontSize: 37, fontWeight: 850}}>{row}</div><div style={{fontSize: 19, color: index === 2 ? palette.red : palette.slate, textAlign: "right", fontWeight: 820}}>{index === 2 ? "LIMIT" : "VISIBLE"}</div></div>;})}</div>
    </AbsoluteFill>
  );
};

const PurposeFrame: React.FC<{beat: Beat}> = ({beat}) => {
  if (beat.purpose === "hardware") return <MetricFrame beat={beat} />;
  if (["workflow", "creator_test", "decision"].includes(beat.purpose)) return <FlowFrame beat={beat} />;
  if (["resolution", "not_fully_local"].includes(beat.purpose)) return <BoundaryFrame beat={beat} />;
  if (beat.purpose === "native_audio") return <SyncFrame beat={beat} />;
  if (["quality", "sample_limits"].includes(beat.purpose)) return <ProofFrame beat={beat} />;
  return <EvidenceFrame beat={beat} />;
};

const ChapterFrame: React.FC<{beat: Beat; index: number}> = ({beat, index}) => {
  const frame = useCurrentFrame();
  const reveal = interpolate(frame, [0, 13], [0, 1], {extrapolateRight: "clamp", easing: ease});
  return (
    <AbsoluteFill style={{background: palette.black, color: palette.white, justifyContent: "center", padding: "0 140px", fontFamily: "Inter Variable,Inter,Arial,sans-serif"}}>
      <div style={{fontSize: 20, letterSpacing: 4, color: palette.slate, fontWeight: 800}}>CHAPTER {String(index + 1).padStart(2, "0")}</div>
      <div style={{marginTop: 22, maxWidth: 1500, fontSize: 105, lineHeight: .93, letterSpacing: -6, fontWeight: 920, opacity: reveal, transform: `translateY(${(1-reveal)*16}px)`}}>{beat.overlay}</div>
      <div style={{marginTop: 28, width: `${reveal * 160}px`, height: 5, background: palette.red}} />
    </AbsoluteFill>
  );
};

const BeatScene: React.FC<{episode: Episode; beat: Beat; index: number}> = ({episode, beat, index}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const chapterFrames = [0, 6, 10, 16, 20, 26].includes(index) ? Math.round(fps * 2.7) : 0;
  if (frame < chapterFrames) return <ChapterFrame beat={beat} index={index} />;
  const localFrame = frame - chapterFrames;
  const slice = Math.max(0, Math.floor(localFrame / (fps * SHOT_SECONDS)));
  const segmentStart = chapterFrames + slice * fps * SHOT_SECONDS;
  if (slice % 5 === 4) {
    return <Sequence from={segmentStart} durationInFrames={fps * SHOT_SECONDS}><PurposeFrame beat={beat} /></Sequence>;
  }
  const sourceEntries: VisualEntry[] = beat.source_ids.flatMap((sourceId) => {
    const asset = episode.assets[sourceId];
    return asset?.viewport ? [{kind: "image" as const, src: asset.viewport, publisher: episode.sources[sourceId]?.publisher ?? "Source", sourceId}] : [];
  });
  const brollEntries: VisualEntry[] = [];
  beat.broll.forEach((assetId) => {
    const src = episode.broll[assetId];
    if (!src) return;
    if (/\.(?:png|jpe?g|webp)$/i.test(src)) {
      brollEntries.push({kind: "image", src, publisher: "Official MiniMax H3 media", sourceId: "minimax_model"});
      return;
    }
    brollEntries.push({kind: "video", src, publisher: "MiniMaxAI", assetId});
  });
  const pool = [...brollEntries, ...sourceEntries];
  if (!pool.length) {
    return <Sequence from={segmentStart} durationInFrames={fps * SHOT_SECONDS}><PurposeFrame beat={beat} /></Sequence>;
  }
  const item = pool[(slice + index) % pool.length];
  return (
    <Sequence from={segmentStart} durationInFrames={fps * SHOT_SECONDS}>
      {item.kind === "video" ? <VideoFrame key={`${beat.id}-${slice}-${item.src}`} src={item.src} beat={beat} assetId={item.assetId} /> : <SourceFrame key={`${beat.id}-${slice}-${item.src}`} src={item.src} beat={beat} publisher={item.publisher} sourceId={item.sourceId} />}
    </Sequence>
  );
};

export const H3DeepDiveEpisode: React.FC = () => {
  const episode = episodeJson as Episode;
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill style={{background: palette.black}}>
      <Audio src={staticFile("episode/h3-10m/narration.wav")} />
      {episode.beats.map((beat, index) => {
        const start = Math.floor(beat.startMs / 1000 * fps);
        const nextStart = episode.beats[index + 1]?.startMs ?? episode.durationSeconds * 1000;
        const end = Math.ceil(nextStart / 1000 * fps);
        return <Sequence key={beat.id} from={start} durationInFrames={Math.max(1, end - start)} premountFor={fps}><BeatScene episode={episode} beat={beat} index={index} /></Sequence>;
      })}
    </AbsoluteFill>
  );
};
