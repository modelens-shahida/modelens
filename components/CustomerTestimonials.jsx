"use client";
import React from "react";
import Image from "next/image";
import { Swiper, SwiperSlide } from "swiper/react";
import { Navigation } from "swiper/modules";
import "swiper/css";
import "swiper/css/navigation";

const testimonials = [
  {
    id: 1,
    userImage:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/6776784e8241e65ca1bc6376_Botika_CustomerReviews_FELIPEALBERNAZ.avif",
    aiImage:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/687ce04311c8d1c3cb5d3ff8_Botika_CustomerReviews_BLVCK.webp",
    desc: "ModeLens delivers the most realistic AI-generated models we’ve experienced — fast, reliable, and backed by exceptional support.",
    name: "Jorge Segura",
    profession: "Product Manager, FELIPE ALBERNAZ",
    brand: "FELIPE",
    subBrand: "ALBERNAZ",
  },
  {
    id: 2,
    userImage:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/67767856b0e8fc2b895a8517_Botika_CustomerReviews_BLVCK.avif",
    aiImage:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/687ce04311c8d1c3cb5d3ff8_Botika_CustomerReviews_BLVCK.webp",
    desc: "Amazing app. The models are very realistic, the solution is quick and easy to use and the team is very fast at helping with any questions we had so far.",
    name: "Steffi Cohen",
    profession: "Head of Growth, BLVCK",
    brand: "BLVCK",
    subBrand: "PARIS",
  },
  {
    id: 3,
    userImage:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/6776786efa3c22b693b7746d_Botika_CustomerReviews_PromGirl.avif",
    aiImage:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/687ce064cefd2731c95a944e_Botika_CustomerReviews_PromGirl.webp",
    desc: "This app is a game changer - the Images look fantastic and very realistic. Very easy to use, reasonably priced and great customer service.",
    name: "Kim Collins",
    profession: "Sr. Vice President CMO, PromGirl",
    brand: "PROMGIRL",
    subBrand: "NEW YORK",
  },
  {
    id: 4,
    userImage:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677678628cb33fb018487a87_Botika_CustomerReviews_NilandMon.avif",
    aiImage:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/687ce084d54fe0a6b08eddc2_Botika_CustomerReviews_NilandMon.webp",
    desc: "ModeLens is incredibly easy to use, affordable, and delivers top-quality results — a true game-changer for fashion brands.",
    name: "Michael Walter",
    profession: "Managing Director, Nil + Mon",
    brand: "NIL + MON",
    subBrand: "BERLIN",
  },
  {
    id: 5,
    userImage:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677677e7cddaabf5f04b4734_Botika_CustomerReviews_ENDERLEGARD.avif",
    aiImage:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/687cdf9b6d01e517d981dc16_Botika_CustomerReviews_ENDERLEGARD.webp",
    desc: "ModeLens has completely transformed the way we present our products. The AI-generated models are incredibly realistic, the platform is easy to use, and the results are consistently professional. It has truly elevated our brand visuals",
    name: "Rinaldo Quacquarini",
    profession: "Co-Founder, ENDER LEGARD",
    brand: "ENDER",
    subBrand: "LEGARD",
  },
  {
    id: 6,
    userImage:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/67767839d73f1fe4ec14935e_Botika_CustomerReviews_Jordache.avif",
    aiImage:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/687cdfccee4cd58800b3001d_Botika_CustomerReviews_Jordache.webp",
    desc: "ModeLens uses advanced AI to create lifelike fashion models and stunning visuals in seconds. Save time, cut costs, and showcase your brand with elegance and precision",
    name: "Shaul Cohen",
    profession: "Executive Vice President, Jordache",
    brand: "JORDACHE",
    subBrand: "NEW YORK",
  },
];

const CustomerTestimonials = () => {
  return (
    <section className="py-20 bg-gray-50">
      <h2 className="text-4xl font-bold text-center mb-4 text-gray-600">
        Don’t take our word for it
      </h2>
      <p className="text-center text-gray-600 mb-12">
        Take a look at what our customers think about using our AI generated
        models for fashion.
      </p>

      <div className="max-w-6xl mx-auto px-6 relative">
        <Swiper
          modules={[Navigation]}
          spaceBetween={50}
          slidesPerView={1}
          navigation
          loop
        >
          {testimonials.map((t) => (
            <SwiperSlide key={t.id}>
              <div className="bg-white rounded-3xl shadow-lg hover:shadow-2xl transition-all duration-300 overflow-hidden flex flex-row h-[420px]">
                {/* Left side Image */}
                <div className="w-1/2 h-full">
                  <Image
                    src={t.aiImage}
                    alt="AI generated model"
                    width={160}
                    height={160}
                    className="object-contain w-full h-full rounded-xl"
                  />
                </div>

                {/* Right side content */}
                <div className="w-1/2 p-8 flex flex-col justify-between">
                  <p className="text-gray-800 text-base leading-relaxed mb-4">
                    {t.desc}
                  </p>

                  <div className="flex items-center justify-between mt-4">
                    {/* User info */}
                    <div className="flex items-center gap-4">
                      <Image
                        src={t.userImage}
                        alt={t.name}
                        width={60}
                        height={60}
                        className="rounded-full object-cover w-14 h-14"
                      />
                      <div>
                        <h3 className="font-semibold text-gray-900 text-base">
                          {t.name}
                        </h3>
                        <p className="text-sm text-gray-500">{t.profession}</p>
                      </div>
                    </div>

                    {/* Text-based logo (BLVCK PARIS style) */}
                    <div className="text-right">
                      <h1 className="text-3xl font-extrabold tracking-wider text-black">
                        {t.brand}
                      </h1>
                      <p className="text-xs tracking-[0.3em] text-black mt-1 uppercase">
                        {t.subBrand}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </SwiperSlide>
          ))}
        </Swiper>
      </div>
    </section>
  );
};

export default CustomerTestimonials;
