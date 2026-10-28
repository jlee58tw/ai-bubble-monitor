/** @type {import('next').NextConfig} */
// STATIC_EXPORT=1 builds the read-only GitHub Pages snapshot (see scripts/publish_pages.sh).
const isStatic = process.env.STATIC_EXPORT === "1";
const basePath = isStatic ? process.env.NEXT_PUBLIC_BASE_PATH || "" : "";
const nextConfig = isStatic
  ? { output: "export", distDir: ".next-static", basePath, trailingSlash: true, images: { unoptimized: true }, reactStrictMode: true }
  : { output: "standalone", reactStrictMode: true };
export default nextConfig;
