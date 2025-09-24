import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  turbopack: {
    // Pin Turbopack root to the UI app so it ignores the root lockfile
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
