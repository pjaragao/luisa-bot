"""Lembretes e mensagens recorrentes da Luisa (únicos, diários, semanais, mensais), entregues pelo cron a cada minuto.

Independe do LLM: o agente só cria/cancela; quem envia é `lembretes_tick.py` (script do cron do Hermes) pelo Evolution.
"""
import datetime
import fcntl
import json
import os
import urllib.request
from typing import Any, Dict, List, Optional

HOME = os.environ.get("HERMES_HOME", "/opt/data")
PATH = os.path.join(HOME, "lembretes_luisa.json")
LOCK = PATH + ".lock"
DESTINO = os.environ.get("EVOLUTION_HOME_CHANNEL", "")
CATCHUP_MIN = 180  # se o tick falhar, ainda envia até 3h depois do horário
DIAS = {"seg": 0, "ter": 1, "qua": 2, "qui": 3, "sex": 4, "sab": 5, "sáb": 5, "dom": 6}
NOMES = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


class _Lock:
    def __enter__(self):
        os.makedirs(HOME, exist_ok=True)
        self.f = open(LOCK, "w")
        fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *a):
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


def _load() -> List[Dict[str, Any]]:
    try:
        with open(PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _save(rows: List[Dict[str, Any]]) -> None:
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    os.replace(tmp, PATH)


def _dias(v: Any) -> List[int]:
    if not v:
        return []
    if isinstance(v, str):
        v = [x.strip().lower() for x in v.replace(";", ",").split(",") if x.strip()]
    if v == ["uteis"] or v == ["úteis"]:
        return [0, 1, 2, 3, 4]
    out = []
    for x in v:
        out.append(int(x) if str(x).isdigit() else DIAS[str(x).lower()[:3]])
    return sorted(set(out))


def criar(texto: str = "", hora: str = "09:00", tipo: str = "unico", data: Optional[str] = None, dias: Any = None,
          dia_mes: Optional[int] = None, ate: Optional[str] = None, conteudo: str = "texto") -> str:
    """tipo: unico (exige data) | diario | semanal (dias) | mensal (dia_mes). conteudo: 'texto' ou 'tarefas' (lista as abertas)."""
    tipo = (tipo or "").lower()
    if tipo not in ("unico", "diario", "semanal", "mensal"):
        return "Erro: tipo deve ser unico, diario, semanal ou mensal."
    try:
        datetime.datetime.strptime(hora, "%H:%M")
    except (ValueError, TypeError):
        return "Erro: hora deve ser HH:MM (ex.: 09:30)."
    if conteudo == "texto" and len((texto or "").strip()) < 3:
        return "Erro: informe o texto do lembrete."
    if tipo == "unico":
        try:
            datetime.date.fromisoformat(data or "")
        except ValueError:
            return "Erro: lembrete único precisa de data AAAA-MM-DD."
    try:
        dl = _dias(dias) if tipo in ("semanal", "diario") else []
    except (KeyError, ValueError):
        return "Erro: dias inválidos (use seg,ter,qua,qui,sex,sab,dom ou 'uteis')."
    if tipo == "semanal" and not dl:
        return "Erro: lembrete semanal precisa de dias."
    if tipo == "mensal" and not (dia_mes and 1 <= int(dia_mes) <= 31):
        return "Erro: lembrete mensal precisa de dia_mes (1 a 31)."
    with _Lock():
        rows = _load()
        nid = max([r["id"] for r in rows] + [0]) + 1
        rows.append({"id": nid, "texto": (texto or "").strip(), "conteudo": conteudo, "tipo": tipo, "hora": hora,
                     "data": data, "dias": dl, "dia_mes": int(dia_mes) if dia_mes else None, "ate": ate, "ativo": True,
                     "ultimo_envio": None, "criado_em": datetime.datetime.now().isoformat(timespec="seconds")})
        _save(rows)
    return f"Lembrete #{nid} criado: {_descr(rows[-1])}"


def _descr(r: Dict[str, Any]) -> str:
    quando = {"unico": f"em {r.get('data')} às {r['hora']}", "diario": f"todo dia às {r['hora']}",
              "semanal": "toda " + ", ".join(NOMES[d] for d in r.get("dias") or []) + f" às {r['hora']}",
              "mensal": f"todo dia {r.get('dia_mes')} às {r['hora']}"}[r["tipo"]]
    if r["tipo"] == "diario" and r.get("dias"):
        quando = "dias " + ", ".join(NOMES[d] for d in r["dias"]) + f" às {r['hora']}"
    what = "lista das tarefas em aberto" if r.get("conteudo") == "tarefas" else f"“{r['texto']}”"
    return f"{what} — {quando}" + (f" (até {r['ate']})" if r.get("ate") else "")


def listar() -> str:
    rows = [r for r in _load() if r.get("ativo")]
    return "\n".join(f"• #{r['id']} {_descr(r)}" for r in rows) if rows else "Nenhum lembrete ativo."


def editar(rid: int, texto: Optional[str] = None, hora: Optional[str] = None, tipo: Optional[str] = None,
           data: Optional[str] = None, dias: Any = None, dia_mes: Optional[int] = None, ate: Optional[str] = None) -> str:
    with _Lock():
        rows = _load()
        for r in rows:
            if r["id"] == int(rid) and r.get("ativo"):
                if texto is not None and texto.strip():
                    r["texto"] = texto.strip()
                if hora is not None and hora.strip():
                    try:
                        datetime.datetime.strptime(hora.strip(), "%H:%M")
                        r["hora"] = hora.strip()
                    except ValueError:
                        return "Erro: hora deve ser HH:MM (ex.: 09:30)."
                if tipo is not None and tipo.strip().lower() in ("unico", "diario", "semanal", "mensal"):
                    r["tipo"] = tipo.strip().lower()
                if data is not None:
                    r["data"] = data
                if dias is not None:
                    try:
                        r["dias"] = _dias(dias)
                    except (KeyError, ValueError):
                        return "Erro: dias inválidos."
                if dia_mes is not None:
                    r["dia_mes"] = int(dia_mes)
                if ate is not None:
                    r["ate"] = ate
                _save(rows)
                return f"✏️ Lembrete #{rid} atualizado: {_descr(r)}"
    return f"Lembrete #{rid} não encontrado."


def cancelar(rid: int) -> str:
    with _Lock():
        rows = _load()
        for r in rows:
            if r["id"] == int(rid) and r.get("ativo"):
                r["ativo"] = False
                _save(rows)
                return f"Lembrete #{rid} cancelado."
    return f"Lembrete #{rid} não encontrado."


def _slot(r: Dict[str, Any], now: datetime.datetime) -> Optional[datetime.datetime]:
    """Horário programado de hoje para este lembrete (ou None se hoje não é dia dele)."""
    h, m = map(int, r["hora"].split(":"))
    today = now.date()
    if r.get("ate") and today > datetime.date.fromisoformat(r["ate"]):
        return None
    ok = {"unico": r.get("data") == today.isoformat(),
          "diario": not r.get("dias") or today.weekday() in r["dias"],
          "semanal": today.weekday() in (r.get("dias") or []),
          "mensal": today.day == r.get("dia_mes")}[r["tipo"]]
    return datetime.datetime.combine(today, datetime.time(h, m)) if ok else None


def vencidos(now: Optional[datetime.datetime] = None) -> List[Dict[str, Any]]:
    now = now or datetime.datetime.now()
    out = []
    for r in _load():
        if not r.get("ativo"):
            continue
        slot = _slot(r, now)
        if not slot or now < slot or (now - slot).total_seconds() > CATCHUP_MIN * 60:
            continue
        if r.get("ultimo_envio") and datetime.datetime.fromisoformat(r["ultimo_envio"]) >= slot:
            continue
        out.append(r)
    return out


def _mensagem(r: Dict[str, Any]) -> str:
    if r.get("conteudo") == "tarefas":
        import pendencias
        abertas = pendencias.abertas_texto()
        return ("🌿 *Suas tarefas em aberto*\n" + "\n".join(f"• {l}" for l in abertas.split("\n"))
                + "\n\nMe diga o que já foi feito que eu dou baixa. ✅") if abertas else \
               "🌿 Nenhuma tarefa em aberto agora. Tudo em dia! ✅"
    if r.get("conteudo") == "bruto":
        return r["texto"]
    return f"⏰ *Lembrete:* {r['texto']}"


def _enviar(texto: str) -> bool:
    base, key, inst = (os.environ.get("EVOLUTION_API_URL", "").rstrip("/"), os.environ.get("EVOLUTION_API_KEY", ""),
                       os.environ.get("EVOLUTION_INSTANCE", ""))
    if not (base and key and inst and DESTINO):
        return False
    req = urllib.request.Request(f"{base}/message/sendText/{inst}",
                                 data=json.dumps({"number": DESTINO, "text": texto, "delay": 0, "linkPreview": False}).encode(),
                                 headers={"apikey": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status in (200, 201)
    except Exception:
        return False


def tick(now: Optional[datetime.datetime] = None) -> str:
    now = now or datetime.datetime.now()
    sent = []
    with _Lock():
        rows = _load()
        due = {r["id"] for r in vencidos(now)}
        for r in rows:
            if r["id"] in due and _enviar(_mensagem(r)):
                r["ultimo_envio"] = now.isoformat(timespec="seconds")
                if r["tipo"] == "unico":
                    r["ativo"] = False
                sent.append(r["id"])
        if sent:
            _save(rows)
    return f"enviados: {sent}" if sent else "nada a enviar"
