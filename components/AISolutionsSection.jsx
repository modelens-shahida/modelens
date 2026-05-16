"use client";

import React from "react";
import Image from "next/image";

const solutions = [
  {
    Image:
      "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f0118f796b5690d5ffb09_e5387e2a426bf8a7db7cebffdc36dd9d_Botika_AIGeneratedFashionModels_Feature_ModelPortfolio.webp",
    title: "Ever-growing model portfolio",
    description:
      "Our unique selection of AI generated models for fashion includes diverse body types, ethnicities, and ages.",
  },
  {
    Image:
      "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f01181b6bcbf650a4c6e2_58689482f79827385def2fa807dca94a_Botika_AIGeneratedFashionModels_Feature_FlatLayProcess.webp",
    title: "Flat-lay to on-model",
    description:
      "Turn your packshot Images into stunning on-model photos. No photoshoot required.",
  },
  {
    Image:
      "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f01184314f55d5e8e295e_bff58ee04eb9cc85659553dfb258467d_Botika_AIGeneratedFashionModels_Feature_BackgroundSelection.webp",
    title: "Swap backgrounds",
    description:
      "Enhance basic photos or create stunning lifestyle Images with just one click.",
  },
  {
    Image:
      "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f0118a93179f4bcbb0c71_ef352fa715ebb23ae2280b9441cb818b_Botika_AIGeneratedFashionModels_Feature_EnhanceCroppedPhotos.webp",
    title: "Enhance cropped photos",
    description:
      "Our solution easily integrates AI fashion models into your cropped Images.",
  },
  {
    Image:
      "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f0118594137306534d368_9b5a7230f1d229787a63de16aed1b7af_Botika_AIGeneratedFashionModels_PerfectYourProductPhotos.webp",
    title: "Perfect your photos",
    description:
      "Get flawless photos with ModeLens's AI-powered touch-ups. Quick and simple for flawless results.",
  },
  {
    Image:
      "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f01183a136e7b24eccc50_Botika_AIGeneratedFashionModels_Feature_SocialMediaPosts.avif",
    title: "Share everywhere",
    description:
      "Easily connect and export content to your website, social media accounts, and more.",
  },
];

const AISolutions = () => {
  return (
    <section className="bg-white py-24 px-6 md:px-12 text-gray-900">
      {/* Heading */}
      <div className="text-center mb-16">
        <h2 className="text-3xl md:text-4xl font-bold mb-4">
         ModeLens – Redefining Fashion with AI
        </h2>
        <p className="text-lg text-gray-600 max-w-3xl mx-auto">
“Discover how ModeLens’ AI elevates your fashion brand, from lifelike model creation to flawless visuals.”        </p>
      </div>

      {/* Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-10 max-w-7xl mx-auto">
        {solutions.map((solution, index) => (
          <div
            key={index}
            className="group bg-gray-50 rounded-3xl shadow-md hover:shadow-xl transition-all duration-500 overflow-hidden border border-gray-100 hover:-translate-y-2"
          >
            <div className="w-full h-60 overflow-hidden">
              <Image
                src={solution.Image}
                alt={solution.title}
                width={500}
                height={400}
                unoptimized
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
              />
            </div>
            <div className="p-6 text-center">
              <h3 className="text-xl font-semibold mb-3">{solution.title}</h3>
              <p className="text-gray-600 text-base leading-relaxed mb-4">
                {solution.description}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Button */}
      <div className="text-center mt-16">
        <button className="px-8 py-3 cursor-pointer bg-black text-white rounded-full font-semibold text-sm hover:bg-gray-800 transition duration-300">
          Learn More
        </button>
      </div>
    </section>
  );
};

export default AISolutions;
