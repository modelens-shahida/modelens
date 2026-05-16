"use client";
import React, { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

const faqData = [
  {
    id: "general",
    title: "General FAQs",
    items: [
      {
        question: "What is Botika?",
        answer:
          "Botika is a generative AI platform that helps clothing brands and retailers make beautiful and realistic fashion photos using virtual models. It simplifies the photo creation process, saves money, and helps you get your clothing collections out to customers quicker.",
      },
      {
        question: "How do I get started?",
        answer:
          "Getting started with Botika is simple – just upload photos of your clothing products. You can take them with your smartphone, get them from suppliers, or even use customer photos. No need for professional photography. Start with a free trial today.",
      },
      {
        question: "What are credits and how many do I need?",
        answer:
          "Generating photos and videos requires credits: each photo costs 1 credit and each video costs 5 credits. For example, if you want to upload 4 photos and 1 video for a certain product, it will cost you 9 credits.",
      },
      {
        question: "How soon will my photos be ready?",
        answer:
          "It takes about 15 minutes for our AI to process your photos. We take extra time to ensure your images look like they were shot in a studio. If there's an issue, we’ll fix it for free.",
      },
      {
        question: "Can I upload headless or cropped images?",
        answer:
          "Definitely. Upload your cropped photo, and Botika will perfectly blend the AI model into it, keeping things natural and realistic.",
      },
    ],
  },
  {
    id: "product",
    title: "Product FAQs",
    items: [
      {
        question: "What types of photos and poses can I use with Botika?",
        answer:
          "Botika offers three main workflows: On-model photos, Flat lays and Mannequin, and AI Video. Each lets you create high-quality visuals easily without a studio setup.",
      },
      {
        question: "Where do Botika AI fashion models come from?",
        answer:
          "All our models are 100% AI-generated—no stock models, no real people, no photo references. Every detail is built from scratch by our tech, from the subtle features in each model’s face to their skin texture and makeup style.",
      },
      {
        question: "Can I use accessories in my photo?",
        answer:
          "If your model is wearing glasses, hats, or jewelry, our AI will try to keep them as close as possible to the original. However, we don’t officially support accessories yet.",
      },
      {
        question: "What tech powers your AI models?",
        answer:
          "We developed our own foundation models—trained on fashion-specific data and backed by years of computer vision research. Our AI understands fabric flow, fit, and poses because it was designed for fashion.",
      },
    ],
  },
  {
    id: "pricing",
    title: "Pricing & Billing",
    items: [
      {
        question: "Do you offer a free trial?",
        answer:
          "Yes. You can sign up any time for a free trial, no credit card needed. You can test our platform with 8 free credits and decide if you want to upgrade to one of our paid plans.",
      },
      {
        question: "What payment methods do you accept?",
        answer:
          "We accept all major credit and debit cards like Visa, Mastercard, and American Express. You can also pay with PayPal.",
      },
      {
        question: "Can I make changes to my plan?",
        answer:
          "Yes, you can change your subscription anytime. When logged into your account, go to the 'Account & Billing' page and select 'Change Plan' or 'Cancel Subscription'.",
      },
      {
        question: "What happens to my unused credits?",
        answer:
          "We offer unlimited credit rollover for active users. When your plan renews, any unused credits will automatically be added to your new batch of credits.",
      },
      {
        question: "Do I need to pay usage rights fees to use the generated photos?",
        answer:
          "No. All of the photos you generate on the Botika platform are free from usage rights fees and can be used freely for commercial use.",
      },
    ],
  },
];

export default function FAQPage() {
  const [activeSection, setActiveSection] = useState("general");
  const sectionRefs = useRef({});

  useEffect(() => {
    const handleScroll = () => {
      const offsets = Object.entries(sectionRefs.current).map(([id, ref]) => ({
        id,
        top: ref.offsetTop - 200,
      }));

      const scrollPos = window.scrollY;
      let current = "general";
      for (let i = 0; i < offsets.length; i++) {
        if (scrollPos >= offsets[i].top) {
          current = offsets[i].id;
        }
      }
      setActiveSection(current);
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <>
      {/* 🖤 Top Hero Section */}
      <section className="bg-[#1b1919] text-white text-center py-24 px-4">
        <h1 className="text-5xl font-bold">Frequently Asked Questions</h1>
      </section>

      {/* 💬 FAQ Content Section */}
      <div className="min-h-screen bg-gray-50 flex flex-col md:flex-row px-6 md:px-20 py-16 gap-10">
        {/* Sidebar */}
        <div className="md:w-1/4 sticky top-24 self-start">
          <ul className="space-y-4">
            {faqData.map((section) => (
              <li key={section.id}>
                <motion.button
                  onClick={() =>
                    sectionRefs.current[section.id]?.scrollIntoView({
                      behavior: "smooth",
                    })
                  }
                  className={`text-lg font-medium transition-all duration-300 relative cursor-pointer
                    ${
                      activeSection === section.id
                        ? "text-black font-semibold scale-105"
                        : "text-gray-500 hover:text-black hover:scale-105"
                    }
                    before:content-[''] before:absolute before:left-0 before:-bottom-1 before:w-0 before:h-[2px] before:bg-black before:transition-all before:duration-300 hover:before:w-full
                  `}
                >
                  {section.title}
                </motion.button>
              </li>
            ))}
          </ul>
        </div>

        {/* Main FAQ Section */}
        <div className="md:w-3/4 space-y-20">
          {faqData.map((section) => (
            <div
              key={section.id}
              ref={(el) => (sectionRefs.current[section.id] = el)}
              id={section.id}
            >
              <h2 className="text-3xl font-bold text-gray-900 mb-8">
                {section.title}
              </h2>
              <div className="space-y-8">
                {section.items.map((faq, idx) => (
                  <div key={idx}>
                    <h3 className="text-xl font-semibold text-gray-800 mb-2">
                      {faq.question}
                    </h3>
                    <p className="text-gray-600 leading-relaxed">
                      {faq.answer}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
