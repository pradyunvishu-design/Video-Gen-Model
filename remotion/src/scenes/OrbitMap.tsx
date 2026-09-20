import {spring, useCurrentFrame, useVideoConfig} from "remotion";
import {EditorialMascot, GlassPanel, Headline, Kicker, MagicHourBackdrop, editorialPalette} from "../design-system";
import type {MotionShotProps} from "../types";

export const OrbitMap: React.FC<MotionShotProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const labels = props.labels.slice(0, 4);
  return (
    <MagicHourBackdrop variant="orbit_map">
      {props.showEditorialHeading ? <div style={{display: "flex", flexDirection: "column", alignItems: "center"}}><Kicker accent={props.accent}>{props.kicker}</Kicker><div style={{marginTop: 50}}><Headline size={132} align="center">{props.title}</Headline></div></div> : null}
      <div style={{position: "absolute", left: 0, right: 0, top: props.showEditorialHeading ? 480 : 360, height: 1440, display: "flex", alignItems: "center", justifyContent: "center"}}>
        <div
          style={{
            position: "relative",
            width: 1200,
            height: 1200,
            borderRadius: "50%",
            border: "7px dashed rgba(255,255,255,0.24)",
          }}
        >
          <GlassPanel style={{position: "absolute", left: 215, right: 215, top: 455, height: 290, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", padding: "0 72px"}}>
            <div style={{fontSize: 58, lineHeight: 1.12, fontWeight: 820, textAlign: "center"}}>{props.body || props.title}</div>
          </GlassPanel>
          {labels.map((label, index) => {
            const angle = -Math.PI / 2 + (index * Math.PI * 2) / labels.length;
            const radius = 500;
            const x = 600 + Math.cos(angle) * radius - 150;
            const y = 600 + Math.sin(angle) * radius - 150;
            const entrance = spring({frame: frame - index * 7, fps, config: {damping: 200, stiffness: 150, mass: 0.75}});
            const color = [props.accent, props.accentSecondary, editorialPalette.blue, editorialPalette.paper][index % 4];
            const mascot = props.mascots[index % Math.max(1, props.mascots.length)] || "codex";
            return (
              <div
                key={`${label}-${index}`}
                style={{
                  position: "absolute",
                  left: x,
                  top: y,
                  width: 300,
                  height: 300,
                  borderRadius: 54,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  background: editorialPalette.card,
                  border: `4px solid ${color}`,
                  boxShadow: "0 36px 80px rgba(0,0,0,0.35)",
                  scale: entrance,
                }}
              >
                <EditorialMascot kind={mascot} size={170} delay={index * 7} />
                <div style={{fontSize: 38, lineHeight: 1.05, fontWeight: 760, marginTop: 0, textAlign: "center", maxWidth: 260}}>{label}</div>
              </div>
            );
          })}
        </div>
      </div>
    </MagicHourBackdrop>
  );
};
