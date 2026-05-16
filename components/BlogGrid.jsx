"use client";
import React, { useState } from "react";
import Link from "next/link";

const blogPosts = [
  {
    id: 1,
    category: "Marketing Tips",
    title: "Luxury fashion trends in 2025: Balancing heritage and innovation",
    author: "Avi Friedman",
    date: "November 12, 2025",
    image:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/690b674abfd9535617e001dd_Botika_TheThread_LuxuryFashionTrends2025_Header.webp",
    link: "/resources/blog/luxury-fashion-trends-2025",
  },
  {
    id: 2,
    category: "eCommerce",
    title: "Holiday eCommerce strategy for fashion brands in 2025",
    author: "Avi Friedman",
    date: "November 5, 2025",
    image:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/690a5a5961a1439f58ff5999_Botika_TheThread_HolidayeCommerceStrategyforFashionBrands_Header.webp",
    link: "/resources/blog/holiday-ecommerce-strategy-2025",
  },
  {
    id: 3,
    category: "Guides",
    title: "Sustainability in fashion operations: For innovative leaders",
    author: "Avi Friedman",
    date: "October 29, 2025",
    image:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/690237af849c587634ef016d_Botika_TheThread_Sustainabilityinfashionoperations_Header.webp",
    link: "/resources/blog/sustainability-in-fashion",
  },
  {
    id: 4,
    category: "Photography",
    title: "How AI is changing fashion photography forever",
    author: "Sarah Mitchell",
    date: "October 21, 2025",
    image:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/68f78ff84e70fa5f032c4b47_Botika_TheThread_EmergingFashionMarkets_Header.webp",
    link: "/resources/blog/ai-fashion-photography",
  },
  {
    id: 5,
    category: "Generative AI",
    title: "Why AI styling will take over fashion shoots",
    author: "Ben Carter",
    date: "October 18, 2025",
    image:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/68ee7366f64eaedfce91e643_Botika_TheThread_VerticalPhotosTrend_Hero.webp",
    link: "/resources/blog/ai-styling",
  },
  {
    id: 6,
    category: "News",
    title: "The future of digital fashion in retail",
    author: "Avi Friedman",
    date: "October 10, 2025",
    image:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/68dbee0a424b01f8fe630bc1_Botika_TheThread_GenZinfluencermarketingtrends_Inner%20image_02-1.webp",
    link: "/resources/blog/digital-fashion-retail",
  },
  {
    id: 7,
    category: "News",
    title: "The future of digital fashion in retail",
    author: "Avi Friedman",
    date: "October 10, 2025",
    image:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/68cb0add43b80b2d7fc142d4_Botika_TheThread_Sustainablefashionmarkettrends_Hero.webp",
    link: "/resources/blog/digital-fashion-retail",
  },
  {
    id: 8,
    category: "News",
    title: "The future of digital fashion in retail",
    author: "Avi Friedman",
    date: "October 10, 2025",
    image:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/68ca9bb9456211f0b255624a_Botika_TheThread_MeetnewBotikaAIforFashionTeams_Hero.webp",
    link: "/resources/blog/digital-fashion-retail",
  },
  {
    id: 9,
    category: "News",
    title: "The future of digital fashion in retail",
    author: "Avi Friedman",
    date: "October 10, 2025",
    image:
      "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/68c0384a19b8de7823194425_Botika_TheThread_DTCMarketingGuide_Header.webp",
    link: "/resources/blog/digital-fashion-retail",
  },
];

const BlogGrid = () => {
  const [activeCategory, setActiveCategory] = useState("All");

  const categories = [
    "All",
    "Guides",
    "eCommerce",
    "News",
    "Marketing Tips",
    "Photography",
    "Generative AI",
  ];

  // Filter logic
  const filteredPosts =
    activeCategory === "All"
      ? blogPosts
      : blogPosts.filter((post) => post.category === activeCategory);

  return (
    <section className="w-full flex justify-center pt-16 pb-28">
      <div className="w-full max-w-5xl mx-auto px-4">
        
        {/* Category Filter */}
        <div className="flex justify-center gap-6 text-sm font-medium text-gray-500 mb-10 cursor-pointer">
          {categories.map((cat) => (
            <span
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`${
                activeCategory === cat ? "text-black font-semibold" : ""
              }`}
            >
              {cat}
            </span>
          ))}
        </div>

        {/* Blog Cards */}
        <div className="flex justify-center">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-10">
            {filteredPosts.map((post) => (
              <Link key={post.id} href={post.link}>
                <div className="cursor-pointer group w-[250px] mx-auto">

                  <div className="overflow-hidden rounded-xl">
                    <img
                      src={post.image}
                      className="w-full h-40 group-hover:scale-105 transition duration-300"
                      alt={post.title}
                    />
                  </div>

                  <p className="text-xs uppercase text-gray-500 mt-3">{post.category}</p>

                  <h3 className="text-md font-semibold mt-1 text-gray-700 group-hover:underline">
                    {post.title}
                  </h3>

                  <p className="text-xs text-gray-600 mt-1">
                    By {post.author} | {post.date}
                  </p>

                </div>
              </Link>
            ))}
          </div>
        </div>

      </div>
    </section>
  );
};

export default BlogGrid;
