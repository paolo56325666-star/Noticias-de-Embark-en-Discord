import os
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

NEWS_URL = "https://arcraiders.com/es/news"
STATE_FILE = "state.json"

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK"]

MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/140 Safari/537.36"
    )
}


def load_state():
    if not os.path.exists(STATE_FILE):
        return None

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("latest_url")
    except Exception:
        return None


def save_state(url):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "latest_url": url,
                "updated_at": datetime.utcnow().isoformat()
            },
            f,
            ensure_ascii=False,
            indent=2,
        )


def parse_date(text):
    pattern = r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})"

    match = re.search(pattern, text.lower())

    if not match:
        return None

    day = int(match.group(1))
    month_name = match.group(2)
    year = int(match.group(3))

    month = MONTHS.get(month_name)

    if not month:
        return None

    return datetime(year, month, day)


def get_news():
    response = requests.get(
        NEWS_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    articles = []

    for link in soup.find_all("a", href=True):

        href = link.get("href", "").strip()

        if not href.startswith("/es/news/"):
            continue

        title_text = " ".join(link.stripped_strings)

        if not title_text:
            continue

        date = parse_date(title_text)

        if not date:
            continue

        title = re.sub(
            r"\s*\d{1,2}\s+de\s+[a-záéíóú]+\s+de\s+\d{4}",
            "",
            title_text,
            flags=re.IGNORECASE,
        ).strip()

        if not title:
            continue

        if href.startswith("/"):
            url = "https://arcraiders.com" + href
        else:
            url = href

        articles.append(
            {
                "title": title,
                "url": url,
                "date": date,
            }
        )

    unique = {}

    for article in articles:
        unique[article["url"]] = article

    articles = list(unique.values())

    articles.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    return articles


def get_article_data(url):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        description = ""

        meta_description = soup.find(
            "meta",
            attrs={"name": "description"}
        )

        if meta_description:
            description = meta_description.get(
                "content",
                ""
            ).strip()

        image = ""

        og_image = soup.find(
            "meta",
            attrs={"property": "og:image"}
        )

        if og_image:
            image = og_image.get(
                "content",
                ""
            ).strip()

        return description, image

    except Exception as e:
        print("No se pudo obtener información adicional:", e)
        return "", ""


def send_discord(article):
    description, image = get_article_data(
        article["url"]
    )

    embed = {
        "title": "🟡 NUEVA NOTICIA — ARC RAIDERS",
        "description": (
            f"**{article['title']}**\n\n"
            f"{description[:500]}\n\n"
            f"📅 {article['date'].strftime('%d/%m/%Y')}\n"
            f"🔗 [Leer noticia oficial]({article['url']})"
        ),
        "url": article["url"],
        "color": 0xF5C400,
        "footer": {
            "text": "El Talero Server • ARC Raiders News"
        },
    }

    if image:
        embed["image"] = {
            "url": image
        }

    payload = {
        "username": "ARC Raiders News",
        "embeds": [embed]
    }

    response = requests.post(
        WEBHOOK_URL,
        json=payload,
        timeout=30
    )

    response.raise_for_status()


def main():

    print("Comprobando noticias de ARC Raiders...")

    news = get_news()

    if not news:
        raise RuntimeError(
            "No se encontraron noticias."
        )

    latest = news[0]

    print(
        "Última noticia:",
        latest["title"],
        latest["url"]
    )

    previous_url = load_state()

    # Primera ejecución:
    # guarda la noticia actual sin enviarla,
    # evitando que Discord reciba todas las noticias antiguas.
    if previous_url is None:
        print(
            "Primera ejecución. "
            "Guardando noticia actual como referencia."
        )

        save_state(latest["url"])
        return

    if latest["url"] == previous_url:
        print("No hay noticias nuevas.")
        return

    new_articles = []

    for article in news:

        if article["url"] == previous_url:
            break

        new_articles.append(article)

    new_articles.reverse()

    print(
        f"Noticias nuevas encontradas: "
        f"{len(new_articles)}"
    )

    for article in new_articles:

        print(
            "Publicando:",
            article["title"]
        )

        send_discord(article)

    save_state(latest["url"])

    print("Proceso terminado correctamente.")


if __name__ == "__main__":
    main()
