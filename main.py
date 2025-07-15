from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import pdfplumber, docx
import httpx

DEEPSEEK_API_KEY = "sk-ce9e4405b45d4450890693d8a290f2ff"
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def extract_text_from_pdf(file_bytes):
    text = ""
    with pdfplumber.open(file_bytes) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

def extract_text_from_docx(file_bytes):
    text = ""
    import io
    from docx import Document
    doc = Document(io.BytesIO(file_bytes))
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

async def analyze_with_deepseek(paper_text):
    system = "你是学术论文初审专家，论文主题是“节能”。"
    user = f"请判断下面内容是否符合“节能”主题，不符合请指出问题并给出3条修改建议：\n\n{paper_text[:3000]}"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "temperature": 0.3
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(DEEPSEEK_ENDPOINT, headers=headers, json=data, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

@app.get("/", response_class=HTMLResponse)
async def form_view(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "result": None})

@app.post("/upload", response_class=HTMLResponse)
async def upload_and_analyze(request: Request, file: UploadFile = File(...)):
    contents = await file.read()
    if file.filename.endswith(".pdf"):
        text = extract_text_from_pdf(contents)
    elif file.filename.endswith(".docx"):
        text = extract_text_from_docx(contents)
    else:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "result": "仅支持 PDF 或 DOCX 文件"
        })

    try:
        analysis = await analyze_with_deepseek(text)
    except Exception as e:
        analysis = f"调用 DeepSeek API 失败：{str(e)}"

    return templates.TemplateResponse("index.html", {
        "request": request,
        "result": analysis
    })