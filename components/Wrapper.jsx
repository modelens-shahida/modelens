"use client";

import { usePathname } from "next/navigation";
import Navbar from "@/components/Navbar";

export default function Wrapper({ children }) {
  const pathname = usePathname();

  return (
    <>
      <Navbar pathname={pathname} />
      <main>{children}</main>
    </>
  );
}