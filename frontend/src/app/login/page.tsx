"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const router = useRouter();

  // If token is already present, redirect to dashboard
  useEffect(() => {
    const storedToken = localStorage.getItem("token");
    if (storedToken) {
      router.push("/dashboard");
    }
  }, [router]);

  const loginMutation = useMutation({
    mutationFn: async () => {
      const formData = new URLSearchParams();
      formData.append("username", email);
      formData.append("password", password);

      const res = await fetch("/api/auth/login/access-token", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData.toString()
      });
      if (!res.ok) {
        throw new Error("Invalid credentials");
      }
      return res.json();
    },
    onSuccess: (data) => {
      const { access_token } = data;
      localStorage.setItem("token", access_token);
      setLoginError("");
      router.push("/dashboard");
    },
    onError: (err) => {
      setLoginError(err.message);
    }
  });

  return (
    <div className="flex h-screen w-full items-center justify-center bg-black p-4 text-white">
      <div className="w-full max-w-sm space-y-6 bg-[#0E0F11] p-8 rounded-2xl border border-[#2F3336]">
        <div className="space-y-2 text-center">
          <h1 className="text-3xl font-bold">Sign In</h1>
          <p className="text-sm text-gray-400">Enter your credentials to access Cargo.it</p>
        </div>
        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium leading-none text-gray-300">Email</label>
            <Input 
              type="email" 
              value={email} 
              onChange={e => setEmail(e.target.value)} 
              placeholder="admin@example.com" 
              className="bg-[#16181C] border-[#2F3336] text-white focus-visible:ring-1 focus-visible:ring-white"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium leading-none text-gray-300">Password</label>
            <Input 
              type="password" 
              value={password} 
              onChange={e => setPassword(e.target.value)} 
              className="bg-[#16181C] border-[#2F3336] text-white focus-visible:ring-1 focus-visible:ring-white"
            />
          </div>
          {loginError && <div className="text-sm text-red-500 font-medium">{loginError}</div>}
          <Button 
            className="w-full bg-white text-black hover:bg-[#E7E9EA] font-bold" 
            onClick={() => loginMutation.mutate()} 
            disabled={loginMutation.isPending}
          >
            {loginMutation.isPending ? "Signing in..." : "Sign In"}
          </Button>
        </div>
      </div>
    </div>
  );
}
