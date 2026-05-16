"use client";
import Link from "next/link"; // add at the top with other imports
import React, { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";

const ProductPage = () => {
  const [activeIndex, setActiveIndex] = useState(0);
  const sectionRefs = useRef([]);

  const steps = [
    {
      id: 0,
      step: "Step 1",
      title: "Upload Your Photos",
      description:
        "Choose the photos you want to produce with Botika. You can use photos of someone wearing your products or simple product flat lays. Make sure they’re well-lit and show off your products naturally.",
      video:
        "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1%2F678614737cabbc39557af192_Botika_Product_UploadYourPhotos-transcode.mp4",
    },
    {
      id: 1,
      step: "Step 2",
      title: "Choose Your Model",
      description:
        "Next, pick the perfect model for your brand from our AI-generated portfolio. We’ve got a wide range of models in different ethnicities, ages, sizes, and styles. For flat lays, choose up to four poses for your on-model photos.",
      video:
        "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1%2F6786147b9defbf311b95eca5_Botika_Product_ChooseYourModel-transcode.mp4",
    },
    {
      id: 2,
      step: "Step 3",
      title: "Select Your Background",
      description:
        "Swap your original background with a studio look or any of our on-location options. You can also keep your original background, and our AI will blend it all together perfectly.",
      video:
        "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1%2F678614855f19cdb7fd2619ba_Botika_Product_SelectYourBackground-transcode.mp4",
    },
    {
      id: 3,
      step: "Step 4",
      title: "Generate Your New Photos",
      description:
        'Review your choices, click "Generate", and you’re done — your photos will be ready in no time, and we’ll email you when they’re done.',
      video:
        "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1%2F67861494f489fad984102684_Botika_Product_GenerateYourNewPhotos-transcode.mp4",
    },
    {
      id: 4,
      step: "Step 5",
      title: "Refine Your Photos",
      description:
        "Perfect your images with Botika's AI-powered touch-ups. Highlight the areas you’d like us to review. Quick and simple for flawless results.",
      video:
        "https://cdn.prod.website-files.com/66fa67b1f207f846cd05b5a1%2F6786149df1b58ef3ba91aae3_Botika_Product_RefineYourPhotos-transcode.mp4",
    },
  ];

  // Intersection observer to update active video on scroll
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) =>
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setActiveIndex(Number(entry.target.dataset.index));
          }
        }),
      { threshold: 0.6 }
    );

    sectionRefs.current.forEach((ref) => {
      if (ref) observer.observe(ref);
    });

    return () => observer.disconnect();
  }, []);

  // Safe scroll handling
  const handleScroll = () => {
    const offsets = sectionRefs.current
      .filter((ref) => ref) // ignore nulls
      .map((ref, id) => ({
        id,
        top: ref.offsetTop - 200,
      }));

    const scrollPos = window.scrollY;

    for (let i = offsets.length - 1; i >= 0; i--) {
      if (scrollPos >= offsets[i].top) {
        setActiveIndex(offsets[i].id);
        break;
      }
    }
  };

  useEffect(() => {
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  /* -------------------- FAQ Accordion -------------------- */
  const FAQAccordion = () => {
    const [openIndex, setOpenIndex] = useState(null);

    const faqs = [
      {
        question: "What types of photos and poses can I use with Botika?",
        answer: (
          <>
            <p>Botika offers three main workflows to create high-quality visuals:</p>
            <br />
            <p>
              <strong>On-model photos:</strong> Upload a photo of someone wearing the clothing. Botika replaces the person with one of our AI models and updates the background for a realistic look.
            </p>
            <br />
            <p>
              <strong>Flat lays and Mannequin:</strong> Upload front/back shots of your product or clothing on a mannequin. Choose the model, pose, and background for the new image.
            </p>
            <br />
            <p>
              <strong>AI Video:</strong> Turn clothing images into short, dynamic clips for your store.
            </p>
          </>
        ),
      },
      {
        question: "What do I do if there are issues with my photo?",
        answer: (
          <>
            <p>Photo fixes are included with Botika’s paid subscriptions. Request a revision directly via the “Photo Issue” button on your image.</p>
            <br />
            <p>Delivery times vary based on your plan. Check the Pricing page for details.</p>
          </>
        ),
      },
      {
        question: "Can I customize clothing or models using my own prompts?",
        answer: (
          <p>
            We don’t create images from text. Instead, upload clothing photos, pick a model, a pose (for flat lays), and a background. AI enhances your existing photos.
          </p>
        ),
      },
      {
        question: "Can I use your service for jewelry, footwear, or cosmetics?",
        answer: (
          <p>Currently, Botika focuses on clothing for realistic results. More categories may come in the future.</p>
        ),
      },
      {
        question: "Can I use accessories in my photo?",
        answer: (
          <p>
            AI tries to preserve glasses, hats, or jewelry, but results are not guaranteed. Keep photos “accessory-free” until officially supported.
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
              <h3 className="text-lg md:text-xl font-semibold text-gray-900 text-left">{faq.question}</h3>
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
              animate={openIndex === index ? { height: "auto", opacity: 1 } : { height: 0, opacity: 0 }}
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

  /* -------------------- Animated Stat Component -------------------- */
  const AnimatedStat = ({ number, suffix = "", label }) => {
    const [value, setValue] = useState(0);
    const isNegative = number < 0;
    const absNumber = Math.abs(number);

    useEffect(() => {
      let start = 0;
      const duration = 2000;
      const stepTime = 20;
      const increment = absNumber / (duration / stepTime);

      const counter = setInterval(() => {
        start += increment;
        if (start >= absNumber) {
          start = absNumber;
          clearInterval(counter);
        }
        setValue(Math.floor(start));
      }, stepTime);

      return () => clearInterval(counter);
    }, [number]);

    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        viewport={{ once: true }}
        className="flex flex-col items-center text-center"
      >
        <span className="text-4xl md:text-5xl font-extrabold tracking-tight mb-1">
          {isNegative ? "-" : "+"}
          {value}
          {suffix}
        </span>
        <p className="text-gray-400 text-sm md:text-base">{label}</p>
      </motion.div>
    );
  };

  return (
    <div className="bg-white text-black">
      {/* === HERO SECTION === */}
      <section className="flex flex-col items-center justify-center text-center min-h-[100vh] bg-black text-white relative overflow-hidden px-6">
        <div className="absolute inset-0 bg-gradient-to-b from-gray-900 via-black to-gray-950 opacity-90" />
        <div className="absolute top-1/3 w-[500px] h-[500px] bg-white/10 blur-[180px] rounded-full" />
        <div className="relative z-10 max-w-3xl">
          <motion.h1
            initial={{ opacity: 0, y: -30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: "easeOut" }}
            className="text-4xl md:text-6xl font-extrabold mb-6"
          >
            How our AI-generated fashion models work
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="text-lg md:text-xl text-gray-300 leading-relaxed mb-10"
          >
            Start with any product shot. <br className="hidden md:block" />
            Our AI transforms it into stunning, on-model visuals with perfect
            lighting, poses, and detail — instantly.
          </motion.p>
          <motion.button
            className="bg-white text-black px-8 py-3 rounded-full font-semibold text-lg hover:bg-gray-200 transition cursor-pointer"
            whileHover={{ scale: 1.05 }}
          >
            Try Now
          </motion.button>
        </div>
      </section>

      {/* === SCROLL VIDEO + TEXT SECTION === */}
      <section className="relative flex flex-col md:flex-row max-w-7xl mx-auto px-6 py-32 gap-10">
        <div className="md:w-1/2 sticky top-28 h-[70vh] flex items-center justify-center rounded-2xl bg-black shadow-lg overflow-hidden">
          <video
            key={steps[activeIndex].video}
            src={steps[activeIndex].video}
            autoPlay
            muted
            loop
            playsInline
            className="max-w-full max-h-full object-contain transition-all duration-700 ease-in-out"
          />
        </div>

        <div className="md:w-1/2 flex flex-col gap-48">
          {steps.map((step, index) => (
            <motion.div
              key={step.id}
              ref={(el) => (sectionRefs.current[index] = el)}
              data-index={index}
              className="min-h-[60vh] flex flex-col justify-center"
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false }}
              transition={{ duration: 0.6 }}
            >
              <h3 className="text-xl text-gray-500 mb-2 font-medium">{step.step}</h3>
              <h2 className="text-3xl md:text-4xl font-semibold mb-4">{step.title}</h2>
              <p className="text-gray-700 text-lg leading-relaxed mb-6">{step.description}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* === FAQ SECTION === */}
      <section className="bg-gray-50 py-24 px-6 md:px-16">
        <h2 className="text-4xl md:text-5xl text-black font-semibold text-center mb-16">
          Frequently Asked Questions
        </h2>
        <FAQAccordion />

         {/* SEE ALL FAQ BUTTON */}
  <div className="flex justify-center mt-10">
    <Link href="/resources/faqs">
      <button className="px-8 py-3 cursor-pointer bg-[#A855F7] text-white rounded-full font-semibold hover:bg-[#9333EA] transition">
        See All FAQs
      </button>
    </Link>
  </div>
      </section>

      {/* === ADD OTHER SECTIONS (Break-Free, Product Image, Stats, Mobile Studio) === */}
      {/* You can copy your original sections and integrate them as-is here */}

      
    </div>
  );
};

export default ProductPage;
