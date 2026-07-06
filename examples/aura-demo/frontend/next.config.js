// Backend origin. Server-only env (never shipped to client).
// Prod: API_URL set on Vercel. Dev: falls back to 127.0.0.1:8000 because
// on some Windows/Node stacks localhost resolves to ::1 first while uvicorn
// binds to IPv4 127.0.0.1, causing intermittent NetworkError on /api rewrites.
const backend = process.env.API_URL || "http://127.0.0.1:8000";

const cspDirectives = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-eval' 'unsafe-inline'", // Next.js requires unsafe-eval/inline in dev
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com",
  "img-src 'self' data:",
  "connect-src 'self'", // /api rewrites keep requests same-origin
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
];

/** @type {import('next').NextConfig} */
module.exports = {
  output: "standalone",
  async rewrites() {
    // Proxy same-origin /api -> backend in ALL environments (dev + prod).
    // Client never knows the backend URL; avoids build-time env baking.
    return [{ source: "/api/:path*", destination: `${backend}/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Content-Security-Policy", value: cspDirectives.join("; ") },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(self), microphone=(self), geolocation=()" },
        ],
      },
    ];
  },
};
