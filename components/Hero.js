"use client";
import React, { useEffect, useState } from "react";

const Images = [
  "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f03beddcb9104737fd6ff_ddc2c01bea0950dcea92a208ff42be1b_Botika_HomepageHeader_AIGeneratedModelsforFashion.webp",
  "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/682c7754e1a9ad2451d52f42_c6436f1a8c57ae1959294ab680d47db7_Botika_Homepage_FemaleAIGeneratedModelsforFashion_3.webp",
  "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/681a6a2d3a998a1ba41abf31_faf619129c580222eda1c4d4605f8010_Botika_HomepageHeader_AIGeneratedModelsforFashion_MobileMultiply_40_.webp",
  "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/682c77544796f0608b49079b_733f1726df3d9ea602f5dd0f3e47948c_Botika_Homepage_FemaleAIGeneratedModelsforFashion_4.webp",
];

const Hero = () => {
  const [current, setCurrent] = useState(0);
  const [scale, setScale] = useState(1);
  const [rounded, setRounded] = useState(false);

  // Auto Image slider
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrent((prev) => (prev + 1) % Images.length);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  // Scroll-based effect for radius + slight zoom
  useEffect(() => {
    const handleScroll = () => {
      const scrollY = window.scrollY;
      setScale(Math.max(0.95, 1 - scrollY / 3000));
      setRounded(scrollY > 50); // radius activates after small scroll
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div className="relative w-full h-148 overflow-hidden">
      {/* Image container */}
      <div
        className="absolute top-0 left-0 w-full h-full transition-transform duration-500 ease-out"
        style={{ transform: `scale(${scale})` }}
      >
        {Images.map((Image, index) => (
          <div
            key={index}
            className={`absolute top-0 left-0 w-full h-full bg-cover bg-center transition-all duration-700 ${
              index === current ? "opacity-100" : "opacity-0"
            } ${rounded ? "rounded-[50px]" : "rounded-none"}`}
            style={{
              backgroundImage: `url(${Image})`,
            }}
          ></div>
        ))}
        {/* Overlay */}
        <div
          className={`absolute top-0 left-0 w-full h-full bg-black/30 transition-all duration-700 ${
            rounded ? "rounded-[50px]" : "rounded-none"
          }`}
        ></div>
      </div>

      {/* Text Overlay */}
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center text-white px-4">
        <h1 className="text-5xl font-bold mb-4 drop-shadow-lg">
         <i>AI Fashion, Redefined by ModeLens</i>
        </h1>
        <p className="text-lg max-w-2xl drop-shadow-md">
          ModeLens empowers online fashion brands with intelligent, lifelike AI models and visuals that set a new standard for digital creativity
        </p>
      </div>
    </div>
  );
};

export default Hero;
