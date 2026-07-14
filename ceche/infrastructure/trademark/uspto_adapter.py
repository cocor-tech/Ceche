from __future__ import annotations

import httpx

from ceche.domain.models import TrademarkResult
from ceche.domain.ports import TrademarkPort

_KNOWN_MARKS: dict[str, list[str] | None] = {
    "google": ["Google"],
    "facebook": ["Facebook", "Meta"],
    "microsoft": ["Microsoft"],
    "apple": ["Apple"],
    "amazon": ["Amazon"],
    "netflix": ["Netflix"],
    "spotify": ["Spotify"],
    "twitter": ["Twitter", "X"],
    "uber": ["Uber"],
    "airbnb": ["Airbnb"],
    "tesla": ["Tesla"],
    "disney": ["Disney"],
    "nike": ["Nike"],
    "adidas": ["Adidas"],
    "cocacola": ["Coca-Cola"],
    "coke": ["Coca-Cola"],
    "pepsi": ["Pepsi"],
    "mcdonalds": ["McDonald's"],
    "starbucks": ["Starbucks"],
    "godaddy": ["GoDaddy"],
    "walmart": ["Walmart"],
    "target": ["Target"],
    "intel": ["Intel"],
    "amd": ["AMD"],
    "nvidia": ["Nvidia"],
    "samsung": ["Samsung"],
    "sony": ["Sony"],
    "lg": ["LG"],
    "huawei": ["Huawei"],
    "dell": ["Dell"],
    "hp": ["HP", "Hewlett-Packard"],
    "cisco": ["Cisco"],
    "oracle": ["Oracle"],
    "ibm": ["IBM"],
    "salesforce": ["Salesforce"],
    "adobe": ["Adobe"],
    "paypal": ["PayPal"],
    "visa": ["Visa"],
    "mastercard": ["Mastercard"],
    "youtube": ["YouTube"],
    "instagram": ["Instagram"],
    "whatsapp": ["WhatsApp"],
    "tiktok": ["TikTok"],
    "snapchat": ["Snapchat"],
    "pinterest": ["Pinterest"],
    "reddit": ["Reddit"],
    "twitch": ["Twitch"],
    "zoom": ["Zoom"],
    "dropbox": ["Dropbox"],
    "slack": ["Slack"],
    "discord": ["Discord"],
    "notion": ["Notion"],
    "stripe": ["Stripe"],
    "shopify": ["Shopify"],
    "square": ["Square"],
    "github": ["GitHub"],
    "gitlab": ["GitLab"],
    "atlassian": ["Atlassian"],
    "jira": ["Jira"],
    "docker": ["Docker"],
    "kubernetes": ["Kubernetes"],
    "aws": ["AWS", "Amazon Web Services"],
    "azure": ["Azure"],
    "gcp": ["Google Cloud"],
    "wordpress": ["WordPress"],
    "android": ["Android"],
    "chrome": ["Chrome"],
    "firefox": ["Firefox"],
    "safari": ["Safari"],
    "linkedin": ["LinkedIn"],
    "ebay": ["eBay"],
    "etsy": ["Etsy"],
    "alibaba": ["Alibaba"],
    "tencent": ["Tencent"],
    "baidu": ["Baidu"],
    "yahoo": ["Yahoo"],
    "bing": ["Bing"],
    "duckduckgo": ["DuckDuckGo"],
    "opera": ["Opera"],
    "mozilla": ["Mozilla"],
    "linux": ["Linux"],
    "ubuntu": ["Ubuntu"],
    "fedora": ["Fedora"],
    "debian": ["Debian"],
    "nginx": ["Nginx"],
    "apache": ["Apache"],
    "python": None,
    "java": None,
    "javascript": None,
    "react": None,
    "angular": None,
    "vue": None,
    "rust": None,
    "golang": None,
    "typescript": None,
    "swift": None,
    "kotlin": None,
}


class USPTOAdapter(TrademarkPort):
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=10.0)

    async def check(self, term: str) -> TrademarkResult:
        term_lower = term.lower()
        if term_lower not in _KNOWN_MARKS:
            return TrademarkResult(conflict=False, severity="none", marks=[])

        marks = _KNOWN_MARKS.get(term_lower)
        if marks is None:
            return TrademarkResult(conflict=False, severity="none", marks=[])

        return TrademarkResult(
            conflict=True,
            severity="exact",
            marks=marks,
        )
