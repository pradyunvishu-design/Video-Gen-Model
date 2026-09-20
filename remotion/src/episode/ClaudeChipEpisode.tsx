import {Audio} from "@remotion/media";
import {useEffect, useState} from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  OffthreadVideo,
  continueRender,
  delayRender,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {SourceCredit} from "./SourceCredit";

type Chapter = {
  id: string;
  title: string;
  kicker: string;
  narration: string;
  evidence: string[];
  start: number;
  duration: number;
};

type Episode = {
  title: string;
  durationSeconds: number;
  chapters: Chapter[];
  captures: Array<{file?: string; status: string; url?: string}>;
};

const palette = {
  black: "#070708",
  board: "#101012",
  paper: "#f5f0e8",
  muted: "#b8b0a5",
  orange: "#d97745",
  slate: "#8E9B95",
  blue: "#5b8cff",
  red: "#ef4c47",
};
const ease = Easing.bezier(0.22, 1, 0.36, 1);

const useEpisode = () => {
  const [episode, setEpisode] = useState<Episode | null>(null);
  const [handle] = useState(() => delayRender("Loading Claude chip episode"));
  useEffect(() => {
    fetch(staticFile("episode/claude-chips/episode.json"))
      .then((response) => response.json() as Promise<Episode>)
      .then((data) => {
        setEpisode(data);
        continueRender(handle);
      });
  }, [handle]);
  return episode;
};

const Header: React.FC<{chapter: Chapter; index: number; count: number}> = ({chapter, index, count}) => (
  <>
    <div style={{position: "absolute", left: 54, top: 36, zIndex: 30, display: "flex", alignItems: "center", gap: 13, color: palette.paper, fontSize: 17, fontWeight: 850, letterSpacing: 3.4}}>
      <span style={{width: 3, height: 25, background: palette.orange}} />
      AI MEDIA BRIEF
    </div>
    <div style={{position: "absolute", right: 54, top: 38, zIndex: 30, color: "rgba(245,240,232,.72)", fontSize: 17, fontWeight: 700}}>
      CLAUDE × CHIP VALIDATION · {String(index + 1).padStart(2, "0")}/{String(count).padStart(2, "0")}
    </div>
    <div style={{position: "absolute", right: 54, bottom: 38, zIndex: 30, color: "rgba(245,240,232,.48)", fontSize: 15, fontWeight: 700, letterSpacing: 1.8}}>
      {chapter.evidence.join(" · ")}
    </div>
  </>
);

const FilmGrain: React.FC = () => (
  <AbsoluteFill style={{pointerEvents: "none", opacity: 0.045, mixBlendMode: "screen", background: "repeating-linear-gradient(0deg,rgba(255,255,255,.08) 0px,rgba(255,255,255,.08) 1px,transparent 1px,transparent 4px)"}} />
);

const OfficialVideo: React.FC<{file: string; label: string; offset: number}> = ({file, label, offset}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const local = frame % Math.round(fps * 6);
  const opacity = interpolate(local, [0, 5, fps * 6 - 5, fps * 6], [0, 1, 1, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  const push = interpolate(local, [0, fps * 6], [1.005, 1.035], {easing: ease});
  return <AbsoluteFill style={{background: palette.black, opacity, overflow: "hidden"}}>
    <OffthreadVideo src={staticFile(`episode/claude-chips/${file}`)} startFrom={Math.round(offset * fps)} muted style={{width: "100%", height: "100%", objectFit: "cover", transform: `scale(${push})`}} />
    <AbsoluteFill style={{background: "linear-gradient(180deg,rgba(0,0,0,.28),transparent 24%,transparent 70%,rgba(0,0,0,.46))"}} />
    <SourceCredit label={label} />
  </AbsoluteFill>;
};

const PageCapture: React.FC<{file: string; chapter: Chapter}> = ({file, chapter}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const local = frame % Math.round(fps * 6);
  const enter = spring({frame: local, fps, config: {damping: 22, stiffness: 100}});
  const move = interpolate(local, [0, fps * 6], [0, -28], {easing: ease});
  return <AbsoluteFill style={{background: palette.black, overflow: "hidden"}}>
    <Img src={staticFile(`episode/claude-chips/${file}`)} style={{width: "100%", height: "100%", objectFit: "cover", transform: `translateY(${move}px) scale(1.045)`, filter: "saturate(.9) contrast(1.03)"}} />
    <AbsoluteFill style={{background: "linear-gradient(90deg,rgba(7,7,8,.92) 0%,rgba(7,7,8,.58) 34%,transparent 64%),linear-gradient(180deg,rgba(7,7,8,.35),transparent 28%,rgba(7,7,8,.58))"}} />
    <div style={{position: "absolute", left: 82, top: 210, width: 680, opacity: enter, transform: `translateX(${(1 - enter) * -35}px)`}}>
      <div style={{fontSize: 20, color: palette.orange, fontWeight: 900, letterSpacing: 3.2}}>PRIMARY SOURCE</div>
      <div style={{fontSize: 76, lineHeight: .98, color: palette.paper, fontWeight: 900, letterSpacing: -3.8, marginTop: 16}}>{chapter.title}</div>
      <div style={{width: 160, height: 6, background: palette.red, borderRadius: 9, marginTop: 28}} />
    </div>
    <SourceCredit label="Official company page" />
  </AbsoluteFill>;
};

const ChipFlow: React.FC<{chapter: Chapter; variant: number}> = ({chapter, variant}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const local = frame % Math.round(fps * 6);
  const progress = interpolate(local, [0, fps * 5.5], [0, 1], {extrapolateRight: "clamp", easing: ease});
  const sets = [
    ["SCHEMATIC", "PINOUT", "TEST", "RESULT"],
    ["DESIGN", "REGRESSION", "EQUIPMENT", "DIGITAL TWIN"],
    ["DRAFT", "REVIEW", "RUN", "HUMAN APPROVAL"],
  ];
  const labels = sets[variant % sets.length];
  return <AbsoluteFill style={{background: `radial-gradient(circle at 82% 16%,rgba(217,119,69,.17),transparent 34%),linear-gradient(135deg,${palette.black},${palette.board})`, color: palette.paper}}>
    <div style={{position: "absolute", left: 100, right: 100, top: 170}}>
      <div style={{fontSize: 19, color: palette.orange, fontWeight: 900, letterSpacing: 4}}>{chapter.kicker}</div>
      <div style={{fontSize: 76, fontWeight: 920, letterSpacing: -4, marginTop: 13}}>{chapter.title}</div>
      <div style={{width: 175, height: 6, background: palette.red, borderRadius: 99, marginTop: 24}} />
    </div>
    <div style={{position: "absolute", left: 100, right: 100, bottom: 175, display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 34, alignItems: "center"}}>
      {labels.map((label, index) => {
        const item = interpolate(progress, [index * .18, index * .18 + .22], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
        return <div key={label} style={{position: "relative", height: 210, borderRadius: 12, display: "grid", placeItems: "center", textAlign: "center", padding: 22, background: index === 2 ? "#202723" : "rgba(255,255,255,.045)", color: palette.paper, border: `1px solid ${index === 2 ? palette.slate : "rgba(255,255,255,.14)"}`, boxShadow: "0 20px 60px rgba(0,0,0,.28)", opacity: item, transform: `translateY(${(1 - item) * 16}px)`}}>
          <span style={{fontSize: label.length > 12 ? 30 : 38, fontWeight: 900, letterSpacing: -.8}}>{label}</span>
          {index < labels.length - 1 ? <span style={{position: "absolute", right: -33, top: 82, color: palette.orange, fontSize: 48, zIndex: 5}}>→</span> : null}
        </div>;
      })}
    </div>
  </AbsoluteFill>;
};

const MetricScene: React.FC<{chapter: Chapter}> = ({chapter}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const local = frame % Math.round(fps * 6);
  const enter = spring({frame: local, fps, config: {damping: 18, stiffness: 105}});
  const isSpeed = chapter.id === "speed_claim";
  const left = isSpeed ? "4 DAYS" : "AI OUTPUT";
  const right = isSpeed ? "48 HOURS" : "ENGINEER APPROVAL";
  return <AbsoluteFill style={{background: palette.paper, color: palette.black}}>
    <div style={{position: "absolute", left: 88, top: 110, fontSize: 18, fontWeight: 900, letterSpacing: 4, color: palette.orange}}>THE NUMBER NEEDS CONTEXT</div>
    <div style={{position: "absolute", left: 88, right: 88, top: 205, display: "grid", gridTemplateColumns: "1fr 210px 1fr", alignItems: "center", gap: 32}}>
      {[left, "→", right].map((text, index) => <div key={text} style={{height: 340, display: "grid", placeItems: "center", textAlign: "center", borderRadius: index === 1 ? 999 : 14, background: index === 2 ? "#202723" : index === 1 ? palette.red : palette.black, color: index === 1 ? palette.black : palette.paper, border: `1px solid ${index === 2 ? palette.slate : palette.black}`, fontSize: index === 1 ? 82 : text.length > 14 ? 44 : 68, lineHeight: 1, fontWeight: 900, letterSpacing: -2.5, opacity: enter, transform: `translateY(${(1 - enter) * 14}px)`}}>{text}</div>)}
    </div>
    <div style={{position: "absolute", left: 88, right: 88, bottom: 125, display: "flex", justifyContent: "space-between", fontSize: 28, fontWeight: 800}}>
      <span>{chapter.kicker}</span><span style={{color: palette.red}}>ATTRIBUTION STAYS ATTACHED</span>
    </div>
  </AbsoluteFill>;
};

const Intro: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 18, stiffness: 90}});
  return <AbsoluteFill style={{background: `radial-gradient(circle at 78% 35%,rgba(217,119,69,.25),transparent 34%),${palette.black}`, color: palette.paper}}>
    <div style={{position: "absolute", left: 96, top: 160, width: 1160, opacity: enter, transform: `translateY(${(1 - enter) * 38}px)`}}>
      <div style={{fontSize: 20, color: palette.orange, fontWeight: 900, letterSpacing: 4}}>AI MEDIA BRIEF · PRIVATE QUALITY CANARY</div>
      <div style={{fontSize: 106, lineHeight: .91, fontWeight: 950, letterSpacing: -7, marginTop: 24}}>CLAUDE IS<br />TESTING CHIPS.</div>
      <div style={{fontSize: 43, color: palette.muted, fontWeight: 650, marginTop: 30}}>Here’s what that actually means.</div>
    </div>
    <div style={{position: "absolute", right: 126, top: 276, width: 410, height: 410, borderRadius: 70, border: "2px solid rgba(255,255,255,.16)", background: "linear-gradient(145deg,#171719,#09090a)", display: "grid", placeItems: "center", boxShadow: "0 40px 120px rgba(0,0,0,.55)", transform: `rotate(${interpolate(frame, [0, fps * 8], [-4, 3], {easing: ease})}deg)`}}>
      <Img src={staticFile("brands/claude.svg")} style={{width: 240, height: 240, objectFit: "contain"}} />
    </div>
    <div style={{position: "absolute", left: 96, bottom: 105, width: 240, height: 7, background: palette.red, borderRadius: 99}} />
  </AbsoluteFill>;
};

export const ClaudeChipEpisode: React.FC = () => {
  const episode = useEpisode();
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (!episode) return <AbsoluteFill style={{background: palette.black}} />;
  const seconds = frame / fps;
  const chapterIndex = Math.max(0, episode.chapters.findIndex((chapter) => seconds >= chapter.start && seconds < chapter.start + chapter.duration));
  const chapter = episode.chapters[chapterIndex] ?? episode.chapters[episode.chapters.length - 1];
  const slice = Math.floor(seconds / 6);
  const captures = episode.captures.filter((capture) => capture.status === "captured" && capture.file);
  const capture = captures[(slice + chapterIndex) % Math.max(1, captures.length)]?.file;
  const variant = (slice + chapterIndex * 2) % 7;
  const mediaOffset = (slice * 19 + chapterIndex * 23) % 280;
  const visual = variant;

  let content: React.ReactNode;
  if (seconds < 10) {
    content = <Intro />;
  } else if (visual === 0 || visual === 4) {
    content = <OfficialVideo file="intel_packaging_broll.mp4" label="INTEL NEWSROOM" offset={mediaOffset} />;
  } else if (visual === 1 || visual === 5) {
    content = <OfficialVideo file="intel_vision_broll.mp4" label="INTEL NEWSROOM" offset={mediaOffset} />;
  } else if (visual === 2 && capture) {
    content = <PageCapture file={capture} chapter={chapter} />;
  } else if (visual === 3 || chapter.id === "speed_claim") {
    content = <MetricScene chapter={chapter} />;
  } else {
    content = <ChipFlow chapter={chapter} variant={slice} />;
  }

  return <AbsoluteFill style={{fontFamily: "Inter Variable,Inter,Arial,sans-serif", background: palette.black}}>
    <Audio src={staticFile("episode/claude-chips/narration.wav")} />
    {content}
    {seconds >= 10 ? <Header chapter={chapter} index={chapterIndex} count={episode.chapters.length} /> : null}
    <FilmGrain />
  </AbsoluteFill>;
};
