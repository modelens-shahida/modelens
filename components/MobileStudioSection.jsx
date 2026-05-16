"use client";
import React from "react";
import Image from "next/image";
import Link from "next/link";

const MobileStudioSection = () => {
  return (
    <section className="bg-white py-24">
      <div className="max-w-6xl mx-auto px-6 flex flex-col md:flex-row items-center gap-12">
        {/* Left text content */}
        <div className="md:w-1/2 text-center md:text-left">
          <h2 className="text-4xl md:text-5xl font-extrabold text-gray-900 mb-6 leading-tight">
            Your mobile fashion studio
          </h2>
          <p className="text-lg text-gray-600 mb-8">
            With <span className="font-semibold text-black">ModeLens app</span>, puts AI-powered fashion models in your pocket — create realistic visuals in minutes, anytime, anywhere. 
          </p>

          <Link
            href="#"
            className="inline-block bg-black text-white px-6 py-3 rounded-full text-base font-semibold hover:bg-gray-900 transition-all duration-300"
          >
            Try Now
          </Link>
        </div>

        {/* Right Image section */}
        <div className="md:w-1/2 flex justify-center">
          <Image
            src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/67767cb06d84ad05c0ef8e0a_Botika_MobileAppPreview.webp"
            alt="Botika mobile app"
            width={400}
            height={400}
            className="rounded-3xl shadow-xl object-cover"
          />
        </div>
      </div>
    </section>
  );
};

export default MobileStudioSection;
