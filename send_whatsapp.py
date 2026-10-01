"""
send_whatsapp.py
Günlük Su Haber Bülteni Podcastini WhatsApp Grubuna Gönderme Aracı.

Kullanım:
  python send_whatsapp.py           # Günün podcasti henüz gönderilmediyse gönderir
  python send_whatsapp.py --force   # Gönderilmiş olsa dahi tekrar gönderir
"""

import sys
import argparse
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import config
from app.storage import Storage
from app.whatsapp import send_daily_podcast_to_whatsapp

def main():
    parser = argparse.ArgumentParser(description="Günlük Podcasti WhatsApp Grubuna Gönder")
    parser.add_argument("--force", action="store_true", help="Mükerrer kontrolünü atla ve zorla gönder")
    args = parser.parse_args()

    storage = Storage(config.DB_PATH)
    items = storage.get_items(limit=100)

    import json
    meta_path = config.DATA_DIR / "podcast_episodes.json"
    latest_ep = None
    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                episodes = json.load(f)
                if episodes:
                    latest_ep = episodes[0]
        except Exception:
            pass

    if not latest_ep:
        print("[-] Gönderilecek podcast bölümü bulunamadı. Lütfen önce 'python export_static.py' çalıştırın.")
        return

    public_url = config.PUBLIC_BASE_URL or "https://mserman90.github.io/suhaberportali"
    podcast_info = {
        "latest_episode": latest_ep,
        "latest_audio_url": f"{public_url}/episodes/podcast_latest.mp3",
        "podcast_rss_url": f"{public_url}/podcast.xml"
    }

    res = send_daily_podcast_to_whatsapp(podcast_info, items, public_url, force=args.force)
    print(f"Durum: {res['status']} | Sağlayıcı: {res['provider']}")

if __name__ == "__main__":
    main()
