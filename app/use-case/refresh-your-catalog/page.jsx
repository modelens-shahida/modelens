"use client";
import React, { useState, useEffect, useRef } from "react";
import Image from "next/image";
import { motion } from "framer-motion";

/* -------------------- FAQ ACCORDION COMPONENT -------------------- */
const FAQAccordion = () => {
  const [openIndex, setOpenIndex] = useState(null);

  const faqs = [
    {
      question: "How many images can I upload per day?",
      answer: (
        <>
          <p>There’s no daily cap. You can upload as many photos as you’d like.</p>
          <br />
          <p>
            <strong>On-model workflow:</strong> Upload and process multiple
            images in bulk for faster results.
          </p>
          <br />
          <p>
            <strong>Flat lay and mannequin workflows:</strong> Each look is
            created one by one to ensure the best visual consistency, but
            there’s no daily limit.
          </p>
        </>
      ),
    },
    {
      question: "What types of photos and poses can I use with Botika?",
      answer: (
        <>
          <p>Botika offers three main workflows to create high-quality visuals:</p>
          <br />
          <p>
            <strong>On-model photos:</strong> Upload a photo of someone wearing
            the clothing. The pose and body type stay the same while Botika
            replaces the person with one of our AI models and updates the
            background for a clean, realistic look.
          </p>
          <br />
          <p>
            <strong>Flat lays and Mannequin:</strong> Upload front or back shots
            of your product or your clothing on a mannequin. You can then choose
            the model, pose, and background for the new image—no studio setup
            required.
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
      question: "Can I use your service for jewelry, footwear, or cosmetics?",
      answer: (
        <p>
          Right now, we only focus on clothing to ensure top-notch, realistic
          results. We plan to add more categories in the future. Stay tuned.
        </p>
      ),
    },
    {
      question: "Does Botika have kids or baby models?",
      answer: (
        <p>
          Not yet, but we may in the future. If you`re interested, let us know
          via{" "}
          <a href="mailto:info@botika.io" className="text-[#A855F7]">
            info@botika.io
          </a>{" "}
          or our in-app chat service.
        </p>
      ),
    },
    {
      question: "Do you offer a free trial?",
      answer: (
        <p>
          Yes. You can sign up any time for a free trial, no credit card needed.
          You can test our platform with 8 free credits and decide if you want
          to upgrade to one of our paid plans.
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

/* -------------------- MAIN COMPONENT -------------------- */
const RefreshYourCatalog = () => {
  const [activeIndex, setActiveIndex] = useState(0);
  const sections = [
    {
      id: 0,
      title: "Refresh, don’t just replace",
      description:
        "Update old product photos with current models",
      image:
        "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677676d51c184d367bdc4a71_Botika_UseCase_RefreshYourCatalog_ReuseOldPhotos.avif",
    },
    {
      id: 1,
      title: "Change Backgrounds in Minutes",
      description:
        "Diversity goes beyond models. Instantly create new scenes or settings and change the mood to fit your needs.",
      image:
        "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677676dd9e878fb670a3ba38_Botika_UseCase_RefreshYourCatalog_OnDemandUpdates.avif",
    },
    {
      id: 2,
      title: "Appeal to More Customers",
      description:
        "Expand your reach using our diverse AI models. We offer a wide range of ages and ethnicities so your brand connects with all customers.",
      image:
        "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/6770fde99270429c1beab263_Botika_UseCase_RefreshYourCatalog_UpdatePhotosWithYourTopModels.avif",
    },
    {
      id: 3,
      title: "Refresh Images with Top Models",
      description:
        "Easily test different models and see what works best for your brand—stay within budget and keep your customers engaged.",
      image:
        "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677103589492cb74eb63cf12_Botika_UseCases_IncreaseDiversity_RefreshImageswithTopModels.avif",
    },
  ];

  const sectionRefs = useRef([]);
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setActiveIndex(Number(entry.target.dataset.index));
          }
        });
      },
      { threshold: 0.6 }
    );
    sectionRefs.current.forEach((ref) => ref && observer.observe(ref));
    return () => observer.disconnect();
  }, []);

  return (
    <div className="pt-20">
      {/* HEADER SECTION */}
      <section className="text-center max-w-3xl mx-auto px-4 mt-10">
        <h1 className="text-4xl text-black font-bold mb-4">Refresh your catalog</h1>
        <p className="text-lg text-gray-600 mb-6">
         Easily give your catalog a fresh look with Botika—update old photos with the new models and backgrounds.
        </p>
        <button className="bg-black text-white px-6 py-3 rounded-full hover:bg-gray-800 transition">
          Try Now
        </button>
      </section>

      {/* HERO IMAGE */}
      <div className="max-w-6xl mx-auto px-4 mt-10">
        <Image
          src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677676c5124b66d8f76bd9af_Botika_UseCase_RefreshYourCatalog_Header.avif"
          alt="Maintain-Brand-Consistency"
          width={1600}
          height={800}
          className="w-full rounded-3xl object-contain"
        />
      </div>

      {/* WHY FASHION BRANDS SECTION */}
      <section className="mt-24 mb-40">
        <div className="text-center mb-16 px-4">
          <h2 className="text-4xl text-black font-bold mb-4">
            Why Fashion Brands Use Botika
          </h2>
          <p className="text-gray-600 text-lg max-w-2xl mx-auto">
See how brands give old photos a fresh update with ModeLens.          </p>
        </div>

        <div className="relative flex flex-col md:flex-row max-w-7xl mx-auto px-6 gap-10">
          {/* LEFT IMAGE */}
          <div className="md:w-1/2 sticky top-28 h-[70vh] flex items-center justify-center">
            <div className="w-full h-full">
              <Image
                key={sections[activeIndex].image}
                src={sections[activeIndex].image}
                alt={sections[activeIndex].title}
                width={800}
                height={800}
                className="w-full h-full object-cover rounded-2xl transition-all duration-300"
              />
            </div>
          </div>

          {/* RIGHT CONTENT */}
          <div className="md:w-1/2 text-black flex flex-col gap-32">
            {sections.map((item, index) => (
              <motion.div
                key={item.id}
                ref={(el) => (sectionRefs.current[index] = el)}
                data-index={index}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, ease: "easeOut" }}
                className="min-h-[60vh] flex flex-col justify-center"
              >
                <h3 className="text-2xl font-semibold mb-3">{item.title}</h3>
                <p className="text-gray-600 text-lg">{item.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* TESTIMONIAL SECTION */}
      <section className="bg-gray-50 py-24 px-6">
        <div className="max-w-6xl mx-auto text-center">
          <div className="flex justify-center mb-8">
            <Image
              src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/68e795f5254dd43893415a62_Jordache%20Logo.avif"
              alt="Jordache Logo"
              width={200}
              height={80}
              className="object-contain"
            />
          </div>
          
          <p className="text-gray-700 text-lg max-w-3xl mx-auto mb-10">
          Absolutely love this app. I`ve been searching and sampling many apps to change the models on my product images and none of them do it properly until I started using BOTIKA. This app is unbelievable and does 100% what I am after.
          </p>
          <div className="flex flex-col items-center gap-4">
            <Image
              src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/67767839d73f1fe4ec14935e_Botika_CustomerReviews_Jordache.avif"
              alt="Jordache Review"
              width={150}
              height={50}
              className="object-contain"
            />
            <p className="text-lg text-black font-medium">Michael Walter</p>
            <p className="text-gray-500">
               Vice President, <span className="font-semibold">Jordache</span>
            </p>
          </div>
        </div>
      </section>

      {/* HOW FASHION BRANDS INCREASE DIVERSITY */}
      <section className="w-full bg-white py-24 px-6 md:px-16 flex flex-col md:flex-row items-center justify-between gap-12">
        <motion.div
          className="md:w-1/2 space-y-6"
          initial={{ opacity: 0, x: -80 }}
          whileInView={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        >
          <h2 className="text-4xl md:text-5xl font-semibold leading-tight text-gray-900">
           How fashion brands use Botkia to maintain brand consistency
          </h2>
          <p className="text-lg text-gray-700">
           Create consistent looks with models that match your brand. some text
          </p>
          <ul className="list-disc pl-5 text-gray-700 text-base space-y-3">
            <li>
             Creating a unified look with models that represent your brand.
            </li>
            <li>Unifying a cohesive brand style across diverse images from multiple sources.</li>
            <li>
              Making sticking to style guidelines simpler than ignoring them.
            </li>
          </ul>
        </motion.div>

        <motion.div
          className="md:w-1/2 flex justify-center"
          initial={{ opacity: 0, x: 80 }}
          whileInView={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        >
          <Image
            src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/6770ff1b2e6e6b63fe98900b_Botika_UseCase_RefreshYourCatalog_SeeHowEasilyBotikaMakesRefreshingCatalog.avif"
            alt="How fashion brands increase diversity using Botika"
            width={600}
            height={500}
            className="rounded-2xl object-cover shadow-lg"
          />
        </motion.div>
      </section>

      {/* ADVANTAGES SECTION */}
      <section className="bg-[#1b1919] text-white py-20 px-8 md:px-20 text-center">
        <motion.h2
          className="text-4xl font-bold mb-12"
          initial={{ opacity: 0, y: 50 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          Advantages Creating Diversity Offers
        </motion.h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-12 max-w-5xl mx-auto">
          {[{ number: "-90%", label: "Visual production costs" },
            { number: "30x", label: "In ad click-through rates" },
            { number: "12%", label: "Average order value" }].map((item, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: index * 0.2 }}
            >
              <h3 className="text-5xl font-extrabold mb-3">{item.number}</h3>
              <p className="text-gray-300 text-lg">{item.label}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CASE STUDY SECTION */}
      <section className="relative w-full h-[80vh] mt-20 flex items-center justify-start">
        <Image
          src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/686fc0d7b0f517c828ddf218_Botika_CaseStudy_JUANandMe_Header.webp"
          alt="Case Study JUAN & ME"
          fill
          className="object-cover rounded-3xl"
        />
        <div className="absolute inset-0 bg-black/60 rounded-3xl"></div>
        <div className="relative z-10 max-w-2xl px-10 md:px-20">
          <p className="uppercase tracking-wide text-gray-300 mb-3">
            Case Study
          </p>
          <h2 className="text-5xl font-bold text-white mb-4 leading-snug">
            JUAN & ME scales content with Botika`s AI—and sees 128% more
            conversions
          </h2>
          <button className="bg-white text-black px-6 py-3 rounded-full font-semibold hover:bg-gray-200 transition">
            Read More →
          </button>
        </div>
      </section>

      {/* EXPLORE MORE SECTION */}
      <section className="bg-white py-24 px-6 md:px-16">
        <h2 className="text-4xl md:text-5xl text-black font-semibold text-center mb-16">
          Explore more ways to use{" "}
          <span className="text-[#A855F7]">Botika</span>
        </h2>

        <div className="grid grid-cols-1 text-black sm:grid-cols-2 lg:grid-cols-4 gap-10 max-w-7xl mx-auto">
          {[
            {
              title: "Refresh Your Catalog",
              image:
                "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/6776729518a6613ec8d07a5f_Botika_UseCasesLP_RefreshYourCatalog.avif",
            },
            {
              title: "Minimize Licensing Fees",
              image:
                "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677673a081454538c8d8c988_Botika_UseCasesLP_MinimizeLicensingFees%C2%A0.avif",
            },
            {
              title: "Ready-to-Post Social Images",
              image:
                "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677673ae3a99637f64990912_Botika_UseCasesLP_ReadytoPostSocialImages%C2%A0.avif",
            },
            {
              title: "Maintain Brand Consistency",
              image:
                "https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/677672be6143c067ac163bce_Botika_UseCasesLP_MaintainBrandConsistency.avif",
            },
          ].map((card, index) => (
            <motion.div
              key={index}
              className="group relative bg-gray-50 rounded-2xl shadow-md overflow-hidden flex flex-col justify-between hover:shadow-lg transition-all duration-300"
              whileHover={{ scale: 1.03 }}
              transition={{ duration: 0.3 }}
            >
              <div className="relative w-full h-64 overflow-hidden">
                <Image
                  src={card.image}
                  alt={card.title}
                  fill
                  className="object-cover transition-transform duration-500 group-hover:scale-105 rounded-t-2xl"
                />
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-all duration-500"></div>
              </div>
              <div className="p-6 flex flex-col justify-between flex-1">
                <h3 className="text-lg md:text-xl font-semibold mb-8">
                  {card.title}
                </h3>
                <motion.a
                  href="#"
                  className="relative inline-block text-[#A855F7] font-medium after:content-[''] after:absolute after:w-0 after:h-0.5 after:left-0 after:-bottom-1 after:bg-[#A855F7] hover:after:w-full after:transition-all after:duration-300"
                >
                  Read more
                </motion.a>
              </div>
            </motion.div>
          ))}
        </div>
      </section>


       {/* MOBILE FASHION STUDIO SECTION */}
      <section className="bg-[#1b1919] text-white py-24 px-6 md:px-16 text-center">
        <motion.h2
          className="text-4xl md:text-5xl font-bold mb-6"
          initial={{ opacity: 0, y: 50 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
        >
          Your Mobile Fashion Studio
        </motion.h2>
        <motion.p
          className="text-lg md:text-xl text-gray-300 max-w-3xl mx-auto mb-10 leading-relaxed"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.2 }}
        >
          With Botika’s app, you have our AI-generated models for fashion right
          in your pocket. Snap, upload, and get stunning, realistic photos in
          minutes — all on your phone.
        </motion.p>
        <motion.button
          className="bg-white text-black px-8 py-3 rounded-full font-semibold hover:bg-gray-200 transition"
          whileHover={{ scale: 1.05 }}
        >
          Get the App →
        </motion.button>
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

export default RefreshYourCatalog;
