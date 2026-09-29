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
from app.translator import batch_translate_articles
from app.portal import generate_newspaper_portal_html

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
    """Synchronously fetches from Inoreader and saves to SQLite with Turkish translations."""
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

        # Batch translate missing items
        all_items = storage.get_items(limit=100)
        translated_items = batch_translate_articles(all_items)
        for it in translated_items:
            if it.get("title_tr"):
                storage.update_item_translation(
                    it["guid"],
                    it["title_tr"],
                    it.get("summary_tr", ""),
                    it.get("category_tr", "Su Kaynakları")
                )

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        storage.set_meta("last_sync_time", now_utc)
        storage.set_meta("last_sync_status", "Success")
        storage.set_meta("feed_title", "Su Haber Bülteni")
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
    task = asyncio.create_task(periodic_fetcher())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title="Su Haber Bülteni Portal & RSS",
    description="Su, Sulama ve Çevre Araştırmaları Gazetesi & RSS Köprüsü",
    version="2.0.0",
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
    """Renders modern newspaper theme 'Su Haber Bülteni' portal."""
    base_url = get_base_url(request)
    rss_url = f"{base_url}/rss.xml"
    atom_url = f"{base_url}/atom.xml"
    json_url = f"{base_url}/feed.json"
    
    items = storage.get_items(limit=100)
    now_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")

    html_content = generate_newspaper_portal_html(
        items=items,
        last_updated=now_str,
        rss_url=rss_url,
        atom_url=atom_url,
        json_url=json_url
    )
    return HTMLResponse(content=html_content)

@app.api_route("/rss.xml", methods=["GET", "HEAD"], response_class=Response)
@app.api_route("/feed", methods=["GET", "HEAD"], response_class=Response)
@app.api_route("/feed.xml", methods=["GET", "HEAD"], response_class=Response)
async def get_rss_feed(request: Request):
    """Returns fixed RSS 2.0 XML feed with Turkish titles."""
    if storage.count_items() == 0:
        await asyncio.to_thread(perform_sync)

    items = storage.get_items(limit=100)
    base_url = get_base_url(request)
    self_url = f"{base_url}/rss.xml"

    rss_items = []
    for it in items:
        r_item = dict(it)
        if it.get("title_tr"):
            r_item["title"] = f"[{it.get('category_tr', 'Su')}] {it['title_tr']}"
        rss_items.append(r_item)

    xml_content = generate_rss_2_xml(
        feed_title="Su Haber Bülteni - Su & Sulama Gazetesi",
        feed_description="Türkiye ve Dünya Su, Sulama, Çevre ve Hidroloji Araştırmaları Gazetesi",
        feed_link=base_url,
        self_rss_url=self_url,
        items=rss_items,
        language="tr"
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

    rss_items = []
    for it in items:
        r_item = dict(it)
        if it.get("title_tr"):
            r_item["title"] = f"[{it.get('category_tr', 'Su')}] {it['title_tr']}"
        rss_items.append(r_item)

    xml_content = generate_atom_xml(
        feed_title="Su Haber Bülteni",
        feed_description="Türkiye ve Dünya Su, Sulama, Çevre ve Hidroloji Araştırmaları Gazetesi",
        feed_link=base_url,
        self_atom_url=self_url,
        items=rss_items
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

    rss_items = []
    for it in items:
        r_item = dict(it)
        if it.get("title_tr"):
            r_item["title"] = f"[{it.get('category_tr', 'Su')}] {it['title_tr']}"
        rss_items.append(r_item)

    data = generate_json_feed(
        feed_title="Su Haber Bülteni",
        feed_description="Türkiye ve Dünya Su, Sulama, Çevre ve Hidroloji Araştırmaları Gazetesi",
        feed_link=base_url,
        self_json_url=self_url,
        items=rss_items
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
        "newspaper": "Su Haber Bülteni",
        "sync": storage.get_sync_status(),
        "config": {
            "fetch_interval_minutes": config.FETCH_INTERVAL_MINUTES,
            "max_stored_items": config.MAX_STORED_ITEMS,
            "target_url": config.INOREADER_URL
        }
    }
