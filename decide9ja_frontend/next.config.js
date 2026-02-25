/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/backend/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'https://decide9ja.up.railway.app'}/:path*`,
      },
    ];
  },
}

module.exports = nextConfig
