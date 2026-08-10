"use client";
import React, { useEffect, useRef } from "react";

// OpenPose-18 skeleton connections
const POSE_PAIRS = [
  [1, 2], [1, 5], [2, 3], [3, 4], [5, 6], [6, 7],   // arms
  [1, 8], [8, 9], [9, 10],                              // right leg
  [1, 11], [11, 12], [12, 13],                          // left leg
  [1, 0],                                               // neck to nose
  [0, 14], [14, 16],                                    // right eye/ear
  [0, 15], [15, 17],                                    // left eye/ear
];

const KEYPOINT_COLORS = [
  "#FF6B6B", // 0 - nose
  "#FF9F43", // 1 - neck
  "#FECA57", // 2 - right shoulder
  "#48DBFB", // 3 - right elbow
  "#FF6B6B", // 4 - right wrist
  "#1DD1A1", // 5 - left shoulder
  "#54A0FF", // 6 - left elbow
  "#5F27CD", // 7 - left wrist
  "#FECA57", // 8 - right hip
  "#48DBFB", // 9 - right knee
  "#FF6B6B", // 10 - right ankle
  "#1DD1A1", // 11 - left hip
  "#54A0FF", // 12 - left knee
  "#5F27CD", // 13 - left ankle
  "#FF9F43", // 14 - right eye
  "#FECA57", // 15 - left eye
  "#48DBFB", // 16 - right ear
  "#1DD1A1", // 17 - left ear
];

const LIMB_COLORS = [
  "#FF6B6B", "#FF9F43", "#FECA57", "#48DBFB",
  "#1DD1A1", "#54A0FF", "#5F27CD", "#FF6B6B",
  "#FF9F43", "#FECA57", "#48DBFB", "#1DD1A1",
  "#54A0FF", "#5F27CD", "#FF6B6B", "#FF9F43",
];

export default function PoseVisualizer({
  imageUrl,
  keypoints,
  width = 400,
  height = 600,
  showLabels = false,
}) {
  const canvasRef = useRef(null);
  const imgRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current || !keypoints?.length) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const scaleX = canvas.width;
    const scaleY = canvas.height;

    // Draw limb connections
    POSE_PAIRS.forEach(([partA, partB], idx) => {
      const kpA = keypoints[partA];
      const kpB = keypoints[partB];
      if (!kpA || !kpB) return;
      if (kpA[2] < 0.1 || kpB[2] < 0.1) return; // skip low confidence

      const x1 = kpA[0] * scaleX;
      const y1 = kpA[1] * scaleY;
      const x2 = kpB[0] * scaleX;
      const y2 = kpB[1] * scaleY;

      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.strokeStyle = LIMB_COLORS[idx % LIMB_COLORS.length];
      ctx.lineWidth = 3;
      ctx.lineCap = "round";
      ctx.stroke();
    });

    // Draw keypoints
    keypoints.forEach((kp, idx) => {
      if (!kp || kp[2] < 0.1) return;
      const x = kp[0] * scaleX;
      const y = kp[1] * scaleY;

      ctx.beginPath();
      ctx.arc(x, y, 5, 0, 2 * Math.PI);
      ctx.fillStyle = KEYPOINT_COLORS[idx % KEYPOINT_COLORS.length];
      ctx.fill();
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      if (showLabels) {
        ctx.fillStyle = "#fff";
        ctx.font = "10px sans-serif";
        ctx.fillText(idx, x + 7, y + 4);
      }
    });
  }, [keypoints, width, height, showLabels]);

  return (
    <div className="relative inline-block" style={{ width, height }}>
      {imageUrl && (
        <img
          ref={imgRef}
          src={imageUrl}
          alt="Pose reference"
          className="absolute inset-0 w-full h-full object-cover rounded-xl"
          style={{ width, height }}
        />
      )}
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        className="absolute inset-0 rounded-xl"
        style={{ width, height }}
      />
    </div>
  );
}
