import threading
from pathlib import Path
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import time

from data.database import sync_gmails, sync_dhbw_emails
from tools.google.config import PRIMARY_PERSONAL_TOKEN_PATH, SECONDARY_PERSONAL_TOKEN_PATH

@dataclass
class EmailSyncResult:
    name: str
    success: bool
    duration_ms: int
    emails_synced: int
    error: str | None = None

ROOT = Path(__file__).resolve()
while not (ROOT / "pyproject.toml").exists():
    ROOT = ROOT.parent

PRIMARY_PERSONAL_DB_PATH = ROOT / "data" / "emails_primary_account.db"
SECONDARY_PERSONAL_DB_PATH = ROOT / "data" / "emails_secondary_account.db"
SYSTEM_PROCESSES = [
    {"name": "primary personal", "function": lambda: sync_gmails(PRIMARY_PERSONAL_DB_PATH, PRIMARY_PERSONAL_TOKEN_PATH, "primary")},
    {"name": "secondary personal", "function": lambda: sync_gmails(SECONDARY_PERSONAL_DB_PATH, SECONDARY_PERSONAL_TOKEN_PATH, "secondary")},
    {"name": "DHBW", "function": sync_dhbw_emails}
]

def run_system_process(name, function, retries=3, delay=3) -> EmailSyncResult:
    result = None

    for attempt in range(0,retries):

        try:
            start_time = time.perf_counter()
            emails = function()
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            result = EmailSyncResult(name=name, success=True, duration_ms=duration_ms, emails_synced=emails)
            break
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                result = EmailSyncResult(name=name, success=False, duration_ms=0, emails_synced=0, error=str(e))

    return result

def run_all_system_processes() -> list[EmailSyncResult]:
    resultats = []
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(run_system_process, proc["name"], proc["function"]): proc for proc in SYSTEM_PROCESSES}
        for future in futures:
            result = future.result()
            resultats.append(result)

    return resultats

def run_system_processes_background() -> threading.Thread:
    # daemon=True means the thread dies automatically when the server shuts down — no cleanup needed
    thread = threading.Thread(target=run_all_system_processes, daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    results = run_all_system_processes()
    for res in results:
        print(f"[{res.name}] \tduration={res.duration_ms}ms | {res.emails_synced} | error={res.error}")