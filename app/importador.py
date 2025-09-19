# app/importador.py
from io import BytesIO
import pandas as pd
from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import DDZ, Escola, Professor, Ano, Turma, Certificacao, StatusCert

router = APIRouter(prefix="/importar", tags=["Importar"])


def get_or_create(session: Session, Model, defaults=None, **where):
    inst = session.query(Model).filter_by(**where).one_or_none()
    if inst:
        return inst, False
    params = dict(where)
    if defaults:
        params.update(defaults)
    inst = Model(**params)
    session.add(inst)
    session.flush()
    return inst, True


@router.post("/excel")
async def importar_excel(file: UploadFile = File(...), db: Session = Depends(get_session)):
    raw = await file.read()
    name = file.filename.lower()
    if name.endswith(".xlsx"):
        df = pd.read_excel(BytesIO(raw))
    elif name.endswith(".csv"):
        df = pd.read_csv(BytesIO(raw))
    else:
        return {"error": "Formato inválido. Envie .xlsx ou .csv"}

    required = {"DDZ", "Escola", "Professor", "Ano", "Turma"}
    if not required.issubset(set(df.columns)):
        return {"error": f"Colunas esperadas: {', '.join(sorted(required))}"}

    inserted = dict(ddz=0, escola=0, professor=0, ano=0, turma=0, certificacao=0)
    skipped = 0
    inconsistencias: list[dict] = []

    for i, row in df.iterrows():
        try:
            ddz_nome = str(row["DDZ"]).strip()
            escola_nome = str(row["Escola"]).strip()
            prof_nome = str(row["Professor"]).strip()
            ano_valor = int(row["Ano"])
            turma_label = str(row["Turma"]).strip()  # "N/AAAA"

            if not all([ddz_nome, escola_nome, prof_nome, turma_label]):
                raise ValueError("Linha com campos vazios")

            # DDZ
            ddz, created = get_or_create(db, DDZ, nome=ddz_nome)
            inserted["ddz"] += int(created)

            # Escola
            escola, created = get_or_create(db, Escola, nome=escola_nome, defaults={"ddz_id": ddz.id})
            if not created and escola.ddz_id != ddz.id:
                escola.ddz_id = ddz.id  # corrige vínculo se vier trocado
            inserted["escola"] += int(created)

            # Professor (chave frouxa: nome + escola)
            prof, created = get_or_create(db, Professor, nome=prof_nome, escola_id=escola.id)
            inserted["professor"] += int(created)

            # Ano
            ano, created = get_or_create(db, Ano, valor=ano_valor)
            inserted["ano"] += int(created)

            # Turma a partir de "N/AAAA"
            try:
                numero = int(turma_label.split("/")[0])
            except Exception:
                numero = 1  # fallback
            turma, created = get_or_create(db, Turma, numero=numero, ano_id=ano.id)
            inserted["turma"] += int(created)

            # Certificação (única por professor+turma)
            cert = (
                db.query(Certificacao)
                .filter(Certificacao.professor_id == prof.id, Certificacao.turma_id == turma.id)
                .one_or_none()
            )
            if cert is None:
                cert = Certificacao(
                    professor_id=prof.id,
                    turma_id=turma.id,
                    ano_id=ano.id,
                    status=StatusCert.NAO_CERTIFICADO,
                )
                db.add(cert)
                inserted["certificacao"] += 1
            else:
                skipped += 1

        except Exception as e:
            inconsistencias.append({"linha": int(i) + 2, "erro": str(e)})
            continue

    db.commit()
    return {"ok": True, "inserted": inserted, "skipped_existing_certifications": skipped, "inconsistencias": inconsistencias}
