import json

from backend.app.services.scraper import extract_page_data


url = "https://consiva.ai/"

data = extract_page_data(url )

print("Title:", data["title"])
print("Heading:", data["heading"])

print("\nFirst 10 paragraphs:")
for paragraph in data["paragraphs"][:10]:
    print("-", paragraph)

print("\nFirst 20 links:")
for link in data["links"][:20]:
    print("-", link["text"], link["url"])

with open(
    "consiva_scraped_data.json",
    "w",
    encoding="utf-8"
) as file:
    json.dump(
        data,
        file,
        ensure_ascii=False,
        indent=2
    )

print("\nData saved to consiva_scraped_data.json")
