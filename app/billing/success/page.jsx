"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2 } from "lucide-react";
import toast from "react-hot-toast";

export default function CheckoutSuccessPage() {
  const router = useRouter();

  useEffect(() => {
    toast.success("🎉 Subscription activated successfully!");
    const timer = setTimeout(() => {
      router.push("/dashboard/billing");
    }, 4000);
    return () => clearTimeout(timer);
  }, [router]);

  return (
    <div className="min-h-screen bg-black flex items-center justify-center">
      <div className="text-center p-8 max-w-md">
        <CheckCircle2 className="w-20 h-20 text-green-500 mx-auto mb-6" />
        <h1 className="text-3xl font-bold text-white mb-4">Payment Successful!</h1>
        <p className="text-gray-400 mb-6">
          Your subscription has been activated. You will be redirected to your billing dashboard shortly.
        </p>
        <button
          onClick={() => router.push("/dashboard/billing")}
          className="bg-purple-600 hover:bg-purple-700 text-white px-6 py-3 rounded-full font-semibold transition"
        >
          Go to Billing Dashboard
        </button>
      </div>
    </div>
  );
}
