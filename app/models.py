# app/models.py
from datetime import datetime
from enum import Enum
from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint, Enum as SAEnum, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DDZ(Base):
    __tablename__ = "ddz"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    escolas: Mapped[list["Escola"]] = relationship(back_populates="ddz", cascade="all,delete")


class Escola(Base):
    __tablename__ = "escola"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    ddz_id: Mapped[int] = mapped_column(ForeignKey("ddz.id", ondelete="RESTRICT"), index=True)
    ddz: Mapped[DDZ] = relationship(back_populates="escolas")
    professores: Mapped[list["Professor"]] = relationship(back_populates="escola", cascade="all,delete")


class Professor(Base):
    __tablename__ = "professor"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(180), index=True)
    documento: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    escola_id: Mapped[int] = mapped_column(ForeignKey("escola.id", ondelete="RESTRICT"), index=True)
    escola: Mapped[Escola] = relationship(back_populates="professores")
    certificacoes: Mapped[list["Certificacao"]] = relationship(back_populates="professor", cascade="all,delete")


class Ano(Base):
    __tablename__ = "ano"
    id: Mapped[int] = mapped_column(primary_key=True)
    valor: Mapped[int] = mapped_column(index=True, unique=True)
    turmas: Mapped[list["Turma"]] = relationship(back_populates="ano", cascade="all,delete")


class Turma(Base):
    __tablename__ = "turma"
    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[int] = mapped_column(index=True)
    ano_id: Mapped[int] = mapped_column(ForeignKey("ano.id", ondelete="RESTRICT"), index=True)
    ano: Mapped[Ano] = relationship(back_populates="turmas")
    certificacoes: Mapped[list["Certificacao"]] = relationship(back_populates="turma", cascade="all,delete")

    __table_args__ = (UniqueConstraint("numero", "ano_id", name="uq_turma_numero_ano"),)

    @property
    def label(self) -> str:
        if self.ano and self.ano.valor:
            return f"{self.numero}/{self.ano.valor}"
        return f"{self.numero}/—"


class StatusCert(str, Enum):
    CERTIFICADO = "CERTIFICADO"
    NAO_CERTIFICADO = "NAO_CERTIFICADO"


class Certificacao(Base):
    __tablename__ = "certificacao"
    id: Mapped[int] = mapped_column(primary_key=True)
    professor_id: Mapped[int] = mapped_column(ForeignKey("professor.id", ondelete="CASCADE"), index=True)
    turma_id: Mapped[int] = mapped_column(ForeignKey("turma.id", ondelete="RESTRICT"), index=True)
    ano_id: Mapped[int] = mapped_column(ForeignKey("ano.id", ondelete="RESTRICT"), index=True)
    status: Mapped[StatusCert] = mapped_column(SAEnum(StatusCert), index=True, default=StatusCert.NAO_CERTIFICADO)
    certificado_arquivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    professor: Mapped[Professor] = relationship(back_populates="certificacoes")
    turma: Mapped[Turma] = relationship(back_populates="certificacoes")
    ano: Mapped[Ano] = relationship()
