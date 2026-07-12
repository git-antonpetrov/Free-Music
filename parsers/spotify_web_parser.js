/**
 * ИНСТРУКЦИЯ ПО ЗАПУСКУ:
 * 
 * 1. Открой свой плейлист в веб-плеере Spotify (open.spotify.com) в браузере.
 * 2. Нажми F12 на клавиатуре (или правая кнопка мыши -> "Просмотреть код" / "Исследовать элемент").
 * 3. Перейди во вкладку "Console" (Консоль).
 * 4. Скопируй весь этот код, вставь его в консоль и нажми Enter.
 * 5. Страница начнет сама скроллиться вниз и собирать треки с правильными русскими названиями.
 * 6. Когда скроллинг дойдет до самого низа плейлиста, 
 *    напиши в этой же консоли команду STOP() и нажми Enter.
 * 7. Выдели и скопируй финальный список треков в свой текстовый файл (например, Liked songs.txt).
 */

let songsMap = new Map();
let scrollInterval = setInterval(() => {
    let rows = document.querySelectorAll('div[role="row"]');
    
    rows.forEach(row => {
        let index = row.getAttribute('aria-rowindex');
        let titleEl = row.querySelector('a[href*="/track/"]');
        let artistEls = row.querySelectorAll('a[href*="/artist/"]');
        let albumEl = row.querySelector('a[href*="/album/"]');
        let imgEl = row.querySelector('img'); // Обложка обычно в теге img
        
        if (index && titleEl && artistEls.length > 0) {
            let title = titleEl.innerText.trim();
            let artist = Array.from(artistEls).map(a => a.innerText.trim()).join(', ');
            let album = albumEl ? albumEl.innerText.trim() : '';
            let coverUrl = imgEl ? imgEl.src : '';
            
            // Ищем длительность (формат M:SS) в тексте строки
            let timeMatch = row.innerText.match(/\b\d+:\d{2}\b/g);
            let duration = timeMatch ? timeMatch[timeMatch.length - 1] : '';
            
            // Строгий формат: Название - исполнители - альбом - ссылка_на_обложку - длительность
            let formattedString = `${title} - ${artist} - ${album} - ${coverUrl} - ${duration}`;
            
            songsMap.set(index, formattedString);
        }
    });

    // Ультимативный поиск контейнера: находим самый длинный скроллируемый блок
    let scrollContainer = null;
    let maxScroll = 0;
    document.querySelectorAll('div').forEach(el => {
        if (el.scrollHeight > el.clientHeight) {
            let diff = el.scrollHeight - el.clientHeight;
            if (diff > maxScroll) {
                maxScroll = diff;
                scrollContainer = el;
            }
        }
    });

    // Крутим его вниз более плавно (400px), чтобы Спотифай успевал рендерить треки
    if (scrollContainer) {
        scrollContainer.scrollBy(0, 400);
    }
    
    console.clear();
    console.log(`⏳ Собрано строк: ${songsMap.size}... (Идет скроллинг)`);
    console.log(`👉 Когда дойдет до низа, напиши команду: STOP()`);
}, 800);

window.STOP = function() {
    clearInterval(scrollInterval);
    // Сортируем треки по их номеру в плейлисте
    let sortedKeys = Array.from(songsMap.keys()).map(Number).sort((a,b) => a - b);
    let result = sortedKeys.map(k => songsMap.get(k.toString())).join('\n');
    console.clear();
    console.log("%c✅ ГОТОВО! Скопируй весь текст ниже:", "color: #1db954; font-size: 20px; font-weight: bold;");
    console.log(result);
};
