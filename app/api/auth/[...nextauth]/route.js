import NextAuth from "next-auth";
import GoogleProvider from "next-auth/providers/google";
import GithubProvider from "next-auth/providers/github";

const authOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || "mock_google_id",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "mock_google_secret",
    }),
    GithubProvider({
      clientId: process.env.GITHUB_CLIENT_ID || "mock_github_id",
      clientSecret: process.env.GITHUB_CLIENT_SECRET || "mock_github_secret",
    }),
  ],
  secret: process.env.NEXTAUTH_SECRET || "nextauth-secret-placeholder-for-dev",
  session: {
    strategy: "jwt",
  },
  callbacks: {
    async jwt({ token, account, profile }) {
      if (account) {
        token.provider = account.provider;
        token.id_token = account.id_token;
        token.access_token = account.access_token;
      }
      if (profile) {
        token.email = profile.email;
        token.name = profile.name || profile.login;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.email = token.email;
        session.user.name = token.name;
      }
      session.provider = token.provider;
      session.id_token = token.id_token;
      session.access_token = token.access_token;
      return session;
    },
  },
};

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };
