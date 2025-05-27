# main.py
# API para coletar URLs de manuais e fichas técnicas de páginas de produto Intelbras

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import requests
from bs4 import BeautifulSoup

# Cria a instância da aplicação FastAPI com informações de metadados
app = FastAPI(
    title="Intelbras PDF Scraper API",  # Título da aplicação
    description="API que recebe a URL de uma página de produto Intelbras e retorna títulos e links dos manuais e fichas técnicas.",  # Descrição
    version="1.0.4"  # Versão da API
)

# Configuração de CORS (Cross-Origin Resource Sharing) para permitir chamadas da Wiki e localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://suporte.intelbras.com.br", "http://localhost:5500", "*"],  # Origens permitidas
    allow_credentials=True,        # Permitir credenciais (cookies, headers de autorização)
    allow_methods=["*"],          # Métodos HTTP permitidos
    allow_headers=["*"],          # Cabeçalhos permitidos
)

# Define o formato do corpo da requisição de scraping, contendo apenas uma URL válida
class ScrapeRequest(BaseModel):
    url: HttpUrl  # Pydantic assegura que a URL seja válida

# Modelo para representar um documento retornado (título + link)
class Document(BaseModel):
    title: str | None  # Título do documento (pode ser None)
    url: HttpUrl      # URL do PDF

# Modelo de resposta contendo listas de manuais e fichas técnicas
class ScrapeResponse(BaseModel):
    manuals: list[Document] | None     # Lista de manuais ou None
    datasheets: list[Document] | None  # Lista de fichas técnicas ou None

# Rota POST /scrape que recebe ScrapeRequest e retorna ScrapeResponse
@app.post("/scrape", response_model=ScrapeResponse)
def scrape_pdfs(request: ScrapeRequest):
    # Tentativa de buscar o HTML da página com cabeçalho customizado
    try:
        headers = {"User-Agent": "Mozilla/5.0"}  # Simula navegador para evitar bloqueios
        resp = requests.get(request.url, headers=headers, timeout=10)
        resp.raise_for_status()  # Lança erro se status != 200
    except requests.RequestException as e:
        # Retorna HTTP 400 com detalhe em caso de falha na requisição externa
        raise HTTPException(status_code=400, detail=f"Erro ao buscar a página: {e}")

    # Faz parsing do HTML retornado
    soup = BeautifulSoup(resp.text, "html.parser")

    manuals = []    # Lista temporária para armazenar manuais
    datasheets = [] # Lista temporária para armazenar fichas técnicas

    # Função auxiliar para extrair documentos de uma seção específica (li)
    def extract_docs(section_li):
        docs = []  # Lista de dicionários com title e url
        # Percorre cada linha (<tr>) da tabela não listrada
        for tr in section_li.select("table.unstriped tbody tr"):
            span = tr.find('span', class_='text--300')  # Localiza o span que contém o título
            if not span:
                continue  # Pula se não encontrar
            # Concatena apenas as strings (remove span de data)
            title = ''.join([c for c in span.strings]).strip()
            a = tr.find('a', href=True)  # Localiza o link de download
            if not a:
                continue
            href = a['href']  # URL do PDF
            docs.append({"title": title, "url": href})
        return docs

    # Busca seção de manuais através do atributo data-ga-name
    manu_section = soup.find('li', attrs={'data-ga-name': 'manuais'})
    if manu_section:
        manuals = extract_docs(manu_section)

    # Busca seção de ficha técnica através do atributo data-ga-name
    data_section = soup.find('li', attrs={'data-ga-name': 'ficha-tecnica'})
    if data_section:
        datasheets = extract_docs(data_section)

    # Fallback: se não encontrar seções estruturais, procura por links diretos de manual
    if not manuals:
        for a in soup.select('a.product-help-and-download--download-link[href$=".pdf"]'):
            if 'manual' in a.get('data-ga-action', '').lower():
                manuals.append({"title": None, "url": a['href']})

    # Fallback: procura por links diretos de ficha técnica ou datasheet
    if not datasheets:
        for a in soup.select('a.product-help-and-download--download-link[href$=".pdf"]'):
            if 'ficha-tecnica' in a.get('data-ga-action', '').lower() or 'datasheet' in a['href'].lower():
                datasheets.append({"title": None, "url": a['href']})

    # Retorna o modelo de resposta, com None caso as listas estejam vazias
    return ScrapeResponse(
        manuals=manuals or None,
        datasheets=datasheets or None
    )

# Instrução para rodar localmente com uvicorn
# uvicorn main:app --reload --host 0.0.0.0 --port 8000