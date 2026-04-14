/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Allow Next.js dev assets when the app is accessed via RunPod proxy URLs.
  allowedDevOrigins: ["*.proxy.runpod.net"],
};

module.exports = nextConfig;
