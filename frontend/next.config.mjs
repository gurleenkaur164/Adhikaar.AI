import path from "node:path";

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Pin the workspace root — several lockfiles exist on this machine.
  turbopack: { root: path.resolve(".") },
  // Proxy API calls to the FastAPI backend during local dev so the frontend
  // can use relative /api URLs (works the same in prod behind one domain).
  async rewrites() {
    const backend = process.env.BACKEND_URL || "http://127.0.0.1:8000";
    return [
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
      { source: "/health", destination: `${backend}/health` },
    ];
  },
};

export default nextConfig;
