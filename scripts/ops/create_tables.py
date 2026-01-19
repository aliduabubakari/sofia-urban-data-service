from suds_core.db.engine import get_engine
from suds_core.db.models import Base

engine = get_engine()
Base.metadata.create_all(engine)
print("OK: tables created")