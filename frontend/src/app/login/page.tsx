"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { X } from "lucide-react";

function LoginContent() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [authError, setAuthError] = useState("");
  const [isLoadingIntent, setIsLoadingIntent] = useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();

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
    onSuccess: async (data) => {
      const { access_token } = data;
      localStorage.setItem("token", access_token);
      setAuthError("");

      const intent = searchParams.get('intent');
      if (intent === 'priority_air') {
        setIsLoadingIntent(true);
        try {
          const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/billing/checkout`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${access_token}`
            },
            body: JSON.stringify({ action: 'priority_air', user_id: 'temp_user_id' })
          });
          
          const checkoutData = await response.json();
          if (checkoutData.checkout_url) {
            window.location.href = checkoutData.checkout_url;
          } else {
            console.error("No checkout url returned");
            router.push("/dashboard");
          }
        } catch (error) {
          console.error("Error creating checkout session:", error);
          router.push("/dashboard");
        } finally {
          setIsLoadingIntent(false);
        }
      } else {
        router.push("/dashboard");
      }
    },
    onError: (err) => {
      setAuthError(err.message);
    }
  });

  const signUpMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch("/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          first_name: firstName || undefined,
          last_name: lastName || undefined,
        })
      });
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Sign up failed");
      }
      return res.json();
    },
    onSuccess: () => {
      // Auto login after sign up
      loginMutation.mutate();
    },
    onError: (err) => {
      setAuthError(err.message);
    }
  });

  const handleSubmit = () => {
    if (isSignUp) {
      signUpMutation.mutate();
    } else {
      loginMutation.mutate();
    }
  };

  return (
    <div className="flex h-screen w-full items-center justify-center bg-black p-4 text-white relative">
      <button 
        onClick={() => router.push("/")}
        className="absolute top-6 right-6 p-2 text-gray-400 hover:text-white hover:bg-[#16181C] rounded-full transition-colors"
        aria-label="Close"
      >
        <X size={24} />
      </button>
      <div className="w-full max-w-sm space-y-6 bg-[#0E0F11] p-8 rounded-2xl border border-[#2F3336]">
        <div className="space-y-2 text-center">
          <h1 className="text-3xl font-bold">{isSignUp ? "Sign Up" : "Sign In"}</h1>
          <p className="text-sm text-gray-400">
            {isSignUp ? "Create an account to access Cargo.it" : "Enter your credentials to access Cargo.it"}
          </p>
        </div>
        <div className="space-y-4">
          {isSignUp && (
            <div className="flex gap-4">
              <div className="space-y-2 flex-1">
                <label className="text-sm font-medium leading-none text-gray-300">First Name</label>
                <Input 
                  type="text" 
                  value={firstName} 
                  onChange={e => setFirstName(e.target.value)} 
                  placeholder="John" 
                  className="bg-[#16181C] border-[#2F3336] text-white focus-visible:ring-1 focus-visible:ring-white"
                />
              </div>
              <div className="space-y-2 flex-1">
                <label className="text-sm font-medium leading-none text-gray-300">Last Name</label>
                <Input 
                  type="text" 
                  value={lastName} 
                  onChange={e => setLastName(e.target.value)} 
                  placeholder="Doe" 
                  className="bg-[#16181C] border-[#2F3336] text-white focus-visible:ring-1 focus-visible:ring-white"
                />
              </div>
            </div>
          )}
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
          {authError && <div className="text-sm text-red-500 font-medium">{authError}</div>}
          <Button 
            className="w-full bg-white text-black hover:bg-[#E7E9EA] font-bold" 
            onClick={handleSubmit} 
            disabled={loginMutation.isPending || signUpMutation.isPending || isLoadingIntent}
          >
            {isLoadingIntent ? "Preparing Checkout..." : (loginMutation.isPending || signUpMutation.isPending ? "Processing..." : (isSignUp ? "Sign Up" : "Sign In"))}
          </Button>
          <div className="text-center text-sm text-gray-400 mt-4">
            {isSignUp ? "Already have an account? " : "Don't have an account? "}
            <button 
              type="button" 
              onClick={() => {
                setIsSignUp(!isSignUp);
                setAuthError("");
              }}
              className="text-white hover:underline"
            >
              {isSignUp ? "Sign In" : "Sign Up"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="flex h-screen w-full items-center justify-center bg-black text-white">Loading...</div>}>
      <LoginContent />
    </Suspense>
  );
}
