"use client";

import { SessionProvider } from "next-auth/react";

// NextAuth only brokers the Google/GitHub OAuth handshake; app session state lives in lib/auth-context.
export default function SSOCallbackLayout({ children }) {
  return <SessionProvider>{children}</SessionProvider>;
}
