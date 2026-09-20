import type {CalculateMetadataFunction} from "remotion";
import {Composition, Folder} from "remotion";
import {MotionShot} from "./MotionShot";
import {MotionSystemShowcase} from "./Showcase";
import {defaultMotionShotProps, motionShotSchema, type MotionShotProps} from "./types";
import {MagicHourEducationalEpisode} from "./episode/EducationalEpisode";
import {ViralNewsEpisode} from "./episode/ViralNewsEpisode";
import {ClaudeChipEpisode} from "./episode/ClaudeChipEpisode";
import {H3DeepDiveEpisode} from "./episode/H3DeepDiveEpisode";
import {
  H3MotionPack,
  H3_MOTION_SCENE_FRAMES,
  defaultH3MotionPackProps,
  type H3MotionPackProps,
} from "./episode/H3MotionGraphic";
import {EditorialProof30sV4} from "./EditorialProof30sV4";
import {EditorialEpisode, editorialDurationInFrames} from "./editorial/EditorialEpisode";
import {defaultEditorialEpisode} from "./editorial/defaultEpisode";
import {editorialEpisodeSchema, type EditorialEpisodeProps} from "./editorial/schema";

const calculateMotionMetadata: CalculateMetadataFunction<MotionShotProps> = ({props}) => ({
  durationInFrames: Math.max(30, Math.round(props.durationSeconds * 30)),
  // Existing scene measurements use a 2x logical coordinate grid. Remotion
  // rasterizes that grid directly to 1920x1080 via --scale=0.5.
  width: 3840,
  height: 2160,
  fps: 30,
  defaultOutName: `motion-${props.template}-1080p.mp4`,
});

const calculateEditorialMetadata: CalculateMetadataFunction<EditorialEpisodeProps> = ({props}) => ({
  durationInFrames: editorialDurationInFrames(props, 30),
  width: 3840,
  height: 2160,
  fps: 30,
  defaultOutName: `${props.episodeId}-1080p.mp4`,
});

const calculateH3MotionPackMetadata: CalculateMetadataFunction<H3MotionPackProps> = ({props}) => ({
  durationInFrames: Math.max(H3_MOTION_SCENE_FRAMES, props.scenes.length * H3_MOTION_SCENE_FRAMES),
  width: 1920,
  height: 1080,
  fps: 30,
  defaultOutName: "h3-motion-pack-1080p.mp4",
});

export const MotionCompositions: React.FC = () => (
  <>
    <Folder name="AI-Media-Motion-System">
      <Composition
        id="MotionShot1080"
        component={MotionShot}
        durationInFrames={150}
        fps={30}
        width={3840}
        height={2160}
        defaultProps={defaultMotionShotProps}
        schema={motionShotSchema}
        calculateMetadata={calculateMotionMetadata}
      />
      <Composition
        id="MotionSystemShowcase1080"
        component={MotionSystemShowcase}
        durationInFrames={480}
        fps={30}
        width={3840}
        height={2160}
      />
      <Composition
        id="EditorialProof30s1080"
        component={EditorialProof30sV4}
        durationInFrames={900}
        fps={30}
        width={3840}
        height={2160}
      />
      <Composition
        id="EditorialEpisode1080"
        component={EditorialEpisode}
        durationInFrames={900}
        fps={30}
        width={3840}
        height={2160}
        defaultProps={defaultEditorialEpisode}
        schema={editorialEpisodeSchema}
        calculateMetadata={calculateEditorialMetadata}
      />
      <Composition
        id="ProofFirstNarratedShort1080"
        component={EditorialEpisode}
        durationInFrames={900}
        fps={30}
        width={3840}
        height={2160}
        defaultProps={{...defaultEditorialEpisode, creativeProfile: "hermes-proof-first-v1"}}
        schema={editorialEpisodeSchema}
        calculateMetadata={calculateEditorialMetadata}
      />
    </Folder>
    <Folder name="Longform-Episodes">
      <Composition
        id="ClaudeChipEpisode8m"
        component={ClaudeChipEpisode}
        durationInFrames={14400}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{}}
      />
      <Composition
        id="MiniMaxH3DeepDive10m"
        component={H3DeepDiveEpisode}
        durationInFrames={18000}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{}}
      />
      <Composition
        id="MiniMaxH3MotionPack1080"
        component={H3MotionPack}
        durationInFrames={H3_MOTION_SCENE_FRAMES}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={defaultH3MotionPackProps}
        calculateMetadata={calculateH3MotionPackMetadata}
      />
      <Composition
        id="ViralAINews2m30"
        component={ViralNewsEpisode}
        durationInFrames={3600}
        fps={24}
        width={1920}
        height={1080}
        defaultProps={{}}
      />
      <Composition
        id="MagicHourEducational6m"
        component={MagicHourEducationalEpisode}
        durationInFrames={8640}
        fps={24}
        width={1920}
        height={1080}
        defaultProps={{}}
      />
    </Folder>
  </>
);
