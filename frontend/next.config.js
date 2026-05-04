/** @type {import('next').NextConfig} */
const { withSentryConfig } = require("@sentry/nextjs");

const nextConfig = {
  output: "standalone",
  async rewrites() {
    const apiUrl = process.env.API_URL || "http://localhost:5055";
    return [
      { source: "/api/:path*", destination: `${apiUrl}/api/:path*` },
      { source: "/auth/:path*", destination: `${apiUrl}/auth/:path*` },
    ];
  },
};

const sentryBuildConfigured = Boolean(
  process.env.SENTRY_AUTH_TOKEN &&
    process.env.SENTRY_ORG &&
    process.env.SENTRY_PROJECT,
);

module.exports = withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  authToken: process.env.SENTRY_AUTH_TOKEN,
  silent: !process.env.CI,
  hideSourceMaps: sentryBuildConfigured,
  webpack: {
    treeshake: {
      removeDebugLogging: true,
    },
  },
});
