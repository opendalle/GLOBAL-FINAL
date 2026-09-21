from bs4 import BeautifulSoup
from datetime import datetime
from crawler.base_crawler import BaseCrawler

# High-signal roles — companies hire these ONLY when setting up/expanding physical office
OFFICE_SIGNAL_ROLES = [
    "facilities manager",
    "workplace manager",
    "head of real estate",
    "real estate manager",
    "office administrator",
    "admin manager",
    "campus manager",
    "site operations manager",
]

# (naukri-url-keyword, city, confidence_boost)
NAUKRI_TARGETS = [
    ("facilities-manager", "Bengaluru", 35),
    ("facilities-manager", "Hyderabad", 35),
    ("facilities-manager", "Pune", 35),
    ("workplace-manager", "Bengaluru", 30),
    ("workplace-manager", "Mumbai", 30),
    ("head-of-real-estate", "Mumbai", 40),
    ("head-of-real-estate", "Bengaluru", 40),
    ("real-estate-manager", "Pune", 35),
    ("real-estate-manager", "Hyderabad", 35),
    ("campus-manager", "Bengaluru", 30),
    ("campus-manager", "Hyderabad", 30),
    ("office-administrator", "Mumbai", 20),
    ("office-administrator", "Pune", 20),
    ("site-operations-manager", "Hyderabad", 25),
    ("site-operations-manager", "Chennai", 25),
]


class JobBoardCrawler(BaseCrawler):
    def __init__(self):
        super().__init__(delay=3)
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-IN,en;q=0.9",
        })

    def crawl_naukri(self) -> list:
        articles = []
        for keyword, city, confidence_boost in NAUKRI_TARGETS:
            url = f"https://www.naukri.com/{keyword}-jobs-in-{city.lower()}"
            html = self.fetch(url)
            if not html:
                continue

            soup = BeautifulSoup(html, "lxml")
            count = 0

            for card in soup.select(".jobTuple, .cust-job-tuple, article.jobTuple"):
                title_el = card.select_one(".title, .job-title, a.title")
                company_el = card.select_one(".companyName, .comp-name, a.comp-name")
                location_el = card.select_one(".location, .loc-link, li.location")

                if not title_el or not company_el:
                    continue

                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True)
                location = location_el.get_text(strip=True) if location_el else city
                role_lower = title.lower()

                # Only include if role matches office signal keywords
                if not any(role in role_lower for role in OFFICE_SIGNAL_ROLES):
                    continue

                count += 1
                articles.append({
                    "title": f"{company} hiring {title} in {city}",
                    "text": (
                        f"{company} is actively hiring a {title} in {city}. "
                        f"This is a high-confidence CRE demand signal — "
                        f"companies hire {title.lower()} only when setting up "
                        f"or expanding a physical office."
                    ),
                    "url": url,
                    "source": "NAUKRI_JOBS",
                    "company_hint": company,
                    "location_hint": location,
                    "signal_type_hint": "HIRING",
                    "confidence_boost": confidence_boost,
                    "published": datetime.now().isoformat(),
                    "region": "India",
                    "country": "India",
                })

            print(f"[NaukriCrawler] {keyword} in {city}: {count} signal hits")

        print(f"[NaukriCrawler] Total: {len(articles)} high-signal hiring leads")
        return articles

    def crawl(self) -> list:
        return self.crawl_naukri()
