import {zColor} from "@remotion/zod-types";
import {z} from "zod";

export const motionTemplateSchema = z.enum([
  "ui_stage",
  "evidence_focus",
  "orbit_map",
  "step_flow",
  "comparison",
  "stat_reveal",
  "chapter_title",
  "news_intro",
  "list_reveal",
  "timeline",
  "news_workflow",
  "prompt_anatomy",
]);

export const mascotSchema = z.enum(["claude", "codex", "gemini", "open_source"]);

export const motionShotSchema = z.object({
  template: motionTemplateSchema,
  kicker: z.string().max(40),
  title: z.string().max(110),
  body: z.string().max(240),
  metric: z.string().max(32),
  sourceImage: z.string(),
  sourceLabel: z.string().max(64),
  labels: z.array(z.string().max(32)).min(2).max(5),
  durationSeconds: z.number().min(1).max(30),
  showEditorialHeading: z.boolean().default(false),
  accent: zColor(),
  accentSecondary: zColor(),
  annotation: z
    .object({
      style: z.enum(["zoom", "underline", "arrow", "outline", "spotlight", "callout"]),
      x: z.number().min(0).max(1),
      y: z.number().min(0).max(1),
      width: z.number().min(0.01).max(1),
      height: z.number().min(0.01).max(1),
      label: z.string().max(48),
    })
    .nullable(),
  chapterTone: z.enum(["ink", "moss", "clay"]),
  mascots: z.array(mascotSchema).max(4),
  cursor: z
    .object({
      startX: z.number().min(0).max(1),
      startY: z.number().min(0).max(1),
      endX: z.number().min(0).max(1),
      endY: z.number().min(0).max(1),
      click: z.boolean(),
    })
    .nullable(),
});

export type MotionShotProps = z.infer<typeof motionShotSchema>;

export const defaultMotionShotProps: MotionShotProps = {
  template: "orbit_map",
  kicker: "AI MEDIA — EXPLAINED",
  title: "ONE IDEA. CLEAR PROOF.",
  body: "Real source material carries the claim. Motion makes the relationship easier to understand.",
  metric: "1080p",
  sourceImage: "",
  sourceLabel: "PRIMARY SOURCE",
  labels: ["SOURCE", "MODEL", "TOOL", "RESULT"],
  durationSeconds: 5,
  showEditorialHeading: false,
  accent: "#EAF21D",
  accentSecondary: "#607457",
  annotation: null,
  chapterTone: "ink",
  mascots: ["claude", "codex"],
  cursor: null,
};
