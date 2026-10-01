#!/usr/bin/env python3
"""
export_static.py
Inoreader akışını çekip 'dist/' dizinine:
- Türkçe gazete temalı 'Su Haber Bülteni' web portalını (dist/index.html)
- Sabit RSS 2.0 yayınını (dist/rss.xml)
- Atom 1.0 yayınını (dist/atom.xml)
- JSON Feed (dist/feed.json)
dosyalarını üretir.
"""

import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import config
from app.storage import Storage
from app.scraper import scrape_inoreader
from app.feed import generate_rss_2_xml, generate_atom_xml, generate_json_feed
from app.translator import batch_translate_articles, categorize_article
from app.portal import generate_newspaper_portal_html
from app.podcast import generate_daily_podcast

def main():
    dist_dir = Path(os.getenv("DIST_DIR", config.BASE_DIR / "dist"))
    dist_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Inoreader akışı kontrol ediliyor: {config.INOREADER_URL}")
    data = scrape_inoreader(config.INOREADER_URL)
    raw_items = data.get("items", [])
    print(f"[+] Çekilen güncel makale sayısı: {len(raw_items)}")

    storage = Storage(config.DB_PATH)
    storage.save_items(raw_items)
    storage.prune_items(config.MAX_STORED_ITEMS)

    # Retrieve all stored items
    items = storage.get_items(limit=100)
    print(f"[+] Toplam veritabanı kaydı: {len(items)}")

    from app.image_enricher import resolve_article_image

    # Parallel translation for missing items
    items = batch_translate_articles(items)

    # Persist translations, updated categories and resolved images into SQLite
    for idx, it in enumerate(items):
        title_tr = it.get("title_tr") or it["title"]
        category_tr = it.get("category_tr") or categorize_article(title_tr + " " + it["title"], it.get("description", ""))
        it["category_tr"] = category_tr
        storage.update_item_translation(
            it["guid"],
            title_tr,
            it.get("summary_tr", ""),
            category_tr
        )
        resolved_img = resolve_article_image(it, idx)
        it["image_url"] = resolved_img
        storage.update_item_image(it["guid"], resolved_img)
    print(f"[+] {len(items)} haberin görselleri çözümlendi ve veritabanına işlendi.")

    public_url = config.PUBLIC_BASE_URL or "https://mserman90.github.io/suhaberportali"
    rss_self = f"{public_url}/rss.xml"
    atom_self = f"{public_url}/atom.xml"
    json_self = f"{public_url}/feed.json"
    now_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")

    # Format RSS items with 100% Turkish titles & rich Turkish descriptions
    import html
    rss_items = []
    for it in items:
        r_item = dict(it)
        title_tr = it.get("title_tr") or it["title"]
        category_tr = it.get("category_tr", "Su Kaynakları")
        r_item["title"] = f"[{category_tr}] {title_tr}"

        # Construct Turkish description for RSS / Atom feeds
        desc_parts = []
        if it.get("image_url"):
            desc_parts.append(f'<p><img src="{html.escape(it["image_url"])}" alt="{html.escape(title_tr)}" style="max-width:100%; border-radius:6px;" /></p>')
        if it.get("category_tr"):
            desc_parts.append(f'<p><strong>Kategori:</strong> {html.escape(category_tr)}</p>')
        if it.get("source_feed"):
            desc_parts.append(f'<p><strong>Kaynak:</strong> {html.escape(it["source_feed"])}</p>')
        if it.get("title") and it.get("title") != title_tr:
            desc_parts.append(f'<p><strong>Orijinal Başlık:</strong> {html.escape(it["title"])}</p>')
        if it.get("summary_tr"):
            desc_parts.append(f'<p>{html.escape(it["summary_tr"])}</p>')
        desc_parts.append(f'<p><a href="{html.escape(it["link"])}" target="_blank" rel="noopener noreferrer">Makalenin Tamamını Oku &rarr;</a></p>')

        r_item["description"] = "\n".join(desc_parts)
        rss_items.append(r_item)

    # 1. Generate RSS 2.0
    rss_content = generate_rss_2_xml(
        feed_title="Su Haber Bülteni - Su & Sulama Gazetesi",
        feed_description="Türkiye ve Dünya Su, Sulama, Çevre ve Hidroloji Araştırmaları Gazetesi",
        feed_link=public_url,
        self_rss_url=rss_self,
        items=rss_items,
        language="tr"
    )
    (dist_dir / "rss.xml").write_text(rss_content, encoding="utf-8")
    print(f"[+] Üretildi: {dist_dir / 'rss.xml'}")

    # 2. Generate Atom 1.0
    atom_content = generate_atom_xml(
        feed_title="Su Haber Bülteni",
        feed_description="Türkiye ve Dünya Su, Sulama, Çevre ve Hidroloji Araştırmaları Gazetesi",
        feed_link=public_url,
        self_atom_url=atom_self,
        items=rss_items
    )
    (dist_dir / "atom.xml").write_text(atom_content, encoding="utf-8")
    print(f"[+] Üretildi: {dist_dir / 'atom.xml'}")

    # 3. Generate JSON Feed
    json_data = generate_json_feed(
        feed_title="Su Haber Bülteni",
        feed_description="Türkiye ve Dünya Su, Sulama, Çevre ve Hidroloji Araştırmaları Gazetesi",
        feed_link=public_url,
        self_json_url=json_self,
        items=rss_items
    )
    (dist_dir / "feed.json").write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[+] Üretildi: {dist_dir / 'feed.json'}")

    # 4. Generate Daily Podcast & Podcast RSS Feed (podcast.xml)
    podcast_info = None
    try:
        podcast_info = generate_daily_podcast(items, dist_dir, public_url)
    except Exception as pe:
        print(f"[!] Podcast üretimi sırasında hata: {pe}")

    # 5. Generate Modern Newspaper Theme Portal in dist/index.html with Podcast Player
    portal_html = generate_newspaper_portal_html(items, now_str, rss_self, atom_self, json_self, podcast_info=podcast_info)
    (dist_dir / "index.html").write_text(portal_html, encoding="utf-8")
    print(f"[+] Üretildi: {dist_dir / 'index.html'} ('Su Haber Bülteni' Modern Gazete Portalı & Podcast)")

    print("[*] Tüm gazete portalı, podcast ve yayın dosyaları başarıyla hazırlandı!")

if __name__ == "__main__":
    main()
