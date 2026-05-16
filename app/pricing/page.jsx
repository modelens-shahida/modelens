"use client";
import React, { useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";


/* -------------------- FAQ ACCORDION COMPONENT -------------------- */
const FAQAccordion = () => {
  const [openIndex, setOpenIndex] = useState(null);

  const faqs = [
    {
      question: "Do you offer a free trial?",
      answer: (
        <p>
          
          Yes. You can sign up any time for a free trial, no credit card needed. You can test our platform with 8 free credits and decide if you want to upgrade to one of our paid plans.
          <br />
         
        
        </p>
      ),
    },
    {
      question: "What are credits?",
      answer: (
        <>
          <p>Generating photos and videos requires credits: each photo costs 1 credit and each video costs 5 credits.</p>
          <br />
          <p>
        For example, if you want to upload 4 photos and 1 video for a certain product, it will cost you 9 credits. 
          </p>
          <br />
          <p>
        For example, if you want to upload 4 photos and 1 video for a certain product, it will cost you 9 credits. 
          </p>
          <br />
          <p>
          ‍

To estimate how many credits you`ll need for your plan, multiply the number of products or SKUs you plan to render with Botika by the average number of photos and videos per SKU on your website.
          </p>
          <br />
          <p>
            <strong>AI Video:</strong> Turn your clothing images into short,
            dynamic clips that bring your products to life and make your online
            store stand out.
          </p>
        </>
      ),
    },
    {
      question: "Can I make changes to my plan?",
      answer: (
        <p>
         Yes, you can change your subscription anytime. When logged into your account, go to the “Account & Billing” page. In the main menu on the top right, click “Change Plan” to switch plans or “Cancel Subscription” to cancel.
        </p>
                

      ),
    },
    {
      question: "What happens to my unused credits?",
      answer: (
        <p>
        We offer unlimited credit rollover for active users. When your plan renews, any unused credits will automatically be added to your new batch of credits.

‍

You’ll need to have an active plan to keep your credits eligible for rollover.

‍

Annual plans include discounts and give you all 12 months’ worth of credits upfront. More details can be found here.
        </p>
      ),
    },
    {
      question: "What is the difference between the annual and monthly plans?",
      answer: (
        <p>
          Annual plans give you two months free and provide all your credits upfront — no waiting for monthly allotments. This makes it easier to handle peak usage times, like collection launches.Monthly plans` credits won’t expire as long as you have an active subscription.
        </p>
      ),
    },
  ];

  return (
    <div className="max-w-4xl mx-auto divide-y divide-gray-200">
      {faqs.map((faq, index) => (
        <motion.div
          key={index}
          className="py-6 cursor-pointer"
          initial={false}
          onClick={() => setOpenIndex(openIndex === index ? null : index)}
        >
          <div className="flex justify-between items-center">
            <h3 className="text-lg md:text-xl font-semibold text-gray-900 text-left">
              {faq.question}
            </h3>
            <motion.span
              initial={false}
              animate={{ rotate: openIndex === index ? 45 : 0 }}
              transition={{ duration: 0.2 }}
              className="text-3xl font-light text-[#A855F7]"
            >
              +
            </motion.span>
          </div>

          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={
              openIndex === index
                ? { height: "auto", opacity: 1 }
                : { height: 0, opacity: 0 }
            }
            transition={{ duration: 0.3, ease: "easeInOut" }}
            className="overflow-hidden mt-4 text-gray-600 text-left"
          >
            {faq.answer}
          </motion.div>
        </motion.div>
      ))}
    </div>
  );
};

const pricingPlans = {
  monthly: [
    {
      title: "Lite",
      subtitle: "A great way to explore the Botika platform.",
      features: [
        "No Botika watermarks",
        "Limited selection of AI models",
        "Limited selection of backgrounds",
        "HD image resolution",
        "1 free photo review per credit",
        "Photo fixes ready in 4 business days",
        "Social-ready images",
      ],
    },
    {
      title: "Pro",
      subtitle: "Perfect for businesses of all sizes",
      features: [
        "Includes everything in Lite, plus:",
        "Access to all models",
        "Access to all backgrounds",
        "2K image resolution",
        "2 free photo reviews per credit.",
        "Photo fixes in 2 business days",
        "Support for headless images",
        "Allows uploads of flat lay images",
      ],
    },
    {
      title: "Advanced",
      subtitle: "Best for scaling your business with extra AI features",
      features: [
        "Includes everything in Pro, plus:",
        "4K image resolution",
        "3 free photo reviews per credit",
        "Photo fixes in 1 business day",
        "White-glove quality control",
        "Multi-user access",
      ],
    },
  ],
  annual: [
    {
      title: "Lite",
      subtitle: "A great way to explore the Botika platform.",
      features: [
        "Access all credits upfront",
        "No Botika watermarks",
        "Limited selection of AI models",
        "Limited selection of backgrounds",
        "HD image resolution",
        "1 free photo review per credit",
        "Photo fixes ready in 4 business days",
        "Social-ready images",
      ],
    },
    {
      title: "Pro",
      subtitle: "Perfect for businesses of all sizes",
      features: [
        "Access all credits upfront",
        "Includes everything in Lite, plus:",
        "Access to all models",
        "Access to all backgrounds",
        "2K image resolution",
        "2 free photo reviews per credit.",
        "Photo fixes in 2 business days",
        "Support for headless images",
        "Allows uploads of flat lay images",
      ],
    },
    {
      title: "Advanced",
      subtitle: "Best for scaling your business with extra AI features",
      features: [
        "Access all credits upfront",
        "Includes everything in Pro, plus:",
        "4K image resolution",
        "3 free photo reviews per credit",
        "Photo fixes in 1 business day",
        "White-glove quality control",
        "Multi-user access",
      ],
    },
  ],
};

const monthlySteps = [20, 30, 50, 75, 100, 125, 150, 200, 250, 300, 350, 400, 450, 500];
const annualSteps = [240, 300, 600, 900, 1200, 1500, 1800, 2400, 3000, 3600, 4200, 4800, 5400, 6000];

const monthlyPrices = {
  lite: [22, 33, 55, 55, 55, 55, 55, 55, 55, 55, 55, 55, 55, 55],
  pro: [25, 35, 58, 80, 100, 125, 150, 196, 245, 288, 336, 376, 423, 500],
  advanced: [30, 40, 65, 95, 120, 150, 180, 236, 295, 348, 406, 456, 513, 513],
};

const annualPrices = {
  lite: [18, 28, 46, 46, 46, 46, 46, 46, 46, 46, 46, 46, 46, 46],
  pro: [21, 29, 46, 67, 83, 104, 125, 163, 204, 240, 280, 313, 353, 353],
  advanced: [25, 33, 54, 79, 100, 125, 150, 197, 246, 290, 338, 380, 428, 428],
};

const features = [
  "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f01180eafc1c0240497ef_27dbc279bca377e0d6c2ffd39d76fa26_Botika_AIGeneratedFashionModels_Feature_BeforeAfter.webp",
  "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f0118f796b5690d5ffb09_e5387e2a426bf8a7db7cebffdc36dd9d_Botika_AIGeneratedFashionModels_Feature_ModelPortfolio.webp",
  "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f01184314f55d5e8e295e_bff58ee04eb9cc85659553dfb258467d_Botika_AIGeneratedFashionModels_Feature_BackgroundSelection.webp",
  "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f0118a93179f4bcbb0c71_ef352fa715ebb23ae2280b9441cb818b_Botika_AIGeneratedFashionModels_Feature_EnhanceCroppedPhotos.webp",
  "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f01181b6bcbf650a4c6e2_58689482f79827385def2fa807dca94a_Botika_AIGeneratedFashionModels_Feature_FlatLayProcess.webp",
  "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f013841c3cbd6e16868aa_b6417ab67df9bf18179cba47bc6e153e_Botika_AIGeneratedFashionModels_Feature_2.webp",
  "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f0118ea96bdc676177df1_4547430cc083a961efcb843daf921641_Botika_AIGeneratedFashionModels_Feature_AICorrections.webp",
  "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f0118594137306534d368_9b5a7230f1d229787a63de16aed1b7af_Botika_AIGeneratedFashionModels_PerfectYourProductPhotos.webp",
  "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f01183a136e7b24eccc50_Botika_AIGeneratedFashionModels_Feature_SocialMediaPosts.avif",
];

const PricingPage = () => {
  const [isMonthly, setIsMonthly] = useState(true);
  const [sliderValue, setSliderValue] = useState(0);

  const sliderSteps = isMonthly ? monthlySteps : annualSteps;
  const prices = isMonthly ? monthlyPrices : annualPrices;
  const plansToShow = pricingPlans[isMonthly ? "monthly" : "annual"];

  const liteMax = isMonthly ? 50 : 600;
  const liteCredits = Math.min(sliderSteps[sliderValue], liteMax);
  const liteOpacity = sliderSteps[sliderValue] > liteMax ? 0.5 : 1;
  const otherCredits = sliderSteps[sliderValue];

  return (
    <div className="bg-white text-black">

      {/* HERO + SLIDER */}
      <section className="bg-[#1b1919] text-white py-16 px-6 md:px-20 text-center relative overflow-hidden">
        <h1 className="text-3xl md:text-6xl font-extrabold mb-6">
          Take your fashion photos to the next level
        </h1>
        <p className="text-lg md:text-xl text-gray-300 max-w-3xl mx-auto leading-relaxed mb-8">
          I need <strong>{sliderSteps[sliderValue]}</strong>{" "}
          {isMonthly ? "photos per month" : "photos per year"}.
        </p>

        {/* Slider */}
        <div className="max-w-3xl mx-auto mt-2 relative">
          <style jsx>{`
            input[type="range"]::-webkit-slider-thumb {
              -webkit-appearance: none;
              appearance: none;
              width: 45px;
              height: 45px;
              border-radius: 50%;
              background: linear-gradient(135deg, #7e22ce, #9333ea);
              box-shadow: 0 0 25px rgba(147, 51, 234, 0.8);
              border: 2px solid white;
              cursor: pointer;
              transition: transform 0.2s ease;
            }
            input[type="range"]::-webkit-slider-thumb:hover {
              transform: scale(1.3);
            }
          `}</style>

          <input
            type="range"
            min={0}
            max={sliderSteps.length - 1}
            step={1}
            value={sliderValue}
            onChange={(e) => setSliderValue(Number(e.target.value))}
            className="w-full h-5 bg-gray-400 rounded-full cursor-pointer appearance-none"
          />

          <div className="flex justify-between mt-3 text-gray-300 text-sm md:text-base">
            <span>{sliderSteps[0]}</span>
            <span>{sliderSteps[sliderSteps.length - 1]}+</span>
          </div>

          {/* Button */}
          <div className="mt-6 flex justify-center">
            <motion.button
              key={sliderValue}
              className="cursor-pointer bg-gradient-to-r from-purple-700 to-purple-500 text-white font-extrabold py-8 px-24 text-2xl rounded-full shadow-[0_15px_40px_rgba(150,50,250,0.5)] hover:shadow-[0_20px_45px_rgba(150,50,250,0.7)] transition transform hover:scale-110"
            >
              {sliderSteps[sliderValue]} {isMonthly ? "Photos / Month" : "Photos / Year"}
            </motion.button>
          </div>
        </div>
      </section>

      {/* Toggle */}
      <div className="bg-gray-50 py-10 flex justify-center">
        <div className="flex items-center gap-0 border border-gray-300 rounded-full overflow-hidden">
          <button
            onClick={() => {
              setIsMonthly(true);
              setSliderValue(0);
            }}
            className={`px-6 py-3 cursor-pointer font-semibold transition text-lg ${
              isMonthly ? "bg-purple-600 text-white" : "bg-gray-200 text-black"
            }`}
          >
            Monthly
          </button>
          <button
            onClick={() => {
              setIsMonthly(false);
              setSliderValue(0);
            }}
            className={`px-6 py-3 cursor-pointer font-semibold transition text-lg ${
              !isMonthly ? "bg-purple-600 text-white" : "bg-gray-200 text-black"
            }`}
          >
            Annual
          </button>
        </div>
      </div>

      {/* Pricing Cards */}
      <section className="py-10 px-6 md:px-20 bg-gray-50 relative z-10">
        <div className="max-w-7xl mx-auto grid md:grid-cols-1 lg:grid-cols-3 gap-6">
          {plansToShow.map((plan, index) => {
            const displayCredits = index === 0 ? liteCredits : otherCredits;
            const displayPrice =
              index === 0
                ? prices.lite[sliderValue]
                : index === 1
                ? prices.pro[sliderValue]
                : prices.advanced[sliderValue];
            const cardOpacity = index === 0 ? liteOpacity : 1;
            const isMax = sliderValue === sliderSteps.length - 1;

            return (
              <motion.div
                key={`${plan.title}-${index}`}
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: cardOpacity, y: 0 }}
                transition={{ duration: 0.5 }}
                className="relative flex flex-col rounded-2xl p-8 shadow-lg border bg-white"
              >
                <div className="absolute top-4 right-4 bg-purple-600 text-white px-3 py-1 rounded-full font-bold text-sm shadow-md">
                  {displayCredits} Credits
                </div>

                <h3 className="text-2xl font-bold mb-2">{plan.title}</h3>
                <p className="mb-4 text-gray-500">{plan.subtitle}</p>

                {isMax && index > 0 ? (
                  <>
                    <p className="text-3xl font-extrabold mb-2">
                      Over {sliderSteps[sliderSteps.length - 1]}{" "}
                      {isMonthly ? "photos per month?" : "photos per year?"}
                    </p>
                    <p className="mb-3 text-gray-600">Talk to our sales team</p>
                    <Link href="/contact">
                      <button className="w-full py-3 rounded-full font-semibold mb-6 transition bg-purple-600 text-white hover:bg-purple-700">
                        Contact Sales
                      </button>
                    </Link>
                  </>
                ) : (
                  <>
                    <p className="text-3xl font-extrabold mb-2">
                      ${displayPrice} USD / month
                    </p>
                    <p className="mb-4 text-gray-500">
                      Billed {isMonthly ? "monthly" : "annually"}. Unlimited credit rollover
                    </p>
                    <Link href="/signup">
                      <button className="w-full py-3 rounded-full font-semibold mb-4 transition bg-purple-600 text-white hover:bg-purple-700">
                        Get Started
                      </button>
                    </Link>
                  </>
                )}

                <ul className="flex-1 space-y-2 text-gray-700">
                  {plan.features.map((feature, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="text-purple-500 font-bold">✓</span>
                      {feature}
                    </li>
                  ))}
                </ul>
              </motion.div>
            );
          })}
        </div>
      </section>

      {/* Image Showcase Section */}
      <section className="py-24 bg-[#1b1919] flex justify-center items-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.85 }}
          whileInView={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1, ease: "easeOut" }}
          className="relative overflow-hidden rounded-[40px] shadow-[0_0_50px_rgba(168,85,247,0.4)] border border-purple-500/50"
        >
          <motion.img
            src="https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/67769c4c79b7a48aabb46b98_Botika_Pricing_Main.avif"
            alt="Botika Pricing Showcase"
            className="rounded-[40px] w-[95vw] md:w-[85vw] lg:w-[80vw] h-[70vh] md:h-[80vh] object-cover"
            whileHover={{ scale: 1.08, rotate: 0.3 }}
            transition={{ type: "spring", stiffness: 100, damping: 10 }}
          />
          <div className="absolute inset-0 rounded-[40px] bg-gradient-to-tr from-purple-700/10 to-pink-500/10 pointer-events-none" />
        </motion.div>
      </section>

      {/* Transform Section */}
<section className="py-20 bg-white text-center">
  <div className="max-w-6xl mx-auto px-6">
    <h2 className="text-4xl font-bold mb-4">
      Transform your fashion business with AI.
    </h2>
    <p className="text-gray-600 text-lg mb-12">
      Use Botika`s generative AI fashion model solution to publish collections faster and stay on budget.
    </p>

    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
      {/* Card Template */}
      {[
        {
          img: "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f01180eafc1c0240497ef_27dbc279bca377e0d6c2ffd39d76fa26_Botika_AIGeneratedFashionModels_Feature_BeforeAfter.webp",
          title: "No Botika watermarks",
          desc: "Show off your new Botika photos in your online shop and on social media.",
        },
        {
          img: "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f0118f796b5690d5ffb09_e5387e2a426bf8a7db7cebffdc36dd9d_Botika_AIGeneratedFashionModels_Feature_ModelPortfolio.webp",
          title: "Stunning AI model gallery",
          desc: "Access all of Botika's unique AI fashion models.",
        },
        {
          img: "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f01184314f55d5e8e295e_bff58ee04eb9cc85659553dfb258467d_Botika_AIGeneratedFashionModels_Feature_BackgroundSelection.webp",
          title: "AI-enhanced backgrounds",
          desc: "Upgrade basic photos or create eye-catching lifestyle photos with a click of a button.",
        },
        {
          img: "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f0118a93179f4bcbb0c71_ef352fa715ebb23ae2280b9441cb818b_Botika_AIGeneratedFashionModels_Feature_EnhanceCroppedPhotos.webp",
          title: "Restore cropped photos",
          desc: "Botika blends its AI fashion models into your cropped pictures naturally.",
        },
        {
          img: "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f01181b6bcbf650a4c6e2_58689482f79827385def2fa807dca94a_Botika_AIGeneratedFashionModels_Feature_FlatLayProcess.webp",
          title: "Turn packshots into on-model photos",
          desc: "Easily turn your packshots into stunning on-model images. No photoshoot needed.",
        },
        {
          img: "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f013841c3cbd6e16868aa_b6417ab67df9bf18179cba47bc6e153e_Botika_AIGeneratedFashionModels_Feature_2.webp",
          title: "Multi-user access",
          desc: "Easily share access and collaborate with your team members.",
        },
        {
          img: "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f0118ea96bdc676177df1_4547430cc083a961efcb843daf921641_Botika_AIGeneratedFashionModels_Feature_AICorrections.webp",
          title: "High-resolution photos",
          desc: "Show off your products with stunning detail and accuracy.",
        },
        {
          img: "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f0118594137306534d368_9b5a7230f1d229787a63de16aed1b7af_Botika_AIGeneratedFashionModels_PerfectYourProductPhotos.webp",
          title: "White-glove quality control",
          desc: "Top-tier photo quality with Botika’s human-based review system.",
        },
        {
          img: "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1/675f01183a136e7b24eccc50_Botika_AIGeneratedFashionModels_Feature_SocialMediaPosts.avif",
          title: "White-glove quality control",
          desc: "Top-tier photo quality with Botika’s human-based review system.",
        },
      ].map((card, index) => (
        <div
          key={index}
          className="bg-white shadow-lg rounded-2xl overflow-hidden hover:shadow-2xl transition"
        >
          <img src={card.img} alt={card.title} className="w-full h-64 object-cover" />
          <div className="p-6">
            <h3 className="text-xl font-semibold mb-2 text-center">{card.title}</h3>
            <p className="text-gray-600 text-left">{card.desc}</p>
          </div>
        </div>
      ))}
    </div>
  </div>
</section>



      {/* FAQ SECTION */}
      <section className="bg-gray-50 py-24 px-6 md:px-16">
        <h2 className="text-4xl md:text-5xl text-black font-semibold text-center mb-16">
          Frequently Asked Questions
        </h2>
        <FAQAccordion />
      </section>




    </div>
  );
};

export default PricingPage;
