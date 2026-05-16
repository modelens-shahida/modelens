import { FaInstagram, FaFacebook, FaXTwitter, FaYoutube, FaLinkedin } from "react-icons/fa6";

export default function Footer() {
  return (
    <footer className="bg-[#1b1919] text-gray-200 py-12">
      <div className="max-w-7xl mx-auto px-6 md:px-16">
        <div className="flex flex-col md:flex-row justify-evenly items-start gap-12">
          
          {/* Left Section */}
          <div className="max-w-md md:mr-12">
            <div className="flex items-center space-x-2 mb-4">
              <div className="text-3xl font-bold">M</div>
              <h2 className="text-xl font-semibold tracking-wide">ModeLens</h2>
            </div>
            <p className="text-sm text-gray-400 leading-relaxed">
            ModeLens leverages generative AI to elevate online fashion brands, offering lifelike AI models and limitless professional-quality visuals. This technology empowers retailers to captivate customers, reach new markets, and boost conversion rates effortlessly.
            </p>
          </div>

          {/* Right Section (Company + Contact) */}
          <div className="flex flex-col md:flex-row gap-14 md:gap-16">
            
            {/* Company */}
            <div>
              <h3 className="text-sm font-semibold text-gray-100 uppercase tracking-wider mb-3">
                Company
              </h3>
              <ul className="space-y-2 text-sm">
                <li><a href="#" className="hover:text-white">About Us</a></li>
                <li><a href="#" className="hover:text-white">Help Center</a></li>
                <li><a href="#" className="hover:text-white">Blog</a></li>
              </ul>
            </div>

            {/* Contact */}
            <div>
              <h3 className="text-sm font-semibold text-gray-100 uppercase tracking-wider mb-3">
                Contact
              </h3>
              <ul className="space-y-2 text-sm">
                <li><a href="#" className="hover:text-white">Talk to Sales</a></li>
                <li><a href="#" className="hover:text-white">Send us a Message</a></li>
              </ul>

              {/* Social Icons */}
              <div className="flex space-x-4 mt-4 text-gray-400">
                <a href="#" className="hover:text-white"><FaInstagram size={18} /></a>
                <a href="#" className="hover:text-white"><FaFacebook size={18} /></a>
                <a href="#" className="hover:text-white"><FaXTwitter size={18} /></a>
                <a href="#" className="hover:text-white"><FaYoutube size={18} /></a>
                <a href="#" className="hover:text-white"><FaLinkedin size={18} /></a>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Section */}
        <div className="border-t border-gray-700 mt-10 pt-6 text-center text-xs text-gray-400">
          © 2025 ModeLens, all rights reserved. |
          <a href="#" className="hover:text-white ml-1">Terms of service</a> |
          <a href="#" className="hover:text-white ml-1">Privacy policy</a>
        </div>
      </div>
    </footer>
  );
}
