import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Proxy /api/* to the FastAPI backend to avoid CORS preflight on the demo.
  async rewrites() {
    return [
      {
        source: "/backend/:path*",
        destination: `${process.env.BACKEND_URL ?? "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
