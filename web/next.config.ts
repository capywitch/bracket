import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Server Components fazem todo o fetch pro backend FastAPI — nada de
  // rewrites/proxy pro browser aqui, de propósito (mantém API_KEY no server).
  reactStrictMode: true,
  transpilePackages: ["@capywitch/ui"],
};

export default nextConfig;
