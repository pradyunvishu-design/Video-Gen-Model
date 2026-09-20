import type {EditorialEpisodeProps} from "./schema";

const empty = {messages: [], nodes: [], edges: [], items: [], sourceAsset: "", sourceLabel: "", sourceUrl: "", evidenceIds: [], sourceStartSeconds: 0, sourceFocus: null, claim: "", evidence: ""};

export const defaultEditorialEpisode: EditorialEpisodeProps = {
  episodeId: "editorial-system-proof-v1",
  creativeProfile: "default",
  seriesName: "AI NEWS / FIELD NOTES",
  footer: "SOURCE FIRST · EXPLANATION SECOND",
  audioSrc: "",
  captions: [],
  scenes: [
    {
      ...empty,
      id: "launch", kind: "title", durationSeconds: 5, chapter: "01 / THE LAUNCH",
      title: "ONE MODEL. FOUR MODES.",
      subtitle: "The useful question is not what the launch page promises. It is what the evidence can actually support.",
      anchor: "left", accent: "#FF6673",
      logos: [
        {name: "MiniMax", src: "brands/minimax.svg", color: "#FF6673"},
        {name: "Claude", src: "brands/claude.svg", color: "#D97757"},
        {name: "OpenAI", src: "brands/openai.svg", color: "#F2F1ED"},
      ],
    },
    {
      ...empty,
      id: "conversation", kind: "chat", durationSeconds: 5, chapter: "02 / WHAT CHANGED",
      title: "#model-review", subtitle: "", anchor: "center", accent: "#E8E32D", logos: [],
      messages: [
        {speaker: "MiniMax H3", logo: "brands/minimax.svg", color: "#FF6673", time: "9:41", text: "I generate text, images, video, and audio."},
        {speaker: "Editor", logo: "brands/openai.svg", color: "#F2F1ED", time: "9:42", text: "Cool. What is the actual limit?"},
        {speaker: "MiniMax H3", logo: "brands/minimax.svg", color: "#FF6673", time: "9:43", text: "Fifteen seconds, with 2K output on the hosted product."},
        {speaker: "Editor", logo: "brands/openai.svg", color: "#F2F1ED", time: "9:44", text: "That is useful. It is not magic."},
      ],
    },
    {
      ...empty,
      id: "map", kind: "graph", durationSeconds: 5, chapter: "03 / THE SYSTEM",
      title: "THE CLAIM MAP", subtitle: "Every claim needs somewhere specific to land.", anchor: "left", accent: "#FF6673", logos: [],
      nodes: [
        {id: "h3", label: "H3", logo: "brands/minimax.svg", color: "#FF6673", x: 0.18, y: 0.5},
        {id: "text", label: "TEXT", color: "#F2F1ED", x: 0.54, y: 0.2},
        {id: "image", label: "IMAGE", color: "#F2F1ED", x: 0.69, y: 0.4},
        {id: "video", label: "VIDEO", color: "#F2F1ED", x: 0.69, y: 0.67},
        {id: "audio", label: "AUDIO", color: "#F2F1ED", x: 0.54, y: 0.84},
      ],
      edges: [["h3", "text"], ["h3", "image"], ["h3", "video"], ["h3", "audio"]],
    },
    {
      ...empty,
      id: "receipt", kind: "source", durationSeconds: 5, chapter: "04 / THE RECEIPT",
      title: "SHOW THE SOURCE", subtitle: "The underline appears once, on the exact evidence being discussed.", anchor: "right", accent: "#FF6673", logos: [],
      sourceAsset: "episode/h3-news/minimax_launch-minimax-h3-official-launch-viewport.png",
      sourceLabel: "MINIMAX · OFFICIAL LAUNCH", sourceUrl: "https://minimax.io/news/minimax-h3", evidenceIds: ["src-minimax-h3-official-launch"],
      sourceFocus: {x: 0.32, y: 0.16, width: 0.48, height: 0.08, label: "15 SECONDS · 2K"},
    },
    {
      ...empty,
      id: "check", kind: "activity", durationSeconds: 5, chapter: "05 / THE CHECK",
      title: "RESEARCH ACTIVITY", subtitle: "Verification is a sequence, not a vibe.", anchor: "left", accent: "#E8E32D", logos: [],
      items: ["Official announcement", "Repository and model card", "Dates, limits, and pricing", "Independent hands-on result"],
    },
    {
      ...empty,
      id: "verdict", kind: "compare", durationSeconds: 6, chapter: "06 / THE VERDICT",
      title: "PROOF BEATS HYPE.", subtitle: "A clean conclusion is more memorable than another cinematic AI montage.", anchor: "center", accent: "#E8E32D", logos: [],
      claim: "One model replaces every creative tool.",
      evidence: "It combines four output modes, but duration, resolution, cost, and control still decide whether it is useful.",
    },
  ],
};
