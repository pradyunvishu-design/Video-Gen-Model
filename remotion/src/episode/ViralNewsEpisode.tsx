import {createTikTokStyleCaptions} from "@remotion/captions";
import {Audio} from "@remotion/media";
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
import {SourceCredit} from "./SourceCredit";

const color = {
  bg: "#111311",
  surface: "#181B19",
  ink: "#F1F2EE",
  muted: "#A8AFAB",
  line: "#3E4541",
  clay: "#B56F55",
  slate: "#8396A0",
  moss: "#667C6D",
};
const ease = Easing.bezier(0.16, 1, 0.3, 1);

const headings: Record<string, string> = {
  hook: "AI VIDEO JUST ESCAPED",
  what_changed: "VIDEO + SOUND · ONE MODEL",
  open_release: "THE WEIGHTS ARE PUBLIC",
  asterisk: "LOCAL*",
  reality_check: "10 SECONDS · 30 MINUTES",
  why_it_matters: "CONTROL IS THE PRODUCT",
  limitation: "OPEN ≠ COMPLETE",
  verdict: "WHO SHOULD USE IT?",
};

const cards: Record<string, string[]> = {
  hook: ["OPEN WEIGHTS", "COMFYUI", "DAY ZERO"],
  what_changed: ["TEXT / IMAGE", "VIDEO / AUDIO", "STEREO OUTPUT"],
  open_release: ["INSPECT", "AUTOMATE", "FINE-TUNE"],
  asterisk: ["123.6 GB", "→", "42.5 GB"],
  reality_check: ["10 SEC CLIP", "→", "~30 MIN"],
  why_it_matters: ["LOCAL", "REPEATABLE", "CUSTOM"],
  limitation: ["768P BASE", "HOSTED IR", "2K VIA API"],
  verdict: ["BUILDERS: TEST", "CREATORS: HOSTED", "WATCH THIS SPACE"],
};

const useEpisode = (): LoadedEpisode | null => {
  const [loaded, setLoaded] = useState<LoadedEpisode | null>(null);
  const [handle] = useState(() => delayRender("Load H3 episode"));
  useEffect(() => {
    Promise.all([
      fetch(staticFile("episode/h3-news/episode.json")).then((response) => response.json() as Promise<EpisodeData>),
      fetch(staticFile("episode/h3-news/captions.json")).then((response) => response.json()),
    ]).then(([episode, captions]) => {
      setLoaded({episode, captions});
      continueRender(handle);
    });
  }, [handle]);
  return loaded;
};

const Background: React.FC = () => {
  return <AbsoluteFill style={{background: "linear-gradient(145deg,#111311 0%,#151816 58%,#101210 100%)"}}>
    <AbsoluteFill style={{opacity: .24, backgroundImage: "linear-gradient(rgba(188,197,191,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(188,197,191,.035) 1px,transparent 1px)", backgroundSize: "96px 96px"}} />
  </AbsoluteFill>;
};

const Chrome: React.FC<React.PropsWithChildren<{label: string; url: string}>> = ({label, url, children}) => (
  <div style={{position: "absolute", inset: "96px 58px 118px", borderRadius: 14, padding: 8, overflow: "hidden", border: `1px solid ${color.line}`, background: color.surface, boxShadow: "0 28px 80px rgba(0,0,0,.34)"}}>
    <div style={{height: 46, display: "flex", alignItems: "center", gap: 9, padding: "0 16px", borderRadius: "7px 7px 0 0", background: "#141715"}}>
      {[color.clay, "#78827D", color.moss].map((item) => <span key={item} style={{width: 10, height: 10, borderRadius: 20, background: item}} />)}
      <div style={{marginLeft: 15, color: "rgba(255,255,255,.58)", fontSize: 15, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis"}}>{url}</div>
    </div>
    <div style={{position: "absolute", inset: "54px 8px 8px", overflow: "hidden", borderRadius: "0 0 7px 7px", background: "#101210"}}>
      {children}
      <div style={{position: "absolute", inset: 0, background: "linear-gradient(180deg,transparent 68%,rgba(8,10,9,.72))"}} />
      <SourceCredit label={label} inset={28} />
    </div>
  </div>
);

const SourceScene: React.FC<{assets: SourceAssets; publisher: string; url: string}> = ({assets, publisher, url}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 22, stiffness: 120}});
  const zoom = interpolate(frame, [0, fps * 6], [1.0, 1.018], {extrapolateRight: "clamp", easing: ease});
  const source = assets.viewport ?? assets.screen_recording ?? "";
  const mediaStyle: React.CSSProperties = {width: "100%", height: "100%", objectFit: "cover", transform: `scale(${zoom})`};
  return <div style={{position: "absolute", inset: 0, opacity: enter, transform: `translateY(${(1-enter)*12}px)`}}>
    <Chrome label={publisher} url={url}>
      <Img src={staticFile(source)} style={mediaStyle} />
    </Chrome>
  </div>;
};

const ConceptScene: React.FC<{beat: EpisodeBeat}> = ({beat}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 20, stiffness: 115}});
  const items = cards[beat.purpose] ?? ["WHAT CHANGED", "WHY IT MATTERS", "WHAT TO DO"];
  return <div style={{position: "absolute", inset: "145px 105px 160px", display: "flex", flexDirection: "column", justifyContent: "center", opacity: enter, transform: `translateY(${(1-enter)*35}px)`}}>
    <div style={{fontSize: 17, fontWeight: 760, letterSpacing: 2.4, color: color.slate}}>{beat.purpose.replace(/_/g, " ").toUpperCase()}</div>
    <div style={{marginTop: 16, maxWidth: 1550, fontSize: 82, lineHeight: .98, letterSpacing: -4, fontWeight: 900}}>{headings[beat.purpose] ?? beat.purpose.toUpperCase()}</div>
    <div style={{marginTop: 26, width: 126, height: 2, background: color.clay}} />
    <div style={{display: "grid", gridTemplateColumns: `repeat(${items.length},1fr)`, gap: 20, marginTop: 42}}>
      {items.map((item, index) => {
        const progress = spring({frame: frame-index*7, fps, config: {damping: 19, stiffness: 125}});
        return <div key={item} style={{minHeight: 175, padding: "28px 25px", display: "flex", alignItems: "flex-end", borderRadius: 8, borderTop: `2px solid ${index === 1 ? color.clay : color.line}`, background: index === 1 ? "#1D1B18" : color.surface, opacity: progress, transform: `translateY(${(1-progress)*12}px)`}}>
          <span style={{fontSize: item.length > 15 ? 32 : 45, fontWeight: 780, color: color.ink}}>{item}</span>
        </div>;
      })}
    </div>
  </div>;
};

const BeatScene: React.FC<{beat: EpisodeBeat; index: number; episode: EpisodeData}> = ({beat, index, episode}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const slice = Math.floor(frame/(fps*5));
  const sourceId = beat.source_ids[slice % Math.max(1, beat.source_ids.length)];
  const source = episode.sources[sourceId];
  const sourceAssets = episode.assets[sourceId];
  const hasEditorialMedia = Boolean(sourceAssets?.viewport || sourceAssets?.screen_recording);
  const showSource = Boolean(source) && hasEditorialMedia && (slice + index) % 2 === 0;
  return <AbsoluteFill style={{color: color.ink, fontFamily: "Inter Variable,Inter,Arial,sans-serif"}}>
    <Background />
    <div style={{position: "absolute", left: 62, top: 43, zIndex: 30, display: "flex", alignItems: "center", gap: 13, fontSize: 18, fontWeight: 760, letterSpacing: 3.2}}><span style={{width: 3, height: 25, background: color.clay}} />AI MEDIA BRIEF</div>
    <div style={{position: "absolute", right: 62, top: 47, zIndex: 30, color: color.muted, fontSize: 17, fontWeight: 760}}>MINIMAX H3 · {String(index+1).padStart(2,"0")}/{String(episode.beats.length).padStart(2,"0")}</div>
    {showSource ? <SourceScene assets={sourceAssets ?? {}} publisher={source.publisher} url={source.url} /> : <ConceptScene beat={beat} />}
  </AbsoluteFill>;
};

const Captions: React.FC<{loaded: LoadedEpisode}> = ({loaded}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const nowMs = frame/fps*1000;
  const groups = useMemo(() => {
    const tokens = createTikTokStyleCaptions({captions: loaded.captions, combineTokensWithinMilliseconds: 1000}).pages.flatMap((page) => page.tokens);
    const pages: Array<{startMs: number; endMs: number; tokens: typeof tokens}> = [];
    let current: typeof tokens = [];
    for (const token of tokens) {
      if (current.length && (current.length >= 7 || token.toMs-current[0].fromMs > 1400)) {
        pages.push({startMs: current[0].fromMs, endMs: current[current.length-1].toMs, tokens: current});
        current = [];
      }
      current.push(token);
    }
    if (current.length) pages.push({startMs: current[0].fromMs, endMs: current[current.length-1].toMs, tokens: current});
    return pages;
  }, [loaded.captions]);
  const page = groups.find((candidate, index) => nowMs >= candidate.startMs && (!groups[index+1] || nowMs < groups[index+1].startMs));
  if (!page || nowMs > page.endMs+450) return null;
  return <div style={{position: "absolute", zIndex: 80, left: 180, right: 180, bottom: 25, display: "flex", justifyContent: "center", fontFamily: "Inter Variable,Inter,Arial,sans-serif"}}>
    <div style={{maxWidth: 1480, padding: "12px 24px 14px", borderRadius: 7, background: "rgba(12,14,13,.91)", border: `1px solid ${color.line}`, boxShadow: "0 12px 42px rgba(0,0,0,.48)", textAlign: "center", whiteSpace: "pre-wrap", fontSize: 35, lineHeight: 1.2, fontWeight: 760, textShadow: "0 3px 12px #000"}}>
      {page.tokens.map((token, index) => {const active = nowMs >= token.fromMs && nowMs < token.toMs; return <span key={`${token.fromMs}-${index}`} style={{color: active ? color.ink : color.muted}}>{token.text}</span>;})}
    </div>
  </div>;
};

export const ViralNewsEpisode: React.FC = () => {
  const loaded = useEpisode();
  const {fps} = useVideoConfig();
  if (!loaded) return <AbsoluteFill style={{background: color.bg}} />;
  return <AbsoluteFill style={{background: color.bg}}>
    <Audio src={staticFile("episode/h3-news/narration.wav")} />
    {loaded.episode.beats.map((beat, index) => {
      const start = Math.floor(beat.startMs/1000*fps);
      const end = loaded.episode.beats[index+1] ? Math.ceil(loaded.episode.beats[index+1].startMs/1000*fps) : loaded.episode.durationSeconds*fps;
      return <Sequence key={beat.id} from={start} durationInFrames={Math.max(1,end-start)} premountFor={fps}><BeatScene beat={beat} index={index} episode={loaded.episode} /></Sequence>;
    })}
    <Captions loaded={loaded} />
  </AbsoluteFill>;
};
