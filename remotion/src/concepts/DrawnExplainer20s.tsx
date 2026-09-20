import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const BG = "#111216";
const PAPER = "#F2F0E9";
const MUTED = "#9A9B9F";
const INK = "#E9E7DF";
const ACCENT = "#F26C3A";
const BLUE = "#72A7FF";

const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;

const reveal = (frame: number, start: number, duration = 22) =>
  interpolate(frame, [start, start + duration], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});

const enter = (frame: number, start: number) => {
  const progress = reveal(frame, start, 16);
  return {opacity: progress, transform: `translateY(${(1 - progress) * 14}px)`};
};

const DrawPath: React.FC<{
  d: string;
  frame: number;
  start: number;
  length?: number;
  color?: string;
  width?: number;
}> = ({d, frame, start, length = 900, color = INK, width = 8}) => {
  const progress = reveal(frame, start, 30);
  return (
    <path
      d={d}
      fill="none"
      stroke={color}
      strokeWidth={width}
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeDasharray={length}
      strokeDashoffset={length * (1 - progress)}
    />
  );
};

const Label: React.FC<{children: React.ReactNode; x: number; y: number; frame: number; start: number}> = ({
  children,
  x,
  y,
  frame,
  start,
}) => (
  <div
    style={{
      position: "absolute",
      left: x,
      top: y,
      color: MUTED,
      fontFamily: "Arial, sans-serif",
      fontSize: 25,
      fontWeight: 700,
      letterSpacing: 3,
      ...enter(frame, start),
    }}
  >
    {children}
  </div>
);

const PromptBeat: React.FC<{frame: number}> = ({frame}) => {
  const cursor = interpolate(frame, [24, 100], [0, 395], clamp);
  const typed = Math.round(interpolate(frame, [28, 102], [0, 31], clamp));
  const sentence = "a paper plane flying at sunset".slice(0, typed);
  return (
    <>
      <Label x={150} y={118} frame={frame} start={0}>01 · THE PROMPT</Label>
      <div style={{position: "absolute", left: 150, top: 188, color: PAPER, font: "700 72px Arial", ...enter(frame, 5)}}>
        Start with an idea.
      </div>
      <svg width="1920" height="1080" style={{position: "absolute", inset: 0}}>
        <DrawPath frame={frame} start={13} d="M150 304 C390 288 660 292 948 304" color={ACCENT} width={7} />
        <rect x="150" y="390" width="850" height="250" rx="34" fill="#1E2025" stroke="#3B3D43" strokeWidth="4" />
        <circle cx="205" cy="445" r="13" fill={ACCENT} />
        <DrawPath frame={frame} start={116} d="M1085 512 C1195 512 1255 512 1358 512" color={INK} width={8} />
        <path d="M1358 512 L1327 491 L1327 533 Z" fill={INK} opacity={reveal(frame, 132, 12)} />
        <rect x="1410" y="360" width="345" height="305" rx="40" fill="#1C1E23" stroke={BLUE} strokeWidth="5" opacity={reveal(frame, 128, 18)} />
        <path d="M1492 576 Q1580 430 1670 576" fill="none" stroke={PAPER} strokeWidth="8" opacity={reveal(frame, 142)} />
        <circle cx="1640" cy="425" r="38" fill={ACCENT} opacity={reveal(frame, 150)} />
      </svg>
      <div style={{position: "absolute", left: 210, top: 485, color: PAPER, font: "500 41px Arial"}}>
        {sentence}<span style={{opacity: frame % 20 < 12 ? 1 : 0, color: ACCENT}}>|</span>
      </div>
      <div style={{position: "absolute", left: 1468, top: 690, color: MUTED, font: "700 23px Arial", letterSpacing: 2, opacity: reveal(frame, 156)}}>
        KEY FRAME
      </div>
      <div style={{position: "absolute", left: 150 + cursor, top: 664, width: 52, height: 5, borderRadius: 4, background: ACCENT, opacity: reveal(frame, 24)}} />
    </>
  );
};

const MotionBeat: React.FC<{frame: number}> = ({frame}) => {
  const local = frame - 150;
  const orbit = interpolate(local, [38, 130], [0, Math.PI * 1.3], clamp);
  const dots = Array.from({length: 10}, (_, index) => {
    const angle = (index / 10) * Math.PI * 2 + orbit;
    const radius = 205 + (index % 2) * 42;
    return {x: 960 + Math.cos(angle) * radius, y: 525 + Math.sin(angle) * radius};
  });
  return (
    <>
      <Label x={150} y={118} frame={local} start={0}>02 · PLAN THE MOTION</Label>
      <div style={{position: "absolute", left: 150, top: 188, color: PAPER, font: "700 72px Arial", ...enter(local, 5)}}>
        The model connects the frames.
      </div>
      <svg width="1920" height="1080" style={{position: "absolute", inset: 0}}>
        <circle cx="960" cy="525" r="300" fill="#191B20" stroke="#35373D" strokeWidth="4" opacity={reveal(local, 18)} />
        <DrawPath frame={local} start={26} d="M500 525 C640 390 735 400 845 500 C955 600 1075 660 1405 525" color={BLUE} width={10} length={1200} />
        {dots.map((dot, index) => (
          <circle
            key={index}
            cx={dot.x}
            cy={dot.y}
            r={index % 3 === 0 ? 16 : 10}
            fill={index % 3 === 0 ? ACCENT : PAPER}
            opacity={reveal(local, 35 + index * 5, 12)}
          />
        ))}
        <path d="M1405 525 L1368 500 L1368 550 Z" fill={BLUE} opacity={reveal(local, 90)} />
      </svg>
      <div style={{position: "absolute", left: 430, top: 780, width: 1060, color: MUTED, textAlign: "center", font: "500 31px Arial", opacity: reveal(local, 92)}}>
        Position, lighting and shape must remain consistent from one moment to the next.
      </div>
    </>
  );
};

const FramesBeat: React.FC<{frame: number}> = ({frame}) => {
  const local = frame - 300;
  const frameCards = Array.from({length: 5}, (_, index) => {
    const p = reveal(local, 18 + index * 10, 18);
    const planeX = 54 + index * 19;
    const planeY = 63 - Math.sin((index / 4) * Math.PI) * 24;
    return (
      <div
        key={index}
        style={{
          position: "relative",
          width: 278,
          height: 220,
          border: `3px solid ${index === 4 ? ACCENT : "#3A3C42"}`,
          borderRadius: 25,
          background: "linear-gradient(180deg,#253144 0%,#D98156 100%)",
          opacity: p,
          transform: `translateY(${(1 - p) * 12}px)`,
          overflow: "hidden",
        }}
      >
        <div style={{position: "absolute", left: `${planeX}%`, top: `${planeY}%`, width: 58, height: 34, transform: "translate(-50%,-50%) rotate(-12deg)"}}>
          <div style={{width: 0, height: 0, borderTop: "17px solid transparent", borderBottom: "17px solid transparent", borderLeft: `58px solid ${PAPER}`}} />
        </div>
        <div style={{position: "absolute", left: 0, right: 0, bottom: 0, height: 58, background: "#191A1E99"}} />
      </div>
    );
  });
  return (
    <>
      <Label x={150} y={118} frame={local} start={0}>03 · BUILD EVERY FRAME</Label>
      <div style={{position: "absolute", left: 150, top: 188, color: PAPER, font: "700 72px Arial", ...enter(local, 5)}}>
        One image becomes a sequence.
      </div>
      <div style={{position: "absolute", left: 150, top: 405, display: "flex", gap: 34}}>{frameCards}</div>
      <svg width="1920" height="1080" style={{position: "absolute", inset: 0}}>
        <DrawPath frame={local} start={78} d="M194 710 C530 790 1140 800 1720 710" color={ACCENT} width={7} length={1700} />
      </svg>
      <div style={{position: "absolute", left: 150, top: 855, color: MUTED, font: "500 31px Arial", opacity: reveal(local, 95)}}>
        The hard part is not movement. It is keeping the same world intact while it moves.
      </div>
    </>
  );
};

const ResultBeat: React.FC<{frame: number}> = ({frame}) => {
  const local = frame - 450;
  const play = spring({frame: local - 30, fps: 30, config: {damping: 18, stiffness: 110}});
  const flight = interpolate(local, [44, 132], [0, 1], clamp);
  return (
    <>
      <Label x={150} y={118} frame={local} start={0}>04 · THE RESULT</Label>
      <div style={{position: "absolute", left: 150, top: 188, color: PAPER, font: "700 72px Arial", ...enter(local, 5)}}>
        A video that feels continuous.
      </div>
      <div
        style={{
          position: "absolute",
          left: 250,
          top: 360,
          width: 1420,
          height: 510,
          overflow: "hidden",
          borderRadius: 48,
          border: `4px solid ${ACCENT}`,
          background: "linear-gradient(180deg,#273752 0%,#C9734D 72%,#27232A 100%)",
          opacity: Math.max(0, Math.min(1, play)),
          transform: `scale(${0.985 + Math.max(0, Math.min(1, play)) * 0.015})`,
        }}
      >
        <div style={{position: "absolute", right: 140, top: 84, width: 95, height: 95, borderRadius: 95, background: ACCENT}} />
        <div
          style={{
            position: "absolute",
            left: `${18 + flight * 65}%`,
            top: `${66 - Math.sin(flight * Math.PI) * 38}%`,
            width: 132,
            height: 72,
            transform: `translate(-50%,-50%) rotate(${-15 + flight * 12}deg)`,
          }}
        >
          <div style={{width: 0, height: 0, borderTop: "36px solid transparent", borderBottom: "36px solid transparent", borderLeft: `132px solid ${PAPER}`}} />
        </div>
        <svg width="1420" height="510" style={{position: "absolute", inset: 0}}>
          <path d="M170 350 C470 110 890 80 1220 295" fill="none" stroke={PAPER} strokeWidth="5" strokeDasharray="14 20" opacity={0.5} />
        </svg>
      </div>
      <div style={{position: "absolute", left: 0, right: 0, bottom: 92, textAlign: "center", color: PAPER, font: "600 34px Arial", opacity: reveal(local, 108)}}>
        Prompt → key frame → motion plan → finished clip
      </div>
    </>
  );
};

export const DrawnExplainer20s: React.FC = () => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const fadeIn = interpolate(frame, [0, 10], [0, 1], clamp);
  const fadeOut = interpolate(frame, [durationInFrames - 12, durationInFrames - 1], [1, 0], clamp);
  return (
    <AbsoluteFill style={{backgroundColor: BG, overflow: "hidden", opacity: fadeIn * fadeOut}}>
      {frame < 150 && <PromptBeat frame={frame} />}
      {frame >= 150 && frame < 300 && <MotionBeat frame={frame} />}
      {frame >= 300 && frame < 450 && <FramesBeat frame={frame} />}
      {frame >= 450 && <ResultBeat frame={frame} />}
      <div style={{position: "absolute", left: 150, bottom: 55, width: 1620, height: 2, background: "#2C2D32"}} />
    </AbsoluteFill>
  );
};
