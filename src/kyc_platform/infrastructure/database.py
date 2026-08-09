from collections.abc import Generator
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, String, create_engine, func, or_, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, joinedload, mapped_column, relationship, sessionmaker

from kyc_platform.domain.models import NormalizedCustomer, ScreeningMatch, ScreeningResult


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class CustomerORM(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    record_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    registered_country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True, index=True)
    registration_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    normalized_registration_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    lei: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    incorporation_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_kyc_review: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    aum_usd_millions: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_pep: Mapped[bool] = mapped_column(default=False, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    screening_cases: Mapped[list["ScreeningCaseORM"]] = relationship(back_populates="customer")


class ScreeningCaseORM(Base):
    __tablename__ = "screening_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="open", nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(100), nullable=False)
    matched_entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    matched_name: Mapped[str] = mapped_column(String(500), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    decision: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    customer: Mapped[CustomerORM] = relationship(back_populates="screening_cases")


class AuditEventORM(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Database:
    def __init__(self, url: str) -> None:
        parsed = make_url(url)
        if parsed.drivername.startswith("sqlite") and parsed.database not in (None, ":memory:"):
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        connect_args = {"check_same_thread": False} if parsed.drivername.startswith("sqlite") else {}
        self.engine: Engine = create_engine(url, future=True, pool_pre_ping=True, connect_args=connect_args)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False, class_=Session)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def drop_schema(self) -> None:
        Base.metadata.drop_all(self.engine)

    def ping(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


class CustomerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, customer: NormalizedCustomer) -> CustomerORM:
        model = CustomerORM(
            record_id=customer.record_id,
            entity_type=customer.entity_type.value,
            legal_name=customer.legal_name,
            normalized_name=customer.normalized_name,
            aliases=customer.aliases,
            registered_country=customer.registered_country,
            registration_number=customer.registration_number,
            normalized_registration_number=customer.normalized_registration_number,
            lei=customer.lei,
            incorporation_date=customer.incorporation_date,
            last_kyc_review=customer.last_kyc_review,
            aum_usd_millions=customer.aum_usd_millions,
            is_pep=customer.is_pep,
            source=customer.source,
            extra_data=customer.extra_data,
        )
        self.session.add(model)
        try:
            self.session.flush()
        except IntegrityError as exc:
            raise ValueError(f"customer record_id already exists: {customer.record_id}") from exc
        return model

    def get(self, customer_id: str) -> Optional[CustomerORM]:
        return self.session.get(CustomerORM, customer_id)

    def list(
        self,
        offset: int = 0,
        limit: int = 100,
        query: Optional[str] = None,
        country: Optional[str] = None,
        is_pep: Optional[bool] = None,
    ) -> list[CustomerORM]:
        statement = select(CustomerORM)
        if query:
            pattern = f"%{query.strip()}%"
            statement = statement.where(
                or_(
                    CustomerORM.legal_name.ilike(pattern),
                    CustomerORM.normalized_name.ilike(pattern),
                    CustomerORM.record_id.ilike(pattern),
                    CustomerORM.registration_number.ilike(pattern),
                )
            )
        if country:
            statement = statement.where(CustomerORM.registered_country == country.upper())
        if is_pep is not None:
            statement = statement.where(CustomerORM.is_pep.is_(is_pep))
        statement = statement.order_by(CustomerORM.created_at.desc()).offset(offset).limit(limit)
        return list(self.session.scalars(statement))

    def count(self) -> int:
        return int(self.session.scalar(select(func.count(CustomerORM.id))) or 0)

    def count_pep(self) -> int:
        return int(self.session.scalar(select(func.count(CustomerORM.id)).where(CustomerORM.is_pep.is_(True))) or 0)


class ScreeningCaseRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_if_absent(
        self,
        customer_id: str,
        screening: ScreeningResult,
        match: ScreeningMatch,
    ) -> tuple[ScreeningCaseORM, bool]:
        existing = self.session.scalar(
            select(ScreeningCaseORM).where(
                ScreeningCaseORM.customer_id == customer_id,
                ScreeningCaseORM.dataset_version == screening.dataset_version,
                ScreeningCaseORM.matched_entity_id == match.entity_id,
                ScreeningCaseORM.status.in_(["open", "escalated"]),
            )
        )
        if existing:
            return existing, False
        model = ScreeningCaseORM(
            customer_id=customer_id,
            source=match.source,
            dataset_version=screening.dataset_version,
            matched_entity_id=match.entity_id,
            matched_name=match.matched_name,
            score=match.score,
            evidence={
                "components": match.components,
                "programs": match.programs,
                **match.evidence,
            },
        )
        self.session.add(model)
        self.session.flush()
        return model, True

    def get(self, case_id: str) -> Optional[ScreeningCaseORM]:
        return self.session.scalar(
            select(ScreeningCaseORM)
            .options(joinedload(ScreeningCaseORM.customer))
            .where(ScreeningCaseORM.id == case_id)
        )

    def list(self, status: Optional[str] = None, limit: int = 100) -> list[ScreeningCaseORM]:
        statement = select(ScreeningCaseORM).options(joinedload(ScreeningCaseORM.customer))
        if status:
            statement = statement.where(ScreeningCaseORM.status == status)
        statement = statement.order_by(ScreeningCaseORM.created_at.desc()).limit(limit)
        return list(self.session.scalars(statement))

    def decide(self, model: ScreeningCaseORM, decision: str, actor: str, notes: Optional[str]) -> ScreeningCaseORM:
        model.decision = decision
        model.status = "escalated" if decision == "escalate" else "closed"
        model.evidence = {
            **model.evidence,
            "review": {"actor": actor, "notes": notes or "", "decided_at": utc_now().isoformat()},
        }
        model.updated_at = utc_now()
        self.session.flush()
        return model

    def count_active(self) -> int:
        return int(
            self.session.scalar(
                select(func.count(ScreeningCaseORM.id)).where(ScreeningCaseORM.status.in_(["open", "escalated"]))
            )
            or 0
        )

    def count_open(self) -> int:
        return int(
            self.session.scalar(select(func.count(ScreeningCaseORM.id)).where(ScreeningCaseORM.status == "open")) or 0
        )


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        event_type: str,
        actor: str,
        entity_type: str,
        entity_id: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> AuditEventORM:
        event = AuditEventORM(
            event_type=event_type,
            actor=actor,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload or {},
        )
        self.session.add(event)
        self.session.flush()
        return event

    def count(self) -> int:
        return int(self.session.scalar(select(func.count(AuditEventORM.id))) or 0)
