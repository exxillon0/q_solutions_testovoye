# qscript.py
import os
import random
from pathlib import Path

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PWTimeoutError,
    Error as PWError,
)

PATH_TO_VIDEO_FOLDER = "./video"
CHROMIUM_PATH = os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium")

HEADLESS = os.environ.get("PW_HEADLESS", "1") != "0"

_INIT_SCRIPT = r"""
(() => {
    if (window.__pwInjected) return;
    window.__pwInjected = true;

    const CURSOR_ID = '__pw_svg_cursor';
    const STORAGE_KEY = '__pwCursorPos';

    const createLayer = (id, z) => {
        const el = document.createElement('div');
        el.id = id;
        el.style.cssText =
            'position:fixed;top:0;left:0;width:100vw;height:100vh;' +
            'pointer-events:none;overflow:hidden;z-index:' + z + ';';
        return el;
    };

    // Позиция курсора: читаем сохранённую (переживает same-origin навигацию)
    let mx = 100, my = 100;
    try {
        const saved = sessionStorage.getItem(STORAGE_KEY);
        if (saved) {
            const [sx, sy] = saved.split(',').map(Number);
            if (!isNaN(sx) && !isNaN(sy)) { mx = sx; my = sy; }
        }
    } catch (e) {}

    const savePos = () => {
        try { sessionStorage.setItem(STORAGE_KEY, mx + ',' + my); } catch (e) {}
    };

    const updateCursor = () => {
        const c = document.getElementById(CURSOR_ID);
        if (c) {
            c.style.transform = `translate(${mx}px, ${my}px)`;
            c.style.opacity = '1';
        }
    };

    const ensureMounted = () => {
        if (!document.documentElement) return;
        if (!document.getElementById('__pw_ripple_layer'))
            document.documentElement.appendChild(createLayer('__pw_ripple_layer', 2147483646));
        if (!document.getElementById('__pw_callout_layer'))
            document.documentElement.appendChild(createLayer('__pw_callout_layer', 2147483645));

        if (!document.getElementById(CURSOR_ID)) {
            // Контейнер нулевого размера, транслируется прямо на указатель.
            const c = document.createElement('div');
            c.id = CURSOR_ID;
            c.style.cssText =
                'position:fixed;top:0;left:0;width:0;height:0;' +
                'pointer-events:none;will-change:transform;z-index:2147483647;' +
                'opacity:0;transition:opacity 0.15s ease;';

            // 1) Жёлтая подсветка: круг Ø64 (радиус 32 px) с центром в (0,0).
            const highlight =
                '<div style="position:absolute;left:-32px;top:-32px;' +
                'width:64px;height:64px;border-radius:50%;' +
                'background:rgba(255,215,0,0.45);' +
                'box-shadow:0 0 0 2px rgba(255,200,0,0.65);' +
                'pointer-events:none;"></div>';

            // 2) SVG-стрелка: острие в (0,0) относительно контейнера.
            //    Внутри SVG острие в (4,2), значит сдвиг на (-4,-2).
            const arrow =
                '<svg width="32" height="32" viewBox="0 0 32 32" ' +
                'style="position:absolute;left:-4px;top:-2px;pointer-events:none;" ' +
                'xmlns="http://www.w3.org/2000/svg">' +
                '<path d="M4 2 L4 24 L10 18 L14 28 L18 26 L14 16 L22 16 Z" ' +
                'fill="white" stroke="black" stroke-width="1.5" ' +
                'stroke-linejoin="round"/></svg>';

            c.innerHTML = highlight + arrow;  // круг снизу, стрелка сверху
            document.documentElement.appendChild(c);
        }
        updateCursor();
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', ensureMounted);
    } else {
        ensureMounted();
    }

    // Следуем за реальной мышью Playwright
    document.addEventListener('mousemove', (e) => {
        mx = e.clientX; my = e.clientY;
        savePos();
        updateCursor();
    }, true);

    // Ручная синхронизация (нужна после навигации и при rAF-анимации)
    window.__pwSetCursor = (x, y) => {
        mx = x; my = y;
        savePos();
        updateCursor();
    };

    // Ripple при клике
    const spawnRipple = (x, y) => {
        const layer = document.getElementById('__pw_ripple_layer');
        if (!layer) return;
        const size = 32;
        const r = document.createElement('div');
        r.style.cssText =
            `position:absolute;left:${x - size/2}px;top:${y - size/2}px;` +
            `width:${size}px;height:${size}px;border-radius:50%;` +
            'border:2px solid rgba(0,100,255,0.9);' +
            'background:rgba(0,100,255,0.25);' +
            'transform:scale(0.2);opacity:1;' +
            'transition:transform 0.6s ease-out,opacity 0.6s ease-out;';
        layer.appendChild(r);
        requestAnimationFrame(() => {
            r.style.transform = 'scale(2)';
            r.style.opacity = '0';
        });
        setTimeout(() => r.remove(), 700);
    };
    document.addEventListener('mousedown', (e) => spawnRipple(e.clientX, e.clientY), true);

    // Callout: жёлтый фон, чёрный 16pt, авто-размер, fade-in/out
    window.__pwShowCallout = (text, bgColor, textColor, fade) => new Promise((resolve) => {
        const layer = document.getElementById('__pw_callout_layer');
        if (!layer) { resolve(); return; }
        bgColor = bgColor || '#ffee55';
        textColor = textColor || '#000000';
        fade = (fade === undefined || fade === null) ? 2.0 : fade;
        const box = document.createElement('div');
        box.style.cssText =
            'position:absolute;left:40px;bottom:60px;display:inline-block;' +
            `background:${bgColor};color:${textColor};font-size:16pt;` +
            'font-family:Arial,sans-serif;padding:8px 14px;border-radius:6px;' +
            'box-shadow:0 4px 12px rgba(0,0,0,0.3);white-space:pre;' +
            `opacity:0;transition:opacity ${fade}s ease;`;
        box.textContent = text;
        layer.appendChild(box);
        requestAnimationFrame(() => { box.style.opacity = '1'; });
        setTimeout(() => {
            box.style.opacity = '0';
            setTimeout(() => { box.remove(); resolve(); }, fade * 1000);
        }, fade * 1000);
    });
})();
"""


def _ease_in_out(t: float) -> float:
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2


def _smooth_move(page, from_x, from_y, to_x, to_y, duration_ms=800):
    """Плавное движение SVG-курсора через requestAnimationFrame в браузере."""
    page.evaluate(
        """async ([fromX, fromY, toX, toY, duration]) => {
            const easeInOut = t =>
                t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
            const start = performance.now();
            await new Promise(resolve => {
                const step = (now) => {
                    const t = Math.min(1, (now - start) / duration);
                    const e = easeInOut(t);
                    if (window.__pwSetCursor) {
                        window.__pwSetCursor(
                            fromX + (toX - fromX) * e,
                            fromY + (toY - fromY) * e
                        );
                    }
                    if (t < 1) requestAnimationFrame(step);
                    else resolve();
                };
                requestAnimationFrame(step);
            });
        }""",
        [from_x, from_y, to_x, to_y, duration_ms],
    )
    # Синхронизируем виртуальную мышь Playwright с финальной позицией
    page.mouse.move(to_x, to_y)
    return to_x, to_y


def _human_type(page, text, base_delay=80):
    for ch in text:
        page.keyboard.type(ch)
        page.wait_for_timeout(base_delay + random.randint(-25, 25))


def _center_of(box):
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


# ТЗ
def CaptureVideo_Magento(
    url,
    company_name,
    language,
    country,
    postcode,
    city,
    street,
    house_no,
):
    try:
        folder = Path(PATH_TO_VIDEO_FOLDER).resolve()
        folder.mkdir(parents=True, exist_ok=True)

        safe = "".join(c if c.isalnum() or c in " -_." else "_"
                       for c in (company_name or "video")).strip() or "video"
        final_path = folder / f"{safe}.webm"

        with sync_playwright() as p:
            browser = p.chromium.launch(
    headless=HEADLESS,
    executable_path=CHROMIUM_PATH if os.path.exists(CHROMIUM_PATH) else None,
    args=[
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ],
)
            context = browser.new_context(
    viewport={"width": 1280, "height": 720},
    record_video_dir=str(folder),
    record_video_size={"width": 1280, "height": 720},
    user_agent=(
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    locale="en-US",
)
            context.add_init_script(_INIT_SCRIPT)
            page = context.new_page()

            # 1. Открываем страницу
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_function(
                "() => !!document.getElementById('__pw_svg_cursor')", timeout=10000
            )

            start_x, start_y = 640, 360
            page.mouse.move(start_x, start_y)
            page.evaluate(
                f"window.__pwSetCursor && window.__pwSetCursor({start_x}, {start_y})"
            )

            page.evaluate(
                "(t) => { window.__pwShowCallout(t, '#ffee55', '#000000', 1.2); }",
                f"Starting: {company_name}",
            )
            page.wait_for_timeout(700)

            # 3. Плавно едем к строке поиска
            search_box = page.wait_for_selector('textarea[name="q"]', timeout=15000)
            search_box.scroll_into_view_if_needed()
            tx, ty = _center_of(search_box.bounding_box())
            start_x, start_y = _smooth_move(page, start_x, start_y, tx, ty, duration_ms=900)

            page.mouse.click(tx, ty)  # ripple + фокус
            page.wait_for_timeout(300)

            # 4. Человекоподобный ввод
            query = f"Magento developer in {city}"
            page.evaluate(
                "(t) => { window.__pwShowCallout(t, '#ffee55', '#000000', 1.2); }",
                f'Typing: "{query}"',
            )
            _human_type(page, query)
            page.wait_for_timeout(400)

            # 5. Отправляем форму через Enter.
            bx, by = tx, ty
            page.keyboard.press("Enter")
            page.wait_for_timeout(500)

            # 6. Ждём результаты (10+ секунд — норма)
            try:
                page.wait_for_selector(
                    'a[data-testid="result-title-a"]',
                    state="attached",
                    timeout=45000,
                )
            except PWTimeoutError:
                pass
            page.wait_for_timeout(500)

            # Ре-синк курсора после навигации 
            try:
                page.wait_for_function(
                    "() => !!document.getElementById('__pw_svg_cursor')", timeout=10000
                )
                page.evaluate(f"window.__pwSetCursor && window.__pwSetCursor({bx}, {by})")
            except PWError:
                pass
            start_x, start_y = bx, by

            # 7. Двигаемся к первому результату и кликаем
            first_result = page.wait_for_selector(
                'a[data-testid="result-title-a"]', state="visible", timeout=30000
            )
            first_result.scroll_into_view_if_needed()
            page.wait_for_timeout(300)

            rx, ry = _center_of(first_result.bounding_box())
            start_x, start_y = _smooth_move(page, start_x, start_y, rx, ry, duration_ms=900)
            page.wait_for_timeout(250)

            page.evaluate(
                "(t) => { window.__pwShowCallout(t, '#ffee55', '#000000', 1.2); }",
                "Opening first result",
            )

            try:
                page.mouse.click(rx, ry)
            except PWError:
                pass
            page.wait_for_timeout(1500)

            # Запоминаем путь ДО close(): файл дописывается при закрытии контекста
            try:
                video_path_str = str(page.video.path())
            except Exception:
                video_path_str = None

            context.close()
            browser.close()

        if video_path_str and os.path.exists(video_path_str):
            if os.path.exists(final_path):
                os.remove(final_path)
            os.replace(video_path_str, str(final_path))
            return str(final_path.resolve())

        return None
    except Exception as e:
        print(f"[qscript] CaptureVideo_Magento failed: {e}")
        return None