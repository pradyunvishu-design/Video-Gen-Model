import {TransitionSeries, linearTiming} from "@remotion/transitions";
import {fade} from "@remotion/transitions/fade";
import {slide} from "@remotion/transitions/slide";
import {MotionShot} from "./MotionShot";
import {defaultMotionShotProps} from "./types";

const base = {
  ...defaultMotionShotProps,
  sourceImage: "review/magic-hour-generator.png",
  sourceLabel: "magichour.ai · official product page",
  annotation: null,
};

export const MotionSystemShowcase: React.FC = () => (
  <TransitionSeries>
    <TransitionSeries.Sequence durationInFrames={90} name="Real UI proof">
      <MotionShot {...base} annotation={{style: "underline", x: 0.34, y: 0.23, width: 0.32, height: 0.08, label: "Free AI Video Generator"}} template="ui_stage" kicker="REAL PRODUCT · REAL PROOF" title="SHOW THE RESULT FIRST" body="The source remains readable and exact." />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: 12})} />
    <TransitionSeries.Sequence durationInFrames={90} name="Connected explanation">
      <MotionShot {...base} template="orbit_map" kicker="WHY IT MATTERS" title="CONNECT THE EVIDENCE" body="One visible relationship at a time." />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={slide({direction: "from-right"})} timing={linearTiming({durationInFrames: 12})} />
    <TransitionSeries.Sequence durationInFrames={90} name="Controlled comparison">
      <MotionShot {...base} template="comparison" kicker="CONTROLLED TEST" title="CLAIM VERSUS EVIDENCE" body="The marketing promise versus what the captured result supports" labels={["CLAIM", "EVIDENCE"]} />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: 12})} />
    <TransitionSeries.Sequence durationInFrames={90} name="Decision flow">
      <MotionShot {...base} template="step_flow" kicker="USEFUL TAKEAWAY" title="TURN PROOF INTO A DECISION" labels={["SHOW", "EXPLAIN", "DECIDE"]} />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: 12})} />
    <TransitionSeries.Sequence durationInFrames={90} name="Sourced number">
      <MotionShot {...base} template="stat_reveal" kicker="SOURCED METRIC" title="LET THE NUMBER LAND" metric="1080p" body="Exact metrics are rendered locally and remain readable." />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: 12})} />
    <TransitionSeries.Sequence durationInFrames={90} name="Chapter reset">
      <MotionShot {...base} template="chapter_title" kicker="THE NEXT QUESTION" title="WHAT CHANGES FOR CREATORS?" body="A short reset before the next piece of evidence." />
    </TransitionSeries.Sequence>
  </TransitionSeries>
);
