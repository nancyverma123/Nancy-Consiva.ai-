import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


def fetch_html(url: str) -> str:
    """
    Website ka raw HTML download karta hai.
    """

    headers = {
        "User-Agent": "ConsivaResearchBot/1.0"
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=15
    )

    response.raise_for_status()

    # Website ki encoding detect karke text decode karna
    response.encoding = response.apparent_encoding or "utf-8"

    return response.text


def extract_page_data(url: str) -> dict:
    """
    Website ke HTML se title, heading, paragraphs aur links extract karta hai.
    """

    html = fetch_html(url)

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # Page title extract karein
    title = ""

    if soup.title:
        title = soup.title.get_text(
            " ",
            strip=True
        )

    # Main heading extract karein
    heading = ""

    heading_element = soup.select_one("h1")

    if heading_element:
        heading = heading_element.get_text(
            " ",
            strip=True
        )

    # Paragraphs extract karein
    paragraphs = []

    for paragraph in soup.select("p"):
        text = paragraph.get_text(
            " ",
            strip=True
        )

        if text:
            paragraphs.append(text)

    # Links extract karein
    links = []

    for link in soup.select("a[href]"):
        link_text = link.get_text(
            " ",
            strip=True
        )

        link_url = urljoin(
            url,
            link["href"]
        )

        links.append({
            "text": link_text,
            "url": link_url
        })

    return {
        "url": url,
        "title": title,
        "heading": heading,
        "paragraphs": paragraphs,
        "links": links
    }
