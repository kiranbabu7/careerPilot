import type { NextConfig } from "next";

// Bind mounts on Windows/macOS Docker do not propagate inotify events.
// WATCHPACK_POLLING is set in docker-compose for the frontend service.
const usePolling = process.env.WATCHPACK_POLLING === "true";
const pollIntervalMs = Number(process.env.WATCHPACK_POLLING_INTERVAL ?? 1000);

const nextConfig: NextConfig = {
  output: "standalone",
  ...(usePolling && {
    watchOptions: {
      pollIntervalMs,
    },
  }),
  webpack: (config, { dev }) => {
    if (dev && usePolling) {
      config.watchOptions = {
        ...config.watchOptions,
        poll: pollIntervalMs,
        aggregateTimeout: 300,
        ignored: ["**/node_modules/**", "**/.git/**"],
      };
    }
    return config;
  },
};

export default nextConfig;
