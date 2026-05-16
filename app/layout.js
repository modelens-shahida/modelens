import "./globals.css";
import Footer from "@/components/Footer";
import LandingSections from "@/components/LandingSections";
import Wrapper from "@/components/Wrapper";
import Providers from "./providers";

export const metadata = {
  title: "Botika Clone",
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
          <Footer />
        </Providers>
      </body>
    </html>
  );
}