import type {Caption} from "@remotion/captions";

export type EpisodeBeat = {
  id: string;
  narration: string;
  claim_ids: string[];
  purpose: string;
  visual_direction: string;
  source_ids: string[];
  startMs: number;
  endMs: number;
  wordCount: number;
};

export type SourceInfo = {
  title: string;
  url: string;
  publisher: string;
};

export type SourceAssets = Partial<Record<"viewport" | "full_page" | "screen_recording", string>>;

export type EpisodeData = {
  episodeId: string;
  title: string;
  description: string;
  disclosure: string;
  durationSeconds: number;
  beats: EpisodeBeat[];
  sources: Record<string, SourceInfo>;
  assets: Record<string, SourceAssets>;
  generatedMotion?: string[];
  credits: number;
};

export type LoadedEpisode = {
  episode: EpisodeData;
  captions: Caption[];
};
