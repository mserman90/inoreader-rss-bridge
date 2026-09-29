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
from app.translator import batch_translate_articles
from app.portal import generate_newspaper_portal_html

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

    # Parallel translation for missing items
    items = batch_translate_articles(items)

    # Persist translations into SQLite
    for it in items:
        if it.get("title_tr") or it.get("category_tr"):
            storage.update_item_translation(
                it["guid"],
                it.get("title_tr", it["title"]),
                it.get("summary_tr", ""),
                it.get("category_tr", "Su Kaynakları")
            )

    public_url = config.PUBLIC_BASE_URL or "https://mserman90.github.io/inoreader-rss-bridge"
    rss_self = f"{public_url}/rss.xml"
    atom_self = f"{public_url}/atom.xml"
    json_self = f"{public_url}/feed.json"
    now_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")

    # Format RSS items with Turkish titles & descriptions if available
    rss_items = []
    for it in items:
        r_item = dict(it)
        if it.get("title_tr"):
            r_item["title"] = f"[{it.get('category_tr', 'Su')}] {it['title_tr']}"
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

    # 4. Generate Modern Newspaper Theme Portal in dist/index.html
    portal_html = generate_newspaper_portal_html(items, now_str, rss_self, atom_self, json_self)
    (dist_dir / "index.html").write_text(portal_html, encoding="utf-8")
    print(f"[+] Üretildi: {dist_dir / 'index.html'} ('Su Haber Bülteni' Modern Gazete Portalı)")

    print("[*] Tüm gazete portalı ve yayın dosyaları başarıyla hazırlandı!")

if __name__ == "__main__":
    main()
