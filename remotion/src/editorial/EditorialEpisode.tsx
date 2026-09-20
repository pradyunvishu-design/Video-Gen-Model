import {Audio} from "@remotion/media";
import {TransitionSeries, linearTiming} from "@remotion/transitions";
import {fade} from "@remotion/transitions/fade";
import {slide} from "@remotion/transitions/slide";
import type {ReactNode} from "react";
import {AbsoluteFill, useVideoConfig} from "remotion";
import {CaptionTrack} from "./CaptionTrack";
import {SceneRouter} from "./SceneRouter";
import type {EditorialEpisodeProps} from "./schema";
import {editorial, resolveEditorialAsset} from "./theme";
import {VisualStyleProvider} from "./styleProfile";

export const editorialTransitionFrames = (
  style: "hard-cut" | "fade" | "handoff" | undefined,
  profile?: EditorialEpisodeProps["visualStyleProfile"],
) => style === "handoff"
  ? (profile?.timing.handoffFrames ?? 8)
  : style === "hard-cut"
    ? 0
    : (profile?.timing.fadeFrames ?? 6);

export const editorialDurationInFrames = (props: EditorialEpisodeProps, fps = 30) => {
  const scenes = props.scenes.reduce((sum, scene) => sum + Math.round(scene.durationSeconds * fps), 0);
  const overlaps = props.scenes.slice(0, -1).reduce(
    (sum, scene) => sum + editorialTransitionFrames(scene.transitionAfter, props.visualStyleProfile), 0,
  );
  return Math.max(30, scenes - overlaps);
};

export const EditorialEpisode: React.FC<EditorialEpisodeProps> = (props) => {
  const {fps} = useVideoConfig();
  const gain = (db: number) => Math.pow(10, db / 20);
  const narrationGain = gain(props.audioProfile?.narrationGainDb ?? -1);
  const musicGain = gain(props.audioProfile?.musicGainDb ?? -28);
  const children: ReactNode[] = [];
  props.scenes.forEach((scene, index) => {
    children.push(
      <TransitionSeries.Sequence key={`scene-${scene.id}`} durationInFrames={Math.round(scene.durationSeconds * fps)}>
        <SceneRouter scene={scene} seriesName={props.seriesName} footer={props.footer} />
      </TransitionSeries.Sequence>,
    );
    if (index < props.scenes.length - 1) {
      const transitionFrames = editorialTransitionFrames(scene.transitionAfter, props.visualStyleProfile);
      if (!transitionFrames) return;
      children.push(
        <TransitionSeries.Transition key={`transition-${scene.id}`} presentation={scene.transitionAfter === "handoff" ? slide({direction: "from-right"}) : fade()} timing={linearTiming({durationInFrames: transitionFrames})} />,
      );
    }
  });
  return (
    <VisualStyleProvider value={props.visualStyleProfile ?? null}>
      <AbsoluteFill style={{background: props.visualStyleProfile?.canvas.background ?? editorial.black}}>
        <TransitionSeries>{children}</TransitionSeries>
        {props.audioSrc ? <Audio src={resolveEditorialAsset(props.audioSrc)} volume={narrationGain} /> : null}
        {props.audioProfile?.musicSrc ? <Audio src={resolveEditorialAsset(props.audioProfile.musicSrc)} volume={musicGain} loop /> : null}
        {props.captions.length ? <CaptionTrack captions={props.captions} /> : null}
      </AbsoluteFill>
    </VisualStyleProvider>
  );
};
