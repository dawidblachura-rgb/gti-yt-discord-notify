"""Wysyła na Discorda (webhook) wiadomość o każdym nowym DŁUGIM filmie z kanału YouTube.

Shortsy są pomijane: feed z playlisty "UULF..." zawiera tylko długie filmy kanału.
Stan (już ogłoszone filmy) trzymany jest w state.json. Przy pierwszym uruchomieniu
skrypt tylko zapamiętuje obecne filmy i nic nie wysyła, żeby nie spamować starymi.

Zmienne środowiskowe:
    WEBHOOK_URL   - adres webhooka kanału #nowe-filmy (sekret)
    YT_CHANNEL_ID - ID kanału YouTube (UC...)
    PING_ROLE_ID  - ID roli do pingowania (opcjonalnie)
"""

import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

STATE = Path(__file__).with_name("state.json")
NS = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
MAX_POSTS_PER_RUN = 3  # zabezpieczenie przed spamem, gdyby feed zwrócił coś dziwnego
KEEP_IDS = 100


def fetch_videos(channel_id):
    url = f"https://www.youtube.com/feeds/videos.xml?playlist_id=UULF{channel_id.removeprefix('UC')}"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as resp:
        root = ET.fromstring(resp.read())
    videos = []
    for entry in root.findall("atom:entry", NS):
        videos.append({
            "id": entry.find("yt:videoId", NS).text,
            "title": entry.find("atom:title", NS).text,
            "published": entry.find("atom:published", NS).text,
        })
    return sorted(videos, key=lambda v: v["published"])  # od najstarszego


def post(webhook, video, role_id):
    ping = f"<@&{role_id}> " if role_id else ""
    body = {
        "content": f"{ping}🎬 **Nowy film na kanale!**\n**{video['title']}**\nhttps://www.youtube.com/watch?v={video['id']}",
        "allowed_mentions": {"roles": [role_id] if role_id else []},
    }
    req = urllib.request.Request(webhook, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "GTI-YT-Notify"})
    urllib.request.urlopen(req, timeout=30).close()


def main():
    webhook = os.environ["WEBHOOK_URL"]
    channel_id = os.environ["YT_CHANNEL_ID"]
    role_id = os.environ.get("PING_ROLE_ID", "").strip()

    videos = fetch_videos(channel_id)
    if not STATE.exists():
        STATE.write_text(json.dumps({"posted": [v["id"] for v in videos]}, indent=2))
        print(f"Pierwsze uruchomienie: zapamiętano {len(videos)} filmów, nic nie wysłano.")
        return

    posted = json.loads(STATE.read_text())["posted"]
    new = [v for v in videos if v["id"] not in posted]
    if not new:
        print("Brak nowych filmów.")
        return

    for video in new[-MAX_POSTS_PER_RUN:]:
        post(webhook, video, role_id)
        print(f"Wysłano: {video['title']}")
    posted = (posted + [v["id"] for v in new])[-KEEP_IDS:]
    STATE.write_text(json.dumps({"posted": posted}, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
