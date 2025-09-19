# app/turmas.py
from fastapi import APIRouter, Form, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from app.db import get_session
from app.models import Ano, Turma

router = APIRouter(prefix="/turmas", tags=["Turmas"])


@router.get("")
def listar_turmas(
    ano: int | None = Query(None, description="Filtra por ano (ex.: 2025)"),
    db: Session = Depends(get_session),
):
    q = db.query(Turma).join(Ano)
    if ano is not None:
        q = q.filter(Ano.valor == ano)
    turmas = q.order_by(Ano.valor, Turma.numero).all()
    return [{"id": t.id, "label": t.label, "ano": t.ano.valor, "numero": t.numero} for t in turmas]


@router.post("/create")
def criar_turma(
    ano_valor: int = Form(..., description="Ex.: 2025"),
    db: Session = Depends(get_session),
):
    ano = db.query(Ano).filter_by(valor=ano_valor).one_or_none()
    if not ano:
        ano = Ano(valor=ano_valor)
        db.add(ano)
        db.flush()

    max_num = db.query(func.max(Turma.numero)).filter(Turma.ano_id == ano.id).scalar() or 0
    nova = Turma(numero=max_num + 1, ano_id=ano.id)
    db.add(nova)
    db.commit()
    db.refresh(nova)
    return {"ok": True, "turma": {"id": nova.id, "label": nova.label}}
