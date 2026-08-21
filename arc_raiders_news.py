import os
import json
import requests
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

NEWS_URL = "https://arcraiders.com/es/news"
STATE_FILE = "state.json"

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK"]


def load_state():
    if not os.path.exists(STATE_FILE):
        return None

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("latest_url")
    except Exception:
        return None


def save_state(url):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "latest_url": url,
                "updated_at": datetime.now(timezone.utc).isoformat()
            },
            f,
            ensure_ascii=False,
            indent=2
        )


def get_news():

    print("Abriendo página oficial de ARC Raiders...")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1920,
                "height": 1080
            },
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140.0 Safari/537.36"
            )
        )

        try:

            response = page.goto(
                NEWS_URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

            print(
                "Código HTTP:",
                response.status if response else "desconocido"
            )

            page.wait_for_timeout(5000)

            print(
                "Título de página:",
                page.title()
            )

            # Guardamos HTML por si necesitamos depurar
            html = page.content()

            with open(
                "debug_page.html",
                "w",
                encoding="utf-8"
            ) as f:
                f.write(html)

            # ------------------------------------------------
            # Buscar enlaces de noticias
            # ------------------------------------------------

            links = page.locator(
                'a[href*="/news/"]'
            )

            count = links.count()

            print(
                "Enlaces /news/ encontrados:",
                count
            )

            articles = []

            seen = set()

            for i in range(count):

                link = links.nth(i)

                try:

                    href = link.get_attribute(
                        "href"
                    )

                    if not href:
                        continue

                    if not href.startswith(
                        "/news/"
                    ):
                        continue

                    url = (
                        "https://arcraiders.com"
                        + href
                    )

                    if url in seen:
                        continue

                    seen.add(url)

                    text = (
                        link.inner_text(
                            timeout=5000
                        )
                        .strip()
                    )

                    if not text:
                        continue

                    # Limpiar saltos de línea
                    text = " ".join(
                        text.split()
                    )

                    articles.append(
                        {
                            "title": text,
                            "url": url
                        }
                    )

                    print(
                        f"{len(articles)}.",
                        text,
                        url
                    )

                except Exception as error:

                    print(
                        "No se pudo leer enlace:",
                        error
                    )

            browser.close()

            return articles

        except Exception:

            browser.close()
            raise


def send_discord(article):

    embed = {

        "title": "🟡 NUEVA NOTICIA — ARC RAIDERS",

        "description": (
            f"## {article['title']}\n\n"
            f"📰 **Embark Studios ha publicado "
            f"una nueva noticia.**\n\n"
            f"🔗 [Leer noticia oficial]"
            f"({article['url']})"
        ),

        "url": article["url"],

        "color": 0xF5C400,

        "author": {
            "name": "Embark Studios"
        },

        "footer": {
            "text": (
                "El Talero Server • ARC Raiders News"
            )
        }
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

    print(
        "✅ Noticia enviada a Discord:",
        article["title"]
    )


def main():

    print(
        "======================================"
    )

    print(
        "ARC RAIDERS → DISCORD"
    )

    print(
        "======================================"
    )

    news = get_news()

    if not news:

        raise RuntimeError(
            "No se encontraron enlaces de "
            "noticias en la página oficial."
        )

    print(
        "Noticias encontradas:",
        len(news)
    )

    latest = news[0]

    print(
        "Primera noticia:",
        latest["title"]
    )

    print(
        "URL:",
        latest["url"]
    )

    previous_url = load_state()

    # --------------------------------------------------------
    # Primera ejecución
    # --------------------------------------------------------

    if previous_url is None:

        print(
            "Primera ejecución."
        )

        print(
            "Guardando la noticia actual "
            "sin enviarla a Discord."
        )

        save_state(
            latest["url"]
        )

        return

    # --------------------------------------------------------
    # No hay novedades
    # --------------------------------------------------------

    if latest["url"] == previous_url:

        print(
            "No hay noticias nuevas."
        )

        return

    # --------------------------------------------------------
    # Encontrar nuevas noticias
    # --------------------------------------------------------

    new_articles = []

    for article in news:

        if article["url"] == previous_url:
            break

        new_articles.append(
            article
        )

    # Orden cronológico
    new_articles.reverse()

    print(
        "Noticias nuevas:",
        len(new_articles)
    )

    # --------------------------------------------------------
    # Publicar
    # --------------------------------------------------------

    for article in new_articles:

        send_discord(
            article
        )

    save_state(
        latest["url"]
    )

    print(
        "======================================"
    )

    print(
        "✅ PROCESO FINALIZADO CORRECTAMENTE"
    )

    print(
        "======================================")


if __name__ == "__main__":
    main()
