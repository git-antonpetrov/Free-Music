import os
import asyncio
import threading
import urllib.parse
import re
# pyrefly: ignore [missing-import]
import customtkinter as ctk
from tkinter import filedialog, messagebox
# pyrefly: ignore [missing-import]
from playwright.async_api import async_playwright
import aiohttp
import aiofiles
import sys

# Настраиваем глобальный путь для браузеров Playwright, чтобы он не искал их во временной папке PyInstaller
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.path.expanduser("~"), "AppData", "Local", "ms-playwright")

class HitmosDownloader(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Hitmos Downloader")
        self.geometry("600x450")
        
        self.download_dir = ctk.StringVar()
        self.txt_file = ctk.StringVar()
        
        # UI Elements
        # Directory Selection
        self.dir_label = ctk.CTkLabel(self, text="Папка для сохранения:")
        self.dir_label.pack(pady=(15, 0))
        self.dir_entry = ctk.CTkEntry(self, textvariable=self.download_dir, width=450, state="disabled")
        self.dir_entry.pack(pady=5)
        self.dir_btn = ctk.CTkButton(self, text="Выбрать папку", command=self.select_directory)
        self.dir_btn.pack(pady=5)
        
        # File Selection
        self.file_label = ctk.CTkLabel(self, text="Файл с треками (.txt):")
        self.file_label.pack(pady=(15, 0))
        self.file_entry = ctk.CTkEntry(self, textvariable=self.txt_file, width=450, state="disabled")
        self.file_entry.pack(pady=5)
        self.file_btn = ctk.CTkButton(self, text="Выбрать файл", command=self.select_file)
        self.file_btn.pack(pady=5)
        
        # Start Button
        self.start_btn = ctk.CTkButton(self, text="СТАРТ", command=self.start_download, fg_color="#28a745", hover_color="#218838")
        self.start_btn.pack(pady=20)
        
        # Log Textbox
        self.log_box = ctk.CTkTextbox(self, width=550, height=130)
        self.log_box.pack(pady=10)
        self.log_box.configure(state="disabled")
        
    def select_directory(self):
        d = filedialog.askdirectory()
        if d:
            self.download_dir.set(d)
            
    def select_file(self):
        f = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if f:
            self.txt_file.set(f)
            
    def log(self, message):
        def _append():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", message + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, _append)
        
    def start_download(self):
        if not self.download_dir.get() or not self.txt_file.get():
            messagebox.showerror("Ошибка", "Выберите папку и файл!")
            return
            
        self.start_btn.configure(state="disabled")
        self.dir_btn.configure(state="disabled")
        self.file_btn.configure(state="disabled")
        
        threading.Thread(target=self.run_async_loop, daemon=True).start()
        
    def run_async_loop(self):
        asyncio.run(self.process_downloads())
        
    async def process_downloads(self):
        self.log("Запуск браузера для парсинга (может занять время при первом запуске)...")
        fails = []
        prefails = []
        try:
            import sys
            # pyrefly: ignore [missing-import]
            import playwright.__main__
            
            # Сохраняем оригинальные аргументы
            original_argv = sys.argv.copy()
            sys.argv = ['playwright', 'install', 'chromium']
            
            try:
                playwright.__main__.main()
            except SystemExit:
                pass
            finally:
                sys.argv = original_argv
                
            with open(self.txt_file.get(), 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            lines.reverse() # Начинаем с последних
            
            # Предварительная фильтрация скачанных треков
            total_tracks = len(lines)
            lines_to_download = []
            for line in lines:
                parts = [p.strip() for p in line.split(' - ')]
                title_meta = parts[0] if len(parts) > 0 else line
                artist_meta = parts[1] if len(parts) > 1 else ""
                safe_name = "".join([c for c in f"{title_meta} - {artist_meta}" if c.isalpha() or c.isdigit() or c in [' ', '-']]).strip()
                if not safe_name: safe_name = "track"
                filepath = os.path.join(self.download_dir.get(), f"{safe_name}.mp3")
                if os.path.exists(filepath):
                    self.log(f"Пропуск (уже скачан): {title_meta} - {artist_meta}")
                else:
                    lines_to_download.append(line)
            
            lines = lines_to_download
            if not lines:
                self.log(f"\nВсе {total_tracks} треков уже скачаны!")
                self.after(0, lambda: messagebox.showinfo("Успех", "Все треки уже скачаны!"))
                return
                
            semaphore = asyncio.Semaphore(1)
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                
                async def fetch_track(line):
                    async with semaphore:
                        page = await context.new_page()
                        try:
                            # Парсим строку (разделитель ' - ' из нашего JS парсера)
                            parts = [p.strip() for p in line.split(' - ')]
                            title_meta = parts[0] if len(parts) > 0 else line
                            artist_meta = parts[1] if len(parts) > 1 else ""
                            album_meta = parts[2] if len(parts) > 2 else ""
                            cover_meta = parts[3] if len(parts) > 3 else ""
                            duration_meta = parts[4] if len(parts) > 4 else ""
                            
                            if 'i.scdn.co/image/' in cover_meta:
                                cover_meta = re.sub(r'([0-9a-f]{8})[0-9a-f]{8}([0-9a-f]{24})', r'\g<1>0000b273\g<2>', cover_meta)
                                
                            target_sec = 0
                            if duration_meta and ':' in duration_meta:
                                try:
                                    m, s = map(int, duration_meta.split(':'))
                                    target_sec = m * 60 + s
                                except: pass
                                
                            safe_name = "".join([c for c in f"{title_meta} - {artist_meta}" if c.isalpha() or c.isdigit() or c in [' ', '-']]).strip()
                            if not safe_name: safe_name = "track"
                            filepath = os.path.join(self.download_dir.get(), f"{safe_name}.mp3")
                            
                            if os.path.exists(filepath):
                                self.log(f"Пропуск (уже скачан): {title_meta} - {artist_meta}")
                                return
                            
                            # Для поиска на сайте используем только название и автора
                            search_line = f"{title_meta} {artist_meta}".strip()
                            words = [w.lower() for w in search_line.split() if w.strip()]
                            if not words: return
                            
                            query = urllib.parse.quote(search_line)
                            await page.goto(f'https://rus.hitmos.fm/search?q={query}', timeout=30000)
                            await page.wait_for_timeout(2000)
                            
                            from bs4 import BeautifulSoup
                            html = await page.content()
                            soup = BeautifulSoup(html, 'html.parser')
                            tracks = soup.find_all('li')
                            
                            is_plan_b = False
                            # Если ничего не нашли (из-за транслита артиста и т.д.), ищем только по названию песни
                            if not tracks or soup.find('div', class_='not-found'):
                                is_plan_b = True
                                query = urllib.parse.quote(title_meta)
                                await page.goto(f'https://rus.hitmos.fm/search?q={query}', timeout=30000)
                                await page.wait_for_timeout(2000)
                                html = await page.content()
                                soup = BeautifulSoup(html, 'html.parser')
                                tracks = soup.find_all('li')
                            
                            import difflib
                            
                            found_song_url = None
                            best_score = 0
                            
                            for t in tracks:
                                links = t.find_all('a', href=True)
                                title_artist = t.text.strip().replace('\n', ' ')
                                if not title_artist: continue
                                
                                song_link = None
                                for a in links:
                                    if '/song/' in a['href']:
                                        song_link = 'https://rus.hitmos.fm' + a['href']
                                        break
                                
                                if song_link:
                                    ta_lower = title_artist.lower()
                                    # Вычисляем процент сходства (от 0 до 1)
                                    score = difflib.SequenceMatcher(None, search_line.lower(), ta_lower).ratio()
                                    
                                    track_sec = 0
                                    m = re.search(r'\b(\d{1,2}):(\d{2})\b', title_artist)
                                    if m:
                                        track_sec = int(m.group(1)) * 60 + int(m.group(2))
                                            
                                    if target_sec > 0 and track_sec > 0:
                                        if abs(target_sec - track_sec) > 10:
                                            score -= 0.4
                                            
                                    bad_words = ['radio', 'edit', 'remix', 'mix', 'live', 'cover', 'slowed', 'sped up', 'reverb', 'instrumental', 'karaoke', 'version', 'кавер', 'ремикс', 'микс']
                                    for bw in bad_words:
                                        if bw in ta_lower and bw not in search_line.lower():
                                            score -= 0.3
                                            break
                                            
                                    if score > best_score:
                                        best_score = score
                                        found_song_url = song_link
                                        
                            # Скачиваем наиболее похожий трек (если сходство больше 30%)
                            if found_song_url and best_score > 0.3:
                                self.log(f"Найдено: {search_line}")
                                await page.goto(found_song_url, timeout=30000)
                                await page.wait_for_timeout(2000)
                                
                                s_html = await page.content()
                                s_soup = BeautifulSoup(s_html, 'html.parser')
                                
                                audio_url = None
                                audio_tag = s_soup.find('audio')
                                if audio_tag and audio_tag.get('src'):
                                    audio_url = audio_tag['src']
                                else:
                                    for script in s_soup.find_all('script'):
                                        if script.string and '.mp3' in script.string:
                                            match = re.search(r'(https?://[^\s\"\']+\.mp3)', script.string)
                                            if match:
                                                audio_url = match.group(1)
                                                break
                                                
                                    if not audio_url:
                                        dl_links = s_soup.find_all('a', href=True)
                                        for a in dl_links:
                                            if 'download' in a.get('class', []) or 'dl' in a.get('class', []) or '/download/' in a['href']:
                                                audio_url = a['href']
                                                if not audio_url.startswith('http'):
                                                    audio_url = 'https://rus.hitmos.fm' + audio_url
                                                break
                                
                                if audio_url:
                                    self.log(f"Скачивание {search_line}...")
                                    headers = {
                                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                                        'Referer': found_song_url
                                    }
                                    
                                    pw_cookies = await context.cookies()
                                    cookie_dict = {c['name']: c['value'] for c in pw_cookies}
                                    
                                    timeout = aiohttp.ClientTimeout(total=180, sock_read=30) 
                                    async with aiohttp.ClientSession(timeout=timeout, cookies=cookie_dict) as session:
                                        async with session.get(audio_url, headers=headers) as resp:
                                            if resp.status == 200:
                                                # Имя файла уже сформировано в начале функции (filepath)
                                                async with aiofiles.open(filepath, 'wb') as out_f:
                                                    async for chunk in resp.content.iter_chunked(1024 * 64): # 64KB chunks
                                                        await out_f.write(chunk)
                                                        
                                                # Прописываем метаданные ID3
                                                try:
                                                    # pyrefly: ignore [missing-import]
                                                    import mutagen.id3
                                                    # pyrefly: ignore [missing-import]
                                                    from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, ID3NoHeaderError
                                                    
                                                    # Удаляем весь мусор от Hitmos (рекламные комменты, левые обложки)
                                                    try:
                                                        old_tags = ID3(filepath)
                                                        old_tags.delete(filepath)
                                                    except Exception:
                                                        pass
                                                        
                                                    audio_tags = ID3()
                                                        
                                                    if title_meta: audio_tags.add(TIT2(encoding=3, text=title_meta))
                                                    if artist_meta: audio_tags.add(TPE1(encoding=3, text=artist_meta))
                                                    if album_meta: audio_tags.add(TALB(encoding=3, text=album_meta))
                                                    
                                                    # Скачиваем и вшиваем обложку
                                                    if cover_meta and cover_meta.startswith('http'):
                                                        async with session.get(cover_meta) as cover_resp:
                                                            if cover_resp.status == 200:
                                                                cover_data = await cover_resp.read()
                                                                audio_tags.add(
                                                                    APIC(
                                                                        encoding=3,
                                                                        mime='image/jpeg',
                                                                        type=3, # 3 is for the cover image
                                                                        desc=u'Cover',
                                                                        data=cover_data
                                                                    )
                                                                )
                                                                
                                                    audio_tags.save(filepath, v2_version=3)
                                                except Exception as tag_e:
                                                    self.log(f"Не удалось записать теги: {tag_e}")

                                                self.log(f"Успех: {search_line}")
                                                if is_plan_b:
                                                    prefails.append(line)
                                            else:
                                                fails.append(line)
                                                self.log(f"Ошибка загрузки (HTTP {resp.status}): {line}")
                                                
                                    await asyncio.sleep(2)
                                else:
                                    fails.append(line)
                                    self.log(f"Не найден MP3 URL: {line}")
                            else:
                                fails.append(line)
                                self.log(f"Не найдено совпадений: {line}")
                                
                        except Exception as e:
                            fails.append(line)
                            self.log(f"Ошибка с {line}: {e}")
                        finally:
                            await page.close()

                batch_size = 30
                for i in range(0, len(lines), batch_size):
                    batch = lines[i:i+batch_size]
                    tasks = [fetch_track(line) for line in batch]
                    await asyncio.gather(*tasks)
                    
                    if i + batch_size < len(lines):
                        self.log(f"Пауза 1 минута для отдыха сервера (скачано {i+batch_size} из {len(lines)})...")
                        await asyncio.sleep(60)
                        
                await browser.close()
                
            if prefails:
                pf_path = os.path.join(self.download_dir.get(), "prefails.txt")
                with open(pf_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(prefails))
                    
            if fails:
                f_path = os.path.join(self.download_dir.get(), "fails.txt")
                with open(f_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(fails))
                self.log(f"\nГотово! Успешно скачано: {len(lines) - len(fails)} из {len(lines)} недостающих треков (всего в файле {total_tracks}).")
                if prefails:
                    self.log(f"Сработал План Б для {len(prefails)} треков (сохранены в prefails.txt).")
                self.log(f"Ошибки сохранены в fails.txt")
                messagebox.showwarning("Завершено с ошибками", f"Не удалось скачать {len(fails)} треков.\nСписок в fails.txt")
            else:
                self.log(f"\nУспешно скачаны все {len(lines)} новых треков (всего в файле {total_tracks})!")
                if prefails:
                    self.log(f"Сработал План Б для {len(prefails)} треков (сохранены в prefails.txt).")
                messagebox.showinfo("Успех", "Все треки успешно скачаны!")

        except Exception as e:
            self.log(f"Критическая ошибка: {e}")
        finally:
            self.after(0, lambda: self.start_btn.configure(state="normal"))
            self.after(0, lambda: self.dir_btn.configure(state="normal"))
            self.after(0, lambda: self.file_btn.configure(state="normal"))

if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    app = HitmosDownloader()
    app.mainloop()
