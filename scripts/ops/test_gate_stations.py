from suds_core.connectors.gate import GateClient

def main():
    client = GateClient()
    stations = client.list_stations()
    print("variant:", client.variant_name)
    print("stations:", len(stations))
    print("sample:", stations[0] if stations else None)

if __name__ == "__main__":
    main()