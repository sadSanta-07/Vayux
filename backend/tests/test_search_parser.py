import asyncio
import httpx
import re
from bs4 import BeautifulSoup

async def search_web_intel(query: str):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    async with httpx.AsyncClient() as client:
        try:
            res = await client.post("https://html.duckduckgo.com/html/", data={"q": query}, headers=headers, timeout=6.0)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                results = []
                for result in soup.select(".result")[:5]:
                    title_elem = result.select_one(".result__title")
                    snippet_elem = result.select_one(".result__snippet")
                    if title_elem and snippet_elem:
                        results.append({
                            "title": title_elem.get_text(strip=True),
                            "snippet": snippet_elem.get_text(strip=True)
                        })
                return results
        except Exception as e:
            print("Search error:", e)
    return []

async def main():
    res = await search_web_intel("Delhi air quality CAQM GRAP stage 4 rules 2026")
    print(f"Found {len(res)} results:")
    for r in res:
        print(f"- {r['title']}\n  {r['snippet']}\n")

if __name__ == "__main__":
    asyncio.run(main())
