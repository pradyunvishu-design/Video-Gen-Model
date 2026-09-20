import {Easing, interpolate, useCurrentFrame} from "remotion";

type SourceCreditProps = {
  label: string;
  placement?: "bottomLeft" | "topRight";
  inset?: number;
};

const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;

export const SourceCredit: React.FC<SourceCreditProps> = ({
  label,
  placement = "bottomLeft",
  inset = placement === "topRight" ? 42 : 38,
}) => {
  const frame = useCurrentFrame();
  const enter = interpolate(frame, [5, 13], [0, 1], {
    ...clamp,
    easing: Easing.out(Easing.cubic),
  });
  const position = placement === "topRight"
    ? {right: inset, top: inset}
    : {left: inset, bottom: inset};

  return (
    <div
      style={{
        position: "absolute",
        zIndex: 30,
        ...position,
        minHeight: 48,
        display: "grid",
        gridTemplateColumns: "3px auto 1px auto",
        alignItems: "center",
        columnGap: 16,
        padding: "0 18px 0 0",
        background: "rgba(14,17,15,.88)",
        borderTop: "1px solid rgba(167,177,171,.42)",
        color: "#F1F2EE",
        fontFamily: "Inter Variable,Inter,Arial,sans-serif",
        opacity: enter,
        transform: `translateX(${(1 - enter) * (placement === "topRight" ? 8 : -8)}px)`,
      }}
    >
      <span style={{alignSelf: "stretch", background: "#83938C"}} />
      <span style={{fontSize: 16, fontWeight: 650, letterSpacing: 1.8, color: "#A8AFAB"}}>SOURCE</span>
      <span style={{height: 25, background: "#4B534E"}} />
      <span style={{fontSize: 19, fontWeight: 720, letterSpacing: .25, whiteSpace: "nowrap"}}>{label}</span>
    </div>
  );
};
