"use client";
import React, { useState } from "react";
import { Search, ChevronDown, ChevronUp, BookOpen, Image, Brain, Webhook, CreditCard, CheckCircle2, Loader2 } from "lucide-react";
import toast from "react-hot-toast";

const CATEGORIES = [
  { id: "all", label: "All Topics", icon: BookOpen },
  { id: "getting-started", label: "Getting Started", icon: BookOpen },
  { id: "asset-management", label: "Asset Management", icon: Image },
  { id: "ai-training", label: "AI Model Training", icon: Brain },
  { id: "integrations", label: "Integrations & Webhooks", icon: Webhook },
  { id: "billing", label: "Billing & Credits", icon: CreditCard },
];

const FAQS = [
  { id: 1, category: "getting-started", q: "How do I create my first brand workspace?", a: "Navigate to the Brands section in the dashboard, click 'Create Brand', enter your brand name, and you're ready to start uploading assets and running AI generations." },
  { id: 2, category: "getting-started", q: "How do I invite team members to my workspace?", a: "Go to your Brand Details page, click the 'Team Members' tab, and use the 'Invite Member' button to send email invitations with specific roles (Viewer, Editor, or Admin)." },
  { id: 3, category: "getting-started", q: "What roles are available for team members?", a: "ModeLens offers four roles: Owner (full access), Admin (manage members and settings), Editor (create and edit content), and Viewer (read-only access)." },
  { id: 4, category: "asset-management", q: "What file formats are supported for asset uploads?", a: "ModeLens supports JPG, PNG, and WebP image formats. Uploaded images are automatically converted to WebP and optimized with 250x250 thumbnails and 800x800 previews." },
  { id: 5, category: "asset-management", q: "How does AI auto-tagging work?", a: "When you upload an asset, our AI vision model (GPT-4o-mini) automatically generates 3-5 descriptive tags. You can also manually add or remove tags from the asset detail panel." },
  { id: 6, category: "asset-management", q: "How do I restore a deleted asset?", a: "Deleted assets are soft-deleted and moved to the Trash. Click 'View Trash' on the Assets page to see deleted assets and restore them within 30 days." },
  { id: 7, category: "ai-training", q: "How do I train a custom AI character model?", a: "Navigate to AI Characters, create a character, upload reference images as training assets, then click 'Train New Version'. Training typically takes a few minutes and logs metrics via MLflow." },
  { id: 8, category: "ai-training", q: "What is a Character Version?", a: "Each training run creates a new Character Version with its own MLflow run ID, hyperparameters, and model weights. You can select specific versions when generating campaign creatives." },
  { id: 9, category: "ai-training", q: "How do I view training metrics?", a: "Go to AI Characters, select a character, and open the version drawer. Each version shows its MLflow run ID and training metrics including loss curves and hyperparameters." },
  { id: 10, category: "integrations", q: "How do I set up a webhook subscription?", a: "Go to the Webhooks page in your dashboard, click 'New Webhook', enter your endpoint URL, select events (e.g. job.completed), and choose a payload format. A signing secret is automatically generated." },
  { id: 11, category: "integrations", q: "How do I verify webhook signatures?", a: "Every webhook request includes an X-Modelens-Signature header. Use HMAC SHA256 with your secret token to verify the signature. See our developer docs for Python and Node.js examples." },
  { id: 12, category: "integrations", q: "What happens when a webhook delivery fails?", a: "Failed deliveries are automatically retried up to 5 times with exponential backoff. After 5 failures, the delivery enters the Dead Letter Queue and you receive an in-app notification." },
  { id: 13, category: "billing", q: "How does the credit system work?", a: "Each AI generation job costs 1 credit. Credits are deducted when a job starts. If a job fails, credits are automatically refunded. You can top up credits from the Billing & Credits page." },
  { id: 14, category: "billing", q: "What are the available subscription plans?", a: "ModeLens offers three plans: Lite (100 credits/month), Plus (500 credits/month), and Pro (2000 credits/month). You can upgrade or downgrade at any time from the Billing page." },
  { id: 15, category: "billing", q: "What happens when I run out of credits?", a: "When your balance drops below 20 credits, you'll see a warning banner on the dashboard and receive an email alert. You can purchase additional credits from the Billing & Credits page." },
];

export default function HelpCenterPage() {
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [openFaq, setOpenFaq] = useState(null);
  const [ticketForm, setTicketForm] = useState({ name: "", email: "", category: "getting-started", description: "" });
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const filteredFaqs = FAQS.filter(faq => {
    const matchesCategory = selectedCategory === "all" || faq.category === selectedCategory;
    const matchesSearch = !search || faq.q.toLowerCase().includes(search.toLowerCase()) || faq.a.toLowerCase().includes(search.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const handleTicketSubmit = async (e) => {
    e.preventDefault();
    if (!ticketForm.name || !ticketForm.email || !ticketForm.description) {
      toast.error("Please fill in all required fields");
      return;
    }
    setSubmitting(true);
    await new Promise(r => setTimeout(r, 1500));
    setSubmitting(false);
    setSubmitted(true);
    toast.success("Support ticket submitted! We'll get back to you within 24 hours.");
  };

  return (
    <div className="min-h-screen bg-black text-white">
      {/* Hero Banner */}
      <div className="bg-gradient-to-br from-purple-950/50 to-black border-b border-purple-900/30 px-6 py-16 text-center">
        <h1 className="text-4xl font-bold text-white mb-3">Help Center</h1>
        <p className="text-zinc-400 text-lg mb-8">Find answers, guides, and support for ModeLens</p>
        <div className="relative max-w-xl mx-auto">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search FAQs and guides..."
            className="w-full bg-zinc-900 border border-zinc-700 focus:border-purple-500 rounded-2xl pl-12 pr-4 py-3 text-sm text-white outline-none transition"
          />
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 py-12">
        {/* Category Grid */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-10">
          {CATEGORIES.map(cat => {
            const Icon = cat.icon;
            return (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`flex flex-col items-center gap-2 p-4 rounded-2xl border transition text-center ${
                  selectedCategory === cat.id
                    ? "bg-purple-600 border-purple-500 text-white"
                    : "bg-zinc-900/50 border-zinc-800 text-zinc-400 hover:border-purple-500 hover:text-white"
                }`}
              >
                <Icon className="w-5 h-5" />
                <span className="text-xs font-medium">{cat.label}</span>
              </button>
            );
          })}
        </div>

        {/* FAQ Accordion */}
        <div className="mb-12">
          <h2 className="text-lg font-semibold text-white mb-4">
            {filteredFaqs.length} {filteredFaqs.length === 1 ? "Result" : "Results"}
          </h2>
          {filteredFaqs.length === 0 ? (
            <div className="text-zinc-500 text-sm text-center py-12 border border-zinc-800 rounded-2xl">
              No results found. Try a different search term or category.
            </div>
          ) : (
            <div className="space-y-3">
              {filteredFaqs.map(faq => (
                <div key={faq.id} className="bg-zinc-900/50 border border-zinc-800 rounded-2xl overflow-hidden">
                  <button
                    onClick={() => setOpenFaq(openFaq === faq.id ? null : faq.id)}
                    className="w-full flex items-center justify-between px-5 py-4 text-left"
                  >
                    <span className="text-sm font-medium text-white">{faq.q}</span>
                    {openFaq === faq.id
                      ? <ChevronUp className="w-4 h-4 text-purple-400 shrink-0" />
                      : <ChevronDown className="w-4 h-4 text-zinc-500 shrink-0" />
                    }
                  </button>
                  {openFaq === faq.id && (
                    <div className="px-5 pb-4 text-sm text-zinc-400 border-t border-zinc-800 pt-3">
                      {faq.a}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Support Ticket Form */}
        <div className="bg-gradient-to-br from-zinc-900/80 to-purple-950/20 border border-zinc-800 rounded-2xl p-8">
          <h2 className="text-lg font-semibold text-white mb-2">Still need help?</h2>
          <p className="text-zinc-400 text-sm mb-6">Submit a support ticket and we'll get back to you within 24 hours.</p>

          {submitted ? (
            <div className="flex flex-col items-center py-8 gap-3">
              <CheckCircle2 className="w-12 h-12 text-green-400" />
              <p className="text-white font-semibold">Ticket Submitted!</p>
              <p className="text-zinc-400 text-sm">We'll respond within 24 hours.</p>
              <button onClick={() => { setSubmitted(false); setTicketForm({ name: "", email: "", category: "getting-started", description: "" }); }} className="text-xs text-purple-400 hover:text-purple-300 mt-2">Submit another ticket</button>
            </div>
          ) : (
            <form onSubmit={handleTicketSubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-zinc-400 block mb-1">Name *</label>
                  <input type="text" value={ticketForm.name} onChange={e => setTicketForm(p => ({...p, name: e.target.value}))} placeholder="Your name" className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-2.5 text-sm text-white outline-none focus:border-purple-500 transition" />
                </div>
                <div>
                  <label className="text-xs text-zinc-400 block mb-1">Email *</label>
                  <input type="email" value={ticketForm.email} onChange={e => setTicketForm(p => ({...p, email: e.target.value}))} placeholder="your@email.com" className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-2.5 text-sm text-white outline-none focus:border-purple-500 transition" />
                </div>
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Category</label>
                <select value={ticketForm.category} onChange={e => setTicketForm(p => ({...p, category: e.target.value}))} className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-2.5 text-sm text-white outline-none">
                  {CATEGORIES.filter(c => c.id !== "all").map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Description *</label>
                <textarea value={ticketForm.description} onChange={e => setTicketForm(p => ({...p, description: e.target.value}))} placeholder="Describe your issue in detail..." rows={4} className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-2.5 text-sm text-white outline-none focus:border-purple-500 transition resize-none" />
              </div>
              <button type="submit" disabled={submitting} className="w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-50 py-3 rounded-xl text-sm font-semibold transition flex items-center justify-center gap-2">
                {submitting ? <><Loader2 className="w-4 h-4 animate-spin" /> Submitting...</> : "Submit Ticket"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
