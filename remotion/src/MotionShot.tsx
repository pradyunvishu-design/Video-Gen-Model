import type {MotionShotProps} from "./types";
import {
  ChapterTitle,
  Comparison,
  EvidenceFocus,
  OrbitMap,
  NewsIntro,
  StatReveal,
  StepFlow,
  UiStage,
} from "./scenes";
import {ListReveal} from "./scenes/ListReveal";
import {Timeline} from "./scenes/Timeline";
import {NewsWorkflow} from "./scenes/NewsWorkflow";
import {PromptAnatomy} from "./scenes/PromptAnatomy";

export const MotionShot: React.FC<MotionShotProps> = (props) => {
  let scene: React.ReactNode;
  switch (props.template) {
    case "ui_stage":
      scene = <UiStage {...props} />;
      break;
    case "evidence_focus":
      scene = <EvidenceFocus {...props} />;
      break;
    case "orbit_map":
      scene = <OrbitMap {...props} />;
      break;
    case "comparison":
      scene = <Comparison {...props} />;
      break;
    case "stat_reveal":
      scene = <StatReveal {...props} />;
      break;
    case "chapter_title":
      scene = <ChapterTitle {...props} />;
      break;
    case "news_intro":
      scene = <NewsIntro {...props} />;
      break;
    case "list_reveal":
      scene = <ListReveal {...props} />;
      break;
    case "timeline":
      scene = <Timeline {...props} />;
      break;
    case "news_workflow":
      scene = <NewsWorkflow {...props} />;
      break;
    case "prompt_anatomy":
      scene = <PromptAnatomy {...props} />;
      break;
    case "step_flow":
    default:
      scene = <StepFlow {...props} />;
      break;
  }
  return scene;
};
