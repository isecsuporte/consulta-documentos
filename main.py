# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
import requests
from bs4 import BeautifulSoup, Tag

app = FastAPI(
    title="Consulta de documentos Intelbras - PDF Scraper API",
    description="API que recebe a URL de uma página de produto Intelbras e retorna títulos, datas e links de manuais, fichas técnicas e tutoriais.",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MODELS
class ScrapeRequest(BaseModel):
    url: HttpUrl


class Document(BaseModel):
    title: Optional[str]
    url: HttpUrl
    date: Optional[str] = None


class ScrapeResponse(BaseModel):
    manuals: Optional[List[Document]]
    datasheets: Optional[List[Document]]
    #tutorials: Optional[List[Document]]


# UTILS
def fetch_html(url: str) -> BeautifulSoup:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Erro ao buscar a página: {e}")


def extract_documents(section_li: Tag) -> List[Document]:
    documents = []

    for row in section_li.select("table.unstriped tbody tr"):
        title_span = row.find('span', class_='text--300')
        if not title_span:
            continue

        date_span = title_span.find('span', class_='download-info')
        date = date_span.text.strip() if date_span else None
        if date_span:
            date_span.extract()

        title = title_span.get_text(strip=True)
        link = row.find('a', href=True)
        if not link:
            continue

        documents.append(Document(title=title, url=link['href'], date=date))

    return documents


def extract_section_documents(soup: BeautifulSoup, section_name: str) -> List[Document]:
    section = soup.find('li', attrs={'data-ga-name': section_name})
    return extract_documents(section) if section else []


def fallback_extract(soup: BeautifulSoup, keyword: str) -> List[Document]:
    fallback_docs = []
    for link in soup.select('a.product-help-and-download--download-link[href$=".pdf"]'):
        action = link.get('data-ga-action', '').lower()
        href = link.get('href')

        if not href:
            continue

        if keyword == 'manual' and 'manual' in action:
            fallback_docs.append(Document(title=None, url=href))
        elif keyword == 'datasheet' and ('ficha-tecnica' in action or 'datasheet' in href.lower()):
            fallback_docs.append(Document(title=None, url=href))
        # elif keyword == 'tutorial' and 'tutoriais-pdf' in action:
        #    fallback_docs.append(Document(title=None, url=href))

    return fallback_docs


# ENDPOINT
@app.post("/consultar-documentos", response_model=ScrapeResponse)
def scrape_documents(request: ScrapeRequest) -> ScrapeResponse:
    soup = fetch_html(request.url)

    manuals = extract_section_documents(soup, 'manuais')
    datasheets = extract_section_documents(soup, 'ficha-tecnica')
    #tutorials = extract_section_documents(soup, 'tutoriais-pdf')

    if not manuals:
        manuals = fallback_extract(soup, 'manual')
    if not datasheets:
        datasheets = fallback_extract(soup, 'datasheet')
    #if not tutorials:
    #    tutorials = fallback_extract(soup, 'tutorial')

    return ScrapeResponse(
        manuals=manuals or None,
        datasheets=datasheets or None,
        #tutorials=tutorials or None
    )

# Rodar localmente com:
# uvicorn main:app --reload --host 0.0.0.0 --port 8000
