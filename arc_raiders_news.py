import os
import json
import html
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlparse, parse_qs

# ============================================================
# CONFIGURACIÓN
# ============================================================

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK"]

STATE_FILE = "state.json"

GOOGLE_NEWS_URL = (
    "https://news.google.com/rss/search?"
    "q=" + quote('site:arcraiders.com/news') +
    "&hl=es-419&gl=UY&ceid=UY:es-419"
)

ALLOWED_DOMAIN = "arcraiders.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    )
}


# ============================================================
# ESTADO
# ============================================================

def load_state():
    if not os.path.exists(STATE_FILE):
        return None

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data.get("latest_guid")

    except Exception as error:
        print("No se pudo leer state.json:", error)
        return None


def save_state(guid):
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(
            {
                "latest_guid": guid,
                "updated_at": datetime.now(
                    timezone.utc
                ).isoformat()
            },
            file,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# GOOGLE NEWS
# ============================================================

def get_google_news():
    print("Consultando Google News RSS...")

    response = requests.get(
        GOOGLE_NEWS_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    print(
        "Google News respondió:",
        response.status_code
    )

    root = ET.fromstring(response.content)

    articles = []

    for item in root.findall("./channel/item"):

        title_element = item.find("title")
        link_element = item.find("link")
        guid_element = item.find("guid")
        date_element = item.find("pubDate")
        source_element = item.find("source")

        if (
            title_element is None
            or link_element is None
            or guid_element is None
            or date_element is None
        ):
            continue

        title = (
            title_element.text or ""
        ).strip()

        google_link = (
            link_element.text or ""
        ).strip()

        guid = (
            guid_element.text or ""
        ).strip()

        pub_date = (
            date_element.text or ""
        ).strip()

        source_url = ""

        if source_element is not None:
            source_url = (
                source_element.attrib.get(
                    "url",
                    ""
                )
                .strip()
            )

        # ----------------------------------------------------
        # Solo aceptamos ARC Raiders / Embark
        # ----------------------------------------------------

        if ALLOWED_DOMAIN not in source_url.lower():

            # Algunas versiones del RSS pueden no incluir
            # correctamente el atributo source.
            # En ese caso intentamos detectar el dominio
            # dentro de la descripción/enlace.
            description_element = item.find(
                "description"
            )

            description = ""

            if description_element is not None:
                description = (
                    description_element.text or ""
                )

            combined = (
                google_link
                + " "
                + description
                + " "
                + title
            ).lower()

            if "arcraiders.com" not in combined:
                continue

        # ----------------------------------------------------
        # Fecha
        # ----------------------------------------------------

        try:
            date = parsedate_to_datetime(
                pub_date
            )

        except Exception:
            print(
                "Fecha inválida:",
                pub_date
            )
            continue

        # ----------------------------------------------------
        # Limpiar título
        # ----------------------------------------------------

        title = html.unescape(title)

        # Google suele añadir " - ARC Raiders"
        title = re.sub(
            r"\s+-\s+ARC Raiders\s*$",
            "",
            title,
            flags=re.IGNORECASE
        ).strip()

        articles.append(
            {
                "title": title,
                "google_link": google_link,
                "guid": guid,
                "date": date,
                "source_url": source_url
            }
        )

    # Más reciente primero
    articles.sort(
        key=lambda article: article["date"],
        reverse=True
    )

    # Eliminar duplicados
    unique = {}

    for article in articles:
        unique[article["guid"]] = article

    return list(unique.values())


# ============================================================
# OBTENER URL REAL DE ARC RAIDERS
# ============================================================

def get_real_url(google_url):
    """
    Google News utiliza enlaces intermedios.
    Intentamos obtener la URL oficial.
    """

    try:

        response = requests.get(
            google_url,
            headers=HEADERS,
            timeout=30,
            allow_redirects=True
        )

        final_url = response.url

        if ALLOWED_DOMAIN in final_url.lower():
            return final_url

    except Exception as error:
        print(
            "No se pudo resolver la URL:",
            error
        )

    return google_url


# ============================================================
# DESCRIPCIÓN
# ============================================================

def clean_description(text):

    if not text:
        return ""

    text = html.unescape(text)

    # Eliminar HTML
    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    if len(text) > 600:
        text = text[:597] + "..."

    return text


# ============================================================
# DISCORD
# ============================================================

def send_discord(article):

    real_url = get_real_url(
        article["google_link"]
    )

    title = article["title"]

    date = article["date"].astimezone(
        timezone.utc
    ).strftime("%d/%m/%Y %H:%M UTC")

    embed = {
        "title": "🟡 NUEVA NOTICIA — ARC RAIDERS",

        "description": (
            f"## {title}\n\n"
            f"📅 **Publicada:** {date}\n\n"
            f"🔗 [Leer noticia oficial]({real_url})"
        ),

        "url": real_url,

        "color": 0xF5C400,

        "author": {
            "name": "Embark Studios"
        },

        "footer": {
            "text": "El Talero Server • ARC Raiders News"
        },

        "timestamp": article[
            "date"
        ].astimezone(
            timezone.utc
        ).isoformat()
    }

    payload = {
        "username": "ARC Raiders News",

        "embeds": [
            embed
        ]
    }

    response = requests.post(
        WEBHOOK_URL,
        json=payload,
        timeout=30
    )

    response.raise_for_status()

    print(
        "Noticia enviada correctamente a Discord:"
    )

    print(title)


# ============================================================
# PRINCIPAL
# ============================================================

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

    articles = get_google_news()

    if not articles:
        raise RuntimeError(
            "Google News no devolvió ninguna "
            "noticia oficial de ARC Raiders."
        )

    print(
        f"Noticias oficiales encontradas: "
        f"{len(articles)}"
    )

    latest = articles[0]

    print(
        "Última noticia:",
        latest["title"]
    )

    print(
        "GUID:",
        latest["guid"]
    )

    previous_guid = load_state()

    # --------------------------------------------------------
    # Primera ejecución
    # --------------------------------------------------------

    if previous_guid is None:

        print(
            "Primera ejecución detectada."
        )

        print(
            "Guardando la noticia actual "
            "sin enviarla a Discord."
        )

        save_state(
            latest["guid"]
        )

        return

    # --------------------------------------------------------
    # No hay novedades
    # --------------------------------------------------------

    if latest["guid"] == previous_guid:

        print(
            "No hay noticias nuevas."
        )

        return

    # --------------------------------------------------------
    # Buscar todas las novedades
    # --------------------------------------------------------

    new_articles = []

    for article in articles:

        if article["guid"] == previous_guid:
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

    # --------------------------------------------------------
    # Actualizar estado
    # --------------------------------------------------------

    save_state(
        latest["guid"]
    )

    print(
        "======================================"
    )

    print(
        "Proceso finalizado correctamente."
    )

    print(
        "======================================"
    )


if __name__ == "__main__":
    main()
