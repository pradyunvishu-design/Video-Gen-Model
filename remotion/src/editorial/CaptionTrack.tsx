import {createTikTokStyleCaptions} from "@remotion/captions";
import type {Caption} from "@remotion/captions";
import {useMemo} from "react";
import {useCurrentFrame, useVideoConfig} from "remotion";
import {editorial} from "./theme";

export const CaptionTrack: React.FC<{captions: Caption[]}> = ({captions}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const nowMs = frame / fps * 1000;
  const pages = useMemo(() => createTikTokStyleCaptions({captions, combineTokensWithinMilliseconds: 900}).pages, [captions]);
  const page = pages.find((candidate) => nowMs >= candidate.startMs && nowMs < candidate.startMs + candidate.durationMs);
  if (!page) return null;
  return (
    <div style={{position: "absolute", zIndex: 90, left: 420, right: 420, bottom: 88, display: "flex", justifyContent: "center", fontFamily: "Inter Variable, Inter, Arial, sans-serif"}}>
      <div style={{maxWidth: 2300, padding: "13px 24px 15px", borderRadius: 14, background: "rgba(9,10,10,.91)", border: `1px solid ${editorial.line}`, boxShadow: "0 14px 44px rgba(0,0,0,.42)", textAlign: "center", whiteSpace: "pre-wrap", fontSize: 56, lineHeight: 1.16, fontWeight: 650}}>
        {page.tokens.map((token, index) => {
          const active = nowMs >= token.fromMs && nowMs < token.toMs;
          return <span key={`${token.fromMs}-${index}`} style={{color: active ? editorial.yellow : editorial.white}}>{token.text}</span>;
        })}
      </div>
    </div>
  );
};
