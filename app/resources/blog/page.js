"use client";
import React from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import BlogGrid from "@/components/BlogGrid";

export default function BlogPage() {
  return (
    <section className="w-full min-h-screen bg-white">
      {/* ---------- HEADER ---------- */}
      <div className="max-w-5xl mx-auto text-center px-6 pt-24 pb-16">
        <motion.h1
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-4xl md:text-5xl font-bold mb-6 text-gray-700 leading-tight"
        >
          The Thread
        </motion.h1>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.5 }}
          className="text-gray-600 text-lg md:text-xl max-w-3xl mx-auto"
        >
          Discover new ways to elevate your brand with tips and trends from the
          fashion world.
        </motion.p>
      </div>

      {/* ---------------- HERO SECTION ---------------- */}
      <div className="max-w-7xl mx-auto mt-5 mb-5 px-6">
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.7 }}
          className="relative rounded-3xl overflow-hidden shadow-2xl border border-gray-200 bg-black cursor-pointer"
        >
          {/* FULL IMAGE — NO CROP */}
          <img
            src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/691f16eb9d4ccf9d0d0b053d_Botika_TheThread_NewEraofAIPoweredFashion_Header.webp"
            alt="Case Study — Get Dressed Collective"
            className="w-full h-auto object-contain"
          />

          {/* LEFT OVERLAY */}
          <div className="absolute inset-0 bg-gradient-to-r from-black/80 via-black/40 to-transparent flex items-center">
            <div className="pl-10 md:pl-16 max-w-xl py-10 text-left">
              <p className="text-white/80 text-sm font-semibold uppercase tracking-wider mb-3">
                Generative AI
              </p>

              <h2 className="text-4xl md:text-5xl font-bold text-white leading-snug mb-6">
                The new era of AI powered fashion{" "}
              </h2>

              <h3 className="text-white/90 mb-4">
                By Eran Dagan | November 20, 2025
              </h3>

              {/* READ MORE BUTTON WITH LINK */}
              <Link
                href="/resources/blog/thethread/generative-ai/new-era-of-ai-powered-fashion"
                
              >
                <motion.button
                  whileHover={{ scale: 1.06 }}
                  whileTap={{ scale: 0.95 }}
                  className="mt-4 bg-white/90 cursor-pointer text-black font-semibold px-7 py-3 rounded-full shadow-lg hover:bg-white transition backdrop-blur-md"
                >
                  Read More →
                </motion.button>
              </Link>
            </div>
          </div>
        </motion.div>
      </div>

      <BlogGrid />
    </section>
  );
}
