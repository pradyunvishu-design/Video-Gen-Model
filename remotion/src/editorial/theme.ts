import {Easing, interpolate, staticFile} from "remotion";

export const editorial = {
  black: "#070808",
  blackSoft: "#0E0F0F",
  stage: "#101111",
  board: "#303231",
  boardRaised: "#3A3C3B",
  panel: "#171818",
  panelRaised: "#202121",
  line: "#343737",
  white: "#F2F1ED",
  muted: "#8E9290",
  mutedDark: "#626664",
  yellow: "#E8E32D",
  earth: "#4F5144",
  clay: "#5A4036",
  moss: "#3F5246",
};

export const editorialEase = Easing.bezier(0.22, 1, 0.36, 1);

export const enter = (frame: number, delay = 0, duration = 20) =>
  interpolate(frame, [delay, delay + duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: editorialEase,
  });

export const progress = (frame: number, start: number, end: number) =>
  interpolate(frame, [start, end], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: editorialEase,
  });

export const resolveEditorialAsset = (src: string) => {
  if (!src || /^(https?:|data:)/.test(src)) return src;
  return staticFile(src.replace(/^\/+/, ""));
};
