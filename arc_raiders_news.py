import os
import json
import html
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlparse

# ============================================================
# CONFIGURACIÓN
# ============================================================

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK"]

STATE_FILE = "state.json"

SEARCH_QUERY = quote(
    'site:arcraiders.com/news "ARC Raiders"'
)

GOOGLE_NEWS_URL = (
    "https://news.google.com/rss/search?"
    f"q={SEARCH_QUERY}"
    "&hl=es-419"
    "&gl=UY"
    "&ceid=UY:es-419"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    )
}

ALLOWED_DOMAIN = "arcraiders.com"


# ============================================================
# ESTADO
# ============================================================

def load_state():

    if not os.path.exists(STATE_FILE):
        return None

    try:

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

            return data.get("latest_guid")

    except Exception as error:

        print(
            "No se pudo leer state.json:",
            error
        )

        return None


def save_state(guid):

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as file:

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
# COMPROBAR SI UNA URL ES DE ARC RAIDERS
# ============================================================

def is_arc_raiders_url(url):

    if not url:
        return False

    try:

        parsed = urlparse(url)

        hostname = (
            parsed.hostname or ""
        ).lower()

        return (
            hostname == "arcraiders.com"
            or hostname.endswith(
                ".arcraiders.com"
            )
        )

    except Exception:

        return False


# ============================================================
# OBTENER NOTICIAS DESDE GOOGLE NEWS
# ============================================================

def get_google_news():

    print(
        "Consultando Google News RSS..."
    )

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

    root = ET.fromstring(
        response.content
    )

    items = root.findall(
        "./channel/item"
    )

    print(
        "Elementos encontrados en RSS:",
        len(items)
    )

    articles = []

    for item in items:

        title_element = item.find(
            "title"
        )

        link_element = item.find(
            "link"
        )

        guid_element = item.find(
            "guid"
        )

        date_element = item.find(
            "pubDate"
        )

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

        # ----------------------------------------------------
        # Fecha
        # ----------------------------------------------------

        try:

            date = parsedate_to_datetime(
                pub_date
            )

        except Exception:

            print(
                "No se pudo interpretar fecha:",
                pub_date
            )

            continue

        # ----------------------------------------------------
        # Resolver el enlace de Google
        # ----------------------------------------------------

        real_url = resolve_google_url(
            google_link
        )

        print(
            "Noticia encontrada:",
            title
        )

        print(
            "URL:",
            real_url
        )

        # ----------------------------------------------------
        # SOLO aceptar arcraiders.com
        # ----------------------------------------------------

        if not is_arc_raiders_url(
            real_url
        ):

            print(
                "Descartada: no pertenece "
                "a arcraiders.com"
            )

            continue

        # ----------------------------------------------------
        # Limpiar título
        # ----------------------------------------------------

        title = html.unescape(
            title
        )

        # Google puede añadir el nombre
        # del sitio al final.

        if " - ARC Raiders" in title:

            title = title.replace(
                " - ARC Raiders",
                ""
            ).strip()

        articles.append(
            {
                "title": title,
                "url": real_url,
                "guid": guid,
                "date": date
            }
        )

    # --------------------------------------------------------
    # Eliminar duplicados
    # --------------------------------------------------------

    unique = {}

    for article in articles:

        unique[
            article["url"]
        ] = article

    articles = list(
        unique.values()
    )

    # --------------------------------------------------------
    # Ordenar por fecha
    # --------------------------------------------------------

    articles.sort(
        key=lambda article: article["date"],
        reverse=True
    )

    print(
        "Noticias oficiales encontradas:",
        len(articles)
    )

    return articles


# ============================================================
# RESOLVER ENLACE DE GOOGLE NEWS
# ============================================================

def resolve_google_url(
    google_url
):

    try:

        response = requests.get(
            google_url,
            headers=HEADERS,
            timeout=30,
            allow_redirects=True
        )

        final_url = response.url

        if is_arc_raiders_url(
            final_url
        ):

            return final_url

    except Exception as error:

        print(
            "No se pudo resolver enlace:",
            error
        )

    return google_url


# ============================================================
# OBTENER IMAGEN DE LA NOTICIA
# ============================================================

def get_article_image(url):

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        if response.status_code != 200:

            return None

        # Buscamos og:image directamente
        # sin depender de BeautifulSoup.

        text = response.text

        marker = (
            'property="og:image"'
        )

        position = text.find(
            marker
        )

        if position == -1:

            marker = (
                "property='og:image'"
            )

            position = text.find(
                marker
            )

        if position == -1:

            return None

        section = text[
            position:
            position + 1000
        ]

        # content="..."
        content_marker = (
            'content="'
        )

        start = section.find(
            content_marker
        )

        if start == -1:

            content_marker = (
                "content='"
            )

            start = section.find(
                content_marker
            )

        if start == -1:

            return None

        start += len(
            content_marker
        )

        end = section.find(
            '"',
            start
        )

        if end == -1:

            end = section.find(
                "'",
                start
            )

        if end == -1:

            return None

        image = section[
            start:end
        ].strip()

        return image or None

    except Exception as error:

        print(
            "No se pudo obtener imagen:",
            error
        )

        return None


# ============================================================
# ENVIAR A DISCORD
# ============================================================

def send_discord(article):

    image = get_article_image(
        article["url"]
    )

    date = article[
        "date"
    ].astimezone(
        timezone.utc
    )

    embed = {

        "title": (
            "🟡 NUEVA NOTICIA — ARC RAIDERS"
        ),

        "description": (
            f"## {article['title']}\n\n"
            f"📅 **Publicado:** "
            f"{date.strftime('%d/%m/%Y %H:%M UTC')}\n\n"
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
        },

        "timestamp": date.isoformat()
    }

    if image:

        embed["image"] = {
            "url": image
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
        "✅ Enviada a Discord:",
        article["title"]
    )


# ============================================================
# PROGRAMA PRINCIPAL
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
            "No se encontraron noticias "
            "oficiales de ARC Raiders."
        )

    latest = articles[0]

    print(
        "Última noticia oficial:",
        latest["title"]
    )

    print(
        "URL:",
        latest["url"]
    )

    previous_guid = load_state()

    # ========================================================
    # PRIMERA EJECUCIÓN
    # ========================================================

    if previous_guid is None:

        print(
            "Primera ejecución."
        )

        print(
            "Guardando la noticia actual "
            "sin enviarla a Discord."
        )

        save_state(
            latest["guid"]
        )

        print(
            "✅ Estado guardado."
        )

        return

    # ========================================================
    # SIN NOVEDADES
    # ========================================================

    if latest["guid"] == previous_guid:

        print(
            "No hay noticias nuevas."
        )

        return

    # ========================================================
    # ENCONTRAR NOVEDADES
    # ========================================================

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
        "Nuevas noticias:",
        len(new_articles)
    )

    # ========================================================
    # PUBLICAR
    # ========================================================

    for article in new_articles:

        send_discord(
            article
        )

    # ========================================================
    # GUARDAR ESTADO
    # ========================================================

    save_state(
        latest["guid"]
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
