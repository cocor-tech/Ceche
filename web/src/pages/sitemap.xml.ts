export const prerender = true;

export async function GET() {
  const pages = [
    { loc: "/", priority: "1.0" },
    { loc: "/appraise", priority: "0.9" },
    { loc: "/pricing", priority: "0.8" },
    { loc: "/faq", priority: "0.7" },
    { loc: "/enterprise", priority: "0.8" },
    { loc: "/contact", priority: "0.6" },
    { loc: "/blog", priority: "0.8" },
    { loc: "/compare?slug=godaddy", priority: "0.7" },
    { loc: "/compare?slug=dynadot", priority: "0.7" },
    { loc: "/compare?slug=estibot", priority: "0.7" },
  ];
  const site = "https://ceche.app";

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  ${pages.map(p => `  <url>
    <loc>${site}${p.loc}</loc>
    <changefreq>weekly</changefreq>
    <priority>${p.priority}</priority>
  </url>`).join("\n")}
</urlset>`;

  return new Response(xml, {
    headers: { "Content-Type": "application/xml" },
  });
}
