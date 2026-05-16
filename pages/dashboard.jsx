"use client";

import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function Dashboard() {
  const sessionHook = useSession();

  const session = sessionHook?.data;
  const status = sessionHook?.status;

  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/auth/login");
    }
  }, [status, router]);

  if (status === "loading") {
    return <p>Loading...</p>;
  }

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold">
        Welcome, {session?.user?.name}
      </h1>

      <p>This is a protected page.</p>
    </div>
  );
}