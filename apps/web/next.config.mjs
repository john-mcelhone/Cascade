/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // plotly.js-dist-min is shipped as a UMD bundle; transpile it so Next can ESM-import it.
  transpilePackages: ["plotly.js-dist-min", "react-plotly.js", "three"],
  webpack: (config) => {
    // Three.js + R3F + drei sometimes ship .glsl files we don't import here, but this keeps
    // future shader imports working.
    config.module.rules.push({
      test: /\.(glsl|vs|fs|vert|frag)$/,
      type: "asset/source",
    });
    return config;
  },
};

export default nextConfig;
