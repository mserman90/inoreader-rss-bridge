# Inoreader Stream to RSS Bridge 📡

Bu uygulama, **Inoreader** üzerindeki herhangi bir herkese açık HTML akış sayfasını (özellikle `https://www.inoreader.com/stream/user/1006125058/tag/SU/view/html?cs=m` sayfasını) periyodik olarak tarayarak, RSS okuyucularınızda (Feedly, NetNewsWire, Thunderbird, Inoreader, Outlook, Reeder vb.) doğrudan kullanabileceğiniz **sabit ve standart bir RSS 2.0 / Atom yayınına** dönüştürür.

---

## 💡 Neden Bu Köprüye İhtiyaç Var?

Inoreader, akışlar için yerel RSS çıktısı (`/stream/user/.../tag/...`) sunmaktadır; ancak bu özellik **"Inoreader Pro" ücretli aboneliği** arkasında kilitlidir (`Feed suspended! Please contact the owner. Inoreader Pro plan is required to export RSS feeds`).

Buna karşılık ilgili akışın web görünümü (`/view/html?cs=m`) herkese açıktır ve tüm güncellemeleri barındırır. Bu uygulama:
1. İlgili HTML sayfasını periyodik aralıklarla kontrol eder.
2. Makale başlıklarını, kaynak linklerini, yazarları, yayınlandığı dergi/bülten adlarını, özetleri, tarihleri ve kapak görsellerini ayrıştırır.
3. Cloudflare e-posta gizlemelerini çözer.
4. SQLite veritabanında geçmişi saklayarak her öğeye kalıcı bir `GUID` ve yayın tarihi atar (tarih kaymalarını önler).
5. Sabit bir link üzerinden standart **RSS 2.0**, **Atom 1.0** ve **JSON Feed** formatlarında yayın yapar.

---

## 📁 Proje Dizin Yapısı

```text
inoreader-rss-bridge/
├── app/
│   ├── __init__.py
│   ├── config.py             # Konfigürasyon ve ortam değişkenleri
│   ├── scraper.py            # Inoreader HTML ayrıştırıcı & makale çıkarıcı
│   ├── storage.py            # SQLite kalıcı önbellek & geçmiş yönetimi
│   ├── feed.py               # RSS 2.0, Atom 1.0 ve JSON Feed XML/JSON üretici
│   └── main.py               # FastAPI web sunucusu & arka plan periyodik görevi
├── dist/                     # Statik dışa aktarım dosyaları (rss.xml, atom.xml...)
├── export_static.py          # Statik dosya üreten bağımsız betik (GitHub Actions / Cron için)
├── run.py                    # Yerel sunucu başlatma betiği
├── requirements.txt          # Python bağımlılıkları
├── Dockerfile                # Docker imaj tanımı
├── docker-compose.yml        # Docker Compose yapılandırması
├── .github/
│   └── workflows/
│       └── update_feed.yml   # 7/24 ücretsiz GitHub Pages otomasyon iş akışı
└── README.md
```

---

## 🚀 Çalıştırma Yöntemleri

İhtiyacınıza göre aşağıdaki 3 yöntemden birini seçebilirsiniz:

### Yöntem 1: Yerel Bilgisayarda veya Kendi Sunucunuzda (Python ile)

1. **Bağımlılıkları yükleyin:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Sunucuyu başlatın:**
   ```bash
   python run.py
   ```

3. **Erişim sağlayın:**
   * **Web Yönetim Paneli:** `http://localhost:8000/`
   * **Sabit RSS 2.0 Linki:** `http://localhost:8000/rss.xml` (veya `http://localhost:8000/feed`)
   * **Sabit Atom Linki:** `http://localhost:8000/atom.xml`
   * **JSON Feed Linki:** `http://localhost:8000/feed.json`
   * **Sağlık Durumu:** `http://localhost:8000/health`

---

### Yöntem 2: Docker & Docker Compose ile (Sunucuda Tek Komutla)

Kendi sanal sunucunuzda (VPS) 7/24 kesintisiz çalıştırmak için:

```bash
docker compose up -d
```

* Uygulama arka planda başlar, SQLite verilerini `inoreader-data` volume'ünde saklar.
* Port: `8000` (dilerseniz `docker-compose.yml` içinden değiştirebilirsiniz).

---

### Yöntem 3: Tamamen Ücretsiz ve Sunucusuz (GitHub Pages + Actions)

Kendi bilgisayarınızı açık tutmak ya da sunucu kiralamak istemiyorsanız, GitHub'ın ücretsiz altyapısını kullanabilirsiniz:

1. Bu klasördeki dosyaları yeni bir GitHub deposuna yükleyin (Push edin).
2. Deponuzun **Settings > Pages** sekmesine gidin:
   * **Build and deployment > Source** seçeneğini **GitHub Actions** olarak ayarlayın.
3. `.github/workflows/update_feed.yml` iş akışı her 30 dakikada bir otomatik çalışacak, akışı çekip GitHub Pages'e yükleyecektir.
4. Sabit RSS linkiniz otomatik olarak şu adrese dönüşecektir:
   ```text
   https://<kullanici-adiniz>.github.io/<repo-adiniz>/rss.xml
   ```
   Bu linki istediğiniz RSS okuyucuya kalıcı olarak ekleyebilirsiniz.

---

## ⚙️ Yapılandırma ve Ortam Değişkenleri (Environment Variables)

Aşağıdaki değişkenler sistem ortamından (`.env` veya `docker-compose.yml`) özelleştirilebilir:

| Değişken | Varsayılan Değer | Açıklama |
| :--- | :--- | :--- |
| `INOREADER_URL` | `https://www.inoreader.com/stream/user/1006125058/tag/SU/view/html?cs=m` | Kaynak Inoreader HTML akış bağlantısı |
| `FETCH_INTERVAL_MINUTES` | `15` | Kaynağın kaç dakikada bir taranacağı |
| `MAX_STORED_ITEMS` | `200` | Veritabanında saklanacak maksimum makale sayısı |
| `PORT` | `8000` | Web sunucusunun dinleyeceği port |
| `HOST` | `0.0.0.0` | Dinlenecek IP adresi |
| `FEED_TITLE` | `SU - Inoreader Akışı` | RSS başlığında görünecek isim |
| `FEED_DESCRIPTION` | `Inoreader SU akışı güncellemeleri` | RSS kanal açıklaması |
| `PUBLIC_BASE_URL` | *(Boş)* | Eğer ters vekil (Nginx/Cloudflare) arkasındaysanız genel domain adresi (örn. `https://rss.ornek.com`) |

---

## 🔍 Desteklenen Uç Noktalar (Endpoints)

* `GET /`: Canlı istatistikleri, sonraki güncelleme süresini, son makaleleri gösteren ve linkleri kopyalamanızı sağlayan modern gösterge paneli.
* `GET /rss.xml` veya `/feed`: RSS 2.0 formatında yayın çıktısı (`application/rss+xml`).
* `GET /atom.xml`: Atom 1.0 formatında yayın çıktısı (`application/atom+xml`).
* `GET /feed.json`: JSON Feed v1.1 formatında çıktı (`application/feed+json`).
* `POST /api/refresh` veya `GET /api/refresh`: Zamanlayıcıyı beklemeden hemen anında yeni veri çekmeyi tetikler.
* `GET /health` veya `/api/status`: Sistemin çalışma ve senkronizasyon durumunu JSON olarak döndürür.
