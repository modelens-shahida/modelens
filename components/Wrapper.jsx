"use client";

import { usePathname } from "next/navigation";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

export default function Wrapper({ children }) {
  const pathname = usePathname();
  const isDashboard = pathname.startsWith("/dashboard");
  const isAuth = pathname.startsWith("/auth");

  return (
    <>
      {!isDashboard && !isAuth && <Navbar pathname={pathname} />}
      <main className="min-h-screen flex flex-col">{children}</main>
      {!isDashboard && !isAuth && <Footer />}
    </>
  );
}