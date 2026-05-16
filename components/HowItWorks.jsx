"use client";
import React, { useRef, useState, useEffect } from "react";

const HowItWorks = () => {
  const videoRef = useRef(null);
  const [activeStep, setActiveStep] = useState(0);

  // Random timestamps (in seconds)
  const steps = [
    { title: "Upload", desc: "Upload the Images of your products", time: 0 },
    { title: "Transform", desc: "Select the model and background", time: 5 },
    { title: "Share", desc: "Add to your website, social media profile or digital campaign", time: 10 },
  ];

  // Update active step based on current video time
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => {
      const currentTime = video.currentTime;
      if (currentTime >= 0 && currentTime < 5) setActiveStep(0);
      else if (currentTime >= 5 && currentTime < 10) setActiveStep(1);
      else setActiveStep(2);
    };

    video.addEventListener("timeupdate", handleTimeUpdate);
    return () => video.removeEventListener("timeupdate", handleTimeUpdate);
  }, []);

  // Jump to timestamp on step click
  const handleStepClick = (time, index) => {
    const video = videoRef.current;
    if (video) {
      video.currentTime = time;
      video.play();
      setActiveStep(index);
    }
  };

  return (
    <section className="w-full bg-white text-black py-20 px-8 md:px-20 text-center">
      {/* Heading */}
      <h2 className="text-4xl md:text-5xl font-bold mb-6">How ModeLens Works</h2>

      {/* Subtext */}
      <p className="max-w-2xl mx-auto text-lg text-gray-600 mb-12">
        No studio. No models. No limits.
With just a few clicks, ModeLens turns your garments into breathtaking, photorealistic visuals — powered entirely by AI precision and creative intelligence.
      </p>

      {/* Step Buttons */}
      <div className="flex flex-col md:flex-row justify-center items-start gap-10 mb-16">
        {steps.map((step, index) => (
          <div
            key={index}
            onClick={() => handleStepClick(step.time, index)}
            className="flex-1 text-center cursor-pointer group transition-all duration-300"
          >
            <div className="w-12 h-12 mx-auto mb-4 bg-black text-white flex items-center justify-center rounded-full text-lg font-bold">
              {index + 1}
            </div>
            <h3 className="text-xl font-semibold mb-2">{step.title}</h3>
            <p className="text-gray-600">{step.desc}</p>

            {/* Animated underline */}
            <div
              className={`h-[3px] mt-4 transition-all duration-300 ${
                activeStep === index ? "w-16 mx-auto bg-black" : "w-0 mx-auto bg-transparent"
              }`}
            ></div>
          </div>
        ))}
      </div>

      {/* Video */}
      <div className="max-w-4xl mx-auto mb-12">
        <video
          ref={videoRef}
          id="Botika-howitworks-video"
          className="w-full rounded-2xl shadow-lg"
          autoPlay
          muted
          loop
          playsInline
        >
          <source
            src="https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/678613c90a5e2a10ab0b7fc2_Botika_HowitWorks_On_Model_Transform-transcode.mp4"
            type="video/mp4"
          />
          Your browser does not support the video tag.
        </video>
      </div>

      {/* Try Now Button */}
      <button className="px-6 py-2 rounded-full font-semibold text-sm bg-black text-white hover:bg-gray-800 transition cursor-pointer">
        Try Now
      </button>
    </section>
  );
};

export default HowItWorks;
