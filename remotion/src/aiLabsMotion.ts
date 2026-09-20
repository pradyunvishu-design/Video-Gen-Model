import {Easing, interpolate, spring, type SpringConfig} from "remotion";

export const aiLabsEase = Easing.bezier(0.22, 1, 0.36, 1);

const gentleSpring: SpringConfig = {damping: 26, stiffness: 145, mass: 0.82, overshootClamping: true};

/** A small, settled entrance: fade + 12 px movement, never a dramatic pop. */
export const softEnter = (frame: number, fps: number, delay = 0) =>
  spring({frame: frame - delay, fps, config: gentleSpring});

export const eased = (frame: number, start: number, end: number) =>
  interpolate(frame, [start, end], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: aiLabsEase,
  });

export const smoothValue = (frame: number, start: number, end: number, from: number, to: number) =>
  interpolate(frame, [start, end], [from, to], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.cubic),
  });

export const quadraticPoint = (
  start: [number, number],
  control: [number, number],
  end: [number, number],
  progress: number,
) => {
  const inverse = 1 - progress;
  return {
    x: inverse * inverse * start[0] + 2 * inverse * progress * control[0] + progress * progress * end[0],
    y: inverse * inverse * start[1] + 2 * inverse * progress * control[1] + progress * progress * end[1],
  };
};
