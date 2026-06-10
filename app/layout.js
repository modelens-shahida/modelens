import "./globals.css";
import LandingSections from "@/components/LandingSections";
import Wrapper from "@/components/Wrapper";
import Providers from "./providers";

export const metadata = {
  title: "ModeLens",
  description: "AI Fashion Store Clone",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="bg-white text-black">
        <Providers>
          <Wrapper>
            {children}
            <LandingSections />
          </Wrapper>
        </Providers>
      </body>
    </html>
  );
}