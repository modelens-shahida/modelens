"use client";

import React, { useState, useRef } from "react";
import Image from "next/image"; // ✅ Import added here

const BotikaInAction = () => {
  const [dividerX, setDividerX] = useState(50);
  const containerRef = useRef(null);

  // Handle mouse movement for slider
  const handleMouseMove = (e) => {
    if (!containerRef.current) return;

    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left; // x position inside container
    const newPos = (x / rect.width) * 100;

    // Clamp between 0–100%
    if (newPos >= 0 && newPos <= 100) setDividerX(newPos);
  };

  return (
    <section className="bg-white py-24 px-6 md:px-12 text-gray-900">
      {/* Heading */}
      <div className="text-center mb-16">
        <h2 className="text-3xl md:text-4xl font-bold mb-4">
        Watch ModeLens in Action
        </h2>
        <p className="text-lg text-gray-600">
          Hover and move your mouse to compare AI-generated and original fashion photos
        </p>
      </div>

      {/* Image Comparison Section */}
      <div
        ref={containerRef}
        className="relative mx-auto max-w-5xl w-full aspect-[16/9] overflow-hidden rounded-3xl shadow-xl cursor-col-resize select-none"
        onMouseMove={handleMouseMove}
      >
        {/* After Image (Background) */}
        <Image
          src="https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/67b1d25ccf7d399e089c6896_b120939f8d4beae5d45606d699d96f42_Botika_AIGeneratedModel_ComparisonAfter.avif"
          alt="After Botika"
          fill
          className="object-cover"
        />

        {/* Before Image (Overlay) */}
        <div
          className="absolute inset-0 overflow-hidden transition-all duration-75 ease-linear"
          style={{ clipPath: `inset(0 ${100 - dividerX}% 0 0)` }}
        >
          <Image
            src="https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/67b1d23f0649fa2a908026c6_67393b2efb5ad528a7eaa9d6699e56fa_Botika_AIGeneratedModel_ComparisonBefore.avif"
            alt="Before Botika"
            fill
            className="object-cover"
          />
        </div>

        {/* Divider Line */}
        <div
          className="absolute top-0 bottom-0 w-[3px] bg-gray-800 transition-all duration-75 ease-linear"
          style={{ left: `${dividerX}%`, transform: "translateX(-50%)" }}
        >
          {/* Handle Circle */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white border-2 border-gray-800 w-6 h-6 rounded-full shadow-md"></div>
        </div>
      </div>
    </section>
  );
};

export default BotikaInAction;
