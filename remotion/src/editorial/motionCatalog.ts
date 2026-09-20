import type {EditorialScene} from "./schema";

export type MotionFamily = EditorialScene["kind"];
export type StageMode = "full" | "wide" | "split" | "open";
export type RevealMode = "type" | "stagger" | "draw" | "wipe" | "replace" | "focus";

export type MotionPattern = {
  id: string;
  family: MotionFamily;
  stage: StageMode;
  reveal: RevealMode;
  dominance: number;
  description: string;
};

// Original, reusable editorial patterns distilled from broad motion-design grammar.
// These are not copied frames: each entry describes an information relationship,
// a stage footprint, and a reveal order that can be populated with verified data.
export const MOTION_PATTERNS = [
  {id: "title-cold-open", family: "title", stage: "open", reveal: "wipe", dominance: .78, description: "Large claim, delayed evidence cue"},
  {id: "title-number-hook", family: "title", stage: "open", reveal: "replace", dominance: .82, description: "Number first, explanation second"},
  {id: "title-quote-reveal", family: "title", stage: "wide", reveal: "focus", dominance: .76, description: "Quote resolves into attribution"},
  {id: "title-chapter-reset", family: "title", stage: "full", reveal: "wipe", dominance: .84, description: "Full-frame chapter statement"},
  {id: "title-logo-verdict", family: "title", stage: "split", reveal: "stagger", dominance: .72, description: "Product mark and editorial verdict"},
  {id: "title-final-takeaway", family: "title", stage: "open", reveal: "focus", dominance: .8, description: "Single memorable closing idea"},
  {id: "title-brand-verdict-lockup", family: "title", stage: "split", reveal: "replace", dominance: .82, description: "Equal product marks resolve into one criterion-specific verdict"},
  {id: "title-keynote-stage", family: "title", stage: "full", reveal: "focus", dominance: .88, description: "Neutral synthetic presenter frames a verified product proof on a stage"},

  {id: "chat-peer-debate", family: "chat", stage: "wide", reveal: "stagger", dominance: .82, description: "Two-speaker disagreement"},
  {id: "chat-agent-handoff", family: "chat", stage: "full", reveal: "stagger", dominance: .88, description: "Work passes between agents"},
  {id: "chat-correction-thread", family: "chat", stage: "wide", reveal: "replace", dominance: .84, description: "Claim is corrected in sequence"},
  {id: "chat-async-status", family: "chat", stage: "full", reveal: "stagger", dominance: .86, description: "Parallel agent status messages"},
  {id: "chat-approval-gate", family: "chat", stage: "split", reveal: "focus", dominance: .78, description: "Request, review, approval"},
  {id: "chat-decision-log", family: "chat", stage: "wide", reveal: "wipe", dominance: .84, description: "Decision history with timestamps"},
  {id: "chat-brand-review-relay", family: "chat", stage: "full", reveal: "stagger", dominance: .9, description: "Builder output passes to an independent reviewer and verified result"},
  {id: "chat-studio-podcast", family: "chat", stage: "full", reveal: "stagger", dominance: .88, description: "Two neutral synthetic speakers discuss one verified product claim"},

  {id: "graph-hub-spoke", family: "graph", stage: "full", reveal: "draw", dominance: .88, description: "One system routes to many tools"},
  {id: "graph-dependency-chain", family: "graph", stage: "wide", reveal: "draw", dominance: .86, description: "Ordered dependency path"},
  {id: "graph-agent-network", family: "graph", stage: "full", reveal: "draw", dominance: .9, description: "Agents exchange work and state"},
  {id: "graph-request-response", family: "graph", stage: "split", reveal: "draw", dominance: .8, description: "Request and response directions"},
  {id: "graph-loop-cycle", family: "graph", stage: "full", reveal: "draw", dominance: .86, description: "Iterative feedback loop"},
  {id: "graph-branching-plan", family: "graph", stage: "wide", reveal: "stagger", dominance: .84, description: "Decision branches from one plan"},
  {id: "graph-brand-capability-ring", family: "graph", stage: "full", reveal: "draw", dominance: .9, description: "Verified capabilities attach to one product identity"},

  {id: "source-browser-proof", family: "source", stage: "full", reveal: "focus", dominance: .92, description: "Dominant browser evidence"},
  {id: "source-paper-callout", family: "source", stage: "full", reveal: "focus", dominance: .9, description: "Paper figure with one callout"},
  {id: "source-repo-metrics", family: "source", stage: "wide", reveal: "focus", dominance: .88, description: "Repository metrics and release state"},
  {id: "source-ui-feature", family: "source", stage: "full", reveal: "wipe", dominance: .92, description: "Product UI with feature focus"},
  {id: "source-demo-crop", family: "source", stage: "full", reveal: "focus", dominance: .94, description: "Locked crop of public demo"},
  {id: "source-before-after-ui", family: "source", stage: "split", reveal: "replace", dominance: .84, description: "Two verified interface states"},
  {id: "source-ui-focus-corridor", family: "source", stage: "full", reveal: "focus", dominance: .94, description: "Locked full-screen interface with one readable evidence corridor"},

  {id: "activity-task-queue", family: "activity", stage: "full", reveal: "stagger", dominance: .88, description: "Queued tasks resolve in order"},
  {id: "activity-checklist-progress", family: "activity", stage: "wide", reveal: "stagger", dominance: .84, description: "Verification checklist"},
  {id: "activity-status-ladder", family: "activity", stage: "full", reveal: "replace", dominance: .86, description: "Status advances through stages"},
  {id: "activity-error-recovery", family: "activity", stage: "wide", reveal: "replace", dominance: .84, description: "Failure becomes recovery"},
  {id: "activity-verification-pass", family: "activity", stage: "full", reveal: "focus", dominance: .88, description: "Checks end in a verdict"},
  {id: "activity-benchmark-run", family: "activity", stage: "split", reveal: "stagger", dominance: .8, description: "Measured run with result panel"},
  {id: "activity-ui-plan-to-progress", family: "activity", stage: "full", reveal: "replace", dominance: .9, description: "Authentic plan items advance into verified status rows"},

  {id: "compare-claim-proof", family: "compare", stage: "split", reveal: "focus", dominance: .82, description: "Claim beside evidence"},
  {id: "compare-old-new", family: "compare", stage: "split", reveal: "replace", dominance: .86, description: "Old workflow becomes new"},
  {id: "compare-side-by-side", family: "compare", stage: "full", reveal: "wipe", dominance: .88, description: "Equal product comparison"},
  {id: "compare-tradeoff-grid", family: "compare", stage: "wide", reveal: "stagger", dominance: .82, description: "Tradeoffs across dimensions"},
  {id: "compare-promise-reality", family: "compare", stage: "split", reveal: "focus", dominance: .84, description: "Marketing promise versus test"},
  {id: "compare-scorecard", family: "compare", stage: "full", reveal: "stagger", dominance: .88, description: "Criteria resolve into score"},
  {id: "compare-brand-prompt-fork", family: "compare", stage: "full", reveal: "wipe", dominance: .9, description: "One shared task forks to equal product lanes and measured outputs"},

  {id: "timeline-launch-sequence", family: "timeline", stage: "full", reveal: "draw", dominance: .88, description: "Launch milestones"},
  {id: "timeline-causality-chain", family: "timeline", stage: "full", reveal: "draw", dominance: .9, description: "Cause and effect sequence"},
  {id: "timeline-iteration-history", family: "timeline", stage: "wide", reveal: "stagger", dominance: .84, description: "Product iterations"},
  {id: "timeline-rollback-path", family: "timeline", stage: "full", reveal: "replace", dominance: .86, description: "Failure and rollback"},
  {id: "timeline-week-recap", family: "timeline", stage: "wide", reveal: "stagger", dominance: .82, description: "Weekly news chronology"},
  {id: "timeline-checkpoint-run", family: "timeline", stage: "full", reveal: "focus", dominance: .88, description: "Checkpoints end in verdict"},
  {id: "timeline-ui-agent-handoff", family: "timeline", stage: "full", reveal: "draw", dominance: .9, description: "A labeled task packet passes between authentic product stages"},

  {id: "terminal-command-run", family: "terminal", stage: "full", reveal: "type", dominance: .94, description: "Command followed by concise output"},
  {id: "terminal-streaming-output", family: "terminal", stage: "full", reveal: "type", dominance: .94, description: "Progressive logs with active line"},
  {id: "terminal-diff-apply", family: "terminal", stage: "full", reveal: "stagger", dominance: .92, description: "Readable patch with additions and removals"},
  {id: "terminal-test-suite", family: "terminal", stage: "full", reveal: "stagger", dominance: .92, description: "Tests resolve into pass or failure"},
  {id: "terminal-tool-call", family: "terminal", stage: "full", reveal: "replace", dominance: .94, description: "Tool request becomes structured result"},
  {id: "terminal-file-tree", family: "terminal", stage: "full", reveal: "stagger", dominance: .9, description: "Repository tree expands by branch"},
  {id: "terminal-ui-command-to-diff", family: "terminal", stage: "full", reveal: "replace", dominance: .94, description: "A real command resolves into a readable changed-files proof"},

  {id: "stack-context-layers", family: "stack", stage: "full", reveal: "stagger", dominance: .88, description: "Context layers in priority order"},
  {id: "stack-architecture", family: "stack", stage: "wide", reveal: "stagger", dominance: .86, description: "System architecture layers"},
  {id: "stack-source-rank", family: "stack", stage: "full", reveal: "focus", dominance: .88, description: "Evidence sources ranked"},
  {id: "stack-model-ladder", family: "stack", stage: "wide", reveal: "replace", dominance: .84, description: "Models ordered by capability"},
  {id: "stack-workflow-stages", family: "stack", stage: "full", reveal: "stagger", dominance: .88, description: "Workflow stages assemble"},
  {id: "stack-cost-layers", family: "stack", stage: "split", reveal: "stagger", dominance: .8, description: "Cost components accumulate"},
  {id: "stack-ui-proof-stack", family: "stack", stage: "full", reveal: "stagger", dominance: .9, description: "Official claim, tested output, and independent check assemble in order"},
] satisfies MotionPattern[];

export const MOTION_PATTERN_IDS = MOTION_PATTERNS.map((pattern) => pattern.id);

export const patternForScene = (scene: EditorialScene): MotionPattern => {
  const exact = MOTION_PATTERNS.find((pattern) => pattern.id === scene.motionPattern);
  return exact ?? MOTION_PATTERNS.find((pattern) => pattern.family === scene.kind)!;
};
