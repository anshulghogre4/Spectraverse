/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  experimental: {
    // Allow server components to call the local FastAPI backend
    serverComponentsExternalPackages: [],
  },
};

module.exports = nextConfig;
