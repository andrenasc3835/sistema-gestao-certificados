# app/main.py
import os
from typing import Optional, Tuple

from fastapi import FastAPI, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.orm import aliased

from app.db import init_db, get_session
from app.models import (
    DDZ,
    Escola,
    Professor,
    Ano,
    Turma,
    Certificacao,
    StatusCert,
)
from app.certificados import router as certificados_router
from app.turmas import router as turmas_router
from app.importador import router as importador_router


# ------------------------------------------------------------------------------
# APP / STATIC / TEMPLATES
# ------------------------------------------------------------------------------
app = FastAPI(title="Gestão de Certificados")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ------------------------------------------------------------------------------
# STARTUP
# ------------------------------------------------------------------------------
@app.on_event("startup")
def on_startup():
    # Dev: cria tabelas (em prod, use Alembic)
    init_db()
    os.makedirs("storage/certificados", exist_ok=True)


# ------------------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------------------
def parse_turma_label(label: str) -> Optional[Tuple[int, int]]:
    """
    Converte 'N/AAAA' -> (N, AAAA).
    Retorna None se formato inválido.
    """
    try:
        n, a = label.split("/")
        return int(n), int(a)
    except Exception:
        return None


def get_or_create_ano(db: Session, ano_valor: int) -> Ano:
    ano = db.query(Ano).filter_by(valor=ano_valor).one_or_none()
    if not ano:
        ano = Ano(valor=ano_valor)
        db.add(ano)
        db.flush()
    return ano


def get_or_create_turma(db: Session, numero: int, ano: Ano) -> Turma:
    turma = (
        db.query(Turma)
        .filter(Turma.numero == numero, Turma.ano_id == ano.id)
        .one_or_none()
    )
    if not turma:
        turma = Turma(numero=numero, ano_id=ano.id)
        db.add(turma)
        db.flush()
    return turma


# ------------------------------------------------------------------------------
# ROOT / VISÃO GERAL (PAGE + API)
# ------------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse("/visao-geral")


@app.get("/visao-geral", response_class=HTMLResponse)
def visao_geral(request: Request):
    # Página renderiza; dados chegam por /api/visao-geral
    return templates.TemplateResponse("visao_geral.html", {"request": request})


@app.get("/api/visao-geral")
def api_visao_geral(
    turma: str | None = None,
    only_certificados: int = 0,
    db: Session = Depends(get_session),
):
    """
    Construímos as queries a partir de Certificacao (pivot) e fazemos JOINs
    para Professor -> Escola -> DDZ e Turma -> Ano. Assim evitamos perder
    linhas por causa da ordem de join.
    """
    # Raiz
    q_base = (
        db.query(
            DDZ.nome.label("ddz"),
            Escola.nome.label("escola"),
            Professor.nome.label("professor"),
            Ano.valor.label("ano"),
            Turma.numero.label("numero"),
            Certificacao.certificado_arquivo.label("arquivo"),
            Certificacao.status.label("status"),
            Certificacao.id.label("cert_id"),
        )
        .select_from(Certificacao)
        .join(Professor, Professor.id == Certificacao.professor_id)
        .join(Escola, Escola.id == Professor.escola_id)
        .join(DDZ, DDZ.id == Escola.ddz_id)
        .join(Turma, Turma.id == Certificacao.turma_id)
        .join(Ano, Ano.id == Turma.ano_id)
    )

    # Filtros
    if turma:
        try:
            n, a = turma.split("/")
            q_base = q_base.filter(Turma.numero == int(n), Ano.valor == int(a))
        except Exception:
            pass

    if only_certificados:
        q_base = q_base.filter(Certificacao.status == StatusCert.CERTIFICADO)

    rows = q_base.order_by(DDZ.nome, Escola.nome, Professor.nome).all()

    # Contagens para gráficos (reusando a mesma raiz)
    def group_count(select_field, label_cast=str):
        qg = (
            db.query(select_field, func.count(Certificacao.id))
            .select_from(Certificacao)
            .join(Professor, Professor.id == Certificacao.professor_id)
            .join(Escola, Escola.id == Professor.escola_id)
            .join(DDZ, DDZ.id == Escola.ddz_id)
            .join(Turma, Turma.id == Certificacao.turma_id)
            .join(Ano, Ano.id == Turma.ano_id)
        )
        if turma:
            try:
                n, a = turma.split("/")
                qg = qg.filter(Turma.numero == int(n), Ano.valor == int(a))
            except Exception:
                pass
        if only_certificados:
            qg = qg.filter(Certificacao.status == StatusCert.CERTIFICADO)

        if select_field is DDZ.nome:
            qg = qg.group_by(DDZ.nome).order_by(DDZ.nome)
        elif select_field is Escola.nome:
            qg = qg.group_by(Escola.nome).order_by(Escola.nome)
        else:  # Ano.valor
            qg = qg.group_by(Ano.valor).order_by(Ano.valor)

        return [{"label": label_cast(v), "value": c} for v, c in qg.all()]

    por_ddz    = group_count(DDZ.nome)
    por_escola = group_count(Escola.nome)
    por_ano    = group_count(Ano.valor, label_cast=lambda x: str(x))

    return {
        "por_ddz": por_ddz,
        "por_escola": por_escola,
        "por_ano": por_ano,
        "rows": [
            {
                "ddz": r.ddz,
                "escola": r.escola,
                "professor": r.professor,
                "ano": r.ano,
                "turma": f"{r.numero}/{r.ano}",
                "has_cert": bool(r.arquivo),
                "status": getattr(r.status, "value", r.status),
                "cert_id": r.cert_id,
            }
            for r in rows
        ],
    }


# ------------------------------------------------------------------------------
# PÁGINAS (CRUD UI)
# ------------------------------------------------------------------------------
@app.get("/ddz", response_class=HTMLResponse)
def page_ddz(request: Request, db: Session = Depends(get_session)):
    ddzs = db.query(DDZ).order_by(DDZ.nome).all()
    return templates.TemplateResponse("ddz_list.html", {"request": request, "ddzs": ddzs})


@app.get("/escolas", response_class=HTMLResponse)
def page_escolas(request: Request, db: Session = Depends(get_session)):
    escolas = db.query(Escola).order_by(Escola.nome).all()
    ddzs = db.query(DDZ).order_by(DDZ.nome).all()
    return templates.TemplateResponse(
        "escolas_list.html",
        {"request": request, "escolas": escolas, "ddzs": ddzs},
    )


@app.get("/professores", response_class=HTMLResponse)
def page_professores(request: Request, db: Session = Depends(get_session)):
    professores = db.query(Professor).order_by(Professor.nome).all()
    ddzs = db.query(DDZ).order_by(DDZ.nome).all()
    escolas = db.query(Escola).order_by(Escola.nome).all()
    anos = db.query(Ano).order_by(Ano.valor).all()
    turmas = db.query(Turma).join(Ano).order_by(Ano.valor, Turma.numero).all()
    return templates.TemplateResponse(
        "professores_list.html",
        {
            "request": request,
            "professores": professores,
            "ddzs": ddzs,
            "escolas": escolas,
            "anos": anos,
            "turmas": turmas,
        },
    )


@app.get("/anos", response_class=HTMLResponse)
def page_anos(request: Request, db: Session = Depends(get_session)):
    anos = db.query(Ano).order_by(Ano.valor).all()
    return templates.TemplateResponse("anos_list.html", {"request": request, "anos": anos})


@app.get("/turmas", response_class=HTMLResponse)
def page_turmas(request: Request, db: Session = Depends(get_session)):
    turmas = db.query(Turma).join(Ano).order_by(Ano.valor, Turma.numero).all()
    anos = db.query(Ano).order_by(Ano.valor).all()
    return templates.TemplateResponse(
        "turmas_list.html", {"request": request, "turmas": turmas, "anos": anos}
    )


@app.get("/certificados", response_class=HTMLResponse)
def page_certificados(request: Request, view: str = "certificados", db: Session = Depends(get_session)):
    if view == "nao":
        nao_certificadas = (
            db.query(Certificacao)
            .filter(Certificacao.status == StatusCert.NAO_CERTIFICADO)
            .order_by(Certificacao.id.desc())
            .all()
        )
        return templates.TemplateResponse(
            "certificados_list.html",
            {"request": request, "view": "nao", "nao_certificadas": nao_certificadas},
        )
    else:
        certificadas = (
            db.query(Certificacao)
            .filter(Certificacao.status == StatusCert.CERTIFICADO)
            .order_by(Certificacao.id.desc())
            .all()
        )
        return templates.TemplateResponse(
            "certificados_list.html",
            {"request": request, "view": "certificados", "certificadas": certificadas},
        )


@app.get("/importar", response_class=HTMLResponse)
def page_importar(request: Request):
    return templates.TemplateResponse("importar.html", {"request": request})


# ------------------------------------------------------------------------------
# DDZ - CRUD (POST)
# ------------------------------------------------------------------------------
@app.post("/ddz")
def ddz_create(nome: str = Form(...), db: Session = Depends(get_session)):
    nome = nome.strip()
    if not nome:
        return RedirectResponse("/ddz", status_code=status.HTTP_303_SEE_OTHER)
    try:
        d = DDZ(nome=nome)
        db.add(d)
        db.commit()
    except IntegrityError:
        db.rollback()
    return RedirectResponse("/ddz", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/ddz/{ddz_id}/update")
def ddz_update(ddz_id: int, nome: str = Form(...), db: Session = Depends(get_session)):
    d = db.get(DDZ, ddz_id)
    if d:
        d.nome = nome.strip()
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return RedirectResponse("/ddz", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/ddz/{ddz_id}/delete")
def ddz_delete(ddz_id: int, db: Session = Depends(get_session)):
    d = db.get(DDZ, ddz_id)
    if d:
        try:
            db.delete(d)
            db.commit()
        except IntegrityError:
            db.rollback()
    return RedirectResponse("/ddz", status_code=status.HTTP_303_SEE_OTHER)


# ------------------------------------------------------------------------------
# ESCOLAS - CRUD (POST)
# ------------------------------------------------------------------------------
@app.post("/escolas")
def escola_create(
    nome: str = Form(...),
    ddz_id: int = Form(...),
    db: Session = Depends(get_session),
):
    nome = nome.strip()
    ddz = db.get(DDZ, ddz_id)
    if not nome or not ddz:
        return RedirectResponse("/escolas", status_code=status.HTTP_303_SEE_OTHER)

    try:
        e = Escola(nome=nome, ddz_id=ddz.id)
        db.add(e)
        db.commit()
    except IntegrityError:
        db.rollback()
    return RedirectResponse("/escolas", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/escolas/{escola_id}/update")
def escola_update(
    escola_id: int,
    nome: str = Form(...),
    ddz_id: int = Form(...),
    db: Session = Depends(get_session),
):
    e = db.get(Escola, escola_id)
    d = db.get(DDZ, ddz_id)
    if e and d:
        e.nome = nome.strip()
        e.ddz_id = d.id
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return RedirectResponse("/escolas", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/escolas/{escola_id}/delete")
def escola_delete(escola_id: int, db: Session = Depends(get_session)):
    e = db.get(Escola, escola_id)
    if e:
        try:
            db.delete(e)
            db.commit()
        except IntegrityError:
            db.rollback()
    return RedirectResponse("/escolas", status_code=status.HTTP_303_SEE_OTHER)


# ------------------------------------------------------------------------------
# PROFESSORES - CRUD (POST)
# ------------------------------------------------------------------------------
@app.post("/professores")
def professor_create(
    nome: str = Form(...),
    escola_id: int = Form(...),
    ano_valor: Optional[int] = Form(None),
    turma_label: Optional[str] = Form(None),
    db: Session = Depends(get_session),
):
    nome = nome.strip()
    escola = db.get(Escola, escola_id)
    if not nome or not escola:
        return RedirectResponse("/professores", status_code=status.HTTP_303_SEE_OTHER)

    try:
        p = Professor(nome=nome, escola_id=escola.id)
        db.add(p)
        db.flush()

        # Se vier Ano/Turma, cria (se não existir) a certificação NAO_CERTIFICADO
        if ano_valor and turma_label:
            parsed = parse_turma_label(turma_label)
            if parsed:
                numero, ano_label = parsed
                # Segurança: se ano_label e ano_valor divergirem, prioriza o 'ano_valor' do form
                ano = get_or_create_ano(db, ano_valor)
                turma = get_or_create_turma(db, numero, ano)

                exists = (
                    db.query(Certificacao)
                    .filter(
                        Certificacao.professor_id == p.id,
                        Certificacao.turma_id == turma.id,
                    )
                    .one_or_none()
                )
                if not exists:
                    cert = Certificacao(
                        professor_id=p.id,
                        turma_id=turma.id,
                        ano_id=ano.id,
                        status=StatusCert.NAO_CERTIFICADO,
                    )
                    db.add(cert)

        db.commit()
    except IntegrityError:
        db.rollback()

    return RedirectResponse("/professores", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/professores/{prof_id}/delete")
def professor_delete(prof_id: int, db: Session = Depends(get_session)):
    p = db.get(Professor, prof_id)
    if p:
        try:
            db.delete(p)
            db.commit()
        except IntegrityError:
            db.rollback()
    return RedirectResponse("/professores", status_code=status.HTTP_303_SEE_OTHER)


# ------------------------------------------------------------------------------
# ANOS - CRUD (POST)
# ------------------------------------------------------------------------------
@app.post("/anos")
def anos_create(valor: int = Form(...), db: Session = Depends(get_session)):
    try:
        a = Ano(valor=valor)
        db.add(a)
        db.commit()
    except IntegrityError:
        db.rollback()
    return RedirectResponse("/anos", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/anos/{ano_id}/delete")
def anos_delete(ano_id: int, db: Session = Depends(get_session)):
    a = db.get(Ano, ano_id)
    if a:
        try:
            db.delete(a)
            db.commit()
        except IntegrityError:
            db.rollback()
    return RedirectResponse("/anos", status_code=status.HTTP_303_SEE_OTHER)


# ------------------------------------------------------------------------------
# INCLUDE ROUTERS (Certificados / Turmas / Importação)
# ------------------------------------------------------------------------------
app.include_router(certificados_router)
app.include_router(turmas_router)
app.include_router(importador_router)
