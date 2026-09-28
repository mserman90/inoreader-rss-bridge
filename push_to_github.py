#!/usr/bin/env python3
"""
push_to_github.py
Bu betik, yerel Git deposunu oluşturduğunuz GitHub deposuna push eder.
Kullanım:
    python push_to_github.py https://github.com/mserman90/inoreader-rss-bridge.git [GITHUB_TOKEN]
"""

import sys
from pathlib import Path
from dulwich.repo import Repo
from dulwich.porcelain import push

def main():
    if len(sys.argv) < 2:
        print("Kullanım: python push_to_github.py <REPO_URL> [GITHUB_TOKEN]")
        print("Örnek:   python push_to_github.py https://github.com/mserman90/inoreader-rss-bridge.git")
        return

    remote_url = sys.argv[1].strip()
    token = sys.argv[2].strip() if len(sys.argv) > 2 else None

    # URL içine token enjekte et (gerekirse)
    if token and "github.com" in remote_url and "@" not in remote_url:
        remote_url = remote_url.replace("https://", f"https://{token}@")

    repo_dir = Path(__file__).resolve().parent
    repo = Repo(str(repo_dir))

    print(f"[*] Depo push ediliyor: {remote_url}")
    try:
        push(repo, remote_url, refspecs=b"refs/heads/main")
        print("[+] Başarıyla GitHub'a push edildi!")
    except Exception as e:
        print(f"[-] Push sırasında hata: {e}")
        print("\nİpucu: Eğer kurum güvenlik duvarınız GitHub bağlantılarını engelliyorsa,")
        print("bu klasörü VS Code veya GitHub web arayüzü ile doğrudan yükleyebilirsiniz.")

if __name__ == "__main__":
    main()
