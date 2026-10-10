"""
NetraX emergency demo-data uploader.
Run this from your local project/repository folder:
    python upload_netrax_demo_data.py

It uploads existing files under netrax/data/synthetic to the deployed API,
attaching them to the existing demo case. It does NOT modify source files.
"""
from pathlib import Path
import mimetypes
import sys
import requests

API = "https://hackbios-ojao.onrender.com"
CASE_ID = "95476f43-05de-4813-8052-0458eb882b25"
DATA_ROOT = Path("netrax/data/synthetic")
SUPPORTED = {".pdf", ".txt", ".csv"}

def infer_type(path: Path) -> str:
    parts = [p.lower() for p in path.parts]
    if "fir" in parts or "fir" in path.stem.lower() or "police" in path.stem.lower():
        return "FIR"
    if "cdr" in parts or "cdr" in path.stem.lower() or "call" in path.stem.lower():
        return "CDR"
    if "financial" in parts or "finance" in path.stem.lower() or "transaction" in path.stem.lower():
        return "FINANCIAL"
    return "OTHER"

def main():
    if not DATA_ROOT.exists():
        print(f"ERROR: Can't find {DATA_ROOT.resolve()}")
        print("Run this script from the repository root (the folder containing 'netrax').")
        sys.exit(1)

    files = sorted(p for p in DATA_ROOT.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED)
    if not files:
        print(f"No PDF/TXT/CSV files found under {DATA_ROOT.resolve()}")
        sys.exit(1)

    # Check API first
    try:
        r = requests.get(f"{API}/api/cases", timeout=45)
        print(f"API check: GET /api/cases -> {r.status_code}")
        if r.status_code >= 500:
            print(r.text[:1000])
            sys.exit(1)
    except requests.RequestException as e:
        print(f"Cannot reach deployed API: {e}")
        sys.exit(1)

    print(f"Found {len(files)} supported files. Uploading to case {CASE_ID}...")
    uploaded = skipped = failed = 0
    for path in files:
        doc_type = infer_type(path)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        try:
            with path.open("rb") as f:
                response = requests.post(
                    f"{API}/api/documents/upload",
                    data={
                        "case_id": CASE_ID,
                        "document_type": doc_type,
                        "description": f"Synthetic demo data: {path.name}",
                        "source": "Repository synthetic dataset",
                    },
                    files={"file": (path.name, f, mime)},
                    timeout=180,
                )
            if response.status_code in (200, 201, 202):
                uploaded += 1
                print(f"[UPLOADED] {path} ({doc_type}) -> {response.status_code}")
            elif response.status_code == 409:
                skipped += 1
                print(f"[ALREADY EXISTS] {path} -> {response.text[:300]}")
            else:
                failed += 1
                print(f"[FAILED] {path} ({doc_type}) -> {response.status_code}: {response.text[:500]}")
        except requests.RequestException as e:
            failed += 1
            print(f"[FAILED] {path}: {e}")

    print("\nUpload summary")
    print(f"Uploaded/accepted: {uploaded}")
    print(f"Already existed:   {skipped}")
    print(f"Failed:            {failed}")
    print("\nNext: open https://hackbios-ojao.onrender.com/docs")
    print("Check GET /api/dashboard/stats and GET /api/documents.")
    print("Processing may run in the background; wait a minute and refresh stats.")
    if failed:
        print("\nIf failures mention an invalid document_type, open POST /api/documents/upload in Swagger")
        print("and use one of the exact allowed document_type values shown in its schema.")

if __name__ == "__main__":
    main()
