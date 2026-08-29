import React from "react";
import {
  AbsoluteFill,
  Audio,
  CalculateMetadataFunction,
  Img,
  interpolate,
  OffthreadVideo,
  Sequence,
  staticFile,
  useCurrentFrame,
} from "remotion";

export type KraskiRecipe =
  | "bright-observation"
  | "parent-question"
  | "small-discovery";

export type KraskiShot = {
  src: string;
  mediaType: "image" | "video";
  startFrame: number;
  durationFrames: number;
  cropMode?: "cover" | "contain";
  transition?: "crossfade" | "push" | "reveal";
};

export type KraskiCaption = {
  text: string;
  accent?: string;
  startFrame: number;
  durationFrames: number;
  position?: "top" | "center" | "bottom";
};

export type KraskiVerticalProps = {
  shots: KraskiShot[];
  captions: KraskiCaption[];
  musicSrc?: string;
  recipe?: KraskiRecipe;
  accentColor?: string;
  backgroundColor?: string;
};

const resolveMedia = (src: string) =>
  src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:")
    ? src
    : staticFile(src.replace(/^\//, ""));

const recipeMotion = (recipe: KraskiRecipe, frame: number, duration: number) => {
  const progress = interpolate(frame, [0, Math.max(1, duration - 1)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  if (recipe === "parent-question") {
    return `translate3d(0, ${interpolate(progress, [0, 1], [18, -10])}px, 0) scale(${interpolate(progress, [0, 1], [1.04, 1.01])})`;
  }
  if (recipe === "small-discovery") {
    return `translate3d(${interpolate(progress, [0, 1], [-18, 12])}px, 0, 0) scale(${interpolate(progress, [0, 1], [1.08, 1.025])})`;
  }
  return `translate3d(${interpolate(progress, [0, 1], [8, -8])}px, 0, 0) scale(${interpolate(progress, [0, 1], [1.01, 1.055])})`;
};

const ShotLayer: React.FC<{ shot: KraskiShot; recipe: KraskiRecipe }> = ({
  shot,
  recipe,
}) => {
  const frame = useCurrentFrame();
  const fadeFrames = Math.min(8, Math.max(2, Math.floor(shot.durationFrames / 4)));
  const opacity = interpolate(
    frame,
    [0, fadeFrames, shot.durationFrames - fadeFrames, shot.durationFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const commonStyle: React.CSSProperties = {
    width: "100%",
    height: "100%",
    objectFit: shot.cropMode || "cover",
    transform: recipeMotion(recipe, frame, shot.durationFrames),
  };

  return (
    <AbsoluteFill style={{ opacity, overflow: "hidden" }}>
      {shot.mediaType === "video" ? (
        <OffthreadVideo src={resolveMedia(shot.src)} muted style={commonStyle} />
      ) : (
        <Img src={resolveMedia(shot.src)} style={commonStyle} />
      )}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(18,12,7,0.04) 40%, rgba(18,12,7,0.42) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};

const CaptionLayer: React.FC<{ caption: KraskiCaption; accentColor: string }> = ({
  caption,
  accentColor,
}) => {
  const frame = useCurrentFrame();
  const entry = interpolate(frame, [0, 6], [20, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = interpolate(
    frame,
    [0, 5, caption.durationFrames - 5, caption.durationFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const position = caption.position || "bottom";
  const alignItems = position === "center" ? "center" : "flex-end";
  const paddingTop = position === "top" ? 230 : 0;
  const paddingBottom = position === "bottom" ? 300 : position === "center" ? 700 : 0;
  const accentIndex = caption.accent ? caption.text.indexOf(caption.accent) : -1;
  const before = accentIndex >= 0 ? caption.text.slice(0, accentIndex) : caption.text;
  const accent = accentIndex >= 0 ? caption.accent ?? "" : "";
  const after = accentIndex >= 0 ? caption.text.slice(accentIndex + accent.length) : "";

  return (
    <AbsoluteFill
      style={{
        alignItems,
        justifyContent: position === "top" ? "flex-start" : "flex-end",
        padding: `${paddingTop}px 86px ${paddingBottom}px`,
        boxSizing: "border-box",
        opacity,
        transform: `translateY(${entry}px)`,
      }}
    >
      <div
        style={{
          maxWidth: 900,
          padding: "22px 28px 24px",
          borderRadius: 8,
          backgroundColor: "rgba(22, 17, 12, 0.72)",
          color: "#FFFFFF",
          fontFamily: "Inter, Arial, sans-serif",
          fontWeight: 750,
          fontSize: 60,
          lineHeight: 1.12,
          letterSpacing: 0,
          textAlign: "center",
          boxShadow: "0 10px 34px rgba(0, 0, 0, 0.22)",
        }}
      >
        {before}
        {accent && <span style={{ color: accentColor }}>{accent}</span>}
        {after}
      </div>
    </AbsoluteFill>
  );
};

export const KraskiVertical: React.FC<KraskiVerticalProps> = ({
  shots,
  captions,
  musicSrc,
  recipe = "bright-observation",
  accentColor = "#FF6B00",
  backgroundColor = "#17120D",
}) => (
  <AbsoluteFill style={{ backgroundColor }}>
    {shots.map((shot, index) => (
      <Sequence
        key={`${shot.src}-${index}`}
        from={shot.startFrame}
        durationInFrames={shot.durationFrames}
        premountFor={15}
      >
        <ShotLayer shot={shot} recipe={recipe} />
      </Sequence>
    ))}
    {captions.map((caption, index) => (
      <Sequence
        key={`${caption.text}-${index}`}
        from={caption.startFrame}
        durationInFrames={caption.durationFrames}
        premountFor={8}
      >
        <CaptionLayer caption={caption} accentColor={accentColor} />
      </Sequence>
    ))}
    {musicSrc && <Audio src={resolveMedia(musicSrc)} volume={0.18} />}
  </AbsoluteFill>
);

export const calculateKraskiVerticalMetadata: CalculateMetadataFunction<
  KraskiVerticalProps
> = async ({ props }) => {
  const shotEnd = Math.max(0, ...props.shots.map((shot) => shot.startFrame + shot.durationFrames));
  const captionEnd = Math.max(
    0,
    ...props.captions.map((caption) => caption.startFrame + caption.durationFrames),
  );
  return { durationInFrames: Math.max(30, shotEnd, captionEnd) };
};
