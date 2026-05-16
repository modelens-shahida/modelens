import NextAuth from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import nodemailer from "nodemailer";
import twilio from "twilio";

export const authOptions = {
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        emailOrPhone: { label: "Email or Phone", type: "text" },
      },
     async authorize(credentials) {
  console.log("➡ AUTHORIZE START");
  console.log("Received Credentials:", credentials);

  const { emailOrPhone } = credentials;

  try {
    const otp = Math.floor(100000 + Math.random() * 900000).toString();
    console.log("Generated OTP:", otp);

    if (emailOrPhone.includes("@")) {
      console.log("Sending email OTP...");

      const transporter = nodemailer.createTransport({
        service: "gmail",
        auth: {
          user: process.env.EMAIL_USER,
          pass: process.env.EMAIL_PASS,
        },
      });

      await transporter.sendMail({
        from: process.env.EMAIL_USER,
        to: emailOrPhone,
        subject: "Your OTP Code",
        text: `Your OTP code is ${otp}`,
      });

      console.log("Email OTP sent successfully");
    } else {
      console.log("Sending SMS OTP...");

      const client = twilio(
        process.env.TWILIO_SID,
        process.env.TWILIO_AUTH_TOKEN
      );

      await client.messages.create({
        body: `Your OTP code is ${otp}`,
        from: process.env.TWILIO_PHONE_NUMBER,
        to: emailOrPhone,
      });

      console.log("SMS OTP sent successfully");
    }

    console.log("➡ AUTHORIZE SUCCESS");
    return {
      id: emailOrPhone,
      emailOrPhone,
      otp,
    };
  } catch (err) {
    console.error("❌ AUTHORIZE ERROR:", err);
    throw new Error("OTP_SEND_FAILED");
  }
}

    }),
  ],

  session: { strategy: "jwt" },

  pages: {
    signIn: "/auth/login",
  },

  callbacks: {
    async jwt({ token, user }) {
      if (user?.otp) token.otp = user.otp;
      if (user?.emailOrPhone) token.emailOrPhone = user.emailOrPhone;
      return token;
    },
    async session({ session, token }) {
      session.otp = token.otp;
      session.emailOrPhone = token.emailOrPhone;
      return session;
    },
  },
};

const handler = NextAuth(authOptions);

// MUST BE LAST LINE
export { handler as GET, handler as POST };
