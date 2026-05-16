"use client";
import React from "react";
import "./marquee.css"; // import smooth scroll animation CSS
import Image from "next/image"; // ✅ Correct import

const TrustedBy = () => {
  const row1 = [
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/6787512274fedf550c30cf13_Frame.svg",
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677d5a708e8ea05c16335f50_Botika_Customers_BLVCK.avif",
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677d5a678e8ea05c163358ed_Botika_Customers_Felipe.avif",
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677d5aa323b652ef03b937a2_Botika_Customers_Nil.avif",
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677d5a52f70cb794a10b4f71_Botika_Customers_One33.avif",
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677e51cb04bf6088c52f10cc_Botika_HouseOfRare_logo.avif",
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/6771792be48403be61d97836_Botika_Snapdeal.avif",
  ];

  const row2 = [
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/67717959de847249fa995457_Botika_CocoMaternity.avif",
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/67717898cc6be30fdadfae65_Botika_JoCo.avif",
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677178e6e48403be61d9445e_Botika_Loulou.avif",
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677178fc3779394afaf1deb1_Botika_Meotine.avif",
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677d5a87e89f2611756d18fb_Botika_Customers_Lavina.avif",
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677d5a3fac3a77de7f25d511_Botika_Customers_newme.asia.avif",
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/676286e2dfdb334304fbb3bd_675000b839b55dde487552c4_Botika_Customers_Ender.avif",
  ];

  const row3 = [
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/676286e3df77814889ae6e01_675000fa2bf1bfe258a2c45e_Botika_Customers_Promgirl.avif",
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677f880c5833236b66916097_Botika_Bebe.avif",
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677f883d5833236b66918bb4_Botika_Copperose.avif",
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677fb15dca0478c8c3682ef3_Botika_LifeIsAParty.avif",
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677fb1771744e8d6abb2f98a_Botika_NKSW.avif",
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677fb189d5f8510dd6adfc95_Botika_nogin.avif",
    "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677fb19c3aa36bc43f066848_Botika_SaltyCrush.avif",
  ];

  const renderRow = (logos, direction) => (
    <div className={`marquee-wrapper ${direction}`}>
      <div className="marquee-group">
        {[...logos, ...logos].map((logo, i) => (
          <div key={i} className="relative w-[120px] h-[60px] flex items-center justify-center">
            <Image
              src={logo}
              alt="brand logo"
              width={120} // ✅ required width
              height={60} // ✅ required height
              className="object-contain opacity-80 hover:opacity-100 brightness-[0.75] grayscale-[0.25]"
            />
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <section className="w-full bg-white py-16 px-4 text-center overflow-hidden border-t border-gray-200">
      <h2 className="text-lg md:text-xl tracking-wide font-semibold text-gray-700 mb-10 mt-4">
        <span className="border-b-2 border-gray-300 pb-1">
          Trusted by{" "}
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-gray-700 to-black font-bold">
            thousands
          </span>{" "}
          of fashion brands
        </span>
      </h2>

      <div className="max-w-5xl mx-auto space-y-8">
        {renderRow(row1, "normal")}
        {renderRow(row2, "reverse")}
        {renderRow(row3, "normal")}
      </div>
    </section>
  );
};

export default TrustedBy;
