"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/useAuth";
import { Input } from "@/components/ui/input";
import Link from "next/link";
import { useRouter } from "next/navigation";

export default function SettingsPage() {
  const { isAuthenticated } = useAuth();
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const queryClient = useQueryClient();

  useEffect(() => {
    const storedToken = localStorage.getItem("token");
    if (storedToken) {
      setTimeout(() => setToken(storedToken), 0);
    } else {
      router.push("/");
    }
  }, [router]);

  const { data: profile, isLoading } = useQuery({
    queryKey: ["userProfile", token],
    queryFn: async () => {
      if (!token) throw new Error("Not authenticated");
      const res = await fetch("/api/auth/me", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.status === 401) {
        localStorage.removeItem("token");
        router.push("/");
        throw new Error("Unauthorized");
      }
      if (!res.ok) throw new Error("Failed to fetch profile");
      return res.json();
    },
    enabled: !!token,
  });

  useEffect(() => {
    if (profile) {
      setTimeout(() => {
        setFirstName(profile.first_name || "");
        setLastName(profile.last_name || "");
        setEmail(profile.email || "");
      }, 0);
    }
  }, [profile]);

  const updateProfileMutation = useMutation({
    mutationFn: async () => {
      if (!token) throw new Error("Not authenticated");
      
      const payload: Record<string, string> = {
        first_name: firstName,
        last_name: lastName,
        email: email,
      };

      if (newPassword) {
        if (!currentPassword) {
          throw new Error("Current password is required to set a new password");
        }
        payload.current_password = currentPassword;
        payload.new_password = newPassword;
      }

      const res = await fetch("/api/auth/me", {
        method: "PUT",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      });
      
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to update profile");
      }
      
      return res.json();
    },
    onSuccess: () => {
      setMessage("Profile updated successfully!");
      setError("");
      setCurrentPassword("");
      setNewPassword("");
      queryClient.invalidateQueries({ queryKey: ["userProfile"] });
      setTimeout(() => setMessage(""), 3000);
    },
    onError: (err: Error) => {
      setError(err.message);
      setMessage("");
    }
  });

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    updateProfileMutation.mutate();
  };

  if (!isAuthenticated) return null;

  if (!token || isLoading) {
    return <div className="p-10 flex justify-center items-center min-h-screen bg-black text-white">Loading...</div>;
  }

  return (
    <div className="min-h-screen bg-black text-white font-sans selection:bg-[#333] selection:text-white py-10">
      <div className="container mx-auto space-y-8 max-w-3xl px-4 md:px-0">
        
        {/* Header */}
        <div className="flex justify-between items-center pb-6 border-b border-[#2F3336]">
          <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
            Settings
          </h1>
          <Link href="/">
            <Button variant="outline" className="bg-transparent border-[#2F3336] text-white hover:bg-[#16181C] hover:text-white rounded-full px-6 h-11 font-semibold">
              Back to Dashboard
            </Button>
          </Link>
        </div>

        {/* Form Container */}
        <div className="bg-[#16181C] border border-[#2F3336] rounded-2xl p-8">
          <h2 className="text-xl font-bold text-white mb-8">User Profile</h2>
          
          <form onSubmit={handleUpdate} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-bold text-white mb-2 uppercase tracking-widest">First Name</label>
                <Input 
                  value={firstName} 
                  onChange={(e) => setFirstName(e.target.value)} 
                  placeholder="First Name" 
                  className="bg-[#202327] border-[#2F3336] text-white focus-visible:ring-1 focus-visible:ring-[#71767B] rounded-xl h-12 px-4 placeholder:text-[#4B5563]"
                />
              </div>
              <div>
                <label className="block text-sm font-bold text-white mb-2 uppercase tracking-widest">Last Name</label>
                <Input 
                  value={lastName} 
                  onChange={(e) => setLastName(e.target.value)} 
                  placeholder="Last Name" 
                  className="bg-[#202327] border-[#2F3336] text-white focus-visible:ring-1 focus-visible:ring-[#71767B] rounded-xl h-12 px-4 placeholder:text-[#4B5563]"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-bold text-white mb-2 uppercase tracking-widest">Email Address</label>
              <Input 
                type="email" 
                value={email} 
                onChange={(e) => setEmail(e.target.value)} 
                placeholder="Email" 
                required
                className="bg-[#202327] border-[#2F3336] text-white focus-visible:ring-1 focus-visible:ring-[#71767B] rounded-xl h-12 px-4 placeholder:text-[#4B5563]"
              />
            </div>

            <div className="pt-8 border-t border-[#2F3336] mt-8">
              <h3 className="text-xl font-bold text-white mb-2">Security</h3>
              <p className="text-sm text-white mb-6">Leave blank if you do not want to change your password.</p>
              
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-bold text-white mb-2 uppercase tracking-widest">Current Password</label>
                  <Input 
                    type="password" 
                    value={currentPassword} 
                    onChange={(e) => setCurrentPassword(e.target.value)} 
                    placeholder="Enter current password" 
                    className="bg-[#202327] border-[#2F3336] text-white focus-visible:ring-1 focus-visible:ring-[#71767B] rounded-xl h-12 px-4 placeholder:text-[#4B5563]"
                  />
                </div>
                <div>
                  <label className="block text-sm font-bold text-white mb-2 uppercase tracking-widest">New Password</label>
                  <Input 
                    type="password" 
                    value={newPassword} 
                    onChange={(e) => setNewPassword(e.target.value)} 
                    placeholder="Enter new password" 
                    className="bg-[#202327] border-[#2F3336] text-white focus-visible:ring-1 focus-visible:ring-[#71767B] rounded-xl h-12 px-4 placeholder:text-[#4B5563]"
                  />
                </div>
              </div>
            </div>

            {error && (
              <div className="p-4 mt-6 bg-red-950/20 border border-red-900/50 rounded-xl text-red-500 font-medium">
                {error}
              </div>
            )}
            {message && (
              <div className="p-4 mt-6 bg-green-950/20 border border-green-900/50 rounded-xl text-green-500 font-medium">
                {message}
              </div>
            )}

            <div className="pt-6 flex justify-end">
              <Button 
                type="submit" 
                disabled={updateProfileMutation.isPending}
                className="w-full sm:w-auto bg-white hover:bg-[#E7E9EA] text-black font-bold rounded-full px-8 h-12 text-base transition-colors"
              >
                {updateProfileMutation.isPending ? "Saving..." : "Save Changes"}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
