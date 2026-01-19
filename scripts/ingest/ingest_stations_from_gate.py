from suds_core.db.engine import session_scope
from suds_core.services.stations import upsert_stations_from_gate

def main():
    with session_scope() as session:
        result = upsert_stations_from_gate(session)
        print("OK:", result)

if __name__ == "__main__":
    main()