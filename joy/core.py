"""Ferramenta `luisa` do assistente pessoal da Luisa."""
import datetime
import logging
import re
import unicodedata
from typing import Any, Dict

import documentos
import group_history
import lembretes
import link
import pendencias
import perfil
import pesquisa

logger = logging.getLogger("luisa")

# consultas da SIÉ que o assistente pode pedir ao agente da SIÉ (as que alteram avisam o grupo da SIÉ sozinho)
SIE_PERMITIDAS = {
    "listar_reembolsos", "resumo_capex", "consultar_planejamento", "listar_pendencias", "arquivos", "historico_grupo",
    "lancar_reembolso", "editar_reembolso", "cancelar_reembolso", "sincronizar_reembolsos",
    "registrar_pendencia", "atualizar_pendencia", "organizar_arquivos", "pesquisar_produtos",
}
DIAS_PT = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
_SEM = {"segunda": 0, "seg": 0, "terca": 1, "ter": 1, "quarta": 2, "qua": 2, "quinta": 3, "qui": 3, "sexta": 4, "sex": 4,
        "sabado": 5, "sab": 5, "domingo": 6, "dom": 6}


def _rel(v: Any) -> Any:
    """Resolve datas relativas ('hoje', 'amanhã', 'sexta', 'dd/mm/aaaa') para AAAA-MM-DD."""
    if not isinstance(v, str) or not v.strip():
        return v
    t = unicodedata.normalize("NFKD", v).encode("ascii", "ignore").decode().lower().strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", t):
        return v[:10]
    resto = re.sub(r"^(na |no |nesta |neste |proxima |proximo |[aà]s? )", "", t).replace("-feira", "").strip()
    hoje = datetime.date.today()
    d = None
    if resto == "hoje":
        d = hoje
    elif resto == "amanha":
        d = hoje + datetime.timedelta(days=1)
    elif resto == "depois de amanha":
        d = hoje + datetime.timedelta(days=2)
    elif resto.split(" ")[0] in _SEM:
        wd = _SEM[resto.split(" ")[0]]
        if wd == hoje.weekday() and re.search(r"\b(nest[ea]|ness[ea]|hoje)\b", t):
            d = hoje
        else:
            d = hoje + datetime.timedelta(days=(wd - hoje.weekday() - 1) % 7 + 1)
    else:
        m = re.match(r"^(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?$", resto)
        if m:
            ano = int(m.group(3)) + (2000 if m.group(3) and len(m.group(3)) == 2 else 0) if m.group(3) else hoje.year
            d = datetime.date(ano, int(m.group(2)), int(m.group(1)))
            if not m.group(3) and d < hoje:
                d = d.replace(year=d.year + 1)
    return d.isoformat() if d else v


def run_query(consulta: str, args: Dict[str, Any]) -> str:
    c = (consulta or "").lower().strip()
    args = dict(args)
    for k in ("prazo", "data", "ate"):
        if k in args and args[k]:
            args[k] = _rel(args[k])
    try:
        if c == "agora":
            n = datetime.datetime.now()
            return f"{DIAS_PT[n.weekday()]}, {n:%d/%m/%Y} {n:%H:%M} (America/Sao_Paulo)"
        if c == "tarefa_registrar":
            return pendencias.registrar(str(args.get("titulo") or ""), args.get("detalhe"), args.get("responsavel"),
                                        args.get("prazo"))
        if c == "tarefa_atualizar":
            return pendencias.atualizar(int(args.get("id") or 0), str(args.get("estado") or ""), args.get("evidencia"))
        if c == "tarefa_listar":
            return pendencias.listar(str(args.get("estado") or "aberto"), int(args.get("limite") or 30))
        if c in ("pesquisar_produtos", "pesquisa_web"):
            return pesquisa.pesquisar_web(str(args.get("termo") or args.get("alvo") or ""),
                                          str(args.get("foco") or "produtos e fornecedores"),
                                          profundo=str(args.get("profundo", "")).lower() in ("1", "true", "sim"))
        if c == "web_pesquisar":
            return pesquisa.web(str(args.get("termo") or args.get("busca") or ""),
                                profundo=str(args.get("profundo", "")).lower() in ("1", "true", "sim"))
        if c == "documento_ler":
            return documentos.ler(str(args.get("busca") or args.get("termo") or ""), int(args.get("offset") or 0))
        if c == "documento_listar":
            return documentos.listar(int(args.get("limite") or 10))
        if c == "historico_grupo":
            msgs = group_history.get_recent_messages(hours=float(args.get("horas") or 24))
            b = str(args.get("busca") or "").lower().strip()
            if b:
                msgs = [m for m in msgs if b in (m.get("text") or "").lower()]
            return group_history.format_messages(msgs)
        if c == "lembrete_criar":
            return lembretes.criar(str(args.get("texto") or ""), str(args.get("hora") or "09:00"), str(args.get("tipo") or "unico"),
                                   args.get("data"), args.get("dias"), args.get("dia_mes"), args.get("ate"),
                                   str(args.get("conteudo") or "texto"))
        if c == "lembrete_editar":
            return lembretes.editar(int(args.get("id") or 0), args.get("texto"), args.get("hora"), args.get("tipo"),
                                    args.get("data"), args.get("dias"), args.get("dia_mes"), args.get("ate"))
        if c == "lembrete_listar":
            return lembretes.listar()
        if c == "lembrete_cancelar":
            return lembretes.cancelar(int(args.get("id") or 0))
        if c == "perfil_salvar":
            return perfil.salvar(str(args.get("chave") or ""), str(args.get("valor") or ""))
        if c == "perfil_ver":
            return perfil.ver()
        if c == "sie":
            alvo = str(args.get("sie_consulta") or "").lower().strip()
            if alvo not in SIE_PERMITIDAS:
                return "Consulta da SIÉ não permitida. Use: " + ", ".join(sorted(SIE_PERMITIDAS))
            sub = args.get("sie_args") if isinstance(args.get("sie_args"), dict) else {}
            return link.sie(alvo, sub)
        if c in ("ajuda", "help"):
            return ("agora · tarefa_registrar/atualizar/listar · lembrete_criar/editar/listar/cancelar · "
                    "pesquisar_produtos · web_pesquisar · documento_ler/documento_listar · historico_grupo · "
                    "perfil_salvar/perfil_ver · sie (acessa e altera informações da SIÉ; alterações avisam o grupo da SIÉ)")
        return f"Consulta '{consulta}' não reconhecida. Use 'ajuda'."
    except Exception as exc:
        logger.error("[luisa] erro em %s: %s", consulta, exc, exc_info=True)
        return f"Erro ao processar '{consulta}': {exc}"
