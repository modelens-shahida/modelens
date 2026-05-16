"use client";
import React from "react";
import { motion } from "framer-motion";
import Link from "next/link";
// import { Link } from "lucide-react";

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
            src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/67f03160560a32da51cd22d0_Botika_CaseStudy_GetDressedCollective%20_Hero%20Image.webp"
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
                Botika turned Get Dressed Collective into a boutique powerhouse
              </h2>
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
              Discover how Get Dressed Collective saved time, cut costs and boosted their online performance by switching to Botika’s streamlined photo solution.
            </p>

            {/* Challenges */}
            <div>
              <h2 className="text-2xl font-semibold mb-2">Challenges and goals</h2>
              <p className="text-gray-700">
                Get Dressed Collective is an online boutique that curates fashion collections. They had a tough time creating product photos that were consistent, diverse, and affordable. Traditional photoshoots were:
              </p>

              <ul className="list-disc ml-6 text-gray-700 mt-3">
                <li>Expensive</li>
                <li>Time-consuming</li>
                <li>Limited in model diversity</li>
              </ul>

              <p className="text-gray-700 mt-3">
                They needed a solution to make things easier, cut costs, and give them more flexibility to show off their collections.
              </p>
            </div>

            {/* Solution */}
            <div>
              <h2 className="text-2xl font-semibold mb-2">The solution</h2>

              <p className="text-gray-700">
                Botika gave Get Dressed Collective the tools they needed to tackle their biggest challenges. Here`s how we helped:
              </p>

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
              </p>
            </div>

            {/* Results */}
            <div>
              <h2 className="text-2xl font-semibold mb-2">The results</h2>
              <p className="text-gray-700">
                Get Dressed Collective saved close to 90% per photoshoot by cutting out: model hiring costs, studio rental fees and post-production editing expenses.
              </p>

              <h3 className="font-semibold mt-4">Improved online performance:</h3>
              <ul className="list-disc ml-6 text-gray-700">
                <li>Search click-through rates jumped by 150%</li>
                <li>Collections now rank on Google’s first or second page</li>
                <li>Better conversion rates, quicker purchases, higher order values</li>
              </ul>

              <h3 className="font-semibold mt-4">Faster time to market:</h3>
              <ul className="list-disc ml-6 text-gray-700">
                <li>Products launched within 1–3 days</li>
                <li>No more 15–30 day delays for shoots</li>
                <li>No dependency on schedules or editing bottlenecks</li>
              </ul>

              <h3 className="font-semibold mt-4">Business growth:</h3>
              <ul className="list-disc ml-6 text-gray-700">
                <li>Started offering branding consultations</li>
                <li>Built expertise in digital retail optimization</li>
                <li>New revenue stream through consulting</li>
              </ul>
            </div>

            {/* BEFORE / AFTER */}
            <div className="mt-10 space-y-6">
              <h2 className="text-2xl font-semibold">Before & After</h2>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <p className="font-semibold mb-2">Before</p>
                  <img
                    src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/67f03175e9fccbb31ac724ad_Botika_CaseStudy_GetDressedCollective%20_Before.webp"
                    alt="Before Image"
                    className="rounded-lg shadow-md"
                  />
                </div>

                <div>
                  <p className="font-semibold mb-2">After</p>
                  <img
                    src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/67f0318267d63052d590a77c_Botika_CaseStudy_GetDressedCollective%20_After.webp"
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
                  “What started as a solution for our own business has grown into a powerful tool that’s helping elevate the entire boutique retail community.”
                </p>

                <div className="flex items-start gap-4 mt-6">
                  <img
                    src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/67f3eb9ba39792481e038d6d_Botika_GetDressedCollective_BarbaraMarkoe.webp"
                    alt="Barbara Markoe"
                    className="w-16 h-16 rounded-full object-cover shadow-md"
                  />

                  <div className="flex flex-col justify-center">
                    <p className="font-semibold">Barbara Markoe</p>
                    <p className="text-gray-700 text-sm">Owner</p>
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
                <p className="text-4xl font-bold">150%</p>
                <p className="text-gray-600">Click-through rate increase</p>
              </div>

              <div>
                <p className="text-4xl font-bold">90%</p>
                <p className="text-gray-600">Photoshoot cost savings</p>
              </div>

              <div>
                <p className="text-4xl font-bold">10x</p>
                <p className="text-gray-600">Faster time to market</p>
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
          <span> 128% more conversions</span>
        </h3>
      </motion.div>
    </Link>

    {/* CARD 2 */}
    <Link href="/resources/case-studies/need-lots-of-images-fast-blvck-turns-to-botika-for-the-win">
      <motion.div
        whileHover={{ scale: 1.02 }}
        className="cursor-pointer"
      >
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

        <h3 className="text-lg font-semibold mt-2 hover:underline transition">
          Need lots of images fast? BLVCK turns to Botika for the win
        </h3>
      </motion.div>
    </Link>

    {/* CARD 3 */}
    <Link href="/resources/case-studies/jordache-embraces-ai-cutting-costs-boosting-visuals-with-botika">
      <motion.div
        whileHover={{ scale: 1.02 }}
        className="cursor-pointer"
      >
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
