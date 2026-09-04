import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: ["127.0.0.1:13000", "localhost:13000", "127.0.0.1", "localhost"]
};

export default nextConfig;
