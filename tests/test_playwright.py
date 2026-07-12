import asyncio
from playwright.async_api import async_playwright
import urllib.parse
import sys
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        query = urllib.parse.quote('alaska puffer паранойя')
        await page.goto(f'https://rus.hitmos.fm/search?q={query}')
        await page.wait_for_timeout(2000)
        html = await page.content()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        tracks = soup.find_all('li')
        for t in tracks:
            # check if it looks like a track
            links = t.find_all('a', href=True)
            dl_link = None
            title_artist = t.text.strip().replace('\n', ' ')
            if not title_artist: continue
            
            if '/song/' in title_artist or '/song/' in str([a['href'] for a in links]):
                song_url = None
                for a in links:
                    if '/song/' in a['href']:
                        song_url = 'https://rus.hitmos.fm' + a['href']
                        break
                
                if song_url and 'alaska' in title_artist.lower():
                    print(f"Visiting {song_url} for {title_artist}")
                    song_page = await browser.new_page()
                    await song_page.goto(song_url)
                    await song_page.wait_for_timeout(1000)
                    song_html = await song_page.content()
                    with open('C:\\\\Users\\\\anton\\\\source\\\\repos\\\\Free-Music\\\\song_test.html', 'w', encoding='utf-8') as f:
                        f.write(song_html)
                    await song_page.close()
                    break
            
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
