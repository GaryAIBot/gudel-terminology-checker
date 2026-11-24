import csv, hashlib, io, re, unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path

STATUS_MAP={"Vorzugsbenennung":"preferred","Alternative Benennung":"alternative","Verbotene Benennung":"forbidden"}
TERM_RE=re.compile(r'\s*([^"\r\n]+?)\s*\((Vorzugsbenennung|Alternative Benennung|Verbotene Benennung)\)')

def normalise(value:str)->str:
    return " ".join(unicodedata.normalize("NFKC",value).casefold().split())

def parse_english(value:str):
    return [{"text":m.group(1).strip(),"status":STATUS_MAP[m.group(2)]} for m in TERM_RE.finditer(value or "")]

def parse_csv(content:bytes):
    text=content.decode("utf-8-sig")
    rows=list(csv.DictReader(io.StringIO(text,newline=""),delimiter=";"))
    concepts=[]; english=[]; ambiguous=0
    for row in rows:
        terms=parse_english(row.get("Lexikoneintrag (en-US)",""))
        german_status=row.get("Status (de-CH)","")
        is_ambiguous=sum(german_status.count(k) for k in STATUS_MAP)>1
        ambiguous+=int(is_ambiguous)
        concept={"id":row.get("ID",""),"label":row.get("Lexikoneintrag (de-CH)",""),"sap":row.get("Kurzbezeichnung (SAP)",""),"example":row.get("Beispielsatz",""),"department":row.get("Abteilung",""),"domain":row.get("Technischer Bereich",""),"part_of_speech":row.get("Wortart",""),"german_status":german_status,"needs_review":is_ambiguous,"raw":row,"terms":[]}
        for term in terms:
            item={**term,"language":"en-US","normalised":normalise(term["text"]),"concept_id":concept["id"],"concept":concept["label"],"department":concept["department"],"domain":concept["domain"],"example":concept["example"],"source":"Güdel TermBank"}
            concept["terms"].append(item); english.append(item)
        concepts.append(concept)
    checksum=hashlib.sha256(content).hexdigest()
    return {"concepts":concepts,"terms":english,"checksum":checksum,"stats":{"records":len(rows),"concepts":len(concepts),"english_terms":len(english),"preferred":sum(t["status"]=="preferred" for t in english),"forbidden":sum(t["status"]=="forbidden" for t in english),"alternative":sum(t["status"]=="alternative" for t in english),"ambiguous_german_records":ambiguous}}

def check_text(text:str, terms:list, language="en-US", include_preferred=False, include_alternatives=True):
    candidates=[]
    for term in terms:
        if term["language"]!=language: continue
        if term["status"]=="preferred" and not include_preferred: continue
        if term["status"]=="alternative" and not include_alternatives: continue
        pattern=r"(?<!\w)"+re.escape(term["text"]).replace(r"\ ",r"\s+")+r"(?!\w)"
        for m in re.finditer(pattern,text,re.IGNORECASE|re.UNICODE):
            preferred=[t["text"] for t in terms if t["concept_id"]==term["concept_id"] and t["language"]==language and t["status"]=="preferred"]
            candidates.append({"matched_text":m.group(),"status":term["status"],"severity":{"forbidden":"error","alternative":"advisory","preferred":"compliant"}[term["status"]],"start_offset":m.start(),"end_offset":m.end(),"concept_id":term["concept_id"],"concept":term["concept"],"suggested_replacements":preferred,"context":text[max(0,m.start()-55):min(len(text),m.end()+55)].strip(),"department":term["department"],"technical_domain":term["domain"],"source":term["source"]})
    candidates.sort(key=lambda x:(x["start_offset"],-(x["end_offset"]-x["start_offset"])))
    findings=[]
    for item in candidates:
        if any(item["start_offset"]<x["end_offset"] and item["end_offset"]>x["start_offset"] for x in findings): continue
        findings.append(item)
    return findings

DATA_PATH=Path(__file__).resolve().parents[1]/"data"/"GenericReport_TermBank_24-11-2026.csv"
GLOSSARY=parse_csv(DATA_PATH.read_bytes())

