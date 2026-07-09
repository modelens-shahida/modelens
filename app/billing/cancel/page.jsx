"use client";
import { useRouter } from "next/navigation";
import { XCircle } from "lucide-react";

export default function CheckoutCancelPage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-black flex items-center justify-center">
      <div className="text-center p-8 max-w-md">
        <XCircle className="w-20 h-20 text-red-500 mx-auto mb-6" />
        <h1 className="text-3xl font-bold text-white mb-4">Payment Cancelled</h1>
        <p className="text-gray-400 mb-6">
          Your checkout was cancelled. No charges were made. You can try again anytime.
        </p>
        <div className="flex gap-4 justify-center">
          <button
            onClick={() => router.push("/pricing")}
            className="bg-purple-600 hover:bg-purple-700 text-white px-6 py-3 rounded-full font-semibold transition"
          >
            View Plans
          </button>
          <button
            onClick={() => router.push("/dashboard")}
            className="border border-gray-600 text-gray-300 hover:text-white px-6 py-3 rounded-full font-semibold transition"
          >
            Go to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
