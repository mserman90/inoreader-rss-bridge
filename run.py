import uvicorn
from app.config import HOST, PORT

if __name__ == "__main__":
    print(f"==================================================")
    print(f" Inoreader RSS Bridge Başlatılıyor...")
    print(f" Sunucu adresi: http://localhost:{PORT}")
    print(f" Sabit RSS linki: http://localhost:{PORT}/rss.xml")
    print(f" Sabit Atom linki: http://localhost:{PORT}/atom.xml")
    print(f" Web Arayüzü: http://localhost:{PORT}/")
    print(f"==================================================")
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
