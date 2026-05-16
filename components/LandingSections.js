"use client"; // Client component to use usePathname
import React from "react";
import { usePathname } from "next/navigation";
import HowItWorks from "./HowItWorks";
import TrustedBy from "./TrustedBy";
import BotikaImpact from "./BotikaImpact";
import AIFashionModelsSection from "./AIFashionModelsSection";
import AISolutions from "./AISolutionsSection";
import CustomerTestimonials from "./CustomerTestimonials";
import MobileStudioSection from "./MobileStudioSection";
import FAQSection from "./FAQSection";

const LandingSections = () => {
  const pathname = usePathname();
  const isHome = pathname === "/";

  if (!isHome) return null;

  return (
    <>
      <HowItWorks />
      <TrustedBy />
      <BotikaImpact />
      <AIFashionModelsSection />
      <AISolutions />
      <CustomerTestimonials />
      <MobileStudioSection />
      <FAQSection />
    </>
  );
};

export default LandingSections;
