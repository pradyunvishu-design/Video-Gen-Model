import type {Caption} from "@remotion/captions";
import {zColor} from "@remotion/zod-types";
import {z} from "zod";

export const editorialLogoSchema = z.object({
  name: z.string().min(1).max(36),
  src: z.string().min(1),
  color: zColor(),
});

export const editorialMessageSchema = z.object({
  speaker: z.string().min(1).max(36),
  logo: z.string().min(1),
  color: zColor(),
  time: z.string().max(12),
  text: z.string().min(1).max(120),
});

export const editorialNodeSchema = z.object({
  id: z.string().min(1).max(32),
  label: z.string().min(1).max(36),
  logo: z.string().optional(),
  color: zColor(),
  x: z.number().min(0.05).max(0.95),
  y: z.number().min(0.08).max(0.92),
});

export const editorialVisualStyleProfileSchema = z.object({
  version: z.string().min(1).max(64),
  status: z.string().min(1).max(32),
  canvas: z.object({
    background: zColor(),
    paper: zColor(),
    accent: zColor(),
    safeInsetPx: z.number().min(40).max(220),
    logicalWidth: z.number().int().positive().optional(),
    logicalHeight: z.number().int().positive().optional(),
    outputWidth: z.number().int().positive().optional(),
    outputHeight: z.number().int().positive().optional(),
    renderScale: z.number().positive().max(1).optional(),
    allowRepeatedFrameFurniture: z.boolean(),
  }),
  timing: z.object({
    meaningfulStateChangeMinSeconds: z.number().min(1).max(5),
    meaningfulStateChangeMaxSeconds: z.number().min(1).max(6),
    fadeFramesMin: z.number().int().min(1).max(12),
    fadeFramesMax: z.number().int().min(1).max(16),
    fadeFrames: z.number().int().min(1).max(16),
    handoffFrames: z.number().int().min(1).max(16),
  }),
  typography: z.object({minimumBodyPx: z.number().min(18), minimumLabelPx: z.number().min(14)}),
  delivery: z.object({
    width: z.number().int().positive(),
    height: z.number().int().positive(),
    fps: z.number().positive(),
    videoCodec: z.string().min(1),
    audioCodec: z.string().min(1),
    audioChannels: z.number().int().positive(),
    audioSampleRate: z.number().int().positive(),
  }).optional(),
  captions: z.object({
    maximumGapMs: z.number().int().nonnegative(),
    maximumFirstStartMs: z.number().int().nonnegative(),
    maximumTrailingSilenceMs: z.number().int().nonnegative(),
  }).optional(),
  dominance: z.record(z.string(), z.number().min(0.5).max(1)),
  repetition: z.record(z.string(), z.number()),
  routing: z.record(z.string(), z.array(z.string())),
  forbiddenFurniture: z.array(z.string()),
  integrity: z.object({
    failClosed: z.boolean(),
    evidenceLedgerRequired: z.boolean(),
    rendererBindingRequired: z.boolean(),
  }).optional(),
});

export const editorialSceneSchema = z.object({
  id: z.string().min(1).max(64),
  kind: z.enum(["title", "chat", "graph", "source", "activity", "compare", "timeline", "terminal", "stack"]),
  motionPattern: z.string().min(1).max(64).optional(),
  durationSeconds: z.number().min(2).max(20),
  chapter: z.string().max(42),
  title: z.string().max(120),
  subtitle: z.string().max(220),
  anchor: z.enum(["left", "center", "right"]),
  accent: zColor(),
  logos: z.array(editorialLogoSchema).max(6),
  messages: z.array(editorialMessageSchema).max(8),
  nodes: z.array(editorialNodeSchema).max(10),
  edges: z.array(z.tuple([z.string(), z.string()])).max(16),
  items: z.array(z.string().max(72)).max(8),
  sourceAsset: z.string(),
  sourceLabel: z.string().max(60),
  sourceUrl: z.string().max(180),
  evidenceIds: z.array(z.string().min(1).max(80)).max(12),
  sourceStartSeconds: z.number().nonnegative().optional(),
  transitionAfter: z.enum(["hard-cut", "fade", "handoff"]).optional(),
  sourceObjectPosition: z.string().max(24).optional(),
  sourceFocus: z.object({
    x: z.number().min(0).max(1),
    y: z.number().min(0).max(1),
    width: z.number().min(0.02).max(1),
    height: z.number().min(0.02).max(1),
    label: z.string().max(48),
  }).nullable(),
  claim: z.string().max(120),
  evidence: z.string().max(160),
  semanticIntent: z.string().max(32).optional(),
  compositionFamily: z.string().max(32).optional(),
  proofDominance: z.number().min(0.5).max(1).optional(),
  bodyTextPx: z.number().min(18).max(120).optional(),
  labelTextPx: z.number().min(14).max(80).optional(),
  visualStates: z.array(z.string().min(1).max(64)).max(8).optional(),
  meaningfulStateChangeSeconds: z.number().min(1).max(6).optional(),
  annotationPurpose: z.string().max(120).optional(),
  transitionReason: z.string().max(160).optional(),
  furnitureIds: z.array(z.string().min(1).max(64)).max(12).optional(),
});

export const editorialEpisodeSchema = z.object({
  episodeId: z.string().min(1).max(80),
  creativeProfile: z.enum(["default", "hermes-proof-first-v1"]).optional(),
  visualStyleProfileVersion: z.string().min(1).max(64).optional(),
  visualStyleProfile: editorialVisualStyleProfileSchema.optional(),
  visualStyleProfileSha256: z.string().regex(/^[a-f0-9]{64}$/).optional(),
  lockedEvidenceIds: z.array(z.string().min(1).max(80)).optional(),
  lockedEvidenceLedger: z.record(z.string(), z.object({
    claim: z.string().min(1),
    sourceUrl: z.string().min(1),
    assetPath: z.string().min(1),
    assetSha256: z.string().regex(/^[a-f0-9]{64}$/),
  })).optional(),
  lockedEvidenceLedgerSha256: z.string().regex(/^[a-f0-9]{64}$/).optional(),
  approvedScript: z.string().min(1).optional(),
  seriesName: z.string().min(1).max(42),
  footer: z.string().max(70),
  audioSrc: z.string(),
  audioProfile: z.object({
    narrationGainDb: z.number().min(-24).max(6),
    musicSrc: z.string(),
    musicGainDb: z.number().min(-60).max(-6),
  }).optional(),
  captions: z.array(z.object({
    text: z.string(),
    startMs: z.number().nonnegative(),
    endMs: z.number().nonnegative(),
    timestampMs: z.number().nullable(),
    confidence: z.number().nullable(),
  })),
  scenes: z.array(editorialSceneSchema).min(1).max(180),
});

export type EditorialLogo = z.infer<typeof editorialLogoSchema>;
export type EditorialMessage = z.infer<typeof editorialMessageSchema>;
export type EditorialNode = z.infer<typeof editorialNodeSchema>;
export type EditorialScene = z.infer<typeof editorialSceneSchema>;
export type EditorialEpisodeProps = Omit<z.infer<typeof editorialEpisodeSchema>, "captions"> & {captions: Caption[]};
