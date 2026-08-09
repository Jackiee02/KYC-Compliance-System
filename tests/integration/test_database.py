from sqlalchemy import func, select

from kyc_platform.domain.models import CustomerRecord
from kyc_platform.infrastructure.database import AuditEventORM, AuditRepository, CustomerRepository, Database
from kyc_platform.services.normalization import normalize_customer


def test_customer_repository_and_audit_event(test_settings) -> None:
    database = Database(test_settings.database_url)
    database.create_schema()
    customer = normalize_customer(
        CustomerRecord(record_id="db-1", legal_name="Acme Limited", registered_country="HK", source="test")
    )

    with database.session() as session:
        stored = CustomerRepository(session).create(customer)
        AuditRepository(session).record("customer.created", "tester", "customer", stored.id)

    with database.session() as session:
        assert CustomerRepository(session).get(stored.id).normalized_name == "ACME"
        assert len(CustomerRepository(session).list()) == 1
        assert session.scalar(select(func.count()).select_from(AuditEventORM)) == 1
