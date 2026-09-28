import asyncio
import logging
from datetime import datetime, timezone
import time
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.storage import Storage
from app.scraper import scrape_inoreader
from app.feed import generate_rss_2_xml, generate_atom_xml, generate_json_feed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("inoreader_app")

storage = Storage(config.DB_PATH)
is_syncing = False
last_sync_error: Optional[str] = None
next_sync_ts: Optional[int] = None

def perform_sync():
    """Synchronously fetches from Inoreader and saves to SQLite."""
    global is_syncing, last_sync_error, next_sync_ts
    if is_syncing:
        logger.info("Senkronizasyon zaten devam ediyor, atlandı.")
        return

    is_syncing = True
    start_time = time.time()
    try:
        logger.info("Inoreader akışı kontrol ediliyor: %s", config.INOREADER_URL)
        data = scrape_inoreader(config.INOREADER_URL)
        new_count = storage.save_items(data["items"])
        storage.prune_items(config.MAX_STORED_ITEMS)

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        storage.set_meta("last_sync_time", now_utc)
        storage.set_meta("last_sync_status", "Success")
        storage.set_meta("feed_title", data.get("title", config.FEED_TITLE))
        last_sync_error = None

        logger.info(
            "Senkronizasyon tamamlandı: %d yeni öğe eklendi. Toplam öğe: %d (Süre: %.2fs)",
            new_count, storage.count_items(), time.time() - start_time
        )
    except Exception as exc:
        err_msg = str(exc)
        logger.error("Senkronizasyon hatası: %s", err_msg, exc_info=True)
        last_sync_error = err_msg
        storage.set_meta("last_sync_status", f"Error: {err_msg}")
    finally:
        is_syncing = False
        next_sync_ts = int(time.time()) + (config.FETCH_INTERVAL_MINUTES * 60)

async def periodic_fetcher():
    """Background task running continuously at configured interval."""
    # Run immediate fetch on startup if DB is empty
    if storage.count_items() == 0:
        logger.info("Veritabanı boş, ilk çekme işlemi başlatılıyor...")
        await asyncio.to_thread(perform_sync)

    while True:
        try:
            wait_seconds = config.FETCH_INTERVAL_MINUTES * 60
            await asyncio.sleep(wait_seconds)
            logger.info("Periyodik çekme tetiklendi...")
            await asyncio.to_thread(perform_sync)
        except asyncio.CancelledError:
            logger.info("Periyodik fetcher görevi sonlandırıldı.")
            break
        except Exception as e:
            logger.error("Arka plan fetcher döngüsünde beklenmeyen hata: %s", e)
            await asyncio.sleep(30)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start background task
    task = asyncio.create_task(periodic_fetcher())
    yield
    # Shutdown: Cancel background task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title="Inoreader RSS Bridge",
    description="Inoreader HTML akışını kalıcı ve sabit bir RSS 2.0 / Atom yayınına dönüştürür.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_base_url(request: Request) -> str:
    if config.PUBLIC_BASE_URL:
        return config.PUBLIC_BASE_URL
    return str(request.base_url).rstrip("/")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    base_url = get_base_url(request)
    rss_url = f"{base_url}/rss.xml"
    atom_url = f"{base_url}/atom.xml"
    json_url = f"{base_url}/feed.json"
    status = storage.get_sync_status()
    recent_items = storage.get_items(limit=8)

    next_sync_in = "Hesaplanıyor..."
    if next_sync_ts:
        diff = max(0, next_sync_ts - int(time.time()))
        mins, secs = divmod(diff, 60)
        next_sync_in = f"{mins} dk {secs} sn"

    items_html = ""
    for it in recent_items:
        img_badge = f'<img src="{it["image_url"]}" style="width:50px;height:50px;object-fit:cover;border-radius:6px;margin-right:12px;float:left;" />' if it.get("image_url") else ""
        items_html += f"""
        <li style="padding:14px; border-bottom:1px solid #e2e8f0; list-style:none; clear:both;">
            {img_badge}
            <div>
                <a href="{it['link']}" target="_blank" style="font-weight:600; color:#1e40af; text-decoration:none; font-size:15px;">
                    {it['title']}
                </a>
                <div style="font-size:12px; color:#64748b; margin-top:4px;">
                    <span>📅 {it['pub_date']}</span> | 
                    <span>🏷️ {it.get('source_feed') or it.get('author') or 'Inoreader'}</span>
                </div>
            </div>
        </li>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{config.FEED_TITLE} - RSS Köprüsü</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: #f8fafc;
            color: #0f172a;
            margin: 0;
            padding: 30px 20px;
        }}
        .container {{
            max-width: 820px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
            overflow: hidden;
            border: 1px solid #e2e8f0;
        }}
        .header {{
            background: linear-gradient(135deg, #1e40af, #3b82f6);
            color: white;
            padding: 28px 32px;
        }}
        .header h1 {{ margin: 0 0 8px 0; font-size: 24px; }}
        .header p {{ margin: 0; opacity: 0.9; font-size: 14px; }}
        .content {{ padding: 28px 32px; }}
        .box {{
            background: #f1f5f9;
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 24px;
            border: 1px solid #e2e8f0;
        }}
        .url-row {{
            display: flex;
            align-items: center;
            margin-top: 8px;
            gap: 8px;
        }}
        .url-input {{
            flex: 1;
            padding: 10px 12px;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            font-family: monospace;
            font-size: 13px;
            background: #ffffff;
        }}
        .btn {{
            padding: 10px 16px;
            background: #2563eb;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
            font-size: 13px;
            text-decoration: none;
            display: inline-block;
        }}
        .btn:hover {{ background: #1d4ed8; }}
        .btn-secondary {{
            background: #64748b;
        }}
        .btn-secondary:hover {{ background: #475569; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            gap: 12px;
            margin-bottom: 24px;
        }}
        .stat-card {{
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 14px;
            text-align: center;
        }}
        .stat-val {{ font-size: 20px; font-weight: bold; color: #1e40af; margin-top: 4px; }}
        .stat-lbl {{ font-size: 12px; color: #64748b; }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 9999px;
            font-size: 11px;
            font-weight: 600;
        }}
        .badge-success {{ background: #dcfce7; color: #15803d; }}
        .badge-error {{ background: #fee2e2; color: #b91c1c; }}
        ul {{ padding: 0; margin: 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📡 {config.FEED_TITLE}</h1>
            <p>Inoreader HTML Akışından Otomatik Üretilen Sabit RSS Köprüsü</p>
        </div>

        <div class="content">
            <!-- URL Box -->
            <div class="box">
                <label style="font-weight: 600; font-size: 14px;">🔗 Sabit RSS 2.0 Bağlantınız (Okuyucunuza Ekleyin):</label>
                <div class="url-row">
                    <input type="text" readonly value="{rss_url}" class="url-input" id="rssUrl">
                    <button class="btn" onclick="navigator.clipboard.writeText(document.getElementById('rssUrl').value); alert('RSS Bağlantısı panoya kopyalandı!');">Kopyala</button>
                    <a href="{rss_url}" target="_blank" class="btn btn-secondary">Aç</a>
                </div>
                <div style="margin-top: 10px; font-size: 12px; color:#64748b;">
                    Alternatif formatlar: 
                    <a href="{atom_url}" target="_blank" style="color:#2563eb;">Atom 1.0</a> | 
                    <a href="{json_url}" target="_blank" style="color:#2563eb;">JSON Feed</a>
                </div>
            </div>

            <!-- Stats -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-lbl">Toplam Makale</div>
                    <div class="stat-val">{status['total_items']}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-lbl">Kontrol Aralığı</div>
                    <div class="stat-val">{config.FETCH_INTERVAL_MINUTES} dk</div>
                </div>
                <div class="stat-card">
                    <div class="stat-lbl">Son Güncelleme</div>
                    <div class="stat-val" style="font-size: 13px; line-height: 24px;">{status['last_sync_time'] or 'Henüz yok'}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-lbl">Son Durum</div>
                    <div class="stat-val" style="font-size: 13px;">
                        <span class="badge {'badge-success' if 'Success' in status['last_sync_status'] else 'badge-error'}">
                            {status['last_sync_status']}
                        </span>
                    </div>
                </div>
            </div>

            <!-- Controls -->
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 20px;">
                <div style="font-size:13px; color:#64748b;">
                    Sonraki planlı kontrol: <strong>{next_sync_in}</strong>
                </div>
                <form action="/api/refresh" method="POST" style="margin:0;">
                    <button type="submit" class="btn" style="background:#0f766e;">🔄 Şimdi Güncelle</button>
                </form>
            </div>

            <!-- Recent Items -->
            <h3 style="font-size: 16px; margin: 24px 0 12px 0; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">
                Son Eklenen Öğeler (Önizleme)
            </h3>
            <ul style="border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; background: #fff;">
                {items_html if items_html else '<li style="padding:20px; text-align:center; color:#64748b;">Henüz öğe bulunamadı.</li>'}
            </ul>

            <div style="margin-top:24px; font-size:12px; color:#94a3b8; text-align:center;">
                Kaynak: <a href="{config.INOREADER_URL}" target="_blank" style="color:#64748b;">Inoreader Stream</a> &bull; Inoreader RSS Bridge v1.0
            </div>
        </div>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html_content)

@app.api_route("/rss.xml", methods=["GET", "HEAD"], response_class=Response)
@app.api_route("/feed", methods=["GET", "HEAD"], response_class=Response)
@app.api_route("/feed.xml", methods=["GET", "HEAD"], response_class=Response)
async def get_rss_feed(request: Request):
    """Returns fixed RSS 2.0 XML feed."""
    if storage.count_items() == 0:
        await asyncio.to_thread(perform_sync)

    items = storage.get_items(limit=100)
    base_url = get_base_url(request)
    self_url = f"{base_url}/rss.xml"

    xml_content = generate_rss_2_xml(
        feed_title=storage.get_meta("feed_title") or config.FEED_TITLE,
        feed_description=config.FEED_DESCRIPTION,
        feed_link=config.INOREADER_URL,
        self_rss_url=self_url,
        items=items,
        language=config.FEED_LANGUAGE
    )
    return Response(
        content=xml_content,
        media_type="application/rss+xml; charset=utf-8",
        headers={
            "Cache-Control": f"public, max-age={config.FETCH_INTERVAL_MINUTES * 60}",
            "X-Feed-Items-Count": str(len(items))
        }
    )

@app.api_route("/atom.xml", methods=["GET", "HEAD"], response_class=Response)
async def get_atom_feed(request: Request):
    """Returns Atom 1.0 XML feed."""
    if storage.count_items() == 0:
        await asyncio.to_thread(perform_sync)

    items = storage.get_items(limit=100)
    base_url = get_base_url(request)
    self_url = f"{base_url}/atom.xml"

    xml_content = generate_atom_xml(
        feed_title=storage.get_meta("feed_title") or config.FEED_TITLE,
        feed_description=config.FEED_DESCRIPTION,
        feed_link=config.INOREADER_URL,
        self_atom_url=self_url,
        items=items
    )
    return Response(
        content=xml_content,
        media_type="application/atom+xml; charset=utf-8",
        headers={
            "Cache-Control": f"public, max-age={config.FETCH_INTERVAL_MINUTES * 60}"
        }
    )

@app.api_route("/feed.json", methods=["GET", "HEAD"], response_class=JSONResponse)
async def get_json_feed(request: Request):
    """Returns JSON Feed v1.1."""
    if storage.count_items() == 0:
        await asyncio.to_thread(perform_sync)

    items = storage.get_items(limit=100)
    base_url = get_base_url(request)
    self_url = f"{base_url}/feed.json"

    data = generate_json_feed(
        feed_title=storage.get_meta("feed_title") or config.FEED_TITLE,
        feed_description=config.FEED_DESCRIPTION,
        feed_link=config.INOREADER_URL,
        self_json_url=self_url,
        items=items
    )
    return JSONResponse(
        content=data,
        media_type="application/feed+json; charset=utf-8"
    )

@app.api_route("/api/refresh", methods=["GET", "POST"])
async def trigger_refresh(background_tasks: BackgroundTasks, request: Request):
    """Manual sync trigger endpoint."""
    await asyncio.to_thread(perform_sync)
    status = storage.get_sync_status()

    # If requested by browser HTML form, redirect back to /
    if "text/html" in request.headers.get("accept", ""):
        return Response(status_code=303, headers={"Location": "/"})

    return JSONResponse(content={
        "status": "ok",
        "sync_status": status,
        "items_count": storage.count_items()
    })

@app.get("/health")
@app.get("/api/status")
async def health_check():
    return {
        "status": "healthy",
        "sync": storage.get_sync_status(),
        "config": {
            "fetch_interval_minutes": config.FETCH_INTERVAL_MINUTES,
            "max_stored_items": config.MAX_STORED_ITEMS,
            "target_url": config.INOREADER_URL
        }
    }
