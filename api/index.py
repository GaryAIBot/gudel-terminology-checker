import io, json, re, uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from .engine import GLOSSARY, check_text, normalise, parse_csv

app=FastAPI(title="Güdel Terminology Checker API",version="1.0.0",description="Deterministic, concept-based terminology checking. Offsets are zero-based, end-exclusive Unicode code-point offsets.")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
ROOT=Path(__file__).resolve().parents[1]
REVISION="2026-11-24-001"
CHECKS={}

class TextRequest(BaseModel):
    text:str=Field(min_length=1,max_length=500_000)
    language:str="en-US"
    include_preferred:bool=False
    include_alternatives:bool=True

@app.get("/api/health")
def health(): return {"ok":True,"revision":REVISION,"records":GLOSSARY["stats"]["records"]}

@app.get("/api/v1/glossary/stats")
def stats(): return {**GLOSSARY["stats"],"active_terms":len(GLOSSARY["terms"]),"revision":REVISION,"checksum":GLOSSARY["checksum"]}

@app.get("/api/v1/glossary/revisions")
def revisions(): return [{"id":REVISION,"filename":GLOSSARY["concepts"][0]["raw"] and "GenericReport_TermBank_24-11-2026.csv","imported_at":"2026-11-24T16:18:00Z","checksum":GLOSSARY["checksum"],"statistics":GLOSSARY["stats"]}]

@app.post("/api/v1/check/text")
def check(body:TextRequest):
    findings=check_text(body.text,GLOSSARY["terms"],body.language,body.include_preferred,body.include_alternatives)
    cid=str(uuid.uuid4()); result={"id":cid,"language":body.language,"glossary_revision":REVISION,"compliant":not any(x["status"]=="forbidden" for x in findings),"findings_count":len(findings),"word_count":len(re.findall(r"\b\w+\b",body.text)),"findings":findings,"text":body.text,"checked_at":datetime.now(timezone.utc).isoformat()}
    CHECKS[cid]=result; return result

@app.get("/api/v1/checks/{check_id}")
def get_check(check_id:str):
    if check_id not in CHECKS: raise HTTPException(404,"Check not found (temporary PoC storage may have expired)")
    return CHECKS[check_id]

@app.get("/api/v1/checks/{check_id}/findings")
def get_findings(check_id:str): return get_check(check_id)["findings"]

@app.get("/api/v1/terms/search")
def search_terms(q:str="",status:str|None=None,limit:int=50):
    needle=normalise(q); found=[]
    for term in GLOSSARY["terms"]:
        if needle and needle not in term["normalised"] and needle not in normalise(term["concept"]): continue
        if status and term["status"]!=status: continue
        related=[t["text"] for t in GLOSSARY["terms"] if t["concept_id"]==term["concept_id"] and t["text"]!=term["text"]]
        found.append({**term,"related":related})
    return {"query":q,"count":len(found),"results":found[:min(limit,200)]}

@app.get("/api/v1/concepts/{concept_id}")
def concept(concept_id:str):
    item=next((c for c in GLOSSARY["concepts"] if c["id"]==concept_id),None)
    if not item: raise HTTPException(404,"Concept not found")
    return item

@app.post("/api/v1/imports/preview")
async def import_preview(file:UploadFile=File(...)):
    content=await file.read()
    if len(content)>25*1024*1024: raise HTTPException(413,"File exceeds 25 MB")
    try: parsed=parse_csv(content)
    except Exception as exc: raise HTTPException(400,f"Invalid TermBank CSV: {exc}")
    same=parsed["checksum"]==GLOSSARY["checksum"]
    return {"id":parsed["checksum"][:16],"filename":file.filename,"checksum":parsed["checksum"],"statistics":parsed["stats"],"changes":{"new":0 if same else parsed["stats"]["records"],"modified":0,"unchanged":parsed["stats"]["records"] if same else 0,"ambiguous":parsed["stats"]["ambiguous_german_records"]},"warnings":["German terms with concatenated status values are flagged for review and are not activated as violations."],"can_commit":True}

def extract_docx(content:bytes):
    from docx import Document
    doc=Document(io.BytesIO(content)); blocks=[]
    for p in doc.paragraphs:
        if p.text.strip(): blocks.append(p.text)
    for table in doc.tables:
        for row in table.rows:
            blocks.append(" | ".join(c.text for c in row.cells))
    for section in doc.sections:
        blocks += [p.text for p in section.header.paragraphs if p.text.strip()]
        blocks += [p.text for p in section.footer.paragraphs if p.text.strip()]
    return "\n".join(blocks),"complete",None

def extract_pdf(content:bytes):
    import fitz
    doc=fitz.open(stream=content,filetype="pdf"); pages=[]
    for i,page in enumerate(doc):
        text=page.get_text("text"); pages.append(f"\n[Page {i+1}]\n{text}")
    joined="".join(pages)
    return joined,("complete" if joined.strip() else "incomplete"),(None if joined.strip() else "No extractable text layer detected. OCR is outside this PoC scope; this document is not marked compliant.")

@app.post("/api/v1/check/document")
async def check_document(file:UploadFile=File(...),language:str=Form("en-US")):
    content=await file.read()
    if len(content)>25*1024*1024: raise HTTPException(413,"File exceeds 25 MB")
    suffix=Path(file.filename or "").suffix.lower()
    try:
        if suffix==".docx": text,coverage,warning=extract_docx(content)
        elif suffix==".pdf": text,coverage,warning=extract_pdf(content)
        else: raise HTTPException(415,"Only .docx and .pdf files are supported")
    except HTTPException: raise
    except Exception as exc: raise HTTPException(422,f"Document extraction failed: {exc}")
    result=check(TextRequest(text=text or " ",language=language)); result.update({"filename":file.filename,"file_type":suffix[1:],"coverage":coverage,"warning":warning})
    return result

@app.get("/api/v1/reports/{check_id}.csv")
def report(check_id:str):
    result=get_check(check_id); out=io.StringIO(); out.write("Expression,Status,Suggestion,Concept,Context\n")
    import csv
    w=csv.writer(out)
    for f in result["findings"]: w.writerow([f["matched_text"],f["status"]," | ".join(f["suggested_replacements"]),f["concept"],f["context"]])
    return StreamingResponse(iter([out.getvalue()]),media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="terminology-report-{check_id[:8]}.csv"'})

@app.get("/")
def index(): return FileResponse(ROOT/"index.html")

