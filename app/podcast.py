"""
app/podcast.py
Günlük Su ve Tarımsal Sulama Haberleri Podcast Üreticisi.
1. Güncel haberleri analiz ederek akıcı bir Türkçe sesli bülten metni hazırlar.
2. edge-tts ile yüksek kaliteli nöral Türkçe seslendirme yapar (.mp3).
3. Apple Podcasts, Spotify ve RSS okuyucularıyla %100 uyumlu podcast.xml üretir.
4. Hem son bölümü hem de arşiv bölümlerini saklar.
"""

import os
import sys
import json
import asyncio
import html
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

try:
    import edge_tts
except ImportError:
    edge_tts = None

def clean_for_speech(text: str) -> str:
    """Metni ses sentezleyici için doğal konuşma diline temizler."""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'https?://\S+', '', text)
    # Özel sembolleri ve kısaltmaları temizle
    text = text.replace("&", "ve").replace("%", "yüzde ")
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def build_podcast_script(items: List[Dict[str, Any]], date_str: str) -> str:
    """Haber listesinden doğal konuşma dilinde bir podcast bülteni senaryosu oluşturur."""
    top_items = items[:5]
    if not top_items:
        return "Merhaba! Su Haber Bülteni'ne hoş geldiniz. Bugün için henüz yeni bir makale kaydı bulunmuyor."

    script_parts = [
        f"Merhaba! Su Haber Bülteni'nin {date_str} tarihli günlük sesli podcast yayınına hoş geldiniz.",
        "Bugün öne çıkan tarımsal sulama, su kaynakları ve hidroloji araştırmalarını sizler için derledik.",
        "İşte bugünün dikkat çeken gelişmeleri:"
    ]

    for idx, it in enumerate(top_items, 1):
        title = it.get("title_tr") or it.get("title", "")
        summary = it.get("summary_tr") or it.get("description", "")
        category = it.get("category_tr", "Su Kaynakları")
        source = it.get("source_feed", "Bilimsel Araştırma")

        clean_title = clean_for_speech(title)
        clean_sum = clean_for_speech(summary)
        # Özet çok uzunsa ilk 2 cümleyi al
        sentences = [s.strip() for s in clean_sum.split('.') if len(s.strip()) > 10]
        short_summary = ". ".join(sentences[:2]) if sentences else clean_sum[:250]
        if short_summary and not short_summary.endswith('.'):
            short_summary += '.'

        script_parts.append(
            f"{idx}. haberimiz {category} alanında, {source} kaynağından: {clean_title}. {short_summary}"
        )

    script_parts.append(
        "Bugünkü sesli bültenimizin sonuna geldik. Tüm bu araştırmaların tam metinlerine ve detaylı analizlerine sitemizden ulaşabilirsiniz. "
        "Yarın sabah yeni bültenimizde görüşmek üzere, suyla ve sağlıkla kalın."
    )

    return "\n\n".join(script_parts)

async def synthesize_speech(text: str, output_path: Path, voice: str = "tr-TR-AhmetNeural"):
    """Metni MP3 olarak sentezler."""
    if edge_tts is None:
        raise RuntimeError("edge-tts kütüphanesi yüklü değil!")
    
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))

def generate_podcast_rss(
    episodes: List[Dict[str, Any]],
    feed_title: str,
    feed_description: str,
    public_url: str,
    feed_rss_url: str
) -> str:
    """iTunes ve Spotify uyumlu Podcast RSS 2.0 XML'i üretir."""
    now_rfc822 = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    items_xml = []
    for ep in episodes:
        title = html.escape(ep.get("title", "Günlük Sesli Bülten"))
        desc = html.escape(ep.get("description", ""))
        audio_url = ep.get("audio_url", "")
        file_size = ep.get("file_size_bytes", 0)
        pub_date = ep.get("rfc822_date", now_rfc822)
        guid = ep.get("guid", audio_url)
        duration = ep.get("duration", "04:30")

        items_xml.append(f"""    <item>
      <title>{title}</title>
      <description>{desc}</description>
      <link>{audio_url}</link>
      <guid isPermaLink="false">{guid}</guid>
      <pubDate>{pub_date}</pubDate>
      <enclosure url="{audio_url}" length="{file_size}" type="audio/mpeg" />
      <itunes:author>Su Haber Bülteni</itunes:author>
      <itunes:summary>{desc}</itunes:summary>
      <itunes:duration>{duration}</itunes:duration>
      <itunes:explicit>no</itunes:explicit>
    </item>""")

    joined_items = "\n".join(items_xml)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{html.escape(feed_title)}</title>
    <link>{public_url}</link>
    <atom:link href="{feed_rss_url}" rel="self" type="application/rss+xml" />
    <language>tr</language>
    <itunes:author>Su Haber Bülteni</itunes:author>
    <itunes:summary>{html.escape(feed_description)}</itunes:summary>
    <description>{html.escape(feed_description)}</description>
    <itunes:owner>
      <itunes:name>Su Haber Bülteni</itunes:name>
      <itunes:email>podcast@suhaberportali.local</itunes:email>
    </itunes:owner>
    <itunes:category text="Science">
      <itunes:category text="Earth Sciences"/>
    </itunes:category>
    <itunes:category text="Technology"/>
    <itunes:explicit>no</itunes:explicit>
    <lastBuildDate>{now_rfc822}</lastBuildDate>
    <image>
      <url>https://images.unsplash.com/photo-1544717305-2782549b5136?w=600&amp;q=80</url>
      <title>{html.escape(feed_title)}</title>
      <link>{public_url}</link>
    </image>
{joined_items}
  </channel>
</rss>
"""

def generate_daily_podcast(items: List[Dict[str, Any]], dist_dir: Path, public_base_url: str) -> Dict[str, Any]:
    """
    Günlük podcast bölümünü üretir, dist/episodes içine MP3 olarak kaydeder
    ve dist/podcast.xml dosyasını günceller.
    """
    episodes_dir = dist_dir / "episodes"
    episodes_dir.mkdir(parents=True, exist_ok=True)
    
    data_dir = dist_dir.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    meta_path = data_dir / "podcast_episodes.json"

    # Mevcut bölümleri yükle
    episodes = []
    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                episodes = json.load(f)
        except Exception:
            episodes = []

    now = datetime.now(timezone.utc)
    today_key = now.strftime("%Y%m%d")
    date_display = now.strftime("%d.%m.%Y")
    rfc822_date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

    filename_dated = f"podcast_{today_key}.mp3"
    filepath_dated = episodes_dir / filename_dated
    filepath_latest = episodes_dir / "podcast_latest.mp3"

    print(f"[*] Günlük Podcast metni hazırlanıyor ({date_display})...")
    script = build_podcast_script(items, date_display)

    # Ses dosyasını sentezle (eğer bugün henüz üretilmediyse veya zorunluysa)
    if not filepath_dated.exists() or filepath_dated.stat().st_size < 1000:
        print(f"[*] Edge-TTS ile ses dosyası oluşturuluyor: {filename_dated}...")
        try:
            asyncio.run(synthesize_speech(script, filepath_dated))
            # latest.mp3 olarak da kopyala
            import shutil
            shutil.copy2(filepath_dated, filepath_latest)
            print(f"[+] Podcast ses dosyası başarıyla üretildi: {filepath_dated.stat().st_size} bayt")
        except Exception as e:
            print(f"[!] Podcast ses sentezi hatası: {e}")
            # Hata durumunda mevcut latest varsa onu koru
    else:
        print(f"[*] Bugünün podcasti zaten mevcut: {filename_dated}")
        if not filepath_latest.exists() and filepath_dated.exists():
            import shutil
            shutil.copy2(filepath_dated, filepath_latest)

    file_size = filepath_dated.stat().st_size if filepath_dated.exists() else 0
    audio_public_url = f"{public_base_url}/episodes/{filename_dated}"
    latest_public_url = f"{public_base_url}/episodes/podcast_latest.mp3"

    new_ep = {
        "guid": f"suhaber-{today_key}",
        "title": f"Su & Sulama Günlük Bülteni - {date_display}",
        "description": f"{date_display} tarihli güncel su, tarımsal sulama ve hidroloji araştırmalarının sesli özeti.",
        "filename": filename_dated,
        "audio_url": audio_public_url,
        "file_size_bytes": file_size,
        "rfc822_date": rfc822_date,
        "date_key": today_key,
        "duration": "03:45"
    }

    # Listeyi güncelle (en yeni en başta)
    episodes = [ep for ep in episodes if ep.get("date_key") != today_key]
    episodes.insert(0, new_ep)

    # Meta veriyi kaydet
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(episodes, f, ensure_ascii=False, indent=2)

    # Sabit podcast.xml üret
    podcast_xml = generate_podcast_rss(
        episodes=episodes,
        feed_title="Su Haber Bülteni - Günlük Podcast",
        feed_description="Türkiye ve Dünya Su, Sulama ve Hidroloji Araştırmaları Günlük Sesli Bülteni",
        public_url=public_base_url,
        feed_rss_url=f"{public_base_url}/podcast.xml"
    )
    podcast_xml_path = dist_dir / "podcast.xml"
    podcast_xml_path.write_text(podcast_xml, encoding="utf-8")
    print(f"[+] Sabit Podcast RSS başarıyla üretildi: {podcast_xml_path}")

    return {
        "latest_episode": new_ep,
        "latest_audio_url": latest_public_url,
        "podcast_rss_url": f"{public_base_url}/podcast.xml"
    }
