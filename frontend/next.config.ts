import type { NextConfig } from "next";

const isStaticExport = process.env.NEXT_STATIC_EXPORT === "1";

const nextConfig: NextConfig = isStaticExport
  ? {
      output: "export",
      images: {
        unoptimized: true,
      },
    }
  : {
      async rewrites() {
        return [
          {
            source: "/api/:path*",
            destination: "http://localhost:8000/api/:path*",
          },
        ];
      },
    };

nextConfig.experimental = {
  // Allow long-running backend calls (e.g. /api/news cache miss ~20–30s)
  proxyTimeout: 120000, // 2 minutes (ms)
};

export default nextConfig;
