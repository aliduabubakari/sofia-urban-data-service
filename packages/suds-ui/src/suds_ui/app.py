from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import pydeck as pdk
import requests
import streamlit as st
from dotenv import load_dotenv


def load_repo_env() -> None:
    """
    Try to load repo-root .env so users don't need to export env vars manually.
    We walk up from this file to find a .env.
    """
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        env_path = parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            return


def api_get(base_url: str, path: str, api_key: str, params: Optional[dict[str, Any]] = None) -> Dict[str, Any]:
    url = base_url.rstrip("/") + path
    r = requests.get(url, headers={"X-API-Key": api_key}, params=params, timeout=120)
    r.raise_for_status()
    return r.json()


def geojson_layer(geojson: Dict[str, Any], fill_rgba=(0, 128, 255, 60), line_rgba=(0, 80, 160, 200)) -> pdk.Layer:
    return pdk.Layer(
        "GeoJsonLayer",
        data=geojson,
        pickable=True,
        stroked=True,
        filled=True,
        extruded=False,
        get_fill_color=list(fill_rgba),
        get_line_color=list(line_rgba),
        line_width_min_pixels=1,
    )


load_repo_env()

st.set_page_config(page_title="SUDS UI", layout="wide")
st.title("SUDS UI (Streamlit)")

with st.sidebar:
    st.header("Connection")
    base_url = st.text_input("API Base URL", value=os.getenv("SUDS_API_BASE_URL", "http://127.0.0.1:8000"))
    api_key = st.text_input("X-API-Key", value=os.getenv("SUDS_API_KEY", ""), type="password")
    st.caption("Tip: put SUDS_API_BASE_URL and SUDS_API_KEY in repo-root .env")

    section = st.radio("Mode", ["Datasets", "Enrich Point", "OSM Metrics", "Weather Daily"], index=1)

if not api_key:
    st.warning("Set an API key in the sidebar (X-API-Key).")
    st.stop()

default_lat, default_lon = 42.69, 23.32


if section == "Datasets":
    st.subheader("Datasets → GeoJSON")

    datasets_resp = api_get(base_url, "/datasets", api_key)
    dataset_names = datasets_resp.get("datasets", [])

    col1, col2 = st.columns([1, 1])
    with col1:
        dataset = st.selectbox("Dataset", dataset_names)
        query_mode = st.selectbox("Query mode", ["bbox", "radius"])
        limit = st.number_input("limit", min_value=1, value=2000, step=100)
        simplify_m = st.number_input("simplify_m (lines/polygons)", min_value=0.0, value=5.0, step=1.0)

    params: dict[str, Any] = {"limit": int(limit)}
    if query_mode == "bbox":
        with col2:
            bbox = st.text_input("bbox (minx,miny,maxx,maxy)", value="23.30,42.65,23.36,42.71")
        params["bbox"] = bbox
        if simplify_m > 0:
            params["simplify_m"] = float(simplify_m)
    else:
        with col2:
            lat = st.number_input("lat", value=default_lat, format="%.6f")
            lon = st.number_input("lon", value=default_lon, format="%.6f")
            radius_m = st.number_input("radius_m", min_value=1, value=300, step=50)
        params.update({"lat": float(lat), "lon": float(lon), "radius_m": float(radius_m)})
        if simplify_m > 0:
            params["simplify_m"] = float(simplify_m)

    if st.button("Fetch GeoJSON"):
        try:
            fc = api_get(base_url, f"/datasets/{dataset}", api_key, params=params)
            st.success(f"Returned {len(fc.get('features', []))} features")

            view_state = pdk.ViewState(latitude=default_lat, longitude=default_lon, zoom=13)
            st.pydeck_chart(pdk.Deck(layers=[geojson_layer(fc)], initial_view_state=view_state))

            with st.expander("Raw response"):
                st.json(fc)

        except requests.HTTPError as e:
            st.error(f"HTTP error: {e.response.status_code} {e.response.text}")
        except Exception as e:
            st.error(str(e))


elif section == "Enrich Point":
    st.subheader("Enrich Point (OSM + Weather + optional geometries)")

    col1, col2, col3 = st.columns(3)
    with col1:
        lat = st.number_input("lat", value=default_lat, format="%.6f")
        lon = st.number_input("lon", value=default_lon, format="%.6f")
        radius_m = st.number_input("radius_m", min_value=1, value=300, step=50)

    with col2:
        start = st.text_input("start (YYYY-MM-DD)", value="2024-08-01")
        end = st.text_input("end (YYYY-MM-DD)", value="2024-08-07")
        mode = st.selectbox("geometry mode", ["both", "bbox", "radius", "none"], index=0)

    with col3:
        datasets = st.text_input("datasets (comma-separated)", value="streets,pois,green_areas")
        limit = st.number_input("limit", min_value=1, value=2000, step=100)
        simplify_m = st.number_input("simplify_m", min_value=0.0, value=5.0, step=1.0)

    if st.button("Run enrichment"):
        params = {
            "lat": float(lat),
            "lon": float(lon),
            "radius_m": int(radius_m),
            "start": start,
            "end": end,
            "datasets": datasets,
            "mode": mode,
            "limit": int(limit),
        }
        if simplify_m > 0:
            params["simplify_m"] = float(simplify_m)

        try:
            data = api_get(base_url, "/enrich/point", api_key, params=params)
            st.success("OK")

            st.write("Elevation (m):", data.get("elevation_m"))
            st.write("OSM cached:", data.get("osm", {}).get("cached"))

            geoms = data.get("geometries", {})
            if isinstance(geoms, dict) and "bbox" in geoms:
                layers = []
                for _, fc in geoms["bbox"].items():
                    layers.append(geojson_layer(fc))
                view_state = pdk.ViewState(latitude=float(lat), longitude=float(lon), zoom=14)
                st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view_state))

            with st.expander("Raw response"):
                st.json(data)

        except requests.HTTPError as e:
            st.error(f"HTTP error: {e.response.status_code} {e.response.text}")
        except Exception as e:
            st.error(str(e))


elif section == "OSM Metrics":
    st.subheader("OSM Metrics (cached)")
    lat = st.number_input("lat", value=default_lat, format="%.6f")
    lon = st.number_input("lon", value=default_lon, format="%.6f")
    radius_m = st.number_input("radius_m", min_value=1, value=300, step=50)
    refresh = st.checkbox("refresh (force recompute)", value=False)

    if st.button("Fetch OSM metrics"):
        try:
            data = api_get(
                base_url,
                "/osm/metrics",
                api_key,
                params={"lat": float(lat), "lon": float(lon), "radius_m": int(radius_m), "refresh": refresh},
            )
            st.json(data)
        except requests.HTTPError as e:
            st.error(f"HTTP error: {e.response.status_code} {e.response.text}")
        except Exception as e:
            st.error(str(e))


elif section == "Weather Daily":
    st.subheader("Weather Daily (cached)")
    lat = st.number_input("lat", value=default_lat, format="%.6f")
    lon = st.number_input("lon", value=default_lon, format="%.6f")
    start = st.text_input("start (YYYY-MM-DD)", value="2024-08-01")
    end = st.text_input("end (YYYY-MM-DD)", value="2024-08-07")

    if st.button("Fetch weather"):
        try:
            data = api_get(
                base_url,
                "/weather/daily",
                api_key,
                params={"lat": float(lat), "lon": float(lon), "start": start, "end": end},
            )
            st.json(data)
        except requests.HTTPError as e:
            st.error(f"HTTP error: {e.response.status_code} {e.response.text}")
        except Exception as e:
            st.error(str(e))