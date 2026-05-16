"use client";
import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { signIn, signOut, useSession } from "next-auth/react";

const Navbar = ({ pathname }) => {
  const [scrolled, setScrolled] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [useCasesHovered, setUseCasesHovered] = useState(false);
  const [resourcesHovered, setResourcesHovered] = useState(false);

  const { data: session } = useSession();

  // Detect scroll
  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 50);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Pages that ALWAYS show white navbar
  const forcedWhiteNavbarPages = [
    "/use-case/increase-diversity",
    "/use-case/maintain-brand-consistency",
    "/use-case/ready-to-post-social-images",
    "/use-case/minimize-licensing-fees",
    "/use-case/refresh-your-catalog",
    "/resources/help-center",
    "/resources/blog",
    "/resources/case-studies",
    "/resources/faqs",
    "/resources/case-studies/*",
  ];

  const isForcedWhitePage = forcedWhiteNavbarPages.some((page) => {
    if (page.endsWith("/*")) {
      const base = page.replace("/*", "");
      return pathname.startsWith(base);
    }
    return pathname === page;
  });

  const navbarVisible = isForcedWhitePage || scrolled || hovered;
  const textColor = navbarVisible ? "text-black" : "text-white";
  const bgColor = navbarVisible
    ? scrolled || isForcedWhitePage
      ? "bg-white shadow-[0px_4px_12px_rgba(0,0,0,0.15)]"
      : "bg-white"
    : "bg-transparent";

  const useCasesLinks = [
    { name: "Increase diversity", path: "/use-case/increase-diversity" },
    { name: "Maintain brand consistency", path: "/use-case/maintain-brand-consistency" },
    { name: "Ready to post social images", path: "/use-case/ready-to-post-social-images" },
    { name: "Minimize licensing fees", path: "/use-case/minimize-licensing-fees" },
    { name: "Refresh your catalog", path: "/use-case/refresh-your-catalog" },
  ];

  const resourcesLinks = [
    { name: "Help center", path: "/resources/help-center" },
    { name: "Blog", path: "/resources/blog" },
    { name: "Case studies", path: "/resources/case-studies" },
    { name: "FAQs", path: "/resources/faqs" },
  ];

  return (
    <nav
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={`fixed top-0 left-0 w-full z-50 transition-all duration-300 ${bgColor}`}
    >
      <div className={`flex items-center justify-between px-10 h-16 ${textColor}`}>
        {/* LOGO */}
        <div className="flex items-center gap-2">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="34"
            height="34"
            viewBox="0 0 121 25"
            fill="none"
            className="text-current"
          >
            <path d="M12.961 12.9599C11.912 14.0078 ... Z" fill="currentColor" />
          </svg>
          <span className="text-[27px] font-semibold tracking-wide">
            ModeLens
          </span>
        </div>

        {/* CENTER NAVIGATION */}
        <div className="flex gap-12 text-[18px] font-medium relative">
          {/* USE CASES DROPDOWN */}
          <div
            onMouseEnter={() => setUseCasesHovered(true)}
            onMouseLeave={() => setUseCasesHovered(false)}
            className="relative"
          >
            <span className={`relative group cursor-pointer ${textColor}`}>
              Use Cases
              <span className="absolute left-1/2 bottom-0 w-0 h-[2px] bg-black transition-all group-hover:left-0 group-hover:w-full"></span>
            </span>
            <AnimatePresence>
              {useCasesHovered && (
                <motion.div
                  initial={{ opacity: 0, y: -15 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -15 }}
                  transition={{ duration: 0.3 }}
                  className="absolute top-full left-0 mt-2 w-64 bg-white shadow-xl rounded-lg z-20"
                >
                  <ul className="flex flex-col p-4 gap-2 text-black text-sm">
                    {useCasesLinks.map((link, i) => (
                      <motion.li
                        key={i}
                        className="px-3 py-2 cursor-pointer rounded-md hover:bg-gray-100 transition-all"
                      >
                        <Link href={link.path}>{link.name}</Link>
                      </motion.li>
                    ))}
                  </ul>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* PRODUCT */}
          <Link href="/product" className={`relative group ${textColor}`}>
            Product
            <span className="absolute left-1/2 bottom-0 w-0 h-[2px] bg-black transition-all group-hover:left-0 group-hover:w-full"></span>
          </Link>

          {/* RESOURCES */}
          <div
            onMouseEnter={() => setResourcesHovered(true)}
            onMouseLeave={() => setResourcesHovered(false)}
            className="relative"
          >
            <span className={`relative group cursor-pointer ${textColor}`}>
              Resources
              <span className="absolute left-1/2 bottom-0 w-0 h-[2px] bg-black transition-all group-hover:left-0 group-hover:w-full"></span>
            </span>
            <AnimatePresence>
              {resourcesHovered && (
                <motion.div
                  initial={{ opacity: 0, y: -15 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -15 }}
                  transition={{ duration: 0.3 }}
                  className="absolute top-full left-0 mt-2 w-56 bg-white shadow-xl rounded-lg z-20"
                >
                  <ul className="flex flex-col p-4 gap-2 text-black text-sm">
                    {resourcesLinks.map((link, i) => (
                      <motion.li
                        key={i}
                        className="px-3 py-2 cursor-pointer rounded-md hover:bg-gray-100 transition-all"
                      >
                        <Link href={link.path}>{link.name}</Link>
                      </motion.li>
                    ))}
                  </ul>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* PRICING */}
          <Link href="/pricing" className={`relative group ${textColor}`}>
            Pricing
            <span className="absolute left-1/2 bottom-0 w-0 h-[2px] bg-black transition-all group-hover:left-0 group-hover:w-full"></span>
          </Link>
        </div>

        {/* RIGHT BUTTONS */}
        <div className="flex items-center gap-5 text-[15px] font-medium">
          {session ? (
            <button
              onClick={() => signOut()}
              className={`relative group ${textColor}`}
            >
              Logout
              <span className="absolute left-1/2 bottom-0 w-0 h-[2px] bg-black transition-all group-hover:left-0 group-hover:w-full"></span>
            </button>
          ) : (
            <button
              onClick={() => signIn()}
              className={`relative group ${textColor}`}
            >
              Login
              <span className="absolute left-1/2 bottom-0 w-0 h-[2px] bg-black transition-all group-hover:left-0 group-hover:w-full"></span>
            </button>
          )}

          <Link
            href="/try-now"
            className={`px-4 py-1.5 rounded-full font-semibold text-sm transition ${
              navbarVisible
                ? "bg-black text-white hover:bg-gray-800"
                : "bg-white text-black hover:bg-gray-200"
            }`}
          >
            Try Now
          </Link>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
