import React from "react";
import {Composition, registerRoot} from "remotion";
import {DrawnExplainer20s} from "./concepts/DrawnExplainer20s";

const Root: React.FC = () => (
  <Composition
    id="DrawnExplainer20s"
    component={DrawnExplainer20s}
    durationInFrames={600}
    fps={30}
    width={1920}
    height={1080}
    defaultProps={{}}
  />
);

registerRoot(Root);
