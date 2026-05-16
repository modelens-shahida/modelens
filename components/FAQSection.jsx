"use client";
import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const faqs = [
  {
    question: "Where do ModeLens AI fashion models come from?",
    answer:
      "All our models are 100% AI-generated—no stock models, no real people, no photo references. Every detail is built from scratch by our tech, from the subtle features in each model’s face to their skin texture and makeup style. Unique faces, made just for your brand.",
  },
  {
    question: "What tech powers your AI models?",
    answer:
      "We developed our own foundation models—trained on fashion-specific data and backed by years of computer vision research. Unlike off-the-shelf solutions, our AI understands fabric flow, fit, and poses—because it was designed to. From the ground up, it’s made for fashion.",
  },
  {
    question: "How do I get started?",
    answer:
      "Getting started with ModeLens is simple – just upload photos of your clothing products. You can take them with your smartphone, get them from suppliers, or even use customer photos. No need for professional photography. Start with a free trial today.",
  },
  {
    question: "Can I customize clothing or models using my own prompts?",
    answer:
      "We don’t offer the ability to make Images from text or custom prompts. Instead, we enhance photos you already have, like those with models or flat lays. Our AI can’t create new clothing or generate new models. Simply upload a clothing photo, pick a model, a pose (for flat lays), and a background.",
  },
  {
    question:
      "Can I use your service for jewelry, footwear, or cosmetics?",
    answer:
      "Right now, we only focus on clothing to ensure top-notch, realistic results. We plan to add more categories in the future. Stay tuned.",
  },
];

export default function FaqSection() {
  const [activeIndex, setActiveIndex] = useState(null);

  const toggleAccordion = (index) => {
    setActiveIndex(activeIndex === index ? null : index);
  };

  return (
    <section className="bg-white py-16 px-6 md:px-20">
      <div className="max-w-3xl mx-auto">
        <h2 className="text-3xl md:text-4xl font-semibold text-gray-900 text-center mb-10">
          Frequently Asked Questions
        </h2>

        <div className="space-y-4">
          {faqs.map((faq, index) => (
            <div
              key={index}
              className="border border-gray-200 rounded-2xl p-5 transition-all duration-300 hover:shadow-md"
            >
              <button
                onClick={() => toggleAccordion(index)}
                className="flex justify-between items-center w-full text-left group"
              >
                {/* Question Text */}
                <span className="text-lg font-medium cursor-pointer text-gray-900 relative">
                  {faq.question}
                  {/* Underline Animation */}
                  <span className="absolute left-0 bottom-0 w-0 h-0.5 bg-gray-900 transition-all duration-500 group-hover:w-full group-focus:w-full"></span>
                </span>

                {/* Plus/Minus Icon */}
                <span className="text-2xl font-bold cursor-pointer text-gray-600">
                  {activeIndex === index ? "–" : "+"}
                </span>
              </button>

              <AnimatePresence>
                {activeIndex === index && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.3 }}
                    className="overflow-hidden mt-3"
                  >
                    <p className="text-gray-600 leading-relaxed">{faq.answer}</p>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
