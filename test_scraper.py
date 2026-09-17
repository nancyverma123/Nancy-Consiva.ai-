from datetime import datetime, timezone
from pathlib import Path

from backend.app.services.scraper import extract_page_data


url = "https://consiva.ai/"
data = extract_page_data(url )

output_path = Path(
    "backend/data/consiva_website_scraped.txt"
)

collected_at = datetime.now(timezone.utc).isoformat()

with output_path.open("w", encoding="utf-8") as file:
    file.write(f"Source URL: {data['url']}\n")
    file.write(f"Collected at: {collected_at}\n\n")

    file.write(f"Page title: {data['title']}\n")
    file.write(f"Main heading: {data['heading']}\n\n")

    file.write("Website content:\n\n")

    for paragraph in data["paragraphs"]:
        file.write(paragraph + "\n\n")

print(f"Scraped data saved to: {output_path}")
