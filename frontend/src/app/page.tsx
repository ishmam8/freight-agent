"use client";

import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "../components/ui/card"
import { Badge } from "../components/ui/badge"
import { Separator } from "../components/ui/separator"
import { ArrowRight, Radar, ShieldCheck, Languages, Terminal, Check, Database, Compass, ClipboardCheck, PlaneTakeoff, Activity, Send, CheckCircle, Rocket, Loader2 } from "lucide-react"
import Link from "next/link"
import { useState } from "react"
import { useRouter } from "next/navigation"

export default function CargoLanding() {
  const [loadingTier, setLoadingTier] = useState<string | null>(null)
  const router = useRouter()

  const handleRouting = async (tier: 'free' | 'paid') => {
    setLoadingTier(tier)
    const token = localStorage.getItem("access_token")

    if (!token) {
      if (tier === 'free') {
        router.push('/login?intent=dashboard')
      } else {
        router.push('/login?intent=priority_air')
      }
      return
    }

    if (tier === 'free') {
      router.push('/dashboard')
    } else {
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/billing/checkout`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ action: 'priority_air', user_id: 'temp_user_id' })
        })

        const data = await response.json()
        if (data.checkout_url) {
          window.location.href = data.checkout_url
        } else {
          setLoadingTier(null)
          console.error("No checkout url returned")
        }
      } catch (error) {
        console.error("Error creating checkout session:", error)
        setLoadingTier(null)
      }
    }
  }

  const scrollToSection = (e: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    e.preventDefault();
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground schematic-bg font-sans tracking-tight">
      {/* Navigation */}
      <nav className="fixed top-0 w-full z-50 border-b border-white/10 bg-black/40 backdrop-blur-xl h-20 px-6 md:px-12 flex justify-between items-center">
        <div className="flex items-center gap-3 cursor-pointer" onClick={(e) => { e.preventDefault(); window.scrollTo({ top: 0, behavior: 'smooth' }); }}>
          <img src="/logo.jpg" alt="Logo" className="w-10 h-10 rounded-xl object-cover border border-white/10 shadow-lg" />
          <div className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-b from-zinc-100 to-zinc-400 tracking-tighter">cargoit.ai</div>
        </div>
        <div className="hidden md:flex items-center gap-10 text-sm font-medium text-muted-foreground">
          <a href="#pipeline" onClick={(e) => scrollToSection(e, "pipeline")} className="hover:text-primary transition-colors">Solutions</a>
          <a href="#pricing" onClick={(e) => scrollToSection(e, "pricing")} className="hover:text-primary transition-colors">Pricing</a>
          <a href="#contact" onClick={(e) => scrollToSection(e, "contact")} className="hover:text-primary transition-colors">Contact</a>
        </div>
        <Link href="/login">
          <Button variant="outline" className="border-primary text-primary hover:bg-primary hover:text-primary">
            Sign In
          </Button>
        </Link>
      </nav>

      <main className="pt-20">
        {/* Hero Section */}
        <section className="relative py-24 px-6 md:px-12 max-w-7xl mx-auto grid lg:grid-cols-2 gap-16 items-center">
          <div className="space-y-8">
            <h1 className="text-6xl md:text-8xl font-bold leading-tight tracking-tighter text-zinc-300 bg-clip-text bg-gradient-to-b from-zinc-200 to-zinc-800 pb-2">
              Export Your Vision. <br />
            </h1>
            <p className="text-lg md:text-xl text-muted-foreground font-medium tracking-tight max-w-xl leading-relaxed">
              The AI Sales Agent for cross-border B2B sales. <br /> Automate discovery, enrichment, and hyper-localized outreach at scale.
              We navigate cultural differences and deliver your pitch directly to your buyers.
            </p>
            <div className="flex flex-wrap gap-4">
              <Link href="/login">
                <Button size="lg" className="bg-primary text-primary-foreground font-bold group">
                  Start Outreaching (Free Trial)
                  <ArrowRight className="ml-2 h-4 w-4 group-hover:translate-x-1 transition-transform" />
                </Button>
              </Link>
            </div>
          </div>

          {/* Visual Card Stack */}
          <div className="relative">
            <Card className="glass-card border-primary/20 bg-secondary/20 backdrop-blur-md">
              <CardContent className="p-8 space-y-6">
                <div className="flex items-center gap-4 p-4 bg-background/60 rounded-lg border border-border">
                  <div className="p-2 bg-muted rounded-full"><Terminal className="h-5 w-5 text-muted-foreground" /></div>
                  <div>
                    <p className="text-[13px] uppercase tracking-widest text-muted-foreground">Scout</p>
                    <p className="text-sm font-small">Discover high-intent accounts globally, Our AI scans millions of data poitns to identify your ideal customer profile across borders. </p>
                  </div>
                </div>
                <div className="flex justify-center"><ArrowRight className="rotate-90 text-primary opacity-60" /></div>
                <div className="flex items-center gap-4 p-4 bg-primary/09 rounded-lg border border-primary/40">
                  <div className="p-2 bg-muted rounded-full"><Database className="h-5 w-5 text-muted-foreground" /></div>
                  <div>
                    <p className="text-[13px] uppercase tracking-widest text-muted-foreground">Enrich</p>
                    <p className="text-sm font-small">Establish deep data connections to locate key decision-makers validating authority layers before any engagement</p>
                  </div>
                </div>
                <div className="flex justify-center"><ArrowRight className="rotate-90 text-primary opacity-90" /></div>
                <div className="flex items-center gap-4 p-4 bg-primary/10 rounded-lg border border-primary/30">
                  <div className="p-2 bg-primary/20 rounded-full"><Languages className="h-5 w-5 text-primary" /></div>
                  <div>
                    <p className="text-[13px] uppercase tracking-widest text-primary">Localize</p>
                    <p className="text-sm font-small">Craft hyper-personalized outreach in your desired persona and language. Culturally nuanced messaging that resonates with local decision-makers.</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </section>

        {/* Pipeline Section */}
        <section id="pipeline" className="py-24 bg-card/50 px-6">
          <div className="max-w-4xl mx-auto text-center mb-20 space-y-4">
            <h2 className="text-4xl md:text-5xl font-bold tracking-tighter text-zinc-300 bg-clip-text bg-gradient-to-b from-zinc-200 to-zinc-800 pb-2">Your intelligent SDR that handles <br />the grunt work exceptionally.</h2>
            <p className="text-muted-foreground font-medium tracking-tight">From market discovery to boardroom entry.</p>
          </div>

          <div className="max-w-2xl mx-auto relative space-y-16">
            <div className="absolute left-1/2 -translate-x-1/2 h-full w-[1px] bg-border" />

            {[
              {
                title: "Route Planning",
                desc: "Chat with our AI Co-Pilot to configure your waybill, target audience, and core value proposition.",
                icon: Compass
              },
              {
                title: "Precision Radar",
                desc: "Advanced neural search scans the global market, bypassing dead links to hunt down high-intent companies.",
                icon: Radar
              },
              {
                title: "Customs Clearance",
                desc: "Local AI strictly inspects each website, vetting for quality and quarantining bad fits or competitors.",
                icon: ClipboardCheck
              },
              {
                title: "Manifest Verification",
                desc: "Deep data enrichment pinpoints the exact Consignee (Founder/CEO) and secures their verified email.",
                icon: ShieldCheck
              },
              {
                title: "Cultural Packaging",
                desc: "Your raw pitch is translated into flawless, culturally native English tailored for decision-makers.",
                icon: Languages
              },
              {
                title: "Final Dispatch",
                desc: "Your localized, highly personalized campaign is cleared for takeoff and delivered directly to their inbox.",
                icon: PlaneTakeoff
              },
              {
                title: "The Control Tower",
                desc: "Monitor your global fleet, track delivery telemetry, and manage your pipeline from a high-end command center.",
                icon: Activity
              }
            ].map((step, idx) => (
              <div key={idx} className={`flex items-center gap-8 ${idx % 2 === 0 ? 'md:flex-row' : 'md:flex-row-reverse'} relative z-10`}>
                <div className="flex-1 text-center md:text-right">
                  <h3 className="text-2xl font-bold tracking-tight text-zinc-200 bg-clip-text bg-gradient-to-b from-zinc-200 to-zinc-800 mb-2 pb-1">{step.title}</h3>
                  <p className="text-muted-foreground font-medium text-sm">{step.desc}</p>
                </div>
                <div className="w-12 h-12 bg-background border-2 border-primary rounded-full flex items-center justify-center">
                  <step.icon className="h-6 w-6 text-primary" />
                </div>
                <div className="flex-1 hidden md:block" />
              </div>
            ))}
          </div>
        </section>

        {/* Terminal Section */}
        {/* The Cargo Manifest (Live Product Demo) */}
        <section className="py-24 px-6 md:px-12 max-w-[1300px] mx-auto">
          <div className="mb-12">
            <Badge variant="outline" className="mb-4 bg-primary border-zinc-700 text-zinc-900 px-3 py-1 uppercase tracking-widest text-[10px] font-bold">
              Dashboard
            </Badge>
            <h2 className="text-4xl md:text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-b from-zinc-200 to-zinc-800 mb-4 tracking-tighter pb-2">
              The Cargo <span className="text-zinc-500">Manifest.</span>
            </h2>
            <p className="text-zinc-400 font-medium tracking-tight max-w-2xl text-lg">
              Watch the Freight Agent navigate your request and populate your command center in real-time.
            </p>
          </div>

          <Card className="bg-[#09090b] border-zinc-800 overflow-hidden shadow-2xl rounded-xl ring-2 ring-white/10">
            {/* macOS Style Header */}
            <CardHeader className="bg-[#09090b] border-b border-zinc-800/50 py-3 px-4 flex flex-row items-center justify-between">
              <div className="flex gap-2">
                <div className="w-2.5 h-2.5 rounded-full bg-red-600" />
                <div className="w-2.5 h-2.5 rounded-full bg-orange-400" />
                <div className="w-2.5 h-2.5 rounded-full bg-green-500" />
              </div>
              <span className="text-[11px] font-mono uppercase tracking-widest text-zinc-200">cargoitAI dashboard</span>
              <div className="w-10"></div> {/* Spacer for centering */}
            </CardHeader>

            <CardContent className="p-0 grid lg:grid-cols-12 h-auto lg:h-[650px] divide-y lg:divide-y-0 lg:divide-x divide-zinc-800/50 text-sm">

              {/* LEFT PANEL: Freight Agent (Chat) */}
              <div className="lg:col-span-4 bg-[#09090b] flex flex-col h-[500px] lg:h-full relative">
                <div className="p-4 border-b border-zinc-800/50 flex items-center justify-between">
                  <span className="font-semibold text-zinc-100">Freight Agent</span>
                  <div className="flex bg-zinc-900 rounded-md p-1 border border-zinc-800">
                    <span className="px-3 py-1 text-xs bg-zinc-700 text-zinc-100 rounded shadow-sm">Co-Pilot Mode</span>
                    <span className="px-3 py-1 text-xs text-zinc-500 transition-colors">Express Mode</span>
                  </div>
                </div>

                <div className="p-4 flex-1 space-y-4 overflow-y-auto">
                  <div className="bg-zinc-800/40 border border-zinc-700/50 rounded-lg p-3.5 text-zinc-300 leading-relaxed text-[13px]">
                    Hi, Im Sarah from EcoPack Solutions. We manufacture biodegradable, custom-branded coffee bags that keep beans fresh for 6 months... I want to target boutique, independent coffee roasters based in Seattle and Portland. Please exclude large corporate chains.
                  </div>
                  <div className="bg-transparent border border-zinc-800/80 rounded-lg p-3.5 text-zinc-400 leading-relaxed text-[13px]">
                    Ive drafted a Campaign Blueprint based on your request. Please review it on the right and edit anything if needed.
                  </div>
                </div>

                <div className="p-4 mt-auto">
                  <div className="bg-zinc-900/80 border border-zinc-800 rounded-lg flex items-center px-4 py-3">
                    <span className="text-zinc-600 text-[13px] flex-1">Ask anything...</span>
                    <div className="w-7 h-7 rounded bg-zinc-800 flex items-center justify-center text-zinc-400">
                      <Send className="w-3.5 h-3.5" />
                    </div>
                  </div>
                </div>
              </div>

              {/* RIGHT PANEL: Terminal + Table */}
              <div className="lg:col-span-8 flex flex-col bg-[#050505]">

                {/* Top: Mission Control Terminal */}
                <div className="h-[200px] border-b border-zinc-800/50 p-6 font-mono text-xs overflow-hidden relative bg-[#030303]">
                  <div className="flex items-center gap-2 mb-5 text-zinc-100 font-sans text-sm font-semibold tracking-wide">
                    <Rocket className="w-4 h-4 text-zinc-400" />
                    Mission Control
                  </div>
                  <div className="space-y-2 text-zinc-500">
                    <p>{`> Initializing Exa.ai search protocol...`}</p>
                    <p>{`> Target region: Seattle, Portland. Niche: Independent Roasters.`}</p>
                    <p>{`> [200 OK] 48 candidate domains located.`}</p>
                    <p className="text-teal-500/80">{`> Filtering generic cafes. Applying "roaster" heuristics...`}</p>
                    <p className="text-zinc-100">{`> 5 high-intent targets secured. Commencing deep enrichment...`}</p>
                  </div>
                </div>

                {/* Bottom: Company List Table */}
                <div className="flex-1 overflow-auto p-0">
                  <div className="p-5 border-b border-zinc-800/50 flex items-center gap-2 text-zinc-100 font-semibold tracking-wide bg-[#09090b]">
                    <CheckCircle className="w-4 h-4 text-zinc-400" />
                    Company List
                  </div>

                  <table className="w-full text-left text-[13px]">
                    <thead className="text-zinc-500 border-b border-zinc-800/50 bg-[#0a0a0b]">
                      <tr>
                        <th className="font-normal py-3 px-6">Target</th>
                        <th className="font-normal py-3 px-6">Contacts</th>
                        <th className="font-normal py-3 px-6">State</th>
                        <th className="font-normal py-3 px-6 text-right">Drafts</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/50 text-zinc-300 bg-[#09090b]">
                      {/* Row 1 */}
                      <tr className="hover:bg-zinc-800/30 transition-colors">
                        <td className="py-4 px-6">
                          <p className="text-zinc-100 font-medium">True North Coffee Roasters</p>
                          <p className="text-[11px] text-zinc-500 mt-0.5">https://drinktruenorth.com/</p>
                        </td>
                        <td className="py-4 px-6">
                          <p className="text-zinc-200">John Hofius</p>
                          <p className="text-[11px] text-zinc-500 mt-0.5">john.hofius@drinktruenorth.com</p>
                        </td>
                        <td className="py-4 px-6">
                          <span className="inline-flex items-center px-2.5 py-1 rounded bg-white text-black text-[10px] font-bold tracking-widest">
                            COMPLETED
                          </span>
                        </td>
                        <td className="py-4 px-6 text-right">
                          <button className="text-[11px] bg-zinc-900 border border-zinc-700 hover:border-zinc-500 text-zinc-300 px-3 py-1.5 rounded-md transition-colors">
                            Read Data
                          </button>
                        </td>
                      </tr>

                      {/* Row 2 */}
                      <tr className="hover:bg-zinc-800/30 transition-colors">
                        <td className="py-4 px-6">
                          <p className="text-zinc-100 font-medium">Street Bean Coffee Roasters</p>
                          <p className="text-[11px] text-zinc-500 mt-0.5">https://streetbean.org/</p>
                        </td>
                        <td className="py-4 px-6">
                          <p className="text-zinc-200">roaster@streetbean.org</p>
                          <p className="text-[11px] text-zinc-500 mt-0.5">info@streetbean.org</p>
                        </td>
                        <td className="py-4 px-6">
                          <span className="inline-flex items-center px-2.5 py-1 rounded bg-white text-black text-[10px] font-bold tracking-widest">
                            COMPLETED
                          </span>
                        </td>
                        <td className="py-4 px-6 text-right">
                          <span className="text-[11px] text-zinc-500 pr-2">Standby</span>
                        </td>
                      </tr>

                      {/* Row 3 */}
                      <tr className="hover:bg-zinc-800/30 transition-colors">
                        <td className="py-4 px-6">
                          <p className="text-zinc-100 font-medium">SEVEN COFFEE ROASTERS</p>
                          <p className="text-[11px] text-zinc-500 mt-0.5">https://sevencoffeeroasters.com/</p>
                        </td>
                        <td className="py-4 px-6">
                          <p className="text-zinc-200">Sean Lee</p>
                          <p className="text-[11px] text-zinc-500 mt-0.5">info@sevencoffeeroasters.com</p>
                        </td>
                        <td className="py-4 px-6">
                          <span className="inline-flex items-center px-2.5 py-1 rounded bg-white text-black text-[10px] font-bold tracking-widest">
                            COMPLETED
                          </span>
                        </td>
                        <td className="py-4 px-6 text-right">
                          <button className="text-[11px] bg-zinc-900 border border-zinc-700 hover:border-zinc-500 text-zinc-300 px-3 py-1.5 rounded-md transition-colors">
                            Read Data
                          </button>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

              </div>
            </CardContent>
          </Card>
        </section>

        {/* Pricing Section */}
        <section id="pricing" className="py-32 px-6 max-w-5xl mx-auto grid md:grid-cols-2 gap-8">
          <Card className="p-8 border-border hover:border-primary/50 transition-colors flex flex-col">
            <CardHeader className="p-0 mb-8">
              <CardTitle className="text-2xl font-bold tracking-tight text-zinc-200 bg-clip-text bg-gradient-to-b from-zinc-200 to-zinc-800 pb-1">Standard Freight</CardTitle>
              <div className="text-4xl font-bold tracking-tighter py-4">$0<span className="text-sm font-sans text-muted-foreground tracking-normal font-medium"> /mo</span></div>
              <CardDescription className="font-medium">Essential AI-forwarding for regional businesses.</CardDescription>
            </CardHeader>
            <CardContent className="p-0 space-y-4 flex-1">
              {["100 emails/month", "Precision Radar Scouting (Standard)", "Basic AI Vetting", "Standard Localization Engine"
              ].map((item) => (
                <div key={item} className="flex items-center gap-3 text-sm">
                  <Check className="h-4 w-4 text-primary" /> {item}
                </div>
              ))}
            </CardContent>
            <Button
              className="w-full mt-8"
              variant="outline"
              onClick={() => handleRouting('free')}
              disabled={loadingTier !== null}
            >
              {loadingTier === 'free' ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Initializing...
                </>
              ) : (
                "Get Started"
              )}
            </Button>
          </Card>

          <Card className="p-8 border-primary relative overflow-hidden flex flex-col">
            <div className="absolute top-0 right-0 bg-primary text-primary-foreground px-4 py-1 text-[10px] font-bold uppercase tracking-widest">Priority</div>
            <CardHeader className="p-0 mb-8">
              <CardTitle className="text-2xl font-bold tracking-tight text-primary pb-1">Priority Air</CardTitle>
              <div className="text-4xl font-bold tracking-tighter py-4">$25<span className="text-sm font-sans text-muted-foreground tracking-normal font-medium"> /mo</span></div>
              <CardDescription className="font-medium">Deep-founder enrichment and dedicated AI logistics agents.</CardDescription>
            </CardHeader>
            <CardContent className="p-0 space-y-4 flex-1">
              {["500 emails/month", "Deep CEO/Company Data Manifest", "Integration with APIs (i.e: Apollo.io/Hunter.io)", "Strict ICP Filtering", "Personal AI Agent"].map((item) => (
                <div key={item} className="flex items-center gap-3 text-sm">
                  <Check className="h-4 w-4 text-primary" /> {item}
                </div>
              ))}
            </CardContent>
            <Button
              className="w-full mt-8 bg-primary text-primary-foreground"
              onClick={() => handleRouting('paid')}
              disabled={loadingTier !== null}
            >
              {loadingTier === 'paid' ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Initializing...
                </>
              ) : (
                "Deploy at Scale"
              )}
            </Button>
          </Card>
        </section>

        {/* Contact Form Section */}
        <section id="contact" className="py-24 px-6 max-w-2xl mx-auto">
          <div className="text-center mb-10">
            <h2 className="text-4xl md:text-5xl font-bold tracking-tighter text-zinc-300 bg-clip-text bg-gradient-to-b pb-2">CONTACT US</h2>
            <p className="text-muted-foreground font-medium tracking-tight py-2">Feedback or support? We'd love to hear from you.</p>
            <p className="text-muted-foreground font-medium tracking-tight">Email: <a href="mailto:imon@digitecinnovation.ca" className="text-primary hover:underline transition-colors">imon@digitecinnovation.ca</a></p>
          </div>
          <Card className="bg-[#09090b] border-zinc-800 shadow-2xl">
            <CardContent className="p-8">
              <form action="mailto:imon@digitecinnovation.ca" method="POST" encType="text/plain" className="space-y-6">
                <div className="space-y-2">
                  <label htmlFor="name" className="text-sm font-medium text-zinc-300">Name</label>
                  <input type="text" id="name" name="name" className="w-full bg-zinc-900 border border-zinc-800 rounded-md p-3 text-sm text-zinc-100 focus:outline-none focus:ring-1 focus:ring-primary transition-colors" required />
                </div>
                <div className="space-y-2">
                  <label htmlFor="email" className="text-sm font-medium text-zinc-300">Email</label>
                  <input type="email" id="email" name="email" className="w-full bg-zinc-900 border border-zinc-800 rounded-md p-3 text-sm text-zinc-100 focus:outline-none focus:ring-1 focus:ring-primary transition-colors" required />
                </div>
                <div className="space-y-2">
                  <label htmlFor="message" className="text-sm font-medium text-zinc-300">Message</label>
                  <textarea id="message" name="message" rows={4} className="w-full bg-zinc-900 border border-zinc-800 rounded-md p-3 text-sm text-zinc-100 focus:outline-none focus:ring-1 focus:ring-primary resize-none transition-colors" required></textarea>
                </div>
                <Button type="submit" className="w-full bg-primary text-primary-foreground font-bold">
                  Send Message
                </Button>
              </form>
            </CardContent>
          </Card>
        </section>
      </main>

      {/* Footer */}
      <footer className="relative border-t border-zinc-800/50 bg-[#050505] pt-24 pb-8 overflow-hidden">
        {/* Abstract Logistics Grid Background */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff05_1px,transparent_1px),linear-gradient(to_bottom,#ffffff05_1px,transparent_1px)] bg-[size:32px_32px]"></div>
        <div className="absolute inset-0 bg-gradient-to-t from-[#050505] via-[#050505]/80 to-transparent pointer-events-none" />

        <div className="max-w-[1300px] mx-auto px-6 md:px-12 relative z-10 flex flex-col items-center w-full">

          {/* Enterprise Routing Links */}
          {/* <div className="flex flex-wrap justify-center gap-6 md:gap-12 mb-16 text-[11px] tracking-[0.2em] uppercase text-zinc-500 font-semibold">
            <a href="#" className="hover:text-zinc-200 transition-colors">Manifesto</a>
            <a href="#" className="hover:text-zinc-200 transition-colors">Intelligence</a>
            <a href="#" className="hover:text-zinc-200 transition-colors">Logistics</a>
            <a href="#" className="hover:text-zinc-200 transition-colors">Privacy</a>
            <a href="#" className="hover:text-zinc-200 transition-colors">Terms</a>
          </div> */}

          {/* The Mega Brand */}
          <div className="w-full flex items-center justify-center select-none pointer-events-none mb-12">
            <h2 className="text-[18vw] md:text-[16vw] font-bold text-center leading-none tracking-tighter text-transparent bg-clip-text bg-gradient-to-b from-zinc-200 via-zinc-500 to-[#050505]">
              cargoitai
            </h2>
          </div>

          {/* The Ledger (Copyright) */}
          <div className="w-full flex flex-col md:flex-row justify-between items-center text-[10px] uppercase tracking-widest text-zinc-600 border-t border-zinc-800/50 pt-6">
            <span className="mb-2 md:mb-0">© 2026 cargoitai. All systems operational.</span>
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500/80 animate-pulse"></div>
              <span>Global Network Active</span>
            </div>
          </div>

        </div>
      </footer>
    </div>
  )
}
