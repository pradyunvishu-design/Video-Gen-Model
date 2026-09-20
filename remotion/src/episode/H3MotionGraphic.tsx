import {Sequence, AbsoluteFill, Easing, interpolate, useCurrentFrame} from "remotion";

export type H3MotionKind = "ladder" | "workflow" | "metric" | "boundary" | "checklist" | "title";

export type H3MotionScene = {
  id: string;
  kind: H3MotionKind;
  kicker: string;
  title: string;
  footer: string;
  items: string[];
};

export type H3MotionPackProps = {
  scenes: H3MotionScene[];
};

export const H3_MOTION_SCENE_FRAMES = 150;

export const defaultH3MotionPackProps: H3MotionPackProps = {
  scenes: [
    {
      id: "default",
      kind: "workflow",
      kicker: "MINIMAX H3 · HOW IT WORKS",
      title: "Preview locally. Finish only what matters.",
      footer: "ONE IDEA · ONE READABLE STATE CHANGE",
      items: ["PREVIEW", "LOCK", "FINISH"],
    },
  ],
};

const palette = {
  black: "#070808",
  panel: "#151616",
  line: "#363838",
  paper: "#F2F1ED",
  muted: "#8E9290",
  slate: "#8E9B95",
  clay: "#D77B59",
  green: "#78B394",
};

const ease = Easing.bezier(0.16, 1, 0.3, 1);

const enter = (frame: number, start: number, duration = 14) =>
  interpolate(frame, [start, start + duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });

const Heading: React.FC<{scene: H3MotionScene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const heading = enter(frame, 4, 15);
  const underline = enter(frame, 42, 20);
  return (
    <>
      <div
        style={{
          position: "absolute",
          left: 126,
          top: 92,
          color: palette.clay,
          fontFamily: "Inter Variable,Inter,Arial,sans-serif",
          fontSize: 19,
          fontWeight: 800,
          letterSpacing: 3.2,
          opacity: heading,
          translate: `0px ${(1 - heading) * 10}px`,
        }}
      >
        {scene.kicker}
      </div>
      <div
        style={{
          position: "absolute",
          left: 126,
          top: 132,
          maxWidth: 1580,
          color: palette.paper,
          fontFamily: "Inter Variable,Inter,Arial,sans-serif",
          fontSize: scene.title.length > 48 ? 62 : 74,
          fontWeight: 860,
          letterSpacing: -3.2,
          lineHeight: 0.98,
          opacity: heading,
          translate: `0px ${(1 - heading) * 12}px`,
        }}
      >
        {scene.title}
      </div>
      <div
        style={{
          position: "absolute",
          left: 126,
          top: 236,
          width: 170,
          height: 4,
          borderRadius: 2,
          backgroundColor: palette.slate,
          scale: `${underline} 1`,
          transformOrigin: "left center",
        }}
      />
    </>
  );
};

const Footer: React.FC<{children: React.ReactNode}> = ({children}) => (
  <div
    style={{
      position: "absolute",
      left: 126,
      bottom: 62,
      color: palette.muted,
      fontFamily: "Inter Variable,Inter,Arial,sans-serif",
      fontSize: 19,
      fontWeight: 700,
      letterSpacing: 1.4,
    }}
  >
    {children}
  </div>
);

const Ladder: React.FC<{scene: H3MotionScene}> = ({scene}) => {
  const frame = useCurrentFrame();
  return (
    <div style={{position: "absolute", left: 310, right: 310, top: 350}}>
      {scene.items.slice(0, 3).map((item, index) => {
        const progress = enter(frame, 20 + index * 12, 15);
        return (
          <div
            key={`${item}-${index}`}
            style={{
              height: 150,
              marginBottom: 22,
              border: `1px solid ${index === 2 ? palette.clay : palette.line}`,
              borderRadius: 13,
              backgroundColor: palette.panel,
              display: "grid",
              gridTemplateColumns: "120px 1fr 110px",
              alignItems: "center",
              padding: "0 42px",
              color: palette.paper,
              opacity: progress,
              translate: `0px ${(1 - progress) * 14}px`,
              fontFamily: "Inter Variable,Inter,Arial,sans-serif",
            }}
          >
            <span style={{fontFamily: "ui-monospace,SFMono-Regular,Consolas,monospace", fontSize: 36, color: palette.muted}}>0{index + 1}</span>
            <span style={{fontSize: 40, fontWeight: 820}}>{item}</span>
            <span style={{width: 34, height: 34, borderRadius: 18, border: `3px solid ${index === 2 ? palette.clay : palette.line}`, justifySelf: "end"}} />
          </div>
        );
      })}
    </div>
  );
};

const Workflow: React.FC<{scene: H3MotionScene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const draw = enter(frame, 24, 36);
  return (
    <div style={{position: "absolute", left: 180, right: 180, top: 390, height: 400}}>
      <svg viewBox="0 0 1560 400" style={{position: "absolute", inset: 0}}>
        <path
          d="M160 190 H510 C600 190 600 90 690 90 H900 C990 90 990 290 1080 290 H1400"
          fill="none"
          stroke={palette.line}
          strokeWidth={4}
          pathLength={1}
          strokeDasharray={1}
          strokeDashoffset={1 - draw}
        />
        <path
          d="M160 190 H510"
          fill="none"
          stroke={palette.clay}
          strokeWidth={5}
          pathLength={1}
          strokeDasharray={1}
          strokeDashoffset={1 - draw}
        />
      </svg>
      {scene.items.slice(0, 3).map((item, index) => {
        const progress = enter(frame, 14 + index * 18, 14);
        const positions = [
          {left: 40, top: 125},
          {left: 670, top: 25},
          {right: 30, top: 225},
        ];
        return (
          <div
            key={`${item}-${index}`}
            style={{
              position: "absolute",
              ...positions[index],
              width: 300,
              height: 126,
              borderRadius: 15,
              border: `1px solid ${index === 0 ? palette.clay : palette.line}`,
              backgroundColor: palette.panel,
              color: palette.paper,
              display: "grid",
              placeItems: "center",
              fontFamily: "Inter Variable,Inter,Arial,sans-serif",
              fontSize: 30,
              fontWeight: 820,
              opacity: progress,
              translate: `0px ${(1 - progress) * 12}px`,
            }}
          >
            {item}
          </div>
        );
      })}
    </div>
  );
};

const Metric: React.FC<{scene: H3MotionScene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const left = enter(frame, 16, 16);
  const line = enter(frame, 32, 26);
  const right = enter(frame, 48, 16);
  const values = scene.items.length >= 3 ? scene.items : ["123.6 GB", "66% LESS", "42.5 GB"];
  return (
    <div style={{position: "absolute", left: 180, right: 180, top: 390, height: 380, color: palette.paper, fontFamily: "Inter Variable,Inter,Arial,sans-serif"}}>
      <div style={{position: "absolute", left: 0, top: 55, fontSize: 102, fontWeight: 900, letterSpacing: -6, opacity: left, translate: `${(1 - left) * -12}px 0px`}}>{values[0]}</div>
      <svg viewBox="0 0 500 100" style={{position: "absolute", left: 530, top: 92, width: 500, height: 100}}>
        <path d="M10 50 H460" stroke={palette.line} strokeWidth={5} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - line} />
        <path d="M432 28 L462 50 L432 72" fill="none" stroke={palette.clay} strokeWidth={6} strokeLinecap="round" strokeLinejoin="round" opacity={line} />
      </svg>
      <div style={{position: "absolute", right: 0, top: 55, fontSize: 102, fontWeight: 900, letterSpacing: -6, opacity: right, translate: `${(1 - right) * 12}px 0px`}}>{values[2]}</div>
      <div style={{position: "absolute", left: 610, top: 245, width: 340, textAlign: "center", color: palette.clay, fontSize: 44, fontWeight: 850, opacity: right}}>{values[1]}</div>
    </div>
  );
};

const Boundary: React.FC<{scene: H3MotionScene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const items = scene.items.length >= 3 ? scene.items : ["LOCAL WEIGHTS", "HOSTED HELPERS", "YOU CHOOSE"];
  return (
    <div style={{position: "absolute", left: 176, right: 176, top: 380, height: 410, display: "grid", gridTemplateColumns: "1fr 150px 1fr", alignItems: "center", fontFamily: "Inter Variable,Inter,Arial,sans-serif"}}>
      {[0, 1].map((index) => {
        const progress = enter(frame, 18 + index * 18, 16);
        return (
          <div key={index} style={{gridColumn: index === 0 ? 1 : 3, height: 330, borderRadius: 18, border: `1px solid ${index === 0 ? palette.green : palette.clay}`, backgroundColor: palette.panel, padding: 40, opacity: progress, translate: `${(1 - progress) * (index === 0 ? -14 : 14)}px 0px`}}>
            <div style={{fontSize: 22, color: index === 0 ? palette.green : palette.clay, letterSpacing: 2.4, fontWeight: 800}}>{index === 0 ? "ON YOUR MACHINE" : "STILL ONLINE"}</div>
            <div style={{marginTop: 178, fontSize: 43, color: palette.paper, fontWeight: 850}}>{items[index]}</div>
          </div>
        );
      })}
      <div style={{gridColumn: 2, gridRow: 1, color: palette.muted, fontSize: 26, textAlign: "center", opacity: enter(frame, 52, 12)}}>{items[2]}</div>
    </div>
  );
};

const Checklist: React.FC<{scene: H3MotionScene}> = ({scene}) => {
  const frame = useCurrentFrame();
  return (
    <div style={{position: "absolute", left: 270, right: 270, top: 365, fontFamily: "Inter Variable,Inter,Arial,sans-serif"}}>
      {scene.items.slice(0, 3).map((item, index) => {
        const progress = enter(frame, 20 + index * 12, 14);
        const checked = enter(frame, 48 + index * 10, 8);
        return (
          <div key={`${item}-${index}`} style={{height: 142, display: "grid", gridTemplateColumns: "82px 1fr 80px", alignItems: "center", borderBottom: `1px solid ${palette.line}`, color: palette.paper, opacity: progress, translate: `${(1 - progress) * 12}px 0px`}}>
            <span style={{fontFamily: "ui-monospace,SFMono-Regular,Consolas,monospace", color: palette.muted, fontSize: 24}}>0{index + 1}</span>
            <span style={{fontSize: 39, fontWeight: 810}}>{item}</span>
            <span style={{justifySelf: "end", width: 34, height: 34, borderRadius: 18, border: `2px solid ${palette.line}`, display: "grid", placeItems: "center", color: palette.green, fontSize: 23, opacity: checked}}>✓</span>
          </div>
        );
      })}
    </div>
  );
};

const TitleOnly: React.FC<{scene: H3MotionScene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const progress = enter(frame, 18, 18);
  return (
    <div style={{position: "absolute", left: 126, right: 126, top: 385, color: palette.paper, fontFamily: "Inter Variable,Inter,Arial,sans-serif", opacity: progress, translate: `0px ${(1 - progress) * 14}px`}}>
      <div style={{fontSize: 112, lineHeight: 0.94, letterSpacing: -6.5, fontWeight: 900, maxWidth: 1500}}>{scene.title}</div>
      <div style={{marginTop: 42, color: palette.muted, fontSize: 31}}>{scene.items[0] ?? scene.footer}</div>
    </div>
  );
};

export const H3MotionGraphic: React.FC<{scene: H3MotionScene}> = ({scene}) => {
  return (
    <AbsoluteFill style={{backgroundColor: palette.black, overflow: "hidden"}}>
      {scene.kind !== "title" ? <Heading scene={scene} /> : null}
      {scene.kind === "ladder" ? <Ladder scene={scene} /> : null}
      {scene.kind === "workflow" ? <Workflow scene={scene} /> : null}
      {scene.kind === "metric" ? <Metric scene={scene} /> : null}
      {scene.kind === "boundary" ? <Boundary scene={scene} /> : null}
      {scene.kind === "checklist" ? <Checklist scene={scene} /> : null}
      {scene.kind === "title" ? <TitleOnly scene={scene} /> : null}
      <Footer>{scene.footer}</Footer>
    </AbsoluteFill>
  );
};

export const H3MotionPack: React.FC<H3MotionPackProps> = ({scenes}) => (
  <AbsoluteFill style={{backgroundColor: palette.black}}>
    {scenes.map((scene, index) => (
      <Sequence key={scene.id} from={index * H3_MOTION_SCENE_FRAMES} durationInFrames={H3_MOTION_SCENE_FRAMES}>
        <H3MotionGraphic scene={scene} />
      </Sequence>
    ))}
  </AbsoluteFill>
);
