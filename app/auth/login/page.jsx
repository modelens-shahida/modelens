"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { toast } from "react-hot-toast";

export default function LoginPage() {
  const [emailOrPhone, setEmailOrPhone] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otpInput, setOtpInput] = useState("");

  // STEP 1 → Send OTP
  const handleSendOtp = async () => {
    const result = await signIn("credentials", {
      emailOrPhone,
      redirect: false,
    });

    if (result?.error) {
      toast.error("Error sending OTP");
      return;
    }

    toast.success("OTP sent successfully!");
    setOtpSent(true);
  };

  // STEP 2 → Verify OTP
  const handleVerifyOtp = async () => {
    const sessionReq = await fetch("/api/auth/session");
    const session = await sessionReq.json();

    if (!session?.otp) {
      toast.error("Session expired. Please request OTP again.");
      return;
    }

    if (otpInput === session.otp) {
      toast.success("OTP verified successfully! Login successful 🎉");

      // redirect to dashboard
      window.location.href = "/";
    } else {
      toast.error("Invalid OTP. Please try again.");
    }
  };

  return (
    <div className="w-full max-w-md mx-auto mt-20">
      {!otpSent ? (
        <>
          <input
            type="text"
            placeholder="Email or Phone"
            className="border p-2 w-full mb-3"
            onChange={(e) => setEmailOrPhone(e.target.value)}
          />

          <button
            onClick={handleSendOtp}
            className="bg-blue-600 text-white p-2 w-full rounded"
          >
            Send OTP
          </button>
        </>
      ) : (
        <>
          <input
            type="text"
            placeholder="Enter OTP"
            className="border p-2 w-full mb-3"
            onChange={(e) => setOtpInput(e.target.value)}
          />

          <button
            onClick={handleVerifyOtp}
            className="bg-green-600 text-white p-2 w-full rounded"
          >
            Verify OTP
          </button>
        </>
      )}
    </div>
  );
}
