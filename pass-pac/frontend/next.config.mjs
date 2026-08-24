/** @type {import('next').NextConfig} */
const nextConfig = {
  distDir:
    process.env.NEXT_DIST_DIR ??
    (process.env.NODE_ENV === "development" ? ".next-dev" : ".next"),
  async rewrites() {
    return [
      {
        source: "/sessions/:sessionId/measurements",
        destination: "/research-measurements/:sessionId",
      },
    ];
  },
};

export default nextConfig;
