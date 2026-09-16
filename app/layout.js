import "./globals.css";
import LandingSections from "@/components/LandingSections";
import Wrapper from "@/components/Wrapper";
import Providers from "./providers";

export const metadata = {
  title: "ModeLens | AI Generative Fashion Models & Volumetric CAD Studio",
  description: "Empowering global fashion brands with synthetic AI models, 3D volumetric ghost mannequins, ControlNet sketch-to-product CAD, and omnichannel campaign generation.",
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