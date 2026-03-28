"use client";

import { useState, useEffect } from "react";
import { Zap, Package, Loader2 } from "lucide-react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { useRouter } from "next/navigation";

interface UserProfile {
  id: string;
  email: string;
  credits: number;
  subscription_tier: string;
}

export function CreditBalanceWidget() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const [isLoadingProfile, setIsLoadingProfile] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const fetchProfile = async () => {
      const token = localStorage.getItem("token");
      if (!token) {
        setIsLoadingProfile(false);
        return;
      }

      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/auth/me`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        if (response.ok) {
          const data = await response.json();
          setProfile(data);
        }
      } catch (error) {
        console.error("Failed to fetch profile:", error);
      } finally {
        setIsLoadingProfile(false);
      }
    };

    fetchProfile();
  }, []);

  const handleCheckout = async (action: "priority_air" | "buy_credits") => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    setCheckoutLoading(action);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/billing/checkout`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ action, user_id: profile?.id || "temp_user_id" }),
      });

      const data = await response.json();
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      } else {
        console.error("No checkout url returned");
        setCheckoutLoading(null);
      }
    } catch (error) {
      console.error("Error creating checkout session:", error);
      setCheckoutLoading(null);
    }
  };

  if (isLoadingProfile) {
    return (
      <div className="flex items-center gap-2 text-zinc-500 text-sm font-medium animate-pulse">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading capacity...
      </div>
    );
  }

  if (!profile) return null;

  const isFreeTier = profile.subscription_tier === "free" || profile.subscription_tier === "standard_freight";
  const capacityMax = isFreeTier ? 100 : 500; // Using values from the landing page pricing

  return (
    <div className="flex items-center gap-4 bg-zinc-950 border border-zinc-800 rounded-full px-4 py-1.5 shadow-sm">
      <Badge variant="outline" className="bg-zinc-900 border-zinc-700 text-zinc-300 font-mono text-[11px] tracking-wide rounded-full px-2.5 py-0.5 flex items-center gap-1.5">
        <Package className="h-3 w-3 text-zinc-400" />
        Cargo capacity: {profile.credits} / {capacityMax}
      </Badge>

      <div className="flex items-center gap-2 border-l border-zinc-800 pl-4">
        {isFreeTier && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleCheckout("priority_air")}
            disabled={checkoutLoading !== null}
            className="h-7 text-[11px] uppercase tracking-wider font-semibold text-amber-500 hover:text-amber-400 hover:bg-amber-500/10 transition-colors bg-transparent"
          >
            {checkoutLoading === "priority_air" ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              "Upgrade to Priority Air ($25)"
            )}
          </Button>
        )}

        <Button
          variant="outline"
          size="sm"
          onClick={() => handleCheckout("buy_credits")}
          disabled={checkoutLoading !== null}
          className="h-7 text-[11px] uppercase tracking-wider font-medium text-zinc-300 border-zinc-700 hover:border-zinc-500 hover:bg-zinc-800 hover:text-white transition-all bg-zinc-900 rounded-full px-3"
        >
          {checkoutLoading === "buy_credits" ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <>
              <Zap className="h-3 w-3 mr-1.5 text-blue-400" />
              Top-Up 50 Credits ($10)
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
