# app/certificados.py
import os
import uuid
import shutil
from typing import Literal

from fastapi import APIRouter, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Certificacao, StatusCert

router = APIRouter(prefix="/certificados", tags=["Certificados"])

STORAGE_ROOT = os.getenv("CERTS_DIR", "storage/certificados")


@router.get("/{certificacao_id}/download")
def download_certificado(certificacao_id: int, db: Session = Depends(get_session)):
    c = db.get(Certificacao, certificacao_id)
    if not c or not c.certificado_arquivo:
        return JSONResponse({"error": "Certificado não encontrado"}, status_code=404)
    path = os.path.abspath(c.certificado_arquivo)
    if not os.path.exists(path):
        return JSONResponse({"error": "Arquivo ausente no disco"}, status_code=410)
    filename = os.path.basename(path)
    return FileResponse(path, filename=filename, media_type="application/pdf")


@router.post("/upload")
def upload_certificado(
    certificacao_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
):
    c = db.get(Certificacao, certificacao_id)
    if not c:
        return {"error": "Certificação inválida"}

    os.makedirs(os.path.join(STORAGE_ROOT, str(c.professor_id)), exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower()
    fname = f"{uuid.uuid4().hex}{ext or '.pdf'}"
    path = os.path.join(STORAGE_ROOT, str(c.professor_id), fname)

    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Apaga antigo se existir
    if c.certificado_arquivo and os.path.exists(c.certificado_arquivo):
        try:
            os.remove(c.certificado_arquivo)
        except Exception:
            pass

    c.certificado_arquivo = path
    c.status = StatusCert.CERTIFICADO
    db.commit()
    return {"ok": True, "certificado": {"id": c.id, "path": path}}


@router.post("/delete")
def excluir_certificado(
    certificacao_id: int = Form(...),
    manter_status: Literal["sim", "nao"] = Form("sim"),
    db: Session = Depends(get_session),
):
    c = db.get(Certificacao, certificacao_id)
    if not c:
        return {"error": "Certificação inválida"}

    # Remove arquivo
    if c.certificado_arquivo and os.path.exists(c.certificado_arquivo):
        try:
            os.remove(c.certificado_arquivo)
        except Exception:
            pass
    c.certificado_arquivo = None

    # Regra: manter status ou marcar como NÃO CERTIFICADO
    if manter_status == "nao":
        c.status = StatusCert.NAO_CERTIFICADO

    db.commit()
    return {"ok": True}
