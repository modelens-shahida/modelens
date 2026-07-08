"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // Load token on mount
  useEffect(() => {
    async function initAuth() {
      const storedToken = localStorage.getItem("modelens_token");
      const storedUser = localStorage.getItem("modelens_user");

      if (storedToken) {
        setToken(storedToken);
        if (storedUser) {
          try {
            setUser(JSON.parse(storedUser));
          } catch (e) {
            // ignore JSON parse error
          }
        }

        // Fetch fresh profile details from backend
        try {
          const profile = await api.get("/api/v1/auth/me");
          setUser(profile);
          localStorage.setItem("modelens_user", JSON.stringify(profile));
        } catch (error) {
          console.error("Failed to load user profile, token might be expired", error);
          // Token is invalid/expired
          localStorage.removeItem("modelens_token");
          localStorage.removeItem("modelens_user");
          setToken(null);
          setUser(null);
        }
      }
      setLoading(false);
    }

    initAuth();
  }, []);

  const login = async (email, password, redirectTo = "/dashboard") => {
    setLoading(true);
    try {
      const data = await api.post("/api/v1/auth/login", { email, password });
      localStorage.setItem("modelens_token", data.access_token);
      setToken(data.access_token);

      // Set HTTP-only session cookie for middleware-based route protection
      await fetch("/api/auth/session", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          access_token: data.access_token,
          refresh_token: data.refresh_token,
        }),
      });

      // Fetch user profile immediately
      const profile = await api.get("/api/v1/auth/me");
      setUser(profile);
      localStorage.setItem("modelens_user", JSON.stringify(profile));
      
      router.push(redirectTo);
      return profile;
    } catch (error) {
      setLoading(false);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const register = async (email, password, full_name, redirectTo = "/dashboard") => {
    setLoading(true);
    try {
      const data = await api.post("/api/v1/auth/register", {
        email,
        password,
        full_name,
      });
      // The register endpoint returns user details + access_token directly
      localStorage.setItem("modelens_token", data.access_token);
      setToken(data.access_token);

      // Set HTTP-only session cookie for middleware-based route protection
      await fetch("/api/auth/session", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          access_token: data.access_token,
          refresh_token: data.refresh_token,
        }),
      });

      const profile = {
        id: data.id,
        email: data.email,
        full_name: data.full_name,
        role: "user",
      };
      setUser(profile);
      localStorage.setItem("modelens_user", JSON.stringify(profile));

      router.push(redirectTo);
      return profile;
    } catch (error) {
      setLoading(false);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem("modelens_token");
    localStorage.removeItem("modelens_user");
    setToken(null);
    setUser(null);

    // Clear HTTP-only session cookies
    fetch("/api/auth/session", { method: "DELETE", credentials: "include" });

    router.push("/auth/login");
  };

  const ssoLogin = async (accessToken, userProfile) => {
    localStorage.setItem("modelens_token", accessToken);
    setToken(accessToken);

    // Set HTTP-only session cookie for middleware-based route protection
    await fetch("/api/auth/session", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        access_token: accessToken,
      }),
    });

    setUser(userProfile);
    localStorage.setItem("modelens_user", JSON.stringify(userProfile));
  };

  const refreshUser = async () => {
    try {
      const profile = await api.get("/api/v1/auth/me");
      setUser(profile);
      localStorage.setItem("modelens_user", JSON.stringify(profile));
      return profile;
    } catch (error) {
      console.error("Failed to refresh user profile", error);
      throw error;
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, refreshUser, ssoLogin }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
