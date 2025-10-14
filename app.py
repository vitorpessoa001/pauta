# app.py
import os
import re
import logging
from datetime import datetime, date, timedelta
from time import time as _now
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytz
import requests
from flask import Flask, render_template, request, jsonify
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# -----------------------------------------------------------------------------
# LOG
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# MODELOS
# -----------------------------------------------------------------------------
class ResultadoPauta:
    def __init__(self, encontrou=False, tem_sessao=False, pauta=None, erro=None, situacao=None):
        self.encontrou = encontrou
        self.tem_sessao = tem_sessao
        self.pauta = pauta or []
        self.erro = erro
        self.situacao = situacao

class Destaque:
    def __init__(self, id_proposicao, numero, sigla_tipo, data_hora, ementa, url_inteiro_teor, descricao_tipo, despacho, autores=None):
        self.id_proposicao = id_proposicao
        self.numero = numero
        self.sigla_tipo = sigla_tipo
        self.data_hora = data_hora
        self.ementa = ementa
        self.url_inteiro_teor = url_inteiro_teor
        self.descricao_tipo = descricao_tipo
        self.despacho = despacho
        self.autores = autores or []

class ItemPauta:
    def __init__(
        self,
        id_proposicao,             # ID da proposição PRINCIPAL (não-PPP)
        titulo,                    # Usamos o <titulo> da pauta (ex.: "PL 743/2023")
        sigla_tipo, numero, ano,   # Da proposição principal
        ementa,                    # Ementa correta (pauta -> proposicaoRelacionada_ quando PPP)
        nome_relator,
        regime="",
        topico="",
        autores=None,
        destaques=None,
        relator_foto="",
        pauta_id=None              # ID que veio na pauta (PPP quando houver)
    ):
        self.id_proposicao = id_proposicao
        self.pauta_id = pauta_id
        self.titulo = (titulo or "").strip()
        self.sigla_tipo = sigla_tipo
        self.numero = numero
        self.ano = ano
        self.ementa = ementa
        self.nome_relator = nome_relator
        self.regime = regime
        self.topico = topico
        self.autores = autores or []
        self.destaques = destaques or []
        self.relator_foto = relator_foto or ""
        base_fallback = f"{sigla_tipo} {numero}/{ano}".strip()
        self.identificacao_completa = self.titulo if self.titulo else base_fallback

# -----------------------------------------------------------------------------
# HTTP SESSION
# -----------------------------------------------------------------------------
API_URL = "https://dadosabertos.camara.leg.br/api/v2"
PLENARIO_ID = 180

def build_session():
    s = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update({
        "Accept": "application/json",
        "User-Agent": "PautaCamara/2.1 (+https://dadosabertos.camara.leg.br/)"
    })
    return s

SESSION = build_session()

# -----------------------------------------------------------------------------
# CACHE TTL SIMPLES
# -----------------------------------------------------------------------------
_CACHE = {}
_TTL_SECONDS = 300

def _cache_get(key):
    v = _CACHE.get(key)
    if not v:
        return None
    val, ts = v
    if _now() - ts > _TTL_SECONDS:
        _CACHE.pop(key, None)
        return None
    return val

def _cache_set(key, val):
    _CACHE[key] = (val, _now())

def _cache_clear():
    _CACHE.clear()
    logger.info("CACHE limpo (nocache=1).")

# -----------------------------------------------------------------------------
# UTILS
# -----------------------------------------------------------------------------
def norm(v):
    if v is None:
        return ""
    try:
        return str(v).strip()
    except Exception:
        return ""

def _json_or_xml(resp):
    try:
        return resp.json(), None
    except Exception:
        try:
            return None, ET.fromstring(resp.content)
        except Exception:
            return None, None

def _parse_datetime_flex(dt_str):
    if not dt_str:
        return ""
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
    except Exception:
        pass
    try:
        return datetime.strptime(dt_str.split("+")[0], "%Y-%m-%dT%H:%M:%S").strftime("%d/%m/%Y %H:%M")
    except Exception:
        return dt_str[:16].replace("T", " ") if len(dt_str) >= 16 else dt_str

def _format_nome_partido(nome, sigla):
    nome = norm(nome)
    sigla = norm(sigla)
    return f"{nome} ({sigla})" if (nome and sigla) else nome

def _get(d, *path, default=""):
    """Acesso seguro a dicionários aninhados."""
    cur = d
    for p in path:
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return default
    return cur if cur is not None else default

# -----------------------------------------------------------------------------
# DADOS COMPLEMENTARES (autores, destaques, deputados)
# -----------------------------------------------------------------------------
_PROP_META_CACHE_KEY = "prop_meta:"
_REL_CACHE_KEY = "rel:"

def obter_meta_proposicao(id_proposicao):
    """Usado para detalhes extras quando necessário (ex.: validações)."""
    ck = f"{_PROP_META_CACHE_KEY}{id_proposicao}"
    c = _cache_get(ck)
    if c is not None:
        return c
    try:
        r = SESSION.get(f"{API_URL}/proposicoes/{id_proposicao}", timeout=12)
        r.raise_for_status()
        j, x = _json_or_xml(r)
        meta = {"siglaTipo": "", "numero": "", "ano": "", "ementa": ""}
        if j is not None:
            d = j.get("dados", {}) or {}
            meta["siglaTipo"] = norm(d.get("siglaTipo"))
            meta["numero"] = norm(d.get("numero"))
            meta["ano"] = norm(d.get("ano"))
            meta["ementa"] = norm(d.get("ementa"))
        elif x is not None:
            def tx(p):
                e = x.find(p)
                return norm(e.text if (e is not None and e.text) else "")
            meta["siglaTipo"] = tx(".//siglaTipo")
            meta["numero"] = tx(".//numero")
            meta["ano"] = tx(".//ano")
            meta["ementa"] = tx(".//ementa")
        _cache_set(ck, meta)
        return meta
    except Exception as e:
        logger.warning(f"meta {id_proposicao}: {e}")
        return {"siglaTipo": "", "numero": "", "ano": "", "ementa": ""}

def obter_sigla_partido_por_deputado_uri(uri_deputado):
    uri_deputado = norm(uri_deputado)
    if not uri_deputado:
        return ""
    try:
        r = SESSION.get(uri_deputado, timeout=10)
        r.raise_for_status()
        j, x = _json_or_xml(r)
        if j is not None:
            d = j.get("dados", {}) or {}
            u = d.get("ultimoStatus", {}) or {}
            return norm(u.get("siglaPartido") or d.get("siglaPartido"))
        elif x is not None:
            return norm(x.findtext(".//siglaPartido"))
    except Exception as e:
        logger.warning(f"partido {uri_deputado}: {e}")
    return ""

def obter_foto_por_deputado_uri(uri_deputado):
    uri_deputado = norm(uri_deputado)
    if not uri_deputado:
        return ""
    try:
        r = SESSION.get(uri_deputado, timeout=10)
        r.raise_for_status()
        j, x = _json_or_xml(r)
        if j is not None:
            d = j.get("dados", {}) or {}
            u = d.get("ultimoStatus", {}) or {}
            return norm(u.get("urlFoto") or d.get("urlFoto"))
        elif x is not None:
            return norm(x.findtext(".//urlFoto"))
    except Exception as e:
        logger.warning(f"foto {uri_deputado}: {e}")
    return ""

def obter_autores_proposicao(id_proposicao):
    """Lista simples de autores com partido quando for deputado."""
    try:
        r = SESSION.get(f"{API_URL}/proposicoes/{id_proposicao}/autores", timeout=12)
        r.raise_for_status()
        j, x = _json_or_xml(r)
        bases = []
        if j is not None:
            for a in j.get("dados", []) or []:
                nome = norm(a.get("nome") or (a.get("autor") or {}).get("nome"))
                uri  = norm(a.get("uri")  or a.get("uriAutor") or (a.get("autor") or {}).get("uri"))
                bases.append({"nome": nome, "uri": uri})
        elif x is not None:
            for el in x.findall(".//autor_"):
                bases.append({"nome": norm(el.findtext("nome")), "uri": norm(el.findtext("uri"))})

        def nome_partido(b):
            sig = obter_sigla_partido_por_deputado_uri(b["uri"]) if (b["uri"] and "/deputados/" in b["uri"]) else ""
            return _format_nome_partido(b["nome"], sig)

        nomes = []
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(nome_partido, b) for b in bases]
            for f in as_completed(futures):
                try:
                    nomes.append(f.result())
                except Exception as e:
                    logger.warning(f"autor fmt: {e}")
        if len(nomes) != len(bases):
            nomes = [nome_partido(b) for b in bases]
        return [n for n in nomes if n]
    except Exception as e:
        logger.error(f"autores {id_proposicao}: {e}")
        return []

def obter_detalhes_destaque(id_destaque):
    try:
        r = SESSION.get(f"{API_URL}/proposicoes/{id_destaque}", timeout=10)
        r.raise_for_status()
        j, x = _json_or_xml(r)
        d = {}
        if j is not None:
            d = j.get("dados", {}) or {}
        elif x is not None:
            d = {
                "numero": x.findtext(".//numero") or "",
                "siglaTipo": x.findtext(".//siglaTipo") or "",
                "dataApresentacao": x.findtext(".//dataApresentacao") or "",
                "ementa": x.findtext(".//ementa") or "",
                "urlInteiroTeor": x.findtext(".//urlInteiroTeor") or "",
            }
        return {
            "numero": norm(d.get("numero")),
            "sigla_tipo": norm(d.get("siglaTipo") or "DTQ"),
            "data_hora": _parse_datetime_flex(norm(d.get("dataApresentacao"))),
            "ementa": norm(d.get("ementa")),
            "url_inteiro_teor": norm(d.get("urlInteiroTeor")),
        }
    except Exception as e:
        logger.error(f"destaque {id_destaque}: {e}")
        return {}

def obter_destaques_dtq(id_proposicao):
    try:
        r = SESSION.get(f"{API_URL}/proposicoes/{id_proposicao}/relacionadas", timeout=15)
        r.raise_for_status()
        j, x = _json_or_xml(r)
        rels = []
        if j is not None:
            for rr in j.get("dados", []) or []:
                if rr.get("siglaTipo") == "DTQ":
                    rels.append({
                        "id": rr.get("id"),
                        "descricaoTipo": norm(rr.get("descricaoTipo")),
                        "despacho": norm(rr.get("despacho")),
                    })
        elif x is not None:
            for el in x.findall(".//relacionada_"):
                if norm(el.findtext("siglaTipo")) == "DTQ":
                    rels.append({
                        "id": norm(el.findtext("id")),
                        "descricaoTipo": norm(el.findtext("descricaoTipo")),
                        "despacho": norm(el.findtext("despacho")),
                    })

        out = []
        for rel in rels:
            did = rel.get("id")
            if not did:
                continue
            det = obter_detalhes_destaque(did)
            autores = obter_autores_proposicao(did)
            out.append(Destaque(
                id_proposicao=did,
                numero=det.get("numero", ""),
                sigla_tipo=det.get("sigla_tipo", "DTQ"),
                data_hora=det.get("data_hora", ""),
                ementa=det.get("ementa", ""),
                url_inteiro_teor=det.get("url_inteiro_teor", ""),
                descricao_tipo=rel.get("descricaoTipo", ""),
                despacho=rel.get("despacho", ""),
                autores=autores,
            ))
        return out
    except Exception as e:
        logger.error(f"destaques {id_proposicao}: {e}")
        return []

# -----------------------------------------------------------------------------
# MONTAGEM DOS ITENS A PARTIR DA *PAUTA* (usando proposicaoRelacionada_ p/ PPP)
# -----------------------------------------------------------------------------
def _mk_item_from_pauta(item_raw):
    """
    Constrói um ItemPauta diretamente do JSON da pauta.
    Regras:
      - Se proposicao_.siglaTipo == "PPP" (ou codTipo==192) e houver proposicaoRelacionada_,
        usamos a relacionada como a *proposição principal* (id, sigla, número, ano, ementa).
      - Caso contrário, usamos a própria proposicao_.
    """
    titulo = _get(item_raw, "titulo", default="").strip()
    topico = _get(item_raw, "topico", default="")
    regime = _get(item_raw, "regime", default="")

    prop = _get(item_raw, "proposicao_", default={}) or {}
    rel  = _get(item_raw, "relator", default={}) or {}
    relacionada = _get(item_raw, "proposicaoRelacionada_", default={}) or {}

    sigla_tipo = _get(prop, "siglaTipo", default="")
    cod_tipo   = _get(prop, "codTipo", default=None)
    is_ppp     = (sigla_tipo == "PPP") or (cod_tipo == 192)

    if is_ppp and relacionada:
        principal_id  = _get(relacionada, "id")
        principal_sig = _get(relacionada, "siglaTipo")
        principal_num = _get(relacionada, "numero")
        principal_ano = _get(relacionada, "ano")
        ementa_ok     = _get(relacionada, "ementa")
    else:
        principal_id  = _get(prop, "id")
        principal_sig = _get(prop, "siglaTipo")
        principal_num = _get(prop, "numero")
        principal_ano = _get(prop, "ano")
        ementa_ok     = _get(prop, "ementa")

    # Relator direto da pauta
    rel_nome = _get(rel, "nome")
    rel_part = _get(rel, "siglaPartido")
    rel_foto = _get(rel, "urlFoto")
    rel_uri  = _get(rel, "uri")

    # Complementa se faltar
    if (not rel_part or not rel_foto) and rel_uri:
        if not rel_part:
            rel_part = obter_sigla_partido_por_deputado_uri(rel_uri)
        if not rel_foto:
            rel_foto = obter_foto_por_deputado_uri(rel_uri)

    return ItemPauta(
        id_proposicao = principal_id,
        pauta_id      = _get(prop, "id"),
        titulo        = titulo or f"{principal_sig} {principal_num}/{principal_ano}",
        sigla_tipo    = principal_sig,
        numero        = principal_num,
        ano           = principal_ano,
        ementa        = ementa_ok,
        nome_relator  = _format_nome_partido(rel_nome, rel_part),
        regime        = regime,
        topico        = topico,
        autores       = [],        # preencheremos depois
        destaques     = [],        # preencheremos depois
        relator_foto  = rel_foto or "",
    )

# -----------------------------------------------------------------------------
# PAUTA DA SESSÃO
# -----------------------------------------------------------------------------
def obter_pauta_sessao(data_str):
    ck = f"pauta:{data_str}"
    c = _cache_get(ck)
    if c is not None:
        return c

    try:
        # 1) Buscar eventos do dia
        r = SESSION.get(
            f"{API_URL}/eventos",
            params={
                "idOrgao": PLENARIO_ID,
                "dataInicio": data_str,
                "dataFim": data_str,
                "ordem": "ASC",
                "ordenarPor": "dataHoraInicio",
            },
            timeout=15,
        )
        r.raise_for_status()
        eventos = r.json().get("dados", []) or []
        eventos_delib = [e for e in eventos if isinstance(e.get("descricaoTipo"), str) and "Sessão Deliberativa" in e.get("descricaoTipo")]
        if not eventos_delib:
            res = ResultadoPauta(tem_sessao=False, erro=f"Nenhuma sessão deliberativa em {data_str}")
            _cache_set(ck, res)
            return res

        evento = eventos_delib[-1]
        evento_id = evento.get("id")
        situacao = norm(evento.get("situacao") or "Não Informada")

        # 2) Pauta do evento
        rp = SESSION.get(f"{API_URL}/eventos/{evento_id}/pauta", timeout=15)
        if rp.status_code != 200:
            res = ResultadoPauta(tem_sessao=True, situacao=situacao, erro=f"Erro ao buscar pauta (HTTP {rp.status_code})")
            _cache_set(ck, res)
            return res

        dados_pauta = rp.json().get("dados", []) or []

        # 3) Montagem + Dedup (por id_proposicao principal)
        itens_base = []
        seen = set()
        for raw in dados_pauta:
            try:
                item = _mk_item_from_pauta(raw)
                if not item.id_proposicao:
                    continue
                if item.id_proposicao in seen:
                    continue
                seen.add(item.id_proposicao)
                itens_base.append(item)
            except Exception as e:
                logger.error(f"prep item: {e}")

        # 4) Enriquecer com autores e DTQ em paralelo (usando a proposição principal)
        def _fetch(pid):
            return pid, obter_autores_proposicao(pid), obter_destaques_dtq(pid)

        itens = []
        with ThreadPoolExecutor(max_workers=6) as pool:
            futs = {pool.submit(_fetch, it.id_proposicao): it for it in itens_base}
            for f in as_completed(futs):
                base = futs[f]
                try:
                    _pid, autores, destaques = f.result()
                except Exception as e:
                    logger.error(f"parallel {base.id_proposicao}: {e}")
                    autores, destaques = [], []
                base.autores = autores
                base.destaques = destaques
                itens.append(base)

        res = ResultadoPauta(encontrou=True, tem_sessao=True, pauta=itens, situacao=situacao)
        _cache_set(ck, res)
        return res

    except Exception as e:
        logger.error(f"pauta erro: {e}")
        res = ResultadoPauta(erro=f"Erro na API: {str(e)}")
        _cache_set(ck, res)
        return res

# -----------------------------------------------------------------------------
# FLASK
# -----------------------------------------------------------------------------
app = Flask(__name__, static_url_path='/static', static_folder='static')

@app.route("/", methods=["GET"])
def index():
    # Forçar limpeza de cache: /?data=YYYY-MM-DD&nocache=1
    if request.args.get("nocache", "").lower() in ("1", "true", "yes"):
        _cache_clear()

    tz = pytz.timezone("America/Sao_Paulo")
    hoje = date.today().strftime("%Y-%m-%d")
    data_str = request.args.get("data", hoje)
    try:
        data_fmt = datetime.strptime(data_str, "%Y-%m-%d").date()
        if data_fmt < date.today() - timedelta(days=365):
            data_fmt = date.today()
            data_str = data_fmt.strftime("%Y-%m-%d")
    except ValueError:
        data_fmt = date.today()
        data_str = data_fmt.strftime("%Y-%m-%d")

    resultado = obter_pauta_sessao(data_str)

    if not resultado.tem_sessao:
        mensagem = f"Não há Sessão Deliberativa para {data_fmt.strftime('%d/%m/%Y')}"
        itens_pauta = []
        situacao = "N/A"
    elif resultado.erro:
        mensagem = f"Erro: {resultado.erro}"
        itens_pauta = []
        situacao = "Erro"
    else:
        topico_ex = resultado.pauta[0].topico if (resultado.pauta and resultado.pauta[0].topico) else ""
        situacao = resultado.situacao or "Em Andamento"
        total_dtq = sum(len(i.destaques) for i in resultado.pauta)
        mensagem = (
            f"Pauta da Sessão{f' ({topico_ex})' if topico_ex else ''} - "
            f"{data_fmt.strftime('%d/%m/%Y')} | Status: {situacao} | Destaques DTQ: {total_dtq}"
        )
        itens_pauta = resultado.pauta

    return render_template(
        "pauta.html",
        data=data_fmt.strftime("%Y-%m-%d"),
        data_br=data_fmt.strftime("%d/%m/%Y"),
        mensagem=mensagem,
        itens_pauta=itens_pauta,
        resultado=resultado,
        situacao=situacao,
        atualizacao=datetime.now(tz).strftime("%H:%M:%S"),
    )

@app.route("/api/pauta/<data_str>", methods=["GET"])
def api_pauta(data_str):
    resultado = obter_pauta_sessao(data_str)
    try:
        data_formatada = datetime.strptime(data_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        data_formatada = data_str

    if not resultado.tem_sessao:
        return jsonify({"tem_sessao": False, "mensagem": f"Não há sessão para {data_formatada}"})

    resp = {
        "tem_sessao": True,
        "data": data_formatada,
        "situacao": resultado.situacao,
        "itens_pauta": [{
            "id_proposicao": it.id_proposicao,   # principal
            "pauta_id": it.pauta_id,             # id da pauta (PPP quando houver)
            "titulo": it.titulo,
            "identificacao": it.identificacao_completa,
            "ementa": it.ementa,
            "relator": it.nome_relator,
            "relator_foto": it.relator_foto,
            "regime": it.regime,
            "topico": it.topico,
            "autores": it.autores,
            "destaques": [{
                "numero": d.numero,
                "sigla_tipo": d.sigla_tipo,
                "data_hora": d.data_hora,
                "ementa": d.ementa,
                "url_inteiro_teor": d.url_inteiro_teor,
                "descricao_tipo": d.descricao_tipo,
                "despacho": d.despacho,
                "autores": d.autores
            } for d in it.destaques]
        } for it in resultado.pauta]
    }
    if resultado.erro:
        resp["erro"] = resultado.erro
    return jsonify(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
