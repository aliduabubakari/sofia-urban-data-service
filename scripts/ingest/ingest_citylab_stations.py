from suds_core.db.engine import session_scope
from suds_core.services.citylab_ingest import upsert_citylab_stations

def main():
    with session_scope() as session:
        res = upsert_citylab_stations(session)
        print(res)

if __name__ == "__main__":
    main()