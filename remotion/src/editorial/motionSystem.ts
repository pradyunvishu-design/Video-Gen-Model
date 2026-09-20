import {Easing, interpolate} from "remotion";

export type MotionIntent = "micro" | "enter" | "connect" | "emphasize";

const durations: Record<MotionIntent, number> = {
  micro: 8,
  enter: 16,
  connect: 28,
  emphasize: 22,
};

const easing: Record<MotionIntent, ReturnType<typeof Easing.bezier>> = {
  micro: Easing.bezier(0.2, 0, 0, 1),
  enter: Easing.bezier(0, 0, 0, 1),
  connect: Easing.bezier(0.4, 0, 0.2, 1),
  emphasize: Easing.bezier(0.16, 1, 0.3, 1),
};

export const motionDuration = (intent: MotionIntent, distance = 0) =>
  Math.round(durations[intent] + Math.min(10, Math.abs(distance) / 12));

export const motionProgress = (
  frame: number,
  intent: MotionIntent,
  delay = 0,
  distance = 0,
) => interpolate(frame, [delay, delay + motionDuration(intent, distance)], [0, 1], {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
  easing: easing[intent],
});

export const staggerDelay = (index: number, density: "tight" | "normal" | "open" = "normal") =>
  index * ({tight: 7, normal: 11, open: 15}[density]);

export const typewriterCount = (frame: number, text: string, delay: number, charactersPerSecond = 38, fps = 30) =>
  Math.max(0, Math.min(text.length, Math.floor(((frame - delay) / fps) * charactersPerSecond)));

