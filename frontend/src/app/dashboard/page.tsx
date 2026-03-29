"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Rocket, Sparkles, AlertCircle, CheckCircle2, X, Loader2, MessageSquare, Plus, LogOut, Settings } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Textarea } from "../../components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../../components/ui/dialog";
import { useAuth } from "../../lib/useAuth";

// --- Interfaces ---
interface CampaignBrief {
  id?: number;
  original_prompt: string;
  target_audience: string;
  value_proposition: string;
  banned_terms: string[];
  buyer_titles: string[];
  exa_search_queries: string[];
  sender_name?: string;
  sender_company?: string;
}

interface Message {
  role: "user" | "ai";
  content: string;
}

interface LeadResult {
  id: number;
  company_name: string;
  website_url: string;
  status: string;
  contact_name: string | null;
  contact_email: string | null;
  subject: string | null;
  body: string | null;
  draft_notes: string | null;
  hook_type?: string | null;
  word_count?: number | null;
  rejection_reason?: string | null;
  web_founders_json?: string | null;
  web_emails_json?: string | null;
}

interface Conversation {
  id: number;
  title: string;
  updated_at: string;
}

export default function NewCampaignPage() {
  const { isAuthenticated } = useAuth();
  
  // --- State ---
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);

  const [mode, setMode] = useState<'express' | 'chat'>('chat');
  const [messages, setMessages] = useState<Message[]>([
    { role: "ai", content: "Hey! I'm your Campaign Planner. What kind of companies are we targeting today, and what's the value proposition?" }
  ]);
  const [input, setInput] = useState("");
  const [expressPrompt, setExpressPrompt] = useState("");
  const [brief, setBrief] = useState<CampaignBrief | null>(null);

  const [isDrafting, setIsDrafting] = useState(false);
  const [isLaunching, setIsLaunching] = useState(false);
  const [launchSuccess, setLaunchSuccess] = useState(false);
  const [activeBriefId, setActiveBriefId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<LeadResult[]>([]);

  // Editing Draft States
  const [editingDraftId, setEditingDraftId] = useState<number | null>(null);
  const [editSubject, setEditSubject] = useState("");
  const [editBody, setEditBody] = useState("");
  const [isSavingDraft, setIsSavingDraft] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // --- Effects ---
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    fetchConversations();
  }, []);

  useEffect(() => {
    let interval: NodeJS.Timeout;

    if (launchSuccess) {
      const fetchResults = async () => {
        try {
          const token = localStorage.getItem("token");
          const url = activeBriefId
            ? `/api/campaigns/results?brief_id=${activeBriefId}`
            : `/api/campaigns/results`;

          const res = await fetch(url, {
            headers: { ...(token ? { "Authorization": `Bearer ${token}` } : {}) }
          });
          if (res.ok) {
            const data = await res.json();
            if (data.status === "success" && data.results) {
              setResults(data.results);
            }
          }
        } catch (error) {
          console.error("Failed to fetch results", error);
        }
      };

      fetchResults();
      interval = setInterval(fetchResults, 3000);
    }
    return () => { if (interval) clearInterval(interval); };
  }, [launchSuccess, activeBriefId]);

  // --- API Handlers ---
  const fetchConversations = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("/api/campaigns/conversations", {
        headers: { ...(token ? { "Authorization": `Bearer ${token}` } : {}) }
      });
      if (res.ok) {
        const data = await res.json();
        if (data.status === "success") {
          setConversations(data.conversations);
        }
      }
    } catch (err) {
      console.error("Failed to load sidebar", err);
    }
  };

  const loadConversation = async (id: number) => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`/api/campaigns/conversations/${id}`, {
        headers: { ...(token ? { "Authorization": `Bearer ${token}` } : {}) }
      });
      if (res.ok) {
        const data = await res.json();
        if (data.status === "success") {
          setActiveConversationId(id);
          setMessages(data.messages || []);

          if (data.brief) {
            setBrief(data.brief);
            setActiveBriefId(data.brief.id);
            setLaunchSuccess(true);
          } else {
            setBrief(null);
            setLaunchSuccess(false);
          }
        }
      }
    } catch (err) {
      console.error("Failed to load chat", err);
    }
  };

  const startNewChat = () => {
    setActiveConversationId(null);
    setBrief(null);
    setLaunchSuccess(false);
    setActiveBriefId(null);
    setResults([]);
    setMessages([
      { role: "ai", content: "Hi! What kind of campaign would you like to build today?" }
    ]);
  };

  const handleExpressSubmit = async () => {
    if (!expressPrompt.trim()) return;

    const userPrompt = expressPrompt.trim();
    setExpressPrompt("");
    setIsDrafting(true);
    setError(null);

    try {
      const token = localStorage.getItem("token");

      const payload: { prompt: string; conversation_id?: number } = { prompt: userPrompt };
      if (activeConversationId) {
        payload.conversation_id = activeConversationId;
      }

      const res = await fetch("/api/campaigns/draft-brief", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { "Authorization": `Bearer ${token}` } : {})
        },
        body: JSON.stringify(payload)
      });

      if (!res.ok) throw new Error("Failed to draft brief.");

      const data = await res.json();
      if (data.status === "success" && data.draft_brief) {
        setBrief({ ...data.draft_brief, original_prompt: userPrompt });

        if (data.conversation_id && !activeConversationId) {
          setActiveConversationId(data.conversation_id);
          fetchConversations();
        }
      } else {
        throw new Error("Unexpected response format.");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setIsDrafting(false);
    }
  };

  const handleSendMessage = async () => {
    if (!input.trim()) return;

    const userPrompt = input.trim();
    const newMessages = [...messages, { role: "user" as const, content: userPrompt }];
    setMessages(newMessages);
    setInput("");
    setIsDrafting(true);
    setError(null);

    try {
      const token = localStorage.getItem("token");

      const payload: { messages: Message[]; conversation_id?: number } = { messages: newMessages };
      if (activeConversationId) {
        payload.conversation_id = activeConversationId;
      }

      const res = await fetch("/api/campaigns/planner/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { "Authorization": `Bearer ${token}` } : {})
        },
        body: JSON.stringify(payload)
      });

      if (!res.ok) throw new Error("Failed to get chat response.");

      const data = await res.json();
      if (data.status === "success" && data.response) {
        if (data.conversation_id && !activeConversationId) {
          setActiveConversationId(data.conversation_id);
          fetchConversations();
        }
        const text = data.response;
        
        // Auto-Launch Interceptor
        const jsonMatch = text.match(/```json\n([\s\S]*?)\n```/) || text.match(/```\n([\s\S]*?)\n```/);
        
        if (jsonMatch) {
          try {
            const parsed = JSON.parse(jsonMatch[1]);
            setBrief({
              original_prompt: "Generated via Co-Pilot Mode",
              target_audience: parsed.target_audience || "",
              value_proposition: parsed.value_proposition || "",
              sender_name: parsed.sender_name || "Team",
              sender_company: parsed.sender_company || "Company",
              banned_terms: parsed.banned_terms || [],
              buyer_titles: parsed.buyer_titles || [],
              exa_search_queries: parsed.exa_search_queries || []
            });
            setMessages(prev => [...prev, { role: "ai", content: "Great! I've loaded your Campaign Blueprint. You can review it and deploy when ready." }]);
          } catch (e) {
            setMessages(prev => [...prev, { role: "ai", content: text }]);
          }
        } else {
          setMessages(prev => [...prev, { role: "ai", content: text }]);
        }
      } else {
        throw new Error("Unexpected response format.");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setMessages(prev => [...prev, { role: "ai", content: "Sorry, I encountered an error. Please try again." }]);
    } finally {
      setIsDrafting(false);
    }
  };

  const handleLaunch = async () => {
    if (!brief) return;
    setIsLaunching(true);
    setError(null);

    try {
      const token = localStorage.getItem("token");
      const payload = { ...brief, conversation_id: activeConversationId };

      const res = await fetch("/api/campaigns/launch", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { "Authorization": `Bearer ${token}` } : {})
        },
        body: JSON.stringify(payload)
      });

      if (!res.ok) throw new Error("Failed to launch campaign.");

      const data = await res.json();
      if (data.status === "success" || res.ok) {
        setLaunchSuccess(true);
        if (data.brief_id) {
          setActiveBriefId(data.brief_id);
        }
      } else {
        throw new Error("Failed to launch campaign.");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to launch campaign.");
    } finally {
      setIsLaunching(false);
    }
  };

  const saveDraftEdits = async (leadId: number) => {
    setIsSavingDraft(true);
    setError(null);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`/api/campaigns/${leadId}/draft`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { "Authorization": `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ subject: editSubject, body: editBody })
      });

      if (res.ok) {
        setResults(prev => prev.map(lead =>
          lead.id === leadId
            ? { ...lead, subject: editSubject, body: editBody }
            : lead
        ));
        setEditingDraftId(null);
      } else {
        const data = await res.json();
        setError(data.message || "Failed to save draft.");
      }
    } catch (err) {
      console.error("Failed to save draft", err);
      setError("Failed to save draft.");
    } finally {
      setIsSavingDraft(false);
    }
  };

  const handleArrayChange = (field: keyof CampaignBrief, index: number, value: string) => {
    if (!brief) return;
    const newArray = [...(brief[field] as string[])];
    newArray[index] = value;
    setBrief({ ...brief, [field]: newArray });
  };
  const handleRemoveArrayItem = (field: keyof CampaignBrief, index: number) => {
    if (!brief) return;
    const newArray = [...(brief[field] as string[])];
    newArray.splice(index, 1);
    setBrief({ ...brief, [field]: newArray });
  };
  const handleAddArrayItem = (field: keyof CampaignBrief) => {
    if (!brief) return;
    setBrief({ ...brief, [field]: [...(brief[field] as string[]), ""] });
  };

  const activeLeads = results.filter(lead => lead.status.toLowerCase() !== 'completed' && lead.status.toLowerCase() !== 'fetch_failed' && lead.status.toLowerCase() !== 'rejected');
  const completedLeads = results
    .filter(lead => lead.status.toLowerCase() === 'completed' || lead.status.toLowerCase() === 'rejected')
    .sort((a, b) => {
      if (a.status.toLowerCase() === 'completed' && b.status.toLowerCase() !== 'completed') return -1;
      if (a.status.toLowerCase() !== 'completed' && b.status.toLowerCase() === 'completed') return 1;
      return 0;
    });

  if (!isAuthenticated) return null; // Or a loading spinner

  return (
    <div className="flex h-screen w-full bg-black text-white overflow-hidden text-sm font-sans selection:bg-[#333] selection:text-white">

      {/* 1. LEFT SIDEBAR (The Persistent Nav) */}
      <div className="w-64 flex flex-col border-r border-[#2F3336] bg-black flex-shrink-0">

        {/* Branding & New Chat */}
        <div className="p-4 space-y-4">
          <div className="flex items-center gap-2 px-2 py-1">
            <Sparkles className="w-5 h-5 text-white" />
            <span className="font-bold text-base tracking-wide text-white">Cargo.it</span>
          </div>

          <Button
            onClick={startNewChat}
            className="w-full bg-white hover:bg-[#E7E9EA] text-black font-semibold flex justify-center gap-2 rounded-full h-11"
          >
            <Plus className="w-4 h-4" />
            New Campaign
          </Button>
        </div>

        {/* Conversation History */}
        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1 custom-scrollbar">
          <div className="text-xs font-semibold text-white uppercase tracking-wider mb-2 px-2 mt-4">
            Recent Campaigns
          </div>
          {conversations.map(conv => (
            <button
              key={conv.id}
              onClick={() => loadConversation(conv.id)}
              className={`w-full text-left px-4 py-3 rounded-xl flex items-center gap-3 transition-colors ${activeConversationId === conv.id
                ? "bg-[#16181C] text-white"
                : "text-white hover:bg-[#16181C] hover:text-white"
                }`}
            >
              <MessageSquare className={`w-4 h-4 shrink-0 ${activeConversationId === conv.id ? 'text-white' : 'text-white'}`} />
              <span className="truncate text-sm font-medium">{conv.title}</span>
            </button>
          ))}
          {conversations.length === 0 && (
            <div className="px-3 py-4 text-xs text-white text-center">No history yet.</div>
          )}
        </div>

        {/* User Footer */}
        <div className="p-4 border-t border-[#2F3336] space-y-1">
          <button 
            onClick={() => window.location.href = "/dashboard/settings"}
            className="w-full text-left px-4 py-3 rounded-xl flex items-center gap-3 text-white hover:bg-[#16181C] hover:text-white transition-colors"
          >
            <Settings className="w-4 h-4 shrink-0" />
            <span className="truncate text-sm font-medium">Settings</span>
          </button>
          <button
            onClick={() => { localStorage.removeItem("token"); window.location.href = "/login"; }}
            className="w-full text-left px-4 py-3 rounded-xl flex items-center gap-3 text-white hover:bg-[#16181C] hover:text-white transition-colors"
          >
            <LogOut className="w-4 h-4 shrink-0" />
            <span className="truncate text-sm font-medium">Logout</span>
          </button>
        </div>
      </div>

      {/* 2. MIDDLE PANEL (The Input Box) */}
      <div className="flex-1 min-w-[350px] max-w-2xl flex flex-col border-r border-[#2F3336] bg-[#0E0F11]">
        <div className="p-4 border-b border-[#2F3336] bg-[#0E0F11]/95 backdrop-blur z-10 flex flex-col gap-4">
          <h2 className="font-semibold text-white">Freight Agent</h2>
          <div className="flex p-1 bg-[#16181C] rounded-xl border border-[#2F3336] max-w-[240px]">
            <button
              onClick={() => setMode('chat')}
              className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-colors ${mode === 'chat' ? 'bg-[#2F3336] text-white shadow' : 'text-gray-400 hover:text-white'}`}
            >
              Co-Pilot Mode
            </button>
            <button
              onClick={() => setMode('express')}
              className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-colors ${mode === 'express' ? 'bg-[#2F3336] text-white shadow' : 'text-gray-400 hover:text-white'}`}
            >
              Express Mode
            </button>
          </div>
        </div>

        {mode === 'chat' ? (
          <>
            <div className="flex-1 overflow-y-auto p-4 space-y-6">
              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[85%] p-3.5 leading-relaxed ${msg.role === "user"
                    ? "bg-[#202327] text-white rounded-2xl rounded-br-sm"
                    : "bg-transparent text-white border border-[#2F3336] rounded-2xl rounded-bl-sm whitespace-pre-wrap"
                    }`}>
                    {msg.content}
                  </div>
                </div>
              ))}
              {isDrafting && (
                <div className="flex justify-start">
                  <div className="max-w-[80%] p-3.5 rounded-2xl bg-transparent border border-[#2F3336] text-white animate-pulse rounded-bl-sm">
                    Thinking...
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="p-4 bg-[#0E0F11]">
              <div className="flex gap-2 relative">
                <Textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  placeholder="Ask anything..."
                  className="resize-none min-h-[60px] max-h-[120px] bg-[#202327] border-transparent text-white pr-12 focus-visible:ring-1 focus-visible:ring-[#71767B] rounded-2xl placeholder:text-white"
                />
                <Button
                  size="icon"
                  className="absolute right-2 bottom-2 h-9 w-9 bg-white hover:bg-[#E7E9EA] text-black rounded-xl transition-colors disabled:opacity-50"
                  onClick={handleSendMessage}
                  disabled={isDrafting || !input.trim()}
                >
                  <Send className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col p-6 overflow-hidden">
            <div className="flex-1 flex flex-col bg-[#16181C] border border-[#2F3336] rounded-2xl p-4 shadow-sm relative">
              <label className="text-sm font-semibold text-white mb-2 ml-1">Campaign Prompt</label>
              <Textarea
                value={expressPrompt}
                onChange={(e) => setExpressPrompt(e.target.value)}
                placeholder="Describe your target audience and value proposition..."
                className="flex-1 resize-none bg-transparent border-transparent text-white focus-visible:ring-0 text-base leading-relaxed placeholder:text-[#71767B]"
              />
              <div className="absolute bottom-4 right-4 flex items-center justify-end">
                <Button
                  onClick={handleExpressSubmit}
                  disabled={isDrafting || !expressPrompt.trim()}
                  className="bg-white hover:bg-[#E7E9EA] text-black font-semibold rounded-full px-6 h-10 flex gap-2 items-center"
                >
                  {isDrafting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Rocket className="w-4 h-4" />}
                  {isDrafting ? "Generating..." : "Generate Blueprint"}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 3. RIGHT PANEL (Blueprint or Mission Control) */}
      <div className="flex-1 flex flex-col bg-black overflow-hidden relative">
        {launchSuccess ? (
          <div className="flex flex-col h-full overflow-hidden">
            {/* Top Half: Live Agent Tracker */}
            <div className="flex-1 p-6 border-b border-[#2F3336] overflow-y-auto custom-scrollbar">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <Rocket className="w-5 h-5 text-white" />
                  Mission Control
                </h2>
                <Button
                  variant="outline"
                  size="sm"
                  className="bg-transparent border-[#2F3336] text-white hover:bg-[#16181C] rounded-full px-4"
                  onClick={() => { setLaunchSuccess(false); }}
                >
                  View JSON
                </Button>
              </div>

              {activeLeads.length === 0 ? (
                <div className="text-center py-8 text-white">
                  <p>System idle. No active agents.</p>
                </div>
              ) : (
                <div className="grid gap-4">
                  {activeLeads.map(lead => (
                    <div key={lead.id} className="bg-[#16181C] border border-[#2F3336] rounded-2xl p-4 flex items-center justify-between">
                      <div>
                        <div className="font-bold text-white mb-1">{lead.company_name}</div>
                        <a href={lead.website_url.startsWith('http') ? lead.website_url : `https://${lead.website_url}`} target="_blank" rel="noopener noreferrer" className="text-sm text-white hover:text-white transition-colors">
                          {lead.website_url}
                        </a>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-xs font-bold px-3 py-1.5 rounded-full bg-[#202327] text-white uppercase tracking-widest border border-[#2F3336]">
                          {lead.status}
                        </span>
                        <Loader2 className="w-5 h-5 text-white animate-spin" />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Bottom Half: Results Table */}
            <div className="flex-1 p-6 overflow-y-auto custom-scrollbar bg-black">
              <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-white" />
                Company List
              </h2>

              <div className="rounded-2xl border border-[#2F3336] overflow-hidden bg-[#16181C]">
                <Table>
                  <TableHeader>
                    <TableRow className="border-[#2F3336] hover:bg-transparent">
                      <TableHead className="text-white font-semibold py-4">Target</TableHead>
                      <TableHead className="text-white font-semibold py-4">Contacts</TableHead>
                      <TableHead className="text-white font-semibold py-4">State</TableHead>
                      <TableHead className="text-right text-white font-semibold py-4 px-5">Drafts</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {completedLeads.length === 0 && (
                      <TableRow className="border-[#2F3336] hover:bg-transparent">
                        <TableCell colSpan={4} className="text-center py-12 text-white">
                          Awaiting output...
                        </TableCell>
                      </TableRow>
                    )}
                    {completedLeads.map((lead) => (
                      <TableRow key={lead.id} className="border-[#2F3336] hover:bg-[#202327] transition-colors">
                        <TableCell className="font-medium align-top text-white py-4">
                          {lead.company_name}
                          <div className="text-xs text-white mt-1">
                            {lead.website_url}
                          </div>
                        </TableCell>
                        <TableCell className="align-top text-white py-4">
                          {(() => {
                            if (lead.status.toLowerCase() !== 'completed') {
                              return <span className="text-white text-xs italic">Resolving...</span>;
                            }
                            
                            let founders: unknown[] = [];
                            let emails: unknown[] = [];
                            try {
                              if (lead.web_founders_json) founders = JSON.parse(lead.web_founders_json);
                              if (lead.web_emails_json) emails = JSON.parse(lead.web_emails_json);
                            } catch (_) {}
                            
                            const uniqueFounders: string[] = [];
                            const seenFounders = new Set<string>();
                            for (const f of founders) {
                              if (!f) continue;
                              const display = typeof f === 'object' ? String((f as Record<string, unknown>).name || JSON.stringify(f)) : String(f);
                              const lower = display.toLowerCase().trim();
                              if (!seenFounders.has(lower)) {
                                seenFounders.add(lower);
                                uniqueFounders.push(display);
                              }
                            }
                            
                            const uniqueEmails: string[] = [];
                            const seenEmails = new Set<string>();
                            for (const e of emails) {
                              if (!e) continue;
                              const display = typeof e === 'object' ? String((e as Record<string, unknown>).email || (e as Record<string, unknown>).value || JSON.stringify(e)) : String(e);
                              const lower = display.toLowerCase().trim();
                              if (!seenEmails.has(lower)) {
                                seenEmails.add(lower);
                                uniqueEmails.push(display);
                              }
                            }
                            
                            const maxLen = Math.max(uniqueFounders.length, uniqueEmails.length);
                            if (maxLen === 0) {
                              return <span className="text-white text-xs italic">Not Found</span>;
                            }
                            
                            return (
                              <div className="space-y-3">
                                {Array.from({ length: maxLen }).map((_, i) => {
                                  const founderDisplay = uniqueFounders[i] || null;
                                  const emailDisplay = uniqueEmails[i] || null;
                                  
                                  return (
                                    <div key={i}>
                                      {founderDisplay && <div className="font-medium">{founderDisplay}</div>}
                                      {emailDisplay && <div className="text-xs text-gray-400 mt-1">{emailDisplay}</div>}
                                    </div>
                                  );
                                })}
                              </div>
                            );
                          })()}
                        </TableCell>
                        <TableCell className="align-top py-4">
                          <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-bold uppercase ${lead.status.toLowerCase() === 'rejected' ? 'bg-red-950/30 text-red-500 border border-red-900/50' : 'bg-white text-black'}`}>
                            {lead.status}
                          </span>
                        </TableCell>
                        <TableCell className="text-right align-top py-4">
                          {lead.status.toLowerCase() === 'rejected' ? (
                            <Dialog>
                              <DialogTrigger>
                                <div className="inline-flex h-9 items-center justify-center rounded-full border border-red-900/50 bg-red-950/30 px-4 text-sm font-medium text-red-500 shadow-sm hover:bg-red-900/50 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-red-500 disabled:pointer-events-none disabled:opacity-50">
                                  Reason
                                </div>
                              </DialogTrigger>
                              <DialogContent className="max-w-md bg-[#16181C] border-[#2F3336] text-white rounded-3xl p-6">
                                <DialogHeader>
                                  <DialogTitle className="text-xl font-bold text-red-500 mb-2">Rejection Reason</DialogTitle>
                                </DialogHeader>
                                <div className="text-sm font-mono text-red-400/80 bg-[#202327] border border-[#2F3336] px-4 py-3 rounded-xl">
                                  {lead.rejection_reason || "Validation Failed"}
                                </div>
                              </DialogContent>
                            </Dialog>
                          ) : lead.body && lead.contact_email ? (
                            <Dialog>
                              <DialogTrigger>
                                <div className="inline-flex h-9 items-center justify-center rounded-full border border-[#2F3336] bg-transparent px-4 text-sm font-medium text-white shadow-sm hover:bg-[#2F3336] transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50">Read Data</div>
                              </DialogTrigger>
                              <DialogContent className="max-w-5xl sm:max-w-6xl max-h-[80vh] overflow-y-auto bg-[#16181C] border-[#2F3336] text-white rounded-3xl p-8">
                                <DialogHeader>
                                  <DialogTitle className="text-2xl font-bold text-white mb-4">Draft Output</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-6 pt-2">
                                  {lead.draft_notes && (
                                    <div className="bg-[#202327] border border-[#2F3336] rounded-2xl p-4 mb-2">
                                      <div className="text-xs font-bold text-white uppercase tracking-wider mb-2">Agent Reasoning</div>
                                      <div className="text-sm leading-relaxed text-white">{lead.draft_notes}</div>
                                      <div className="flex items-center gap-3 mt-3">
                                        {lead.hook_type && (
                                          <span className="bg-black border border-[#2F3336] text-indigo-400 text-xs font-bold px-3 py-1.5 rounded-full tracking-wider uppercase flex items-center gap-1.5">
                                            🎯 Hook: {lead.hook_type}
                                          </span>
                                        )}
                                        {lead.word_count && (
                                          <span className="bg-black border border-[#2F3336] text-white text-xs font-bold px-3 py-1.5 rounded-full tracking-wider uppercase flex items-center gap-1.5">
                                            📝 Words: {lead.word_count}
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  )}

                                  <div className="grid grid-cols-[80px_1fr] gap-2 items-baseline">
                                    <div className="text-sm font-bold text-white uppercase tracking-wider">To</div>
                                    <div className="text-base text-white">{lead.contact_name} &lt;{lead.contact_email}&gt;</div>
                                  </div>

                                  {editingDraftId === lead.id ? (
                                    <>
                                      <div className="grid grid-cols-[80px_1fr] gap-2 items-center">
                                        <div className="text-sm font-bold text-white uppercase tracking-wider">Subj</div>
                                        <input
                                          value={editSubject}
                                          onChange={(e) => setEditSubject(e.target.value)}
                                          className="bg-black border border-[#2F3336] rounded-xl px-4 py-2.5 text-white focus:outline-none focus:ring-1 focus:ring-white w-full transition-all"
                                          placeholder="Enter subject..."
                                        />
                                      </div>
                                      <div className="pt-2">
                                        <div className="text-sm font-bold text-white uppercase tracking-wider mb-3">Body</div>
                                        <Textarea
                                          value={editBody}
                                          onChange={(e) => setEditBody(e.target.value)}
                                          className="min-h-[350px] bg-black border border-[#2F3336] rounded-2xl p-6 font-mono text-white leading-relaxed focus-visible:ring-1 focus-visible:ring-white transition-all"
                                        />
                                      </div>
                                      <div className="flex justify-end gap-3 mt-8">
                                        <Button
                                          variant="outline"
                                          className="rounded-full border-[#2F3336] text-white hover:bg-[#202327] px-6 h-11"
                                          onClick={() => setEditingDraftId(null)}
                                        >
                                          Cancel
                                        </Button>
                                        <Button
                                          className="bg-white hover:bg-[#E7E9EA] text-black font-bold rounded-full px-8 h-11"
                                          disabled={isSavingDraft}
                                          onClick={() => saveDraftEdits(lead.id)}
                                        >
                                          {isSavingDraft ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                                          {isSavingDraft ? "Saving..." : "Save Changes"}
                                        </Button>
                                      </div>
                                    </>
                                  ) : (
                                    <>
                                      <div className="grid grid-cols-[80px_1fr] gap-2 items-baseline">
                                        <div className="text-sm font-bold text-white uppercase tracking-wider">Subj</div>
                                        <div className="text-base text-white">{lead.subject}</div>
                                      </div>
                                      <div className="pt-4">
                                        <div className="whitespace-pre-wrap text-base border border-[#2F3336] p-6 rounded-2xl bg-black font-mono text-white leading-relaxed">
                                          {lead.body}
                                        </div>
                                      </div>
                                      <div className="flex justify-end gap-3 mt-8">
                                        <Button
                                          variant="outline"
                                          className="rounded-full border-[#2F3336] text-white hover:bg-[#202327] px-6 h-12 font-bold"
                                          onClick={() => {
                                            setEditingDraftId(lead.id);
                                            setEditSubject(lead.subject || "");
                                            setEditBody(lead.body || "");
                                          }}
                                        >
                                          Edit Draft
                                        </Button>
                                        <Button
                                          className="bg-white hover:bg-[#E7E9EA] text-black font-bold rounded-full px-8 h-12 text-base"
                                          onClick={() => { window.location.href = `mailto:${lead.contact_email}?subject=${encodeURIComponent(lead.subject || "")}&body=${encodeURIComponent(lead.body || "")}`; }}
                                        >
                                          Execute MailClient
                                        </Button>
                                      </div>
                                    </>
                                  )}
                                </div>
                              </DialogContent>
                            </Dialog>
                          ) : (
                            <Button variant="ghost" size="sm" disabled className="text-white">Standby</Button>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          </div>
        ) : !brief ? (
          <div className="flex flex-col items-center justify-center flex-1 p-8 text-center text-white">
            <Sparkles className="w-16 h-16 mb-6 text-[#2F3336]" />
            <h3 className="text-xl font-bold text-white mb-2">Awaiting Parameters</h3>
            <p className="max-w-md text-base leading-relaxed">Initialize a request in the terminal to generate targeting vectors.</p>
          </div>
        ) : (
          <>
            <div className="p-5 border-b border-[#2F3336] flex items-center justify-between bg-black sticky top-0 z-10">
              <h2 className="text-xl font-bold text-white flex items-center gap-3">
                System Blueprint
              </h2>
              <Button
                onClick={handleLaunch}
                disabled={isLaunching}
                className="bg-white hover:bg-[#E7E9EA] text-black font-bold rounded-full px-6 h-10 flex items-center gap-2"
              >
                {isLaunching ? (
                  <span className="animate-pulse">Initializing...</span>
                ) : (
                  <>
                    <Rocket className="w-4 h-4" />
                    Deploy Engine
                  </>
                )}
              </Button>
            </div>

            <div className="flex-1 overflow-y-auto p-8 space-y-8 custom-scrollbar">
              {error && (
                <div className="p-4 bg-transparent border border-red-900 rounded-2xl text-red-500 flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 shrink-0" />
                  <p className="font-medium">{error}</p>
                </div>
              )}

              <div className="space-y-8 max-w-3xl">
                <div>
                  <label className="block text-sm font-bold text-white mb-3 uppercase tracking-widest">Target Vector</label>
                  <Textarea
                    value={brief.target_audience}
                    onChange={(e) => setBrief({ ...brief, target_audience: e.target.value })}
                    className="min-h-[80px] bg-[#16181C] border-[#2F3336] text-white rounded-2xl focus-visible:ring-1 focus-visible:ring-[#71767B] text-base p-4"
                  />
                </div>

                <div>
                  <label className="block text-sm font-bold text-white mb-3 uppercase tracking-widest">Value Prop</label>
                  <Textarea
                    value={brief.value_proposition}
                    onChange={(e) => setBrief({ ...brief, value_proposition: e.target.value })}
                    className="min-h-[120px] bg-[#16181C] border-[#2F3336] text-white rounded-2xl focus-visible:ring-1 focus-visible:ring-[#71767B] text-base p-4 leading-relaxed"
                  />
                </div>

                {[
                  { key: 'buyer_titles', label: 'Nodes (Roles)' },
                  { key: 'banned_terms', label: 'Blacklist' },
                  { key: 'exa_search_queries', label: 'Search Ops' }
                ].map(({ key, label }) => {
                  const items = (brief[key as keyof CampaignBrief] as string[]) || [];
                  return (
                    <div key={key}>
                      <label className="block text-sm font-bold text-white mb-3 uppercase tracking-widest">{label}</label>
                      <div className="flex flex-wrap gap-3">
                        {items.map((item, idx) => (
                          <div key={idx} className="flex items-center gap-2 bg-[#202327] border border-[#2F3336] rounded-full pl-4 pr-1.5 py-1.5 focus-within:ring-1 focus-within:ring-white transition-all">
                            <input
                              value={item}
                              onChange={(e) => handleArrayChange(key as keyof CampaignBrief, idx, e.target.value)}
                              className="bg-transparent border-none text-sm font-medium focus:outline-none text-white w-auto min-w-[60px]"
                              size={Math.max(item.length, 6)}
                            />
                            <button
                              onClick={() => handleRemoveArrayItem(key as keyof CampaignBrief, idx)}
                              className="text-white hover:text-white p-1.5 rounded-full hover:bg-[#2F3336] transition-colors"
                            >
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ))}
                        <button
                          onClick={() => handleAddArrayItem(key as keyof CampaignBrief)}
                          className="text-sm font-bold text-white hover:text-white px-5 py-2 border border-dashed border-[#2F3336] rounded-full hover:bg-[#16181C] transition-colors"
                        >
                          + Add Param
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}