"use client";
import React from "react";
import { motion } from "framer-motion";
import Link from "next/link";


const GetDressedCaseStudy = () => {
  return (
    <div className="bg-white text-black">

      {/* ---------------- HERO SECTION ---------------- */}
      <div className="max-w-7xl mx-auto mt-30 mb-5 px-6">
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
            alt="Case Study — Get Dressed Collective"
            className="w-full h-auto object-contain"
          />

          {/* LEFT OVERLAY */}
          <div className="absolute inset-0 bg-gradient-to-r from-black/80 via-black/40 to-transparent flex items-center">
            <div className="pl-10 md:pl-16 max-w-xl py-10 text-left">
              <p className="text-white/80 text-sm font-semibold uppercase tracking-wider mb-3">
                Case study
              </p>

              <h2 className="text-4xl md:text-5xl font-bold text-white leading-snug mb-6">
JUAN & ME scales content with Botika’s AI—and sees 128% more conversions           </h2>
            </div>
          </div>
        </motion.div>
      </div>

      {/* ---------------- CONTENT + SIDEBAR SECTION ---------------- */}
      <section className="w-full  bg-white py-20">
        <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-10 px-6">

          {/* LEFT — SCROLLABLE CONTENT */}
          <div className="md:col-span-2 h-[80vh] scrollbar-hide overflow-y-auto pr-4 space-y-10">

            {/* Intro */}
            <p className="text-lg text-gray-700">
           From 6 weeks to 24 hours—JUAN & ME scaled fast with AI and saw 128% more sales.
            </p>

            {/* Challenges */}
            <div>
              <h2 className="text-2xl font-semibold mb-2">Challenges and goals</h2>
              <p className="text-gray-700">
             JUAN & ME needed a faster, more cost-effective way to create high-quality visual content. From eCommerce imagery to wholesale lookbooks and campaign assets, the brand had one goal: move at the speed of fashion—without sacrificing quality or creative control. <br /> <br />

              Traditional photoshoots were slowing them down. A single campaign involved weeks of planning and thousands in production costs. Coordinating models, booking locations, and editing post-shoot stretched timelines and budgets alike. <br /> <br />
                As a fast-moving fashion brand, JUAN & ME wanted a more agile way to: <br /> <br />
              </p>

                <ul className="list-disc list-inside space-y-2 text-gray-700">
                    <li>Create lookbook and eCommerce imagery in under 24 hours</li>
                    <li>Cut production costs without compromising quality
</li>
                    <li>Support wholesale partners with rapid visual storytelling
</li>
                    <li>Explore the creative possibilities of all-AI fashion campaigns
</li>
                </ul>

              {/* <ul className="list-disc ml-6 text-gray-700 mt-3">
                <li>Expensive</li>
                <li>Time-consuming</li>
                <li>Limited in model diversity</li>
              </ul>

              <p className="text-gray-700 mt-3">
                They needed a solution to make things easier, cut costs, and give them more flexibility to show off their collections.
              </p> */}
            </div>

            {/* Solution */}
            <div>
              <h2 className="text-2xl font-semibold mb-2">The solution</h2>

              <p className="text-gray-700">
               JUAN & ME turned to Botika to rethink how content gets made. What once took weeks—now took hours. From the moment samples arrive, the team can generate on-model images and campaign-ready content in as little as 15 minutes, using just a photo. <br /> <br />

By replacing traditional photoshoots with Botika’s AI-powered f platform, JUAN & ME created high-quality visuals for eCommerce, social media, and wholesale—at scale. The results? Up to 90% cost savings and near-instant production speed. <br /> <br />

Even better, the brand is now building its first fully AI fashion model generated campaign using Botika, pushing boundaries and proving what’s possible when creativity meets technology. <br /> <br />

The platform also sparked conversations across JUAN & ME’s creative network—photographers, stylists, and wholesale teams—about how AI can amplify, not replace, creative storytelling. For JUAN & ME, AI isn’t about shortcuts. It’s about storytelling at speed, with authenticity and intention. <br /> <br />
               
              </p>
{/* 
              <h3 className="font-semibold mt-4">Customization:</h3>
              <ul className="list-disc ml-6 text-gray-700">
                <li>Models that match their diverse customer base</li>
                <li>Flexible backgrounds to fit any collection</li>
              </ul>

              <h3 className="font-semibold mt-4">Efficiency:</h3>
              <ul className="list-disc ml-6 text-gray-700">
                <li>Super fast turnaround from new inventory to online</li>
                <li>High-quality images ready for eCommerce</li>
              </ul>

              <h3 className="font-semibold mt-4">Customer support:</h3>
              <ul className="list-disc ml-6 text-gray-700">
                <li>Quick answers when they needed help</li>
                <li>A friendly, professional support team</li>
                <li>Easy access to make changes or fixes</li>
              </ul>

              <p className="text-gray-700 mt-3">
                These features gave them full creative control while keeping their brand polished and consistent.
              </p> */}
            </div>

            {/* Results */}
            <div>
              <h2 className="text-2xl font-semibold mb-2">The results</h2>
              <p className="text-gray-700">
With Botika in their toolkit, JUAN & ME no longer has to choose between creativity and efficiency. The team is now producing more content, more consistently, while spending far less—freeing them up to focus on storytelling, not logistics.              </p>

              <h3 className="font-semibold mt-4">Time Savings</h3>
              <ul className="list-disc ml-6 text-gray-700">
                <li>From 4–6 weeks to under 24 hours
</li>
<li>Instant image turnaround for new collections and social content
</li>
<li>Faster execution of ideas, campaigns, and launches
</li>
              
              </ul>

              <h3 className="font-semibold mt-4">Cost  Savings</h3>
              <p>Botika replaced the need for full production crews and logistics and reduced production costs by 90%:</p>
              <ul className="list-disc ml-6 text-gray-700">
                <li>Location: $2,000–$6,000</li>
                <li>Models: $3,000–$6,000</li>
                <li>Photography & video: $3,000–$5,000 each
</li>
                <li>Hair, makeup, editing, meals, assistants: $2,000+
</li>
               
              </ul>

              <h3 className="font-semibold mt-4">Business Impact
</h3>
              <ul className="list-disc ml-6 text-gray-700">
                <li>Increased eCommerce conversion rates
</li>
                <li>Reduced time-to-purchase with faster product storytelling

</li>
                <li>Greater creative agility for trend-responsive campaigns

</li>
                
              </ul>
      
           
            </div>

            {/* BEFORE / AFTER */}
            <div className="mt-10 space-y-6">
              <h2 className="text-2xl font-semibold">Before & After</h2>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <p className="font-semibold mb-2">Before</p>
                  <img
                    src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/6899ff9837bfd032823e2fd7_Botika_CaseStudy_JuanandMe_Before.webp"
                    alt="Before Image"
                    className="rounded-lg shadow-md"
                  />
                </div>

                <div>
                  <p className="font-semibold mb-2">After</p>
                  <img
                    src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/6899ffa037bfd032823e300f_Botika_CaseStudy_JuanandMe_After.webp"
                    alt="After Image"
                    className="rounded-lg shadow-md"
                  />
                </div>
              </div>
            </div>

            {/* Testimonial */}
            <div className="mt-10 flex items-start gap-4">
              <div>
                <p className="text-gray-700 italic leading-relaxed">
                  “Botika has revolutionized how we create visual content—streamlining everything from eCommerce imagery to social media. Since using it, our online conversion rate jumped 128%, and our wholesale launch beat sales goals by 46%, landing us in 22 retail doors.”
                </p>

                <div className="flex items-start gap-4 mt-6">
                  <img
                    src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/686d6b9f9569d84f822b44ea_Botika_CaseStudy_JuanandMe_logo.webp"
                    alt="Barbara Markoe"
                    className="w-16 h-16 rounded-full object-cover shadow-md"
                  />

                  <div className="flex flex-col justify-center">
                    <p className="font-semibold">Bianca
</p>
                    <p className="text-gray-700 text-sm">Founder</p>
                  </div>
                </div>
              </div>
            </div>

          </div>

          {/* RIGHT SIDEBAR — FIXED */}
          <div className="md:col-span-1">
            <div className="sticky top-24 bg-gray-100 p-6 rounded-lg shadow-md space-y-6">
              <h3 className="text-xl font-semibold">Key takeaways</h3>

              <div>
                <p className="text-4xl font-bold">40x</p>
                <p className="text-gray-600">
Faster time to market</p>
              </div>

              <div>
                <p className="text-4xl font-bold">90%</p>
                <p className="text-gray-600">Reduced production costs</p>
              </div>

              <div>
                <p className="text-4xl font-bold">128%</p>
                <p className="text-gray-600">Increase in conversion rate</p>
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* ---------------- HORIZONTAL DIVIDER ---------------- */}
      <div className="w-full border-t border-gray-200 mt-10"></div>


       {/* ---------------- MORE CASE STUDIES GRID ---------------- */}
<section className="max-w-7xl mx-auto px-6 pb-32">
  <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
 <Link href="/resources/case-studies/botika-turned-get-dressed-collective-into-a-boutique-powerhouse">
            <motion.div whileHover={{ scale: 1.02 }} className="cursor-pointer">
              <div className="overflow-hidden rounded-2xl shadow-lg">
                <img
                  src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/67f3ea40de3ac269046d2e4b_Botika_CaseStudy_GetDressedCollective%20_Hero_Mobile.webp"
                  alt="Get Dressed Collective Case Study"
                  className="w-full h-72 object-cover"
                />
              </div>

              <p className="text-sm font-semibold text-gray-700 mt-4 uppercase">Case study</p>

              <h3 className="text-lg font-semibold mt-2 hover:underline transition">
                Botika turned Get Dressed Collective into a boutique powerhouse
              </h3>
            </motion.div>
          </Link>

          {/* CARD 2 */}
          <Link href="/resources/case-studies/need-lots-of-images-fast-blvck-turns-to-botika-for-the-win">
            <motion.div whileHover={{ scale: 1.02 }} className="cursor-pointer">
              <div className="overflow-hidden rounded-2xl shadow-lg">
                <img
                  src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/676a7d4c2b12a754a781f97f_Botika_CaseStudies_BLVCK_Header_Mobile.avif"
                  alt="BLVCK Case Study"
                  className="w-full h-72 object-cover"
                />
              </div>

              <p className="text-sm font-semibold text-gray-700 mt-4 uppercase">Case study</p>

              <h3 className="text-lg font-semibold mt-2 hover:underline transition">
                Need lots of images fast? BLVCK turns to Botika for the win
              </h3>
            </motion.div>
          </Link>

          {/* CARD 3 */}
          <Link href="/resources/case-studies/jordache-embraces-ai-cutting-costs-boosting-visuals-with-botika">
            <motion.div whileHover={{ scale: 1.02 }} className="cursor-pointer">
              <div className="overflow-hidden rounded-2xl shadow-lg">
                <img
                  src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/6767caa8fa536c3a8d7c7012_Jordache_CaseStudies_Mobile%20Header.avif"
                  alt="Jordache Case Study"
                  className="w-full h-72 object-cover"
                />
              </div>

              <p className="text-sm font-semibold text-gray-700 mt-4 uppercase">Case study</p>

              <h3 className="text-lg font-semibold mt-2 hover:underline transition">
                Jordache embraces AI: Cutting costs & boosting visuals with Botika
              </h3>
            </motion.div>
          </Link>

  </div>
</section>



{/* ---------------- CTA SECTION ---------------- */}
<section className="w-full px-6 md:px-12 mt-20 mb-10">
  <div className="bg-[#1b1919] rounded-2xl py-20 text-center px-8 md:px-12 max-w-10xl mx-auto">

    <h2 className="text-3xl md:text-4xl font-bold text-white mb-6">
      Ready to transform your fashion photography?
    </h2>

    <p className="text-gray-300 text-lg md:text-xl mb-8 leading-relaxed">
      Sign up for our free trial to see how Botika can revolutionize your brand`s
      visuals and save you time and money!
    </p>

    <button className="bg-white text-black font-semibold px-10 py-3 rounded-full shadow-md hover:bg-gray-200 transition">
      Try Now
    </button>

  </div>
</section>




    </div>
  );
};

export default GetDressedCaseStudy;
