"""Mídia recebida no WhatsApp (imagens, etc.), guardada por pouco tempo para o Lolo usar como base de memes/edições."""
import json
import os
import time
from typing import Dict, List, Optional

HOME = os.environ.get("HERMES_HOME", "/opt/data")
DIR = os.path.join(HOME, "midia")
MAX_ITENS = 60


def _safe(n: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in n)[:80] or "arquivo"


def save_inbox(data: bytes, filename: str, *, mime: str = "", sender: str = "", ts: Optional[float] = None, msg_id: str = "",
               caption: str = "", kind: str = "documento", extra: Optional[Dict] = None) -> Optional[str]:
    """Mesma assinatura do módulo de arquivos da SIÉ (o adapter chama igual). Só guarda imagens e áudios recentes."""
    if not data or len(data) > 20 * 1024 * 1024 or kind not in ("image", "audio", "document"):
        return None
    os.makedirs(DIR, exist_ok=True)
    ts = ts or time.time()
    path = os.path.join(DIR, f"{int(ts)}__{_safe(filename)}")
    with open(path, "wb") as f:
        f.write(data)
    with open(path + ".json", "w", encoding="utf-8") as f:
        json.dump({"arquivo": os.path.basename(path), "mime": mime, "sender": sender, "ts": ts, "msg_id": msg_id,
                   "caption": caption, "kind": kind, **(extra or {})}, f, ensure_ascii=False)
    itens = sorted(n for n in os.listdir(DIR) if not n.endswith(".json"))
    for n in itens[:-MAX_ITENS]:
        for p in (os.path.join(DIR, n), os.path.join(DIR, n) + ".json"):
            try:
                os.remove(p)
            except OSError:
                pass
    return path


def recentes(kind: str = "image", max_idade_min: int = 60) -> List[Dict]:
    out = []
    if not os.path.isdir(DIR):
        return out
    for n in sorted(os.listdir(DIR), reverse=True):
        if n.endswith(".json"):
            continue
        try:
            meta = json.load(open(os.path.join(DIR, n) + ".json", encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if meta.get("kind") == kind and time.time() - meta.get("ts", 0) <= max_idade_min * 60:
            out.append({**meta, "path": os.path.join(DIR, n)})
    return out
