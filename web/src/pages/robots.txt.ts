export const prerender = true;

export async function GET() {
  const site = "https://ceche.app";
  const text = `User-agent: *
Allow: /

Sitemap: ${site}/sitemap.xml`;

  return new Response(text, {
    headers: { "Content-Type": "text/plain" },
  });
}
