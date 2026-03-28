import type { NextConfig } from "next";

// const nextConfig: NextConfig = {
//   allowedDevOrigins: ["192.168.1.103"],
//   async rewrites() {
//     return [
//       {
//         source: "/api/:path*",
//         destination: "http://localhost:8000/api/:path*",
//       },
//     ];
//   },
// };

// export default nextConfig;

// next.config.ts

const nextConfig = {
  async rewrites() {
    // This grabs your Railway URL in production, but defaults to localhost for local dev
    const backendUrl = process.env.NEXT_PUBLIC_API_URL;
    
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`, 
      },
    ];
  },
  // ... any other config you have
};

export default nextConfig;