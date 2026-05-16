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
            src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/675efd95bee91b289f7502d4_Botika_CaseStudies_Jordache_Header.webp"
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
Jordache embraces AI: Cutting costs & boosting visuals with Botika         </h2>
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
             Jordache, a renowned brand known for its stylish apparel, has been a fashion staple for decades. See how they cut photoshoot costs with AI in our case study.
            </p>

            {/* Challenges */}
            <div>
              <h2 className="text-2xl font-semibold mb-2">Challenges and goals</h2>
              <p className="text-gray-700">
            Jordache faced significant challenges with the cost and time associated with traditional photoshoots. The brand sought to reduce expenses and speed up their time-to-market while maintaining high-quality visuals for their marketing and ecommerce platforms.
              </p>

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
                Thanks to Botika`s AI, Jordache could skip hiring pricey models and photographers. They used AI-generated fashion models and backgrounds to speed up their photography and create stunning images in record time.
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
Here’s how Jordache managed to cut expenses and speed up production with Botika’s AI solution.              </p>

              <h3 className="font-semibold mt-4">Model costs saved
</h3>
              <ul className="list-disc ml-6 text-gray-700">
                <li>‍Traditional models cost $200-$250 per hour, easily adding up to more than $1,000 for a few hours. Jordache saved thousands by switching to Botika`s AI models.</li>
                {/* <li>Collections now rank on Google’s first or second page</li>
                <li>Better conversion rates, quicker purchases, higher order values</li> */}
              </ul>

              <h3 className="font-semibold mt-4">Photographer costs saved
</h3>
              <ul className="list-disc ml-6 text-gray-700">
                <li>‍With photographers charging $25-$35 an hour and retouchers $39/hour, costs can get steep. Jordache cut these expenses with Botika’s AI.</li>
                {/* <li>No more 15–30 day delays for shoots</li>
                <li>No dependency on schedules or editing bottlenecks</li> */}
              </ul>

              <h3 className="font-semibold mt-4">Time savings

</h3>
              <ul className="list-disc ml-6 text-gray-700">
                <li>‍Jordache used 6000 photo credits to produce thousands of photos, each taking just a few minutes from start to finish.</li>
                <li>Understanding the basics is nice, but the table below will allow you to examine the cost and time savings more accurately:</li>
                {/* <li>New revenue stream through consulting</li> */}
              </ul>
              <ul className="list-disc ml-6 text-gray-700">
                <li>Jordache saved a lot of time and money by using Botika`s Generative AI solution. They can now quickly produce thousands of high-quality photos at a fraction of the cost and time, revolutionizing their visual content production.</li>
               
              </ul>
      
            
            </div>

            {/* BEFORE / AFTER */}
            <div className="mt-10 space-y-6">
              <h2 className="text-2xl font-semibold">Before & After</h2>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <p className="font-semibold mb-2">Before</p>
                  <img
                    src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677105dde6e458d66ae69fef_Botika_CaseStudies_Jordache_Before.avif"
                    alt="Before Image"
                    className="rounded-lg shadow-md"
                  />
                </div>

                <div>
                  <p className="font-semibold mb-2">After</p>
                  <img
                    src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677105e874ad9665aed845f9_Botika_CaseStudies_Jordache_After.avif"
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
                  “Using Botika`s AI models has transformed our approach to fashion photography. We`ve cut costs and reduced our production time significantly, all while maintaining the high-quality standards our brand is known for.”
                </p>

                <div className="flex items-start gap-4 mt-6">
                  <img
                    src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/67767839d73f1fe4ec14935e_Botika_CustomerReviews_Jordache.avif"
                    alt="Barbara Markoe"
                    className="w-16 h-16 rounded-full object-cover shadow-md"
                  />

                  <div className="flex flex-col justify-center">
                    <p className="font-semibold">Shaul Cohen</p>
                    <p className="text-gray-700 text-sm">Executive Vice President, Jordache</p>
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
                <p className="text-4xl font-bold">90%</p>
                <p className="text-gray-600">Decrease in production costs</p>
              </div>

              <div>
                <p className="text-4xl font-bold">7x</p>
                <p className="text-gray-600">Faster time to market</p>
              </div>

              <div>
                <p className="text-4xl font-bold">100%</p>
                <p className="text-gray-600">
Savings on image licensing</p>
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

  {/* CARD 1 */}
<Link href="/resources/case-studies/juan-me-scales-content-with-botikas-ai--and-sees-128-more-conversions">
<motion.div
  whileHover={{ scale: 1.02 }}
  className="cursor-pointer"
>
  {/* <Link href="/resources/case-studies/botika-turned-get-dressed-collective-into-a-boutique-powerhouse"> */}
    <div className="overflow-hidden rounded-2xl shadow-lg">
      <img
        src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/686fc0fd1d6fc9f66b649aba_Botika_CaseStudy_JUANandMe_Thumbnail.webp"
        alt="Get Dressed Collective Case Study"
        className="w-full h-72 object-cover"
      />
    </div>

    <p className="text-sm font-semibold text-gray-700 mt-4 uppercase">
      Case study
    </p>

    <h3 className="text-lg font-semibold mt-2 hover:underline transition">
 JUAN & ME scales content with Botika’s AI — 
                <span > 128% more conversions</span>    </h3>
  {/* </Link> */}
</motion.div>
</Link>


    {/* CARD 2 */}
  <Link href="/resources/case-studies/botika-turned-get-dressed-collective-into-a-boutique-powerhouse">
    <motion.div
      whileHover={{ scale: 1.02 }}
      className="cursor-pointer"
    >
      {/* <Link href="/resources/case-studies/botika-turned-get-dressed-collective-into-a-boutique-powerhouse"> */}
        <div className="overflow-hidden rounded-2xl shadow-lg">
          <img
            src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/67f3ea40de3ac269046d2e4b_Botika_CaseStudy_GetDressedCollective%20_Hero_Mobile.webp"
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
Botika turned Get Dressed Collective into a boutique powerhouse        </h3>
      {/* </Link> */}
    </motion.div>
  </Link>

    {/* CARD 3 */}
   <Link href="/resources/case-studies/need-lots-of-images-fast-blvck-turns-to-botika-for-the-win">
    <motion.div
      whileHover={{ scale: 1.02 }}
      className="cursor-pointer"
    >
      {/* <Link href="/resources/case-studies/jordache-embraces-ai-cutting-costs-boosting-visuals-with-botika"> */}
        <div className="overflow-hidden rounded-2xl shadow-lg">
          <img
            src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/676a7d4c2b12a754a781f97f_Botika_CaseStudies_BLVCK_Header_Mobile.avif"
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
Need lots of images fast? BLVCK turns to Botika for the win
        </h3>
      {/* </Link> */}
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
