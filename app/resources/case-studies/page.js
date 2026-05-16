"use client";
import React from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import Image from "next/image";

const CaseStudiesPage = () => {
  return (
    <div className="bg-white text-black">

      {/* ---------------- HERO SECTION ---------------- */}
      <section className="py-24 px-6 md:px-20 text-center">
        <h1 className="text-4xl md:text-6xl font-extrabold mb-6">
          Case studies
        </h1>

        <p className="text-lg md:text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed">
          See how our clients transformed their fashion brands with Botika.
          From cutting production costs to speeding up time to market, these
          stories highlight the real impact of our AI-generated fashion models.
        </p>
      </section>

      {/* ---------------- FEATURED CASE STUDY CARD ---------------- */}
<div className="max-w-7xl mx-auto mb-28 px-6">

  <Link href="/resources/case-studies/juan-me-scales-content-with-botikas-ai--and-sees-128-more-conversions">
    <motion.div
      initial={{ opacity: 0 }}
      whileInView={{ opacity: 1 }}
      viewport={{ once: true }}
      transition={{ duration: 0.7 }}
      className="relative rounded-3xl overflow-hidden shadow-2xl border border-gray-200 bg-black cursor-pointer"
    >

      {/* FULL IMAGE — NO CROP */}
      <img
        src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/686fc0d7b0f517c828ddf218_Botika_CaseStudy_JUANandMe_Header.webp"
        alt="Case Study — Juan & Me"
        className="w-full h-auto object-contain"
      />

      {/* LEFT-SIDE OVERLAY CONTENT */}
      <div className="absolute inset-0 bg-gradient-to-r from-black/80 via-black/40 to-transparent flex items-center">
        <div className="pl-10 md:pl-16 max-w-xl py-10 text-left">

          <p className="text-white/80 text-sm font-semibold uppercase tracking-wider mb-3">
            Case study
          </p>

          <h2 className="text-4xl md:text-5xl font-bold text-white leading-snug mb-6">
            JUAN & ME scales content with Botika’s AI — 
            <span className="text-purple-300"> 128% more conversions</span>
          </h2>

          {/* READ MORE BUTTON */}
          <motion.button
            whileHover={{ scale: 1.06 }}
            whileTap={{ scale: 0.95 }}
            className="mt-4 bg-white/90 text-black font-semibold px-7 py-3 rounded-full shadow-lg hover:bg-white transition backdrop-blur-md"
          >
            Read More →
          </motion.button>

        </div>
      </div>

    </motion.div>
  </Link>

</div>




      {/* ---------------- MORE CASE STUDIES GRID ---------------- */}
<section className="max-w-7xl mx-auto px-6 pb-32">
  <div className="grid grid-cols-1 md:grid-cols-3 gap-10">

  {/* CARD 1 */}
<motion.div
  whileHover={{ scale: 1.02 }}
  className="cursor-pointer"
>
  <Link href="/resources/case-studies/botika-turned-get-dressed-collective-into-a-boutique-powerhouse">
    <div className="overflow-hidden rounded-2xl shadow-lg">
      <img
        src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/67f3ea40de3ac269046d2e4b_Botika_CaseStudy_GetDressedCollective%20_Hero_Mobile.webp"
        alt="Get Dressed Collective Case Study"
        className="w-full h-72 object-cover"
      />
    </div>

    <p className="text-sm font-semibold text-gray-700 mt-4 uppercase">
      Case study
    </p>

    <h3 className="text-lg font-semibold mt-2 hover:underline transition">
      Botika turned Get Dressed Collective into a boutique powerhouse
    </h3>
  </Link>
</motion.div>


    {/* CARD 2 */}
    <motion.div
      whileHover={{ scale: 1.02 }}
      className="cursor-pointer"
    >
      <Link href="/resources/case-studies/need-lots-of-images-fast-blvck-turns-to-botika-for-the-win">
        <div className="overflow-hidden rounded-2xl shadow-lg">
          <img
            src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/676a7d4c2b12a754a781f97f_Botika_CaseStudies_BLVCK_Header_Mobile.avif"
            alt="BLVCK Case Study"
            className="w-full h-72 object-cover"
          />
        </div>

        <p className="text-sm font-semibold text-gray-700 mt-4 uppercase">
          Case study
        </p>

        <h3
          className="text-lg font-semibold mt-2 hover:underline cursor-pointer transition"
        >
          Need lots of images fast? BLVCK turns to Botika for the win
        </h3>
      </Link>
    </motion.div>

    {/* CARD 3 */}
    <motion.div
      whileHover={{ scale: 1.02 }}
      className="cursor-pointer"
    >
      <Link href="/resources/case-studies/jordache-embraces-ai-cutting-costs-boosting-visuals-with-botika">
        <div className="overflow-hidden rounded-2xl shadow-lg">
          <img
            src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/6767caa8fa536c3a8d7c7012_Jordache_CaseStudies_Mobile%20Header.avif"
            alt="Jordache Case Study"
            className="w-full h-72 object-cover"
          />
        </div>

        <p className="text-sm font-semibold text-gray-700 mt-4 uppercase">
          Case study
        </p>

        <h3
          className="text-lg font-semibold mt-2 hover:underline cursor-pointer transition"
        >
          Jordache embraces AI: Cutting costs & boosting visuals with Botika
        </h3>
      </Link>
    </motion.div>

  </div>
</section>


{/* Ready To Upgrade Section */}
<section className="w-full my-20 px-6">
  <div className="max-w-5xl mx-auto bg-[#1b1919] text-white py-20 px-8 rounded-3xl">

    <h2 className="text-4xl md:text-5xl font-bold leading-snug text-center mb-6">
      Ready to upgrade your photos?
    </h2>

    <p className="text-lg md:text-xl opacity-80 text-center mb-10">
      With Botika’s app, you have our AI generated models for fashion right in your pocket.
      Snap, upload, and get stunning, realistic photos in minutes, all on your phone.
    </p>

    <div className="text-center">
      <button
        className="px-10 py-4 bg-white cursor-pointer text-black font-semibold rounded-xl hover:bg-gray-200 transition duration-200"
      >
        Try Now
      </button>
    </div>

  </div>
</section>


    </div>
  );
};

export default CaseStudiesPage;
