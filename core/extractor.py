from bs4 import BeautifulSoup


def extract_page_data(html, url):

    soup = BeautifulSoup(html, "lxml")

    title = soup.title.string if soup.title else "No Title"

    text = soup.get_text(separator=" ", strip=True)

    text = text[:1000]

    data = {
        "url": url,
        "title": title,
        "text": text
    }

    return data