import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "../components/Providers";

export const metadata: Metadata = {
  title: "cargoit.ai",
  description: "Advanced overseas business management and outreach AI orchestrator.",
  icons: {
    icon: "/logo.jpg",
    apple: "/logo.jpg",
  },
  openGraph: {
    images: [
      {
        url: "/logo.jpg",
        width: 800,
        height: 600,
        alt: "CargoIT Logo",
      },
    ],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className="h-full antialiased dark"
    >
      <body className="min-h-full flex flex-col font-sans">
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
