import type {EditorialScene} from "./schema";
import {ActivityScene} from "./scenes/ActivityScene";
import {ChatScene} from "./scenes/ChatScene";
import {CompareScene} from "./scenes/CompareScene";
import {GraphScene} from "./scenes/GraphScene";
import {SourceScene} from "./scenes/SourceScene";
import {TitleScene} from "./scenes/TitleScene";
import {TimelineScene} from "./scenes/TimelineScene";
import {TerminalScene} from "./scenes/TerminalScene";
import {StackScene} from "./scenes/StackScene";
import {KeynoteStageScene, StudioPodcastScene} from "./scenes/PresentationScenes";

export const SceneRouter: React.FC<{scene: EditorialScene; seriesName: string; footer: string}> = (props) => {
  if (props.scene.motionPattern === "chat-studio-podcast") return <StudioPodcastScene {...props} />;
  if (props.scene.motionPattern === "title-keynote-stage") return <KeynoteStageScene {...props} />;
  switch (props.scene.kind) {
    case "chat": return <ChatScene {...props} />;
    case "graph": return <GraphScene {...props} />;
    case "source": return <SourceScene {...props} />;
    case "activity": return <ActivityScene {...props} />;
    case "compare": return <CompareScene {...props} />;
    case "timeline": return <TimelineScene {...props} />;
    case "terminal": return <TerminalScene {...props} />;
    case "stack": return <StackScene {...props} />;
    case "title":
    default: return <TitleScene {...props} />;
  }
};
