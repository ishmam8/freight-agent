"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

interface LeadResult {
  id: number;
  company_name: string;
  website_url: string;
  status: string;
  contact_name: string | null;
  contact_email: string | null;
  subject: string | null;
  body: string | null;
}

export default function MVPCommandCenter() {
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [prompt, setPrompt] = useState("");
  const queryClient = useQueryClient();

  // On mount, check if token is in local storage
  useEffect(() => {
    const storedToken = localStorage.getItem("token");
    if (storedToken) {
      setTimeout(() => setToken(storedToken), 0);
    }
  }, []);

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
      setToken(access_token);
      setLoginError("");
    },
    onError: (err) => {
      setLoginError(err.message);
    }
  });

  const startCampaign = useMutation({
    mutationFn: async (text: string) => {
      if (!token) throw new Error("Not authenticated");
      const res = await fetch("/api/campaigns/start", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ prompt: text }),
      });
      if (!res.ok) throw new Error("Failed to start campaign");
      return res.json();
    },
    onSuccess: () => {
      setPrompt("");
      queryClient.invalidateQueries({ queryKey: ["campaignResults"] });
    }
  });

  const { data, isLoading } = useQuery<{ status: string; results: LeadResult[] }>({
    queryKey: ["campaignResults", token],
    queryFn: async () => {
      if (!token) return { status: "error", results: [] };
      const res = await fetch("/api/campaigns/results", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.status === 401) {
        // Token expired
        localStorage.removeItem("token");
        setToken(null);
        throw new Error("Unauthorized");
      }
      if (!res.ok) throw new Error("Failed to fetch results");
      return res.json();
    },
    enabled: !!token,
    refetchInterval: 5000,
  });

  // Login View
  if (!token) {
    return (
      <div className="flex h-screen w-full items-center justify-center p-4">
        <div className="w-full max-w-sm space-y-6">
          <div className="space-y-2 text-center">
            <h1 className="text-3xl font-bold">Sign In</h1>
            <p className="text-muted-foreground">Enter your credentials to access the MVP Dashboard.</p>
          </div>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium leading-none">Email</label>
              <Input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="admin@example.com" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium leading-none">Password</label>
              <Input type="password" value={password} onChange={e => setPassword(e.target.value)} />
            </div>
            {loginError && <div className="text-sm text-destructive">{loginError}</div>}
            <Button 
              className="w-full" 
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

  const results = data?.results || [];

  return (
    <div className="container mx-auto py-10 space-y-8 max-w-6xl px-4 md:px-0">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Command Center</h1>
          <p className="text-muted-foreground mt-2">
            Submit a natural language prompt defining your target audience.
          </p>
        </div>
        <Button variant="ghost" onClick={() => {
          localStorage.removeItem("token");
          setToken(null);
        }}>
          Sign Out
        </Button>
      </div>

      <div className="mt-4 flex flex-col md:flex-row gap-4">
        <Textarea 
          placeholder="e.g. Find me Canadian denim brands"
          className="flex-1"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
        <Button 
          className="md:self-end" 
          onClick={() => startCampaign.mutate(prompt)}
          disabled={!prompt.trim() || startCampaign.isPending}
        >
          {startCampaign.isPending ? "Starting..." : "Start Pipeline"}
        </Button>
      </div>

      <div>
        <h2 className="text-2xl font-bold tracking-tight">Outbox Dashboard</h2>
        <p className="text-muted-foreground mt-2 mb-4">
          Monitor your background pipelines and send generated emails.
        </p>
        
        <div className="rounded-md border overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Company</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Contact</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {results.length === 0 && !isLoading && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center h-24 text-muted-foreground">
                    No leads found yet. Start a campaign!
                  </TableCell>
                </TableRow>
              )}
              {results.length === 0 && isLoading && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center h-24 text-muted-foreground">
                    Loading...
                  </TableCell>
                </TableRow>
              )}
              {results.map((lead) => (
                <TableRow key={lead.id}>
                  <TableCell className="font-medium align-top">
                    {lead.company_name}
                    <div className="text-xs text-muted-foreground">
                      <a href={lead.website_url.startsWith('http') ? lead.website_url : `https://${lead.website_url}`} target="_blank" rel="noopener noreferrer" className="hover:underline">
                        {lead.website_url}
                      </a>
                    </div>
                  </TableCell>
                  <TableCell className="align-top">
                    <span className="inline-flex items-center rounded-md bg-secondary px-2 py-1 text-xs font-medium ring-1 ring-inset ring-secondary-foreground/10">
                      {lead.status.toUpperCase()}
                    </span>
                  </TableCell>
                  <TableCell className="align-top">
                    {lead.contact_name ? (
                      <>
                        {lead.contact_name}
                        <div className="text-xs text-muted-foreground">
                          {lead.contact_email}
                        </div>
                      </>
                    ) : (
                      <span className="text-muted-foreground text-xs">{lead.status === 'queued' ? 'Waiting...' : 'Finding contact...'}</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right align-top">
                    {lead.body && lead.contact_email ? (
                      <Dialog>
                        <DialogTrigger render={<Button variant="outline" size="sm">View Draft</Button>} />
                        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
                          <DialogHeader>
                            <DialogTitle>Email Draft - {lead.company_name}</DialogTitle>
                          </DialogHeader>
                          <div className="space-y-4 pt-4">
                            <div>
                              <div className="text-sm font-semibold mb-1">To:</div>
                              <div className="text-sm text-muted-foreground">{lead.contact_name} &lt;{lead.contact_email}&gt;</div>
                            </div>
                            <div>
                              <div className="text-sm font-semibold mb-1">Subject:</div>
                              <div className="text-sm text-muted-foreground">{lead.subject}</div>
                            </div>
                            <div>
                              <div className="text-sm font-semibold mb-1">Body:</div>
                              <div className="whitespace-pre-wrap text-sm border p-4 rounded-md bg-secondary/20 font-mono">
                                {lead.body}
                              </div>
                            </div>
                            <div className="flex justify-end mt-4">
                              <Button nativeButton={false} render={<a href={`mailto:${lead.contact_email}?subject=${encodeURIComponent(lead.subject || "")}&body=${encodeURIComponent(lead.body || "")}`}>Send via Email Client</a>} />
                            </div>
                          </div>
                        </DialogContent>
                      </Dialog>
                    ) : (
                      <Button variant="ghost" size="sm" disabled>
                        Wait
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
}
