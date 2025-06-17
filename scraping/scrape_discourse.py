import os
import json
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup

DISCOURCE_BASE_URL = "https://discourse.onlinedegree.iitm.ac.in"
CATEGORY_JSON_URL = f"{DISCOURCE_BASE_URL}/c/courses/tds-kb/34.json"
AUTH_FILE = "auth.json"
FROM_TIME = datetime(2025, 1, 1)
TO_TIME = datetime(2025, 4, 14)


def login(playwright):
    print("Authentication not found. Kindly login in manually via browser...")
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{DISCOURCE_BASE_URL}/login")
    print("Please log in manually using Google.")
    page.pause()
    context.storage_state(path=AUTH_FILE)
    print("Logged in.")
    browser.close()

def is_authenticated(page):
    try:
        page.goto(CATEGORY_JSON_URL, timeout=10)
        page.wait_for_selector("pre", timeout=50)
        json.loads(page.inner_text("pre"))
        return True
    except (TimeoutError, json.JSONDecodeError):
        return False

def scrape_from_discourse(playwright):
    print("Scraping data from discourse")
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(storage_state=AUTH_FILE)
    page = context.new_page()

    all_topics = []
    page_num = 0
    while True:
        paginated_url = f"{CATEGORY_JSON_URL}?page={page_num}"
        print(f"Page num: {page_num}...")
        page.goto(paginated_url)

        try:
            data = json.loads(page.inner_text("pre"))
        except:
            data = json.loads(page.content())

        topics = data.get("topic_list", {}).get("topics", [])
        if not topics:
            break

        all_topics.extend(topics)
        page_num += 1

    print(f"Total num of pages {len(all_topics)}")

    os.makedirs("downloaded_threads", exist_ok=True)
    files_downloaded = 0

    for topic in all_topics:
        created_at = parse_date(topic["created_at"])
        if FROM_TIME <= created_at <= TO_TIME:
            topic_url = f"{DISCOURCE_BASE_URL}/t/{topic['slug']}/{topic['id']}.json"
            page.goto(topic_url)
            try:
                data_from_topic = json.loads(page.inner_text("pre"))
            except:
                data_from_topic = json.loads(page.content())

            for post in data_from_topic.get("post_stream", {}).get("posts", []):
                if "cooked" in post:
                    post["cooked"] = BeautifulSoup(post["cooked"], "html.parser").get_text()

            filename = f"{topic['slug']}_{topic['id']}.json"
            filepath = os.path.join("downloaded_threads", filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data_from_topic, f, indent=2)

            files_downloaded += 1

    print(f"{files_downloaded} JSONObjects scraped and saved to downloaded_threads/")
    browser.close()

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")

def main():
    with sync_playwright() as p:
        if not os.path.exists(AUTH_FILE):
            login(p)
        else:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=AUTH_FILE)
            page = context.new_page()
            if not is_authenticated(page):
                print("Invalid Session.")
                browser.close()
                login(p)
            else:
                print("Using existing session.")
                browser.close()

        scrape_from_discourse(p)

if __name__ == "__main__":
    main()
