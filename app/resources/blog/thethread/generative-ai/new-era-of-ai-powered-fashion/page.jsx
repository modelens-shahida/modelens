"use client";
import React from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { Facebook, Twitter, Linkedin } from "lucide-react";

export default function BlogArticle() {
  const shareUrl =
    "https://yourwebsite.com/resources/blog/thethread/generative-ai/new-era-of-ai-powered-fashion";

  return (
    <section className="w-full min-h-screen bg-white py-20 px-6">
      <div className="max-w-4xl mx-auto">

        {/* ---------- BREADCRUMB ---------- */}
        <nav className="text-sm text-gray-500 mb-6 flex gap-2 flex-wrap">
          <Link href="/resources/blog" className="hover:text-gray-700">
            Blog
          </Link>
          <span>/</span>
          <span className="text-gray-700 font-semibold">Generative AI</span>
        </nav>

         {/* ---------- TITLE ---------- */}
        <motion.h1
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="text-4xl md:text-5xl font-bold text-gray-800 leading-tight mb-4"
        >
          The new era of AI powered fashion
        </motion.h1>

        {/* ---------- AUTHOR + SOCIAL (LEFT + RIGHT) ---------- */}
        <div className="flex justify-between items-center mb-10">

          {/* Left: Author + Date */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2, duration: 0.4 }}
            className="text-gray-600 text-md"
          >
            By <span className="font-semibold text-gray-700">Eran Dagan</span> • November 20, 2025
          </motion.div>

          {/* Right: Social Icons */}
          <div className="flex flex-row gap-4">
            <a
              href={`https://www.facebook.com/sharer/sharer.php?u=${shareUrl}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-500 hover:text-gray-800 transition"
            >
              <Facebook size={22} />
            </a>

            <a
              href={`https://twitter.com/intent/tweet?url=${shareUrl}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-500 hover:text-gray-800 transition"
            >
              <Twitter size={22} />
            </a>

            <a
              href={`https://www.linkedin.com/sharing/share-offsite/?url=${shareUrl}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-500 hover:text-gray-800 transition"
            >
              <Linkedin size={22} />
            </a>
          </div>
        </div>

        {/* ---------- HERO IMAGE ---------- */}
        <motion.img
          src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/691f16eb9d4ccf9d0d0b053d_Botika_TheThread_NewEraofAIPoweredFashion_Header.webp"
          alt="AI Powered Fashion Header"
          className="w-full h-auto rounded-2xl mb-10"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />

       

        {/* ---------- ARTICLE CONTENT ---------- */}
       <motion.div
  initial={{ opacity: 0 }}
  animate={{ opacity: 1 }}
  transition={{ delay: 0.3, duration: 0.5 }}
  className="prose prose-lg max-w-none text-gray-700"
>
  {/* Introduction */}
  <p>
    We all love a trend. And right now, one of the biggest trends in fashion content is this: <strong>AI powered fashion creation</strong>. 
    But there’s a big difference between <em>“we threw a prompt at a text-to-image tool and got something kinda OK”</em> and 
    <em>“we have a production-ready workflow that reliably turns your product catalog into on-model visuals, at scale, on-brand, consistent and high quality.”</em>
  </p>

  <p>
    We want to pull back the curtain and show you how the AI powered fashion workflow is shifting from prompt-play to product-ready visuals 
    and why it matters for fashion brands that need reliability and scale.
  </p>

  {/* Heading: Prompt-based era */}
  <h2 className="mt-8 text-2xl font-semibold text-gray-800">
    The prompt-based era: Exciting but inconsistent AI powered fashion
  </h2>

  <p>
    Let’s take a moment to acknowledge where we started. For many brands and creators, the AI powered fashion workflow kicked off with prompt-based tools. 
    You type something like:
  </p>

  <blockquote className="border-l-4 border-gray-300 pl-4 italic my-4">
    “a female model wearing a red wrap top, urban streetwear background, high-resolution, natural light”
  </blockquote>

  <p>
    … hit Generate, and you get a visual. Sometimes it’s good. Often you get weird arms, strange fabric drapes, logos that are messed up or poses that don’t match your brand aesthetic. 
    As noted in another blog post:
  </p>

  <blockquote className="border-l-4 border-gray-300 pl-4 italic my-4">
    “If you’ve tried using text-to-image tools for fashion visuals … you’ve probably seen the issues: weird hand placements or extra fingers; distorted logos or patterns; clothes that don’t follow real-world physics.”
  </blockquote>

  <p>The big limitation is losing consistency and control. Every output from a generic AI powered fashion prompt-based model is slightly different; you have to iterate, fix, compensate. 
     For a one-off social post this might be fine. But for a full catalog launch, or 1000 SKUs or seasonal refreshes it becomes chaotic.</p>

  {/* Bullet points: Roadblocks */}
  <p>And when you rely on those tools for scale, you hit these roadblocks:</p>
  <ul className="list-disc list-inside ml-4">
    <li>Variability of quality</li>
    <li>Little control over model type, pose, lighting, or background</li>
    <li>Brand aesthetic drift – some images feel “off-brand”</li>
    <li>Time spent cleaning up, rejecting, and re-doing images</li>
    <li>Risk that the garment is misrepresented (folds, texture, drape all don’t match reality)</li>
  </ul>

  <p>In short, AI powered fashion prompt-based tools were a fun experiment, but not yet a workflow that fashion brands could depend on.</p>

  {/* Heading: What brands need */}
  <h2 className="mt-8 text-2xl font-semibold text-gray-800">
    What brands really need: Reliability + scale
  </h2>

  <p>When you’re a fashion brand, no matter your size, what you really need from your visual production engine is:</p>

  {/* Bullet points: Needs */}
  <ul className="list-disc list-inside ml-4">
    <li>
      <strong>Predictability:</strong> When you upload X garments, you want output that meets your quality bar, not a gamble.
    </li>
    <li>
      <strong>Consistency:</strong> Across models, backgrounds, lighting, brand aesthetic – everything should align.
    </li>
    <li>
      <strong>Speed:</strong> Launching new collections, refreshing images, supporting ad campaigns, you want a fast turnaround.
    </li>
    <li>
      <strong>Cost efficiency:</strong> Traditional photoshoots (models, studios, stylists) are expensive, slow and hard to scale.
    </li>
    <li>
      <strong>Brand control and rights:</strong> You need to own your images, ensure they are aligned with your brand values (diversity, representation, ethics) and avoid legal or ethical risk.
    </li>
    <li>
      <strong>Scalability:</strong> The ability to handle many SKUs, many visuals, many contexts (web, ads, social) without exploding cost or logistics.
    </li>
  </ul>

  <p>
    When you evaluate an AI powered fashion workflow, ask: <em>“Does this system deliver on all those demands?”</em> 
    Because if one is weak (say consistency or speed), you’ll end up back in the same bottlenecks as a photoshoot.
  </p>
</motion.div>


{/* ---------- CTA SECTION ---------- */}
<motion.div
  initial={{ opacity: 0, y: 20 }}
  whileInView={{ opacity: 1, y: 0 }}
  viewport={{ once: true }}
  transition={{ duration: 0.6 }}
  className="bg-gray-100 rounded-3xl p-10 mt-16"
>
  <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center gap-8">
    
    {/* Left Side: Text + Button */}
    <div className="flex-1">
      <h2 className="text-3xl md:text-4xl font-bold text-gray-800 mb-4">
        Streamline your visual production
      </h2>
      <p className="text-gray-700 text-lg mb-6">
        Create more, publish faster with AI fashion models
      </p>
      <button className="bg-black text-white font-semibold cursor-pointer px-4 py-2 rounded-full shadow-lg hover:bg-gray-900 transition">
        Start creating
      </button>
    </div>

    {/* Right Side: Image */}
    <div className="flex-1">
      <motion.img
        src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/67bce5d0843a5b4005f1047e_Botika_UseCase_Seamlessvisualsbetterresults.webp"
        alt="AI Fashion Workflow"
        className="w-full rounded-2xl shadow-lg object-cover"
        initial={{ opacity: 0, x: 50 }}
        whileInView={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.6 }}
      />
    </div>
    
  </div>
</motion.div>


{/* ---------- BRAND-READY AI TOOLS ---------- */}
<motion.div
  initial={{ opacity: 0, y: 20 }}
  whileInView={{ opacity: 1, y: 0 }}
  viewport={{ once: true }}
  transition={{ duration: 0.5 }}
  className="prose prose-lg max-w-none text-gray-700 mt-16"
>
  {/* Heading */}
  <h2 className="text-3xl font-bold text-gray-800 mb-4">
    Enter pre-trained, brand-ready AI powered fashion tools
  </h2>

  {/* Intro Paragraph */}
  <p className="mb-6">
    This is where a platform like Botika comes in. We built our system not as a generic
    “type a prompt” engine, but as a purpose-built AI powered fashion workflow for brands.
    Here’s how we turned AI from a creative experiment into a production-ready tool for fashion brands.
  </p>

  {/* Bulleted List */}
  <ul className="list-disc list-inside space-y-3 mb-6">
    <li>
      Instead of starting from “a random image generator + your text prompt”, we start
      from your product photo (flat lay, mannequin or on-model) and a curated library
      of brand-ready AI fashion models (diverse body types, poses, ethnicities, consistent aesthetic).
    </li>
    <li>
      We built our own foundation models trained on fashion-specific data: garments,
      fabric drape, poses, fit, movement. We are not just using “general purpose” diffusion models.
    </li>
    <li>
      We give you a workflow: upload product shot → pick model(s) → pick pose/background → generate → review → refine. 
      No BA degree in text prompts required.
    </li>
    <li>
      Because our models and system are built for fashion, you get features like:
      wide pose/angle coverage, consistent lighting, brand-style backgrounds,
      import to Shopify integration and batch processing for catalogs.
    </li>
    <li>
      You own the output, you avoid legal/rights ambiguity (since our models are fully AI generated, no real person
      or licensed model library) which matters for brand safety.
    </li>
    <li>
      Rather than “type a prompt and hope” you get a tool-chain where each step is optimized, controlled and reliable.
    </li>
  </ul>
  </motion.div>


{/* ---------- WORKFLOW COMPARISON ---------- */}
<motion.div
  initial={{ opacity: 0, y: 20 }}
  whileInView={{ opacity: 1, y: 0 }}
  viewport={{ once: true }}
  transition={{ duration: 0.5 }}
  className="prose prose-lg max-w-none text-gray-700 mt-16"
>
  {/* Section Heading */}
  <h2 className="text-3xl font-bold text-gray-800 mb-4">
    Workflow comparison: Prompt-tool vs brand-ready tool
  </h2>
  <p className="mb-6">
    Let’s compare AI powered fashion workflows side-by-side.
  </p>

  {/* First Image */}
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true }}
    transition={{ duration: 0.5 }}
    className="mb-6"
  >
    <img
      src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/691f173f446208008b55a181_Botika_TheThread_NewEraofAIPoweredFashion_Inner%20image_01.webp"
      alt="Workflow comparison image 1"
      className="w-full rounded-lg shadow-md"
    />
  </motion.div>

  {/* Prompt tool limitations */}
  <h3 className="text-2xl font-semibold text-gray-800 mb-3">
    Where prompt AI powered fashion tools fall short at scale
  </h3>
  <ul className="list-disc list-inside space-y-3 mb-6">
    <li>
      A brand launches 300 SKUs and tries to generate images via prompts. 20% of images show modeling glitches (weird hands, warped fabric). The brand either rejects them or spends hours editing. The time savings vanish.
    </li>
    <li>
      Backgrounds and poses vary too much. You end up with a visual catalog that lacks cohesion, eroding brand trust.
    </li>
    <li>
      The text prompts used yesterday don’t yield the same quality tomorrow due to latent model changes or prompt drift. This variability is a risk.
    </li>
    <li>
      For campaigns (hero image, ads, social), you need multiple angles, consistent lighting, brand style. Prompt tools often give one-off weird images, not a curated set.
    </li>
    <li>
      If you outsource prompt creation to a freelancer, you get manual steps anyway and lose automation benefits.
    </li>
    <li>
      Brand legal risk. If the underlying model was trained on scraped real-people or stock imagery, you might retroactively have liability. Fully AI-generated model library approach mitigates this.
    </li>
    <li>
      In short, at small scale (one image) prompt-based may work. At large scale (catalog refresh, campaign suite, global brand) it gets flaky fast.
    </li>
  </ul>

  {/* Second Image */}
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true }}
    transition={{ duration: 0.5 }}
    className="mb-6"
  >
    <img
      src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/691f2c7173d2c3c294a38aad_Botika_TheThread_NewEraofAIPoweredFashion_Inner%20image_02.webp"
      alt="Workflow comparison image 2"
      className="w-full rounded-lg shadow-md"
    />
  </motion.div>

  {/* Botika workflow */}
  <h3 className="text-2xl font-semibold text-gray-800 mb-3">
    How the AI powered fashion workflow works at Botika
  </h3>
  <ul className="list-decimal list-inside space-y-4 mb-6">
    <li>
      <strong>Step 1: Product photo upload</strong>
      <p>
        Start with any clear garment shot—flat lay, mannequin or on model. Good lighting and visible texture help the system prep your file for production. Batch upload full collections, multiple SKUs, poses, and backgrounds. Key: clear lighting, visible seams, good fabric texture.
      </p>
    </li>
    <li>
      <strong>Step 2: Model / Pose / Background selection</strong>
      <p>
        Choose from a curated library of models (various sizes, ethnicities, poses). Pick a background or keep the original. Select a style (studio, location, lifestyle). This gives deterministic control.
      </p>
    </li>
    <li>
      <strong>Step 3: Generation & Review</strong>
      <p>
        Hit ‘Generate’. The platform uses Botika’s fashion-trained AI engine to map the product photo onto the chosen model + pose + background, adjusting fit, lighting, drape, and preserving brand aesthetic. Results are stronger than generic AI outputs.
      </p>
    </li>
    <li>
      <strong>Step 4: Publish and reuse</strong>
      <p>
        Export images with usage rights, plug into Shopify or CMS, integrate into ads, social posts, and product pages. With consistent workflow and visual style, brand identity stays strong. Upload-to-live image time shrinks from weeks to minutes.
      </p>
    </li>
  </ul>
</motion.div>


     {/* ---------- HEADING ---------- */}
        <motion.h2
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="text-3xl md:text-4xl font-bold text-gray-800 mb-6"
        >
          Why reliability matters more than novelty
        </motion.h2>

        {/* ---------- INTRO TEXT ---------- */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.4 }}
          className="text-gray-700 mb-6"
        >
          In the world of fashion, novelty is nice. But reliability wins. Every day that a SKU sits un-photographed, it's a lost revenue opportunity. Every day your visuals are inconsistent, you erode brand trust. Every time you re-shoot or fix images, you add cost and delay.
        </motion.p>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3, duration: 0.4 }}
          className="text-gray-700 mb-6"
        >
          When I explain our approach at Botika, I often say: it’s not enough to be able to generate one perfect image. You need to repeat that perfect image dozens or hundreds of times, across channels and launch contexts.
        </motion.p>

        {/* ---------- BULLETS ---------- */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4, duration: 0.4 }}
          className="mb-8"
        >
          <h3 className="text-xl font-semibold text-gray-800 mb-4">
            Reliability is achieved through:
          </h3>
          <ul className="list-disc list-inside text-gray-700 space-y-2">
            <li>A clean input workflow (good product photos)</li>
            <li>A curated, consistent model/pose/background system</li>
            <li>A generation engine trained for your domain (fashion)</li>
            <li>Quality control and batch tooling</li>
            <li>Integration into your publishing stack (CMS, ad platforms, social)</li>
          </ul>
        </motion.div>

        {/* ---------- SCALING UP ---------- */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5, duration: 0.4 }}
          className="mb-8"
        >
          <h3 className="text-xl font-semibold text-gray-800 mb-4">
            Scaling up: Catalog refresh, global markets, campaign modes
          </h3>
          <ul className="list-disc list-inside text-gray-700 space-y-2">
            <li><strong>Catalog refreshes:</strong> Update existing SKUs in bulk without studio shoots.</li>
            <li><strong>Localization:</strong> Generate visuals for different markets (US, EU, LATAM, APAC) without reshoots.</li>
            <li><strong>Omnichannel formats:</strong> Hero image, mobile carousels, social verticals, ad creatives.</li>
            <li><strong>Speed to market:</strong> Upload new collections and go live in minutes/hours.</li>
            <li><strong>Cost savings:</strong> Reduced studio rental, limited logistics, no booking models.</li>
          </ul>
        </motion.div>

      {/* ---------- CTA SECTION ---------- */}
<motion.div
  initial={{ opacity: 0, y: 20 }}
  whileInView={{ opacity: 1, y: 0 }}
  viewport={{ once: true }}
  transition={{ duration: 0.6 }}
  className="bg-gray-100 rounded-3xl p-10 mt-16"
>
  <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center gap-8">
    
    {/* Left Side: Text + Button */}
    <div className="flex-1">
      <h2 className="text-3xl md:text-4xl font-bold text-gray-800 mb-4">
    Revolutionize your fashion visuals
      </h2>
      <p className="text-gray-700 text-lg mb-6">
Boost engagement, elevate your brand with AI models.

      </p>
      <button className="bg-black text-white font-semibold cursor-pointer px-4 py-2 rounded-full shadow-lg hover:bg-gray-900 transition">
        Start creating
      </button>
    </div>

    {/* Right Side: Image */}
    <div className="flex-1">
      <motion.img
        src="https://cdn.prod.website-files.com/66faa4f99edc33598569d98f/6888d75bae22866abd633045_Botika_Revolutionizeyourfashionvisuals.webp"
        alt="AI Fashion Workflow"
        className="w-full rounded-2xl shadow-lg object-cover"
        initial={{ opacity: 0, x: 50 }}
        whileInView={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.6 }}
      />
    </div>
    
  </div>
</motion.div>

        {/* ---------- FINAL THOUGHTS ---------- */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.7, duration: 0.4 }}
          className="text-gray-700 prose prose-lg"
        >
          <h3 className="text-xl font-semibold text-gray-800 mb-4">Final thoughts</h3>
          <p>
            The shift from prompt-based creation to structured AI powered fashion workflows marks a quiet but important change. Fashion brands no longer need to gamble with results, they can build visual systems that scale, stay consistent and support creativity instead of slowing it down.
          </p>
          <p>
            When AI creation becomes repeatable, predictable, and aligned with your brand, it stops being an experiment and starts being infrastructure. That’s the quiet revolution happening right now: creativity powered by consistency.
          </p>
        </motion.div>





      </div>
    </section>
  );
}
