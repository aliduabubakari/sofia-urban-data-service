# SUDS API Examples

This document provides practical curl examples for all SUDS API endpoints.

**Base URL (local dev):** `http://127.0.0.1:8000`

**Authentication:** All requests require the `X-API-Key` header.

**Test coordinates (central Sofia):**
- Latitude: `42.6970`
- Longitude: `23.3220`
- Small bbox: `23.3200,42.6950,23.3250,42.6975` (~500m × 250m area)

---

## Health Check

```bash
curl -H "X-API-Key: dev-key-1" \
  http://127.0.0.1:8000/health
```

**Response:**
```json
{"status":"ok"}
```

---

## List Available Datasets

```bash
curl -H "X-API-Key: dev-key-1" \
  http://127.0.0.1:8000/datasets
```

**Response:**
```json
{
  "datasets": [
    "buildings",
    "green_areas",
    "neighbourhoods",
    "pedestrian_network",
    "pois",
    "streets",
    "trees"
  ]
}
```

---

## Dataset Queries


### 1. Buildings (bbox only)

Retrieves building footprints and metadata within a specified geographic bounding box. The data is returned in **GeoJSON** format.

#### **Request Example**
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/datasets/buildings?bbox=23.3200,42.6950,23.3250,42.6975&limit=10&simplify_m=2"
```

#### **Input Parameters**

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `bbox` | `string` | **Required.** Bounding box coordinates: `min_lon,min_lat,max_lon,max_lat`. |
| `limit` | `integer` | Maximum number of features to return (e.g., `500`). |
| `offset` | `integer` | Number of features to skip (used for pagination). |
| `simplify_m`| `float` | Simplification tolerance in meters. Reduces coordinate precision to improve performance. |
| `radius_m` | `integer` | Optional radius filter (often used in conjunction with a center point). |

---

#### **Output Structure**

The response follows the standard **GeoJSON FeatureCollection** schema:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 899,
      "geometry": {
        "type": "Polygon", 
        "coordinates": [[[23.32, 42.69], ...]]
      },
      "properties": {
        "cadnum": "68134.1001.22.1",
        "immaddr": "гр. София, бул. Витоша №2",
        "functype": "Административна, делова сграда",
        "flrcount": 6,
        "_area": 8175.70,
        "_perim": 948.33,
        "dtm2m_median": 552.0,
        "nsi2011_year_built": 1932
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

#### **Key Property Fields**

*   **`cadnum`**: The official cadastral identification number of the building.
*   **`immaddr`**: The full physical address of the property (in Bulgarian).
*   **`functype`**: The primary functional use of the building (e.g., Administrative, Residential, Religious).
*   **`flrcount`**: Total number of floors above ground.
*   **`_area` / `_perim`**: Calculated geometric area (sq. meters) and perimeter (meters).
*   **`dtm2m_median`**: The median elevation/height coordinate for the building base.
*   **`nsi2011_year_built`**: The year the building was constructed (based on 2011 census data).

**Notes:**
- **Geometry:** This dataset returns high-precision polygons. Large bbox queries should always use `simplify_m` to prevent slow browser rendering.
- **Filtering:** Currently, this endpoint is optimized specifically for spatial queries via `bbox`.

### 2. Green Areas

Retrieves polygons representing parks, gardens, and other urban green spaces. This endpoint supports both bounding box (`bbox`) and circular proximity (`radius_m`) queries.

#### **Request Examples**

**Bounding Box Query:**
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/datasets/green_areas?bbox=23.3200,42.6950,23.3250,42.6975&limit=500&simplify_m=5"
```

**Radius Query:**
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/datasets/green_areas?lat=42.6970&lon=23.3220&radius_m=300&limit=500"
```

#### **Input Parameters**

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `bbox` | `string` | Bounding box coordinates: `min_lon,min_lat,max_lon,max_lat`. |
| `lat` | `float` | Latitude of the center point (used with `lon` and `radius_m`). |
| `lon` | `float` | Longitude of the center point (used with `lat` and `radius_m`). |
| `radius_m` | `integer` | Search radius in meters around the center point. |
| `limit` | `integer` | Maximum number of features to return. |
| `simplify_m`| `float` | Simplification tolerance in meters to reduce geometry complexity. |

---

#### **Output Structure**

The response returns a **GeoJSON FeatureCollection**:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 29654,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.3226, 42.6955], ...]]
      },
      "properties": {
        "id": 29654,
        "area_m": 132,
        "source": 0,
        "source_id": "29654"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

#### **Key Property Fields**

*   **`id`**: Unique identifier for the green area feature.
*   **`area_m`**: The calculated area of the green space in square meters.
*   **`source`**: Internal code indicating the data origin/provider.
*   **`source_id`**: The original ID of the feature from the source dataset.

**Notes:**
*   **Query Logic:** You must provide either a `bbox` OR a combination of `lat`, `lon`, and `radius_m`.
*   **Geometry:** Green areas may be returned as `Polygon` or `MultiPolygon` depending on the complexity of the park or garden.


### 3. Neighbourhoods

Retrieves polygons representing administrative districts, planning zones, or residential neighbourhoods. This endpoint supports both bounding box (`bbox`) and circular proximity (`radius_m`) queries.

#### **Request Examples**

**Bounding Box Query:**
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/datasets/neighbourhoods?bbox=23.3200,42.6950,23.3250,42.6975&limit=100&simplify_m=10"
```

**Radius Query:**
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/datasets/neighbourhoods?lat=42.6970&lon=23.3220&radius_m=500&limit=100"
```

#### **Input Parameters**

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `bbox` | `string` | Bounding box coordinates: `min_lon,min_lat,max_lon,max_lat`. |
| `lat` | `float` | Latitude of the center point (used with `lon` and `radius_m`). |
| `lon` | `float` | Longitude of the center point (used with `lat` and `radius_m`). |
| `radius_m` | `integer` | Search radius in meters around the center point. |
| `limit` | `integer` | Maximum number of neighbourhood features to return. |
| `simplify_m`| `float` | Simplification tolerance in meters. Highly recommended for large areas to reduce payload size. |

---

#### **Output Structure**

The response returns a **GeoJSON FeatureCollection**:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 58,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.3235, 42.6974], ...]]
      },
      "properties": {
        "id": 214,
        "rajon": "Средец",
        "regname": "ЦГЧ Зона А - юг",
        "source_id": "214"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

#### **Key Property Fields**

*   **`id` / `source_id`**: Unique identifiers for the zone feature.
*   **`rajon`**: The name of the larger administrative district (Rajon) the neighbourhood belongs to (e.g., "Sredets", "Oborishte").
*   **`regname`**: The specific name of the neighbourhood or planning zone (e.g., "Central Urban Part Zone A - South").

**Notes:**
*   **Geometry Type:** Neighbourhoods are typically returned as `Polygon` but may appear as `MultiPolygon` if the zone is non-contiguous.
*   **Simplification:** Because neighbourhood boundaries can be very detailed, using `simplify_m` (e.g., 10 or 20) significantly improves performance without losing much visual accuracy for map overlays.


### 4. POIs (Points of Interest)

Retrieves specific locations categorized as points of interest (e.g., landmarks, shops, utility points). This dataset returns high-density point geometries.

#### **Request Examples**

**Bounding Box Query:**
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/datasets/pois?bbox=23.3200,42.6950,23.3250,42.6975&limit=1000"
```

**Radius Query:**
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/datasets/pois?lat=42.6970&lon=23.3220&radius_m=300&limit=1000"
```

#### **Input Parameters**

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `bbox` | `string` | Bounding box coordinates: `min_lon,min_lat,max_lon,max_lat`. |
| `lat` | `float` | Latitude of the center point (used with `lon` and `radius_m`). |
| `lon` | `float` | Longitude of the center point (used with `lat` and `radius_m`). |
| `radius_m` | `integer` | Search radius in meters around the center point. |
| `limit` | `integer` | Maximum number of points to return (default is often 100 or 1000). |
| `offset` | `integer` | Number of features to skip for pagination. |

---

#### **Output Structure**

The response returns a **GeoJSON FeatureCollection** where each feature is a `Point`:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 15,
      "geometry": {
        "type": "Point",
        "coordinates": [23.32314, 42.696258996]
      },
      "properties": {
        "id": 34865,
        "guid": "8e8b6d72-9220-4767-ae1b-5e50a759585d",
        "group_id": "gr_6",
        "subgr_id": "s_gr_6_5",
        "source_id": "34865"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

#### **Key Property Fields**

*   **`id` / `source_id`**: The internal database identifier for the point.
*   **`guid`**: A globally unique identifier for the specific POI.
*   **`group_id`**: The top-level category code for the POI (e.g., `gr_6` for Transport, `gr_8` for Commercial).
*   **`subgr_id`**: The specific sub-category code (e.g., a specific type of shop or transit stop).
*   **`orig_id`**: The identifier used in the original source dataset before ingestion.

**Notes:**
*   **Geometry:** POIs are strictly `Point` geometries.
*   **No Simplification:** Unlike buildings or green areas, the `simplify_m` parameter does not apply to point data.
*   **Density:** POI datasets can be very dense in urban centers; it is recommended to use a reasonable `limit` to avoid massive JSON payloads.



### 5. Pedestrian Network

Retrieves line segments representing the walkable urban network, including sidewalks, pedestrian crossings, park alleys, and underpasses. This data is essential for accessibility analysis and pedestrian routing.

#### **Request Examples**

**Bounding Box Query:**
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/datasets/pedestrian_network?bbox=23.3200,42.6950,23.3250,42.6975&limit=1000&simplify_m=3"
```

**Radius Query:**
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/datasets/pedestrian_network?lat=42.6970&lon=23.3220&radius_m=300&limit=1000"
```

#### **Input Parameters**

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `bbox` | `string` | Bounding box coordinates: `min_lon,min_lat,max_lon,max_lat`. |
| `lat` | `float` | Latitude of the center point (used with `lon` and `radius_m`). |
| `lon` | `float` | Longitude of the center point (used with `lat` and `radius_m`). |
| `radius_m` | `integer` | Search radius in meters around the center point. |
| `limit` | `integer` | Maximum number of network segments to return. |
| `simplify_m`| `float` | Simplification tolerance in meters to reduce the number of vertices in paths. |

---

#### **Output Structure**

The response returns a **GeoJSON FeatureCollection** containing `LineString` or `MultiLineString` geometries:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 37,
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [23.321941808, 42.697016788],
          [23.322077715, 42.697519846]
        ]
      },
      "properties": {
        "id": 461,
        "name": "343",
        "type": "Локална алея",
        "str_class": "Алея с настилка",
        "segment_le": 56.98,
        "slope_perc": -5.41,
        "minutes": 0.85,
        "source_id": "461"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

#### **Key Property Fields**

*   **`type`**: The functional type of the segment (e.g., "Локална алея" / Local Alley, "Пресичане" / Crossing).
*   **`str_class`**: The physical classification of the path (e.g., "Тротоар" / Sidewalk, "Подлез" / Underpass, "Алея с настилка" / Paved Alley).
*   **`segment_le`**: The precise length of the segment in meters.
*   **`slope_perc`**: The incline/slope of the segment as a percentage (useful for wheelchair accessibility analysis).
*   **`minutes`**: Estimated walking time in minutes to traverse the segment at average speed.
*   **`altitude_b` / `altitude_e`**: The elevation at the beginning and end of the segment.

**Notes:**
*   **Geometry:** High-resolution network data can be heavy. Use `simplify_m=2` or higher for large-scale visual maps.
*   **Connectivity:** The segments are structured for graph-based analysis; nodes at intersections typically share identical coordinates to allow for pathfinding logic.


### 6. Streets

Retrieves line segments representing the vehicle road network. This dataset includes detailed attributes for traffic modeling and urban planning, such as lane counts and speed limits.

#### **Request Examples**

**Bounding Box Query:**
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/datasets/streets?bbox=23.3200,42.6950,23.3250,42.6975&limit=1000&simplify_m=3"
```

**Radius Query:**
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/datasets/streets?lat=42.6970&lon=23.3220&radius_m=300&limit=100"
```

#### **Input Parameters**

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `bbox` | `string` | Bounding box coordinates: `min_lon,min_lat,max_lon,max_lat`. |
| `lat` | `float` | Latitude of the center point (used with `lon` and `radius_m`). |
| `lon` | `float` | Longitude of the center point (used with `lat` and `radius_m`). |
| `radius_m` | `integer` | Search radius in meters around the center point. |
| `limit` | `integer` | Maximum number of street segments to return. |
| `simplify_m`| `float` | Simplification tolerance in meters to reduce the number of vertices. |

---

#### **Output Structure**

The response returns a **GeoJSON FeatureCollection** containing `LineString` or `MultiLineString` geometries:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 9751,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32115, 42.69578], [23.32249, 42.69555]]
      },
      "properties": {
        "Id": 9751.0,
        "StreetName": "улица Позитано",
        "FRC": 7.0,
        "lanes": 1,
        "Length": 112.87,
        "SpeedLimit": 50.0,
        "Segment Id": "-11000000151382"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

#### **Key Property Fields**

*   **`StreetName`**: The official name of the street (in Bulgarian).
*   **`FRC`**: Functional Road Class. A numeric code indicating the importance/capacity of the road (e.g., highways vs. local streets).
*   **`lanes`**: The number of vehicle driving lanes available on the segment.
*   **`Length`**: The length of the road segment in meters.
*   **`SpeedLimit`**: The legal maximum speed limit in km/h.
*   **`Segment Id`**: A unique identifier for the specific road segment in the network graph.

**Notes:**
*   **Data Density:** Street networks are vertex-heavy. Using `simplify_m` (e.g., 1–3 meters) is highly recommended for web visualization to improve rendering speed.
*   **Directionality:** Segments are typically digitized in the direction of traffic flow where applicable.


### 7. Trees (bbox only)

Retrieves point data for individual urban trees, including physical dimensions (height, crown diameter) and 3D visualization metadata.

#### **Request Example**
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/datasets/trees?bbox=23.3200,42.6950,23.3250,42.6975&limit=2000"
```

#### **Input Parameters**

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `bbox` | `string` | **Required.** Bounding box coordinates: `min_lon,min_lat,max_lon,max_lat`. |
| `limit` | `integer` | Maximum number of tree features to return (e.g., `2000`). |
| `offset` | `integer` | Number of features to skip for pagination. |

---

#### **Output Structure**

The response returns a **GeoJSON FeatureCollection** where each feature is a `Point`:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 43843,
      "geometry": {
        "type": "Point",
        "coordinates": [23.324720561, 42.695051328]
      },
      "properties": {
        "id": 4062254,
        "height_calc": 18.0,
        "crown_diam": 12.0,
        "crown_area": 113.1,
        "z_position": 547.04,
        "leaf_type_": "неопределено",
        "model": "types_round.glb",
        "model_scale": 1.22,
        "source_id": "4062254"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

#### **Key Property Fields**

*   **`height_calc`**: Estimated height of the tree in meters.
*   **`crown_diam`**: The diameter of the tree's canopy/crown in meters.
*   **`crown_area`**: The total horizontal area covered by the canopy in square meters.
*   **`z_position`**: The ground elevation at the tree's location (meters above sea level).
*   **`leaf_type_`**: Classification of the foliage (e.g., "broadleaf", "needleleaf", or "неопределено" for undefined).
*   **`model`**: The filename of the 3D GLB model used to represent this tree type in architectural visualizations.
*   **`model_scale`**: The scaling factor applied to the 3D model to match the tree's real-world dimensions.

**Notes:**
*   **Query Limitation:** Currently, radius-based proximity queries are **disabled** for this dataset. You must use the `bbox` parameter.
*   **Visualization:** This dataset is specifically enriched with `model` and `z_position` properties to support high-fidelity 3D urban twin rendering.
*   **Geometry:** Trees are point geometries; the canopy size is represented numerically in the properties rather than via polygon geometry.

## External Data Queries (with caching)

Here is the updated documentation for the **OSM Metrics** endpoint.

### 8. OSM Metrics

Retrieves a statistical summary of OpenStreetMap (OSM) data within a circular radius of a point. This endpoint provides aggregated data on road infrastructure and facility density rather than raw geometries.

#### **Request Examples**

**Standard Query:**
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/osm/metrics?lat=42.6970&lon=23.3220&radius_m=300"
```

**Force Refresh (Bypass Cache):**
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/osm/metrics?lat=42.6970&lon=23.3220&radius_m=300&refresh=true"
```

#### **Input Parameters**

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `lat` | `float` | **Required.** Latitude of the center point. |
| `lon` | `float` | **Required.** Longitude of the center point. |
| `radius_m` | `integer` | **Required.** Radius of the analysis buffer in meters. |
| `refresh` | `boolean` | If `true`, bypasses the local cache and fetches fresh data from the Overpass API. |

---

#### **Output Structure**

The response returns a structured **JSON object**:

```json
{
  "cached": false,
  "road_total_length_m": 35720.53,
  "road_length_by_class_m": {
    "primary": 1492.53,
    "secondary": 2004.12,
    "residential": 6577.5,
    "service": 2468.47,
    "other": 23177.91
  },
  "facility_counts": {
    "amenity": 296,
    "shop": 387,
    "leisure": 11,
    "tourism": 40,
    "public_transport": 14,
    "bus_stop": 2,
    "rail_stop": 12
  },
  "buffer_m": 300,
  "point": { "lat": 42.697, "lon": 23.322 },
  "source": "overpass"
}
```

#### **Key Property Fields**

*   **`cached`**: Indicates if the data was served from the local cache (`true`) or fetched live (`false`).
*   **`road_total_length_m`**: The total cumulative length of all road segments within the radius (in meters).
*   **`road_length_by_class_m`**: A breakdown of road lengths categorized by OSM highway classes (e.g., primary, residential).
*   **`facility_counts`**: A tally of specific points of interest grouped by type:
    *   `amenity`: Schools, hospitals, banks, etc.
    *   `shop`: Retail outlets.
    *   `leisure`: Parks, sports centers, etc.
    *   `public_transport`: Combined count of transit-related nodes.
*   **`source`**: The data provider (e.g., "overpass" for live OSM data).

**Notes:**
*   **Performance:** Live queries (`cached: false`) may take several seconds as they query external OSM servers.
*   **Accuracy:** This data is derived directly from OpenStreetMap and reflects the current state of the OSM database for that region.
*   **Radius Limit:** High radius values (e.g., >2000m) may result in timeouts due to the volume of data being processed.


### 9. Weather Daily

Retrieves historical daily weather aggregates for a specific location. This endpoint provides a time series including temperature, precipitation, and wind metrics.

#### **Request Example**
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/weather/daily?lat=42.6970&lon=23.3220&start=2024-08-01&end=2024-08-07"
```

#### **Input Parameters**

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `lat` | `float` | **Required.** Latitude of the target location. |
| `lon` | `float` | **Required.** Longitude of the target location. |
| `start` | `string` | **Required.** Start date in `YYYY-MM-DD` format. |
| `end` | `string` | **Required.** End date in `YYYY-MM-DD` format. |

---

#### **Output Structure**

The response returns a JSON object containing metadata and an array of daily observations:

```json
{
  "lat": 42.697,
  "lon": 23.322,
  "start": "2024-08-01",
  "end": "2024-08-07",
  "rows": [
    {
      "date": "2024-08-01",
      "provider": "openmeteo",
      "elevation_m": 548.0,
      "temperature_2m_max": 31.6,
      "temperature_2m_min": 16.5,
      "precipitation_sum": 0.0,
      "windspeed_10m_max": 8.1,
      "windgusts_10m_max": 16.9,
      "winddirection_10m_dominant": 100,
      "relative_humidity_2m_mean": 43.0,
      "daylight_duration": 52096.18
    }
  ]
}
```

#### **Key Property Fields (per day)**

*   **`date`**: The specific date for the observation.
*   **`elevation_m`**: Ground elevation at the specified coordinates (meters).
*   **`temperature_2m_*`**: Maximum, minimum, and mean air temperatures at 2 meters above ground (°C).
*   **`apparent_temperature_*`**: "Feels like" temperature extremes (°C).
*   **`precipitation_sum`**: Total liquid water equivalent (rain/snow) in millimeters (mm).
*   **`windspeed_10m_max`**: Maximum sustained wind speed at 10 meters height (km/h).
*   **`windgusts_10m_max`**: Peak wind gust recorded (km/h).
*   **`winddirection_10m_dominant`**: The most frequent wind direction in degrees (0-360°).
*   **`relative_humidity_2m_mean`**: Average relative humidity percentage (%).
*   **`daylight_duration`**: Total daylight duration in seconds.

**Notes:**
*   **Caching:** Results are cached in a local database to improve performance for frequently requested areas and dates.
*   **Precision:** Coordinate parameters are internally rounded to 3 decimal places (`lat_round`, `lon_round`) for caching consistency.
*   **Units:** All temperatures are in Celsius, and speeds are in km/h.

## Combined Enrichment Endpoint

Here is the updated documentation for the **Enrichment (All-in-One)** endpoint.

### 10. Enrichment (all-in-one)

This endpoint provides a comprehensive data dump for a specific location. It combines metrics from OpenStreetMap, historical weather time-series, and spatial features from multiple datasets (Buildings, Streets, POIs, etc.) into a single JSON response.

#### **Request Examples**

**Full Enrichment (Metrics + Geometries):**
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/enrich/point?lat=42.6970&lon=23.3220&radius_m=300&start=2024-08-01&end=2024-08-07&datasets=streets,pois,green_areas&mode=both&limit=1000&simplify_m=5"
```

**Minimal Enrichment (Metrics Only):**
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/enrich/point?lat=42.6970&lon=23.3220&radius_m=300&start=2024-08-01&end=2024-08-07&mode=none"
```

#### **Input Parameters**

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `lat` / `lon` | `float` | **Required.** Center point coordinates for the analysis. |
| `radius_m` | `integer` | **Required.** Search radius in meters (max 1000m). |
| `start` / `end`| `string` | **Required.** Date range for weather data (`YYYY-MM-DD`). |
| `datasets` | `string` | Comma-separated list of datasets to include (e.g., `streets,pois,buildings,green_areas,trees`). |
| `mode` | `string` | Geometry return mode: `none` (metrics only), `radius` (only features in circle), `bbox` (only features in bounding box), or `both`. |
| `limit` | `integer` | Max features per dataset. |
| `simplify_m` | `float` | Simplification tolerance for returned geometries. |

---

#### **Output Structure**

The response returns a complex nested JSON object:

```json
{
  "point": { "lat": 42.697, "lon": 23.322 },
  "radius_m": 300,
  "bbox": { "minx": 23.31, "miny": 42.69, "maxx": 23.32, "maxy": 42.70 },
  "osm": { 
    "road_total_length_m": 35720,
    "facility_counts": { "shop": 387, "amenity": 296, ... }
  },
  "weather_daily": {
    "rows": [ { "date": "2024-08-01", "temperature_2m_max": 31.6, ... } ]
  },
  "geometries": {
    "radius": {
      "streets": { "type": "FeatureCollection", "features": [...] },
      "pois": { "type": "FeatureCollection", "features": [...] }
    },
    "bbox": {
       "streets": { "type": "FeatureCollection", "features": [...] }
    }
  }
}
```

#### **Key Property Sections**

*   **`osm`**: Contains the OpenStreetMap Metrics summary (see Section 8).
*   **`weather_daily`**: Contains the historical weather time-series (see Section 9).
*   **`geometries`**: This section is only populated if `mode` is not `none`.
    *   **`radius`**: Features strictly contained within the circular buffer.
    *   **`bbox`**: Features contained within the square bounding box derived from the radius.
*   **`limits`**: Provides information on the internal "caps" or maximum allowed features for each dataset to prevent system overload.

**Notes:**
*   **Mode Selection:** Use `mode=none` if you only need statistical data (weather/OSM) to significantly reduce the response size.
*   **Performance:** Because this endpoint hits multiple databases and external services (if not cached), it may have a higher latency than single-dataset endpoints.
*   **Bounding Box:** The `bbox` is automatically computed from the `radius_m` centered on the provided `lat/lon`.

---

## Query Parameter Reference

### Common Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `bbox` | string | Bounding box `minLon,minLat,maxLon,maxLat` | `23.32,42.695,23.325,42.6975` |
| `lat` | float | Latitude (EPSG:4326) | `42.6970` |
| `lon` | float | Longitude (EPSG:4326) | `23.3220` |
| `radius_m` | int | Radius in meters | `300` |
| `limit` | int | Max features to return | `1000` |
| `offset` | int | Pagination offset | `0` |
| `simplify_m` | float | Geometry simplification tolerance (meters) | `5` |

### Enrichment-Specific Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `datasets` | string | Comma-separated dataset names | `streets,pois,trees` |
| `mode` | string | Query mode | `both` / `bbox` / `radius` / `none` |
| `start` | string | Start date (YYYY-MM-DD) | `2024-08-01` |
| `end` | string | End date (YYYY-MM-DD) | `2024-08-07` |
| `refresh` | bool | Force cache refresh (OSM only) | `true` |

---

## Tips

1. **Performance optimization:**
   - Use `simplify_m` for polygon/line datasets to reduce response size
   - Start with small `limit` values and increase as needed
   - Use bbox queries for focused geographic areas

2. **Caching:**
   - OSM metrics and weather data are cached by default
   - Cache TTL is controlled by environment variables
   - Use `refresh=true` to bypass OSM cache

3. **Error handling:**
   - `401`: Invalid/missing API key
   - `400`: Invalid parameters (check bbox format, coordinates, dates)
   - `500`: Server error (check API logs)

4. **Finding coordinates:**
   - Use https://boundingbox.klokantech.com/ for bbox values
   - Use OpenStreetMap (right-click → "Show coordinates") for lat/lon

---

## Response Format

All dataset queries return GeoJSON FeatureCollections:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { ... },
      "properties": { ... }
    }
  ]
}
```

---

## Additional Resources

- **Swagger UI:** http://127.0.0.1:8000/docs
- **API Reference:** See `API.md`
- **Setup Guide:** See `SETUP.md`