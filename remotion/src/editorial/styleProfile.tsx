import {createContext, useContext} from "react";
import type {EditorialEpisodeProps, EditorialScene} from "./schema";

type VisualStyleProfile = NonNullable<EditorialEpisodeProps["visualStyleProfile"]>;

const VisualStyleContext = createContext<VisualStyleProfile | null>(null);

export const VisualStyleProvider = VisualStyleContext.Provider;

export const useVisualStyle = () => useContext(VisualStyleContext);

const logicalPx = (finalPx: number, renderScale: number) => finalPx / Math.max(0.01, renderScale);

export const bodyTextPx = (scene: EditorialScene, fallbackLogicalPx: number, profile: VisualStyleProfile | null) => {
  const finalPx = Math.max(scene.bodyTextPx ?? 0, profile?.typography.minimumBodyPx ?? 0);
  return Math.max(fallbackLogicalPx, logicalPx(finalPx, profile?.canvas.renderScale ?? 1));
};

export const labelTextPx = (scene: EditorialScene, fallbackLogicalPx: number, profile: VisualStyleProfile | null) => {
  const finalPx = Math.max(scene.labelTextPx ?? 0, profile?.typography.minimumLabelPx ?? 0);
  return Math.max(fallbackLogicalPx, logicalPx(finalPx, profile?.canvas.renderScale ?? 1));
};

export const semanticStateFrame = (scene: EditorialScene, index: number, fps: number) =>
  Math.round(index * (scene.meaningfulStateChangeSeconds ?? 2.5) * fps);
