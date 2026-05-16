"use client";

import React, { useEffect, useState, useRef } from "react";

const StatsSection = () => {
  const stats = [
    { label: "Visual production costs", value: -90, suffix: "%" },
    { label: "Faster time to market", value: 10, suffix: "x" },
    { label: "In conversion rates", value: 10, suffix: "%" },
    { label: "Average order value", value: 12, suffix: "%" },
    { label: "In ad click-through rates", value: 30, suffix: "%" },
  ];

  const [counts, setCounts] = useState(stats.map(() => 0));
  const [visible, setVisible] = useState(false);
  const sectionRef = useRef(null);

  // ✅ Animate numbers
  useEffect(() => {
    if (!visible) return;

    const intervals = stats.map((stat, i) => {
      let start = 0;
      const end = stat.value;
      const duration = 2000;
      const stepTime = Math.abs(Math.floor(duration / Math.abs(end)));
      const increment = end / (duration / stepTime);

      const timer = setInterval(() => {
        start += increment;
        if ((end < 0 && start <= end) || (end > 0 && start >= end)) {
          start = end;
          clearInterval(timer);
        }
        setCounts((prev) => {
          const updated = [...prev];
          updated[i] = start;
          return updated;
        });
      }, stepTime);
      return timer;
    });

    return () => intervals.forEach((interval) => clearInterval(interval));
  }, [visible]);

  // ✅ Trigger on scroll into view
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (entry.isIntersecting) {
          setVisible(true);
        }
      },
      { threshold: 0.3 }
    );
    if (sectionRef.current) observer.observe(sectionRef.current);
    return () => {
      if (sectionRef.current) observer.unobserve(sectionRef.current);
    };
  }, []);

  return (
    <section
      ref={sectionRef}
      className={`w-full flex justify-center items-center py-24 px-6 transition-all duration-1000 ease-out ${
        visible ? "scale-100 opacity-100" : "scale-90 opacity-0"
      }`}
    >
      <div className="bg-[#1b1919] text-white w-full max-w-7xl rounded-3xl border border-gray-800 shadow-[0_0_40px_rgba(255,255,255,0.05)] py-20 px-6 md:px-16 overflow-hidden">
        <div className="text-center">
          <h2 className="text-3xl md:text-4xl font-semibold mb-14 tracking-tight">
            With <i>ModeLens</i> AI fashion models, our customers achieve
          </h2>

          {/* Stats Container */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-8">
            {stats.map((stat, index) => (
              <div
                key={index}
                className="bg-zinc-900/70 border border-gray-800 backdrop-blur-md rounded-2xl py-10 px-6 flex flex-col items-center justify-center transition-transform duration-300 hover:scale-105 hover:border-gray-600"
              >
                <h3 className="text-5xl font-bold mb-3 text-white drop-shadow-md">
                  {counts[index].toFixed(0)}
                  {stat.suffix}
                </h3>
                <p className="text-gray-400 text-sm md:text-base font-medium text-center">
                  {stat.label}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};

export default StatsSection;
