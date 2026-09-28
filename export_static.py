#!/usr/bin/env python3
"""
export_static.py
Inoreader akışını çekip 'dist/' dizinine statik rss.xml, atom.xml, feed.json ve index.html dosyaları üretir.
GitHub Pages, Cloudflare Pages, Netlify veya statik web sunucularında sıfır maliyetle çalıştırmak için idealdir.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import config
from app.storage import Storage
from app.scraper import scrape_inoreader
from app.feed import generate_rss_2_xml, generate_atom_xml, generate_json_feed

def main():
    dist_dir = Path(os.getenv("DIST_DIR", config.BASE_DIR / "dist"))
    dist_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Inoreader akışı çekiliyor: {config.INOREADER_URL}")
    data = scrape_inoreader(config.INOREADER_URL)
    print(f"[+] Çekilen öğe sayısı: {len(data['items'])}")

    storage = Storage(config.DB_PATH)
    new_count = storage.save_items(data["items"])
    storage.prune_items(config.MAX_STORED_ITEMS)
    print(f"[+] Veritabanına {new_count} yeni öğe eklendi. Toplam kayıt: {storage.count_items()}")

    items = storage.get_items(limit=100)
    feed_title = data.get("title", config.FEED_TITLE)
    public_url = config.PUBLIC_BASE_URL or "https://example.github.io/my-rss"
    rss_self = f"{public_url}/rss.xml"
    atom_self = f"{public_url}/atom.xml"
    json_self = f"{public_url}/feed.json"

    # Generate RSS 2.0
    rss_content = generate_rss_2_xml(
        feed_title=feed_title,
        feed_description=config.FEED_DESCRIPTION,
        feed_link=config.INOREADER_URL,
        self_rss_url=rss_self,
        items=items,
        language=config.FEED_LANGUAGE
    )
    (dist_dir / "rss.xml").write_text(rss_content, encoding="utf-8")
    print(f"[+] Üretildi: {dist_dir / 'rss.xml'}")

    # Generate Atom 1.0
    atom_content = generate_atom_xml(
        feed_title=feed_title,
        feed_description=config.FEED_DESCRIPTION,
        feed_link=config.INOREADER_URL,
        self_atom_url=atom_self,
        items=items
    )
    (dist_dir / "atom.xml").write_text(atom_content, encoding="utf-8")
    print(f"[+] Üretildi: {dist_dir / 'atom.xml'}")

    # Generate JSON Feed
    import json
    json_data = generate_json_feed(
        feed_title=feed_title,
        feed_description=config.FEED_DESCRIPTION,
        feed_link=config.INOREADER_URL,
        self_json_url=json_self,
        items=items
    )
    (dist_dir / "feed.json").write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[+] Üretildi: {dist_dir / 'feed.json'}")

    # Generate simple HTML landing page in dist/index.html
    html_content = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{feed_title} - RSS Yayını</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; background: #f8fafc; color:#0f172a; padding: 40px 20px; }}
        .card {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
        h1 {{ color: #1e40af; font-size: 22px; }}
        a.btn {{ display: inline-block; background: #2563eb; color: white; padding: 10px 16px; border-radius: 6px; text-decoration: none; margin-right: 8px; }}
        .box {{ background: #f1f5f9; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 13px; margin: 16px 0; word-break: break-all; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>📡 {feed_title}</h1>
        <p>Inoreader yayın akışından otomatik olarak derlenmiş RSS akış linkleri:</p>
        <div class="box">rss.xml</div>
        <p>
            <a href="rss.xml" class="btn">RSS 2.0 Feed</a>
            <a href="atom.xml" class="btn" style="background:#0f766e;">Atom Feed</a>
            <a href="feed.json" class="btn" style="background:#64748b;">JSON Feed</a>
        </p>
        <p style="font-size:12px; color:#64748b; margin-top:20px;">Toplam {len(items)} makale içeriyor.</p>
    </div>
</body>
</html>"""
    (dist_dir / "index.html").write_text(html_content, encoding="utf-8")
    print(f"[+] Üretildi: {dist_dir / 'index.html'}")
    print("[*] Tüm statik dosyalar başarıyla oluşturuldu!")

if __name__ == "__main__":
    main()
