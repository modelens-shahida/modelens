"use client";
import React, { useEffect, useState } from "react";

const Images = [
  "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f03beddcb9104737fd6ff_ddc2c01bea0950dcea92a208ff42be1b_Botika_HomepageHeader_AIGeneratedModelsforFashion.webp",
  "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/682c7754e1a9ad2451d52f42_c6436f1a8c57ae1959294ab680d47db7_Botika_Homepage_FemaleAIGeneratedModelsforFashion_3.webp",
  "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/681a6a2d3a998a1ba41abf31_faf619129c580222eda1c4d4605f8010_Botika_HomepageHeader_AIGeneratedModelsforFashion_MobileMultiply_40_.webp",
  "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/682c77544796f0608b49079b_733f1726df3d9ea602f5dd0f3e47948c_Botika_Homepage_FemaleAIGeneratedModelsforFashion_4.webp",
];

const HeroSlider = () => {
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrent((prev) => (prev + 1) % Images.length);
    }, 5000); // change Image every 5 seconds
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="relative w-full h-screen overflow-hidden">
      {Images.map((Image, index) => (
        <div
          key={index}
          className={`absolute top-0 left-0 w-full h-full bg-cover bg-center transition-opacity duration-1000 ${
            index === current ? "opacity-100" : "opacity-0"
          }`}
          style={{ backgroundImage: `url(${Image})` }}
        ></div>
      ))}

      {/* Overlay (optional slight dark overlay for contrast) */}
      <div className="absolute top-0 left-0 w-full h-full bg-black/20"></div>

      {/* Center text (optional, can be replaced with actual content later) */}
      <div className="absolute inset-0 flex items-center justify-center text-center text-white z-10">
        <div>
          <h1 className="text-5xl font-bold mb-4">AI Generated Fashion Models</h1>
          <p className="text-lg">Experience the next generation of fashion visualization</p>
        </div>
      </div>
    </div>
  );
};

export default HeroSlider;
