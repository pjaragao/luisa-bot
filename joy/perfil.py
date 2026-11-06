"""Perfil e preferências da Luisa (preenchido pelo questionário inicial e atualizado ao longo do uso)."""
import datetime
import fcntl
import json
import os

HOME = os.environ.get("HERMES_HOME", "/opt/data")
PATH = os.path.join(HOME, "perfil_luisa.json")
LOCK = PATH + ".lock"

# Perguntas do questionário inicial: o assistente faz poucas por vez e grava cada resposta.
QUESTOES = [
    ("nome_assistente", "Como quer me chamar? (hoje sou 'Íris')"),
    ("ette_o_que_e", "Etté: o que a loja vende, para quem, e onde fica (física, online ou as duas)?"),
    ("ette_socios_equipe", "Etté: quem são os sócios e quem trabalha com você? (nomes e funções)"),
    ("ette_fornecedores_sistemas", "Etté: quais sistemas, bancos e fornecedores principais usa hoje (PDV, estoque, contador, maquininha...)?"),
    ("ette_prioridades", "Etté: quais são as 3 coisas mais urgentes ou que mais te tomam tempo agora?"),
    ("rotina_horarios", "Rotina: em que horários prefere receber lembretes e o resumo do dia? Quais dias não devo te incomodar?"),
    ("agenda_chatgpt", "Sua agenda do ChatGPT: pode colar o texto aqui (ou exportar) para eu montar o acompanhamento diário?"),
    ("lista_lancamento", "Lista de lançamento: de qual loja/evento é e qual o formato (nome, contato, data)? Quero acrescentar Paola Carlevaro e Mariana Pesca."),
    ("privacidade", "Privacidade: o que da Etté posso compartilhar com o Paulo ou com o agente dele? (padrão: nada)"),
    ("estilo", "Estilo: prefere respostas curtas e diretas, ou mais detalhadas? Áudio ou texto?"),
]


def _load() -> dict:
    try:
        with open(PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def salvar(chave: str, valor: str) -> str:
    chave = (chave or "").strip().lower()
    if not chave or not (valor or "").strip():
        return "Erro: informe chave e valor."
    os.makedirs(HOME, exist_ok=True)
    with open(LOCK, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            d = _load()
            d[chave] = {"valor": valor.strip(), "em": datetime.datetime.now().isoformat(timespec="seconds")}
            tmp = PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
            os.replace(tmp, PATH)
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)
    return f"Anotado: {chave}."


def ver() -> str:
    d = _load()
    lines = ["*Perfil da Luisa*"] + [f"• {k}: {v['valor']}" for k, v in d.items()] if d else ["Perfil vazio."]
    faltam = [(k, q) for k, q in QUESTOES if k not in d]
    if faltam:
        lines += ["", "*Perguntas ainda sem resposta:*"] + [f"• ({k}) {q}" for k, q in faltam]
    return "\n".join(lines)
