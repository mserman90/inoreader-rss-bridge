"""
app/whatsapp.py
Günlük Su Haber Bülteni Podcastlerini WhatsApp Grubuna Otonom Gönderme Modülü.

Hedef Grup: https://chat.whatsapp.com/FT0rXnxAH4IGIwTCEjLADd
Grup Davet Kodu: FT0rXnxAH4IGIwTCEjLADd

Desteklenen Otonom Gönderim Yöntemleri:
1. Green-API (WhatsApp REST API - Otomatik gruba katılma ve ses/metin gönderme)
2. Özel Webhook / HTTP Gateway (n8n, Make, Whapi, UltraMsg, Evolution-API vb.)
3. Çevrimdışı / Simülasyon modu (Direkt paylaşım linki ve taslak üretimi)
"""

import os
import sys
import json
import logging
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except Exception:
        try:
            safe_args = [str(a).encode("ascii", "replace").decode("ascii") for a in args]
            print(*safe_args, **kwargs)
        except Exception:
            pass

logger = logging.getLogger(__name__)

# Sabit WhatsApp Grubu Bilgileri
TARGET_GROUP_INVITE_URL = "https://chat.whatsapp.com/FT0rXnxAH4IGIwTCEjLADd"
TARGET_GROUP_INVITE_CODE = "FT0rXnxAH4IGIwTCEjLADd"

def get_history_file_path() -> Path:
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "whatsapp_history.json"

def load_whatsapp_history() -> Dict[str, Any]:
    history_file = get_history_file_path()
    if history_file.exists():
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("WhatsApp geçmişi okunamadı: %s", e)
    return {}

def save_whatsapp_history(history: Dict[str, Any]):
    history_file = get_history_file_path()
    try:
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("WhatsApp geçmişi kaydedilemedi: %s", e)

def has_podcast_been_sent_today(date_key: str) -> bool:
    history = load_whatsapp_history()
    return date_key in history and history[date_key].get("status") == "success"

def build_whatsapp_podcast_message(podcast_info: Dict[str, Any], items: List[Dict[str, Any]], public_url: str) -> str:
    """WhatsApp grubu için zengin, emojili ve dikkat çekici bülten mesajı oluşturur."""
    ep = podcast_info.get("latest_episode", {})
    now = datetime.now(timezone.utc)
    date_display = now.strftime("%d.%m.%Y")
    
    audio_url = ep.get("audio_url") or f"{public_url}/episodes/podcast_latest.mp3"
    portal_url = public_url.rstrip("/") + "/"
    podcast_rss = f"{public_url.rstrip('/')}/podcast.xml"

    # Öne çıkan haberleri kategorilerine göre derle
    turkey_items = [it for it in items if it.get("is_turkey") or it.get("category_tr") == "Türkiye"]
    sulama_items = [it for it in items if it.get("category_tr") == "Tarımsal Sulama"]
    kaynak_items = [it for it in items if it.get("category_tr") == "Su Kaynakları"]
    teknoloji_items = [it for it in items if it.get("category_tr") in ["Su Teknolojileri", "Su Arıtma & Kalite"]]

    def clean_text(t: str) -> str:
        return " ".join((t or "").split())[:85]

    highlight_lines = []
    if turkey_items:
        t_title = clean_text(turkey_items[0].get("title_tr") or turkey_items[0].get("title", ""))
        highlight_lines.append(f"• 🇹🇷 *Türkiye Su Gündemi:* {t_title}")
    if sulama_items:
        s_title = clean_text(sulama_items[0].get("title_tr") or sulama_items[0].get("title", ""))
        highlight_lines.append(f"• 🌾 *Tarımsal Sulama:* {s_title}")
    if kaynak_items:
        k_title = clean_text(kaynak_items[0].get("title_tr") or kaynak_items[0].get("title", ""))
        highlight_lines.append(f"• 💧 *Su Kaynakları:* {k_title}")
    if teknoloji_items:
        tek_title = clean_text(teknoloji_items[0].get("title_tr") or teknoloji_items[0].get("title", ""))
        highlight_lines.append(f"• 🔬 *Su Teknolojileri:* {tek_title}")

    # Eğer kategori bazlı bulunamadıysa ilk 3 haberi listele
    if len(highlight_lines) < 2 and items:
        for it in items[:3]:
            h_title = clean_text(it.get("title_tr") or it.get("title", ""))
            cat = it.get("category_tr", "Su Gündemi")
            highlight_lines.append(f"• 💧 *{cat}:* {h_title}")

    highlights_block = "\n".join(highlight_lines)

    msg = f"""💧 *SU HABER BÜLTENİ — GÜNLÜK SESLİ PODCAST YAYINDA!* 🎙️
🗓️ *Tarih:* {date_display}

Türkiye ve Dünya su gündeminden, baraj doluluk oranlarından ve tarımsal sulama teknolojilerinden derlenen bugünkü sesli bültenimiz hazırlandı!

📰 *Günün Öne Çıkan Başlıkları:*
{highlights_block}

🎧 *Podcasti Hemen Dinleyin (MP3):*
{audio_url}

🌐 *Gazete Portalını Ziyaret Edin:*
{portal_url}

📡 *Sabit Podcast RSS:*
{podcast_rss}

---
*Su Haber Bülteni Otonom Yayın Servisi*"""

    return msg.strip()

def send_via_green_api(instance_id: str, api_token: str, chat_id: Optional[str], message: str, audio_url: Optional[str]) -> bool:
    """Green API kullanarak WhatsApp grubuna katılır ve ses/metin mesajı gönderir."""
    base_api = f"https://api.green-api.com/waInstance{instance_id}"
    
    # 1. Eğer chat_id belirtilmediyse, davet linkiyle gruba katıl
    actual_chat_id = chat_id
    if not actual_chat_id or not actual_chat_id.endswith("@g.us"):
        join_url = f"{base_api}/joinGroup/{api_token}"
        try:
            print(f"[*] Green-API: Gruba katılınıyor (Davet Kodu: {TARGET_GROUP_INVITE_CODE})...")
            join_resp = requests.post(join_url, json={"inviteCode": TARGET_GROUP_INVITE_CODE}, timeout=15)
            if join_resp.status_code == 200:
                join_data = join_resp.json()
                actual_chat_id = join_data.get("chatId")
                print(f"[+] WhatsApp grubuna başarıyla katılındı! Chat ID: {actual_chat_id}")
            else:
                print(f"[!] Gruba katılma yanıtı: {join_resp.status_code} - {join_resp.text}")
        except Exception as e:
            logger.warning("Green-API gruba katılma isteği başarısız: %s", e)

    if not actual_chat_id:
        print("[-] Grup Chat ID belirlenemedi. Lütfen WHATSAPP_CHAT_ID tanımlayın.")
        return False

    # 2. Metin mesajını gönder
    msg_url = f"{base_api}/sendMessage/{api_token}"
    msg_payload = {
        "chatId": actual_chat_id,
        "message": message
    }
    
    try:
        print(f"[*] Green-API: Grup bülten mesajı gönderiliyor -> {actual_chat_id}...")
        resp = requests.post(msg_url, json=msg_payload, timeout=20)
        if resp.status_code == 200:
            print(f"[+] WhatsApp bülten metni başarıyla iletildi: {resp.json().get('idMessage', 'OK')}")
        else:
            print(f"[!] Green-API mesaj hatası: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        logger.error("Green-API sendMessage hatası: %s", e)
        return False

    # 3. Ses dosyasını doğrudan WhatsApp grubuna gönder (Playable audio)
    if audio_url:
        file_url = f"{base_api}/sendFileByUrl/{api_token}"
        file_payload = {
            "chatId": actual_chat_id,
            "urlFile": audio_url,
            "fileName": f"SuHaber_Podcast_{datetime.now(timezone.utc).strftime('%Y%m%d')}.mp3",
            "caption": "🎙️ Günlük Su & Sulama Sesli Bülteni"
        }
        try:
            print("[*] Green-API: Podcast ses dosyası (MP3) WhatsApp grubuna yükleniyor...")
            f_resp = requests.post(file_url, json=file_payload, timeout=30)
            if f_resp.status_code == 200:
                print(f"[+] Podcast ses dosyası gruba başarıyla iletildi: {f_resp.json().get('idMessage', 'OK')}")
            else:
                print(f"[!] Green-API ses gönderme uyarısı: {f_resp.status_code} - {f_resp.text}")
        except Exception as e:
            logger.warning("Green-API sendFileByUrl hatası: %s", e)

    return True

def send_via_webhook(webhook_url: str, message: str, podcast_info: Dict[str, Any], public_url: str) -> bool:
    """Özel Webhook (n8n, Make, Whapi, UltraMsg vb.) üzerinden gönderir."""
    ep = podcast_info.get("latest_episode", {})
    payload = {
        "group_invite_url": TARGET_GROUP_INVITE_URL,
        "group_invite_code": TARGET_GROUP_INVITE_CODE,
        "message": message,
        "audio_url": ep.get("audio_url"),
        "title": ep.get("title"),
        "portal_url": public_url,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    try:
        print(f"[*] WhatsApp Webhook tetikleniyor: {webhook_url}...")
        resp = requests.post(webhook_url, json=payload, timeout=20)
        if resp.status_code in [200, 201, 202, 204]:
            print(f"[+] WhatsApp Webhook başarıyla yanıt verdi: HTTP {resp.status_code}")
            return True
        else:
            print(f"[!] Webhook hatası: HTTP {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        logger.error("WhatsApp Webhook hatası: %s", e)
        return False

def send_daily_podcast_to_whatsapp(
    podcast_info: Dict[str, Any],
    items: List[Dict[str, Any]],
    public_url: str,
    force: bool = False
) -> Dict[str, Any]:
    """
    Günlük üretilen podcasti otonom olarak belirtilen WhatsApp grubuna gönderir.
    Günde 1 kez çalışacak şekilde mükerrer gönderimleri engeller.
    """
    now = datetime.now(timezone.utc)
    date_key = now.strftime("%Y%m%d")

    # Mükerrer gönderim kontrolü (aynı gün zaten gönderildiyse ve zorlanmıyorsa atla)
    if not force and has_podcast_been_sent_today(date_key):
        print(f"[*] Bugünün podcasti ({date_key}) zaten WhatsApp grubuna başarıyla gönderilmiş. Atlanıyor.")
        return {"status": "skipped", "reason": "already_sent_today"}

    message = build_whatsapp_podcast_message(podcast_info, items, public_url)
    ep = podcast_info.get("latest_episode", {})
    audio_url = ep.get("audio_url")

    # Yapılandırmaları ortam değişkenlerinden oku
    green_instance = os.getenv("GREEN_API_INSTANCE_ID") or os.getenv("WHATSAPP_INSTANCE_ID")
    green_token = os.getenv("GREEN_API_TOKEN") or os.getenv("WHATSAPP_API_TOKEN")
    chat_id = os.getenv("WHATSAPP_CHAT_ID")
    webhook_url = os.getenv("WHATSAPP_WEBHOOK_URL")

    success = False
    provider = "none"

    if green_instance and green_token:
        provider = "green_api"
        success = send_via_green_api(green_instance, green_token, chat_id, message, audio_url)
    elif webhook_url:
        provider = "webhook"
        success = send_via_webhook(webhook_url, message, podcast_info, public_url)
    else:
        # API anahtarları henüz tanımlanmadıysa simülasyon ve hazır paylaşım bağlantısı üret
        provider = "draft"
        encoded_msg = urllib.parse.quote(message)
        direct_link = f"https://api.whatsapp.com/send?text={encoded_msg}"
        
        safe_print("\n" + "="*60)
        safe_print("📢 WHATSAPP PODCAST PAYLAŞIM TASLAĞI HAZIRLANDI")
        safe_print("="*60)
        safe_print(f"Hedef Grup Daveti: {TARGET_GROUP_INVITE_URL}")
        safe_print("-" * 60)
        safe_print(message)
        safe_print("-" * 60)
        safe_print(f"📱 Tek Tıkla Gruba Paylaşma Linki:\n{direct_link}")
        safe_print("="*60 + "\n")

        # Taslak dosyasını dist içine ve data içine kaydet
        base_dir = Path(__file__).resolve().parent.parent
        draft_file = base_dir / "dist" / "latest_whatsapp_message.txt"
        draft_file.parent.mkdir(parents=True, exist_ok=True)
        draft_file.write_text(message, encoding="utf-8")

        success = True  # Taslak başarıyla oluşturuldu

    # Gönderim başarılı ise geçmişe kaydet
    if success and provider != "draft":
        history = load_whatsapp_history()
        history[date_key] = {
            "sent_at": now.isoformat(),
            "status": "success",
            "provider": provider,
            "title": ep.get("title"),
            "audio_url": audio_url
        }
        save_whatsapp_history(history)
        print(f"[+] WhatsApp gönderim kaydı işlendi: {date_key}")

    return {
        "status": "success" if success else "failed",
        "provider": provider,
        "date_key": date_key,
        "message": message
    }

if __name__ == "__main__":
    # Test çalıştırması
    from app import config
    from app.storage import Storage
    
    print("[*] WhatsApp modülü doğrudan test ediliyor...")
    storage = Storage(config.DB_PATH)
    items = storage.get_items(limit=30)
    
    dummy_podcast = {
        "latest_episode": {
            "title": "Su & Sulama Günlük Bülteni - Test",
            "audio_url": f"{config.PUBLIC_BASE_URL or 'https://mserman90.github.io/suhaberportali'}/episodes/podcast_latest.mp3"
        }
    }
    
    res = send_daily_podcast_to_whatsapp(dummy_podcast, items, config.PUBLIC_BASE_URL or "https://mserman90.github.io/suhaberportali", force=True)
    print("Sonuç:", res["status"], "| Sağlayıcı:", res["provider"])
