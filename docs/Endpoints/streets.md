Here is the polished and organized documentation for the **Streets API**. It maintains all requested CURL examples while removing redundancy and structuring the information for high developer readability.

---

# Streets API

## 1. Streets Geospatial Data Endpoint: `GET /datasets/streets`

Retrieves line segments representing the vehicle road network in Sofia, including highways, arterial roads, and local streets. This endpoint is optimized for map visualization, identifying nearby roads, and extracting network segments for routing analysis.

### **Input Parameters**

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `bbox` | `string` | Conditional | Bounding box: `min_lon,min_lat,max_lon,max_lat`. |
| `lat`, `lon` | `float` | Conditional | Center point for radius queries. |
| `radius_m` | `integer` | Conditional | Search radius in meters (Max: 1000m). |
| `limit` | `integer` | No | Maximum number of segments to return. |
| `simplify_m` | `float` | No | Generalizes lines to reduce payload size (Recommended: 1-3m). |
| `include_boundary` | `boolean` | No | `true` (default): include intersecting lines. `false`: strict containment. |
| `clip` | `boolean` | No | `true`: Cut lines exactly at the boundary of the bbox/circle. |
| `include_clipped_metrics`| `boolean` | No | Recalculates length/travel time for the clipped portion (Requires `clip=true`). |
| `order_by` | `string` | No | `id` (stable) or `distance` (nearest-first). |
| `include_distance` | `boolean` | No | Adds `distance_m` to each feature's properties. |

### **Request Examples**

#### **A) BBox Query - Full Segments (Default Mapping)**

This is the standard query for general-purpose map visualization. It retrieves every street segment that either falls within or touches the specified bounding box. In this default mode, if a long road (e.g., a boulevard) enters the box at one corner, the **entire segment geometry** is returned, ensuring the line doesn't appear "broken" on your map.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/streets?bbox=23.3200,42.6950,23.3250,42.6975&limit=10&simplify_m=3"
```

**Response (GeoJSON):**
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
        "Segment Id": "-11000000151382",
        "NewSegId": "-00004247-5200-0400-0000-000000019ff0"
      }
    },
    {
      "type": "Feature",
      "id": 9948,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.3204, 42.69691], [23.32075, 42.69683]]
      },
      "properties": {
        "Id": 9948.0,
        "StreetName": "булевард Александър Стамболийски",
        "FRC": 4.0,
        "lanes": 2,
        "Length": 30.31,
        "SpeedLimit": 50.0
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Output Structure: Property Field Definitions**

The `properties` object contains detailed metadata for each road segment, useful for traffic modeling and urban analysis:

| Field | Type | Description |
| :--- | :--- | :--- |
| **`id`** | `integer` | The top-level unique database identifier. Use this for stable pagination. |
| **`StreetName`** | `string` | The official name of the street in Bulgarian. |
| **`FRC`** | `float` | **Functional Road Class.** Indicates road importance (e.g., `4.0` for major boulevards, `7.0` for local streets). |
| **`lanes`** | `integer` | Number of driving lanes available on the segment. |
| **`Length`** | `float` | The total physical length of the segment in the database (meters). |
| **`SpeedLimit`** | `float` | The legal speed limit in km/h. |
| **`Segment Id`** | `string` | A unique network identifier used for graph-based connectivity and routing. |
| **`NewSegId`** | `string` | Internal UUID used for dataset version tracking. |

---

### **Technical Use Cases**

*   **Mapping & Basemaps:** The most common use case. By returning full geometries, the map looks continuous. `simplify_m=3` ensures that the lines are lightweight enough for mobile browsers while keeping the road alignment accurate.
*   **Neighborhood Road Profiles:** Developers can check the `FRC` and `lanes` to determine the "Character" of a neighborhood (e.g., "This area is dominated by FRC 7 local streets with 1 lane").
*   **Infrastructure Inventory:** Extract all street names within a specific BBox to create local directories or search indexes.


#### **B) BBox Query - Strict Inside BBox**

This query applies the `include_boundary=false` parameter. It restricts the results to only those street segments that are **entirely contained** within the specified bounding box. If any part of a road segment (even a single coordinate) falls outside the box, the entire segment is excluded from the response.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/streets?bbox=23.3200,42.6950,23.3250,42.6975&include_boundary=false&limit=10&simplify_m=3"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 9718,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32249, 42.69555], [23.32247, 42.69547]]
      },
      "properties": {
        "Id": 9718.0,
        "StreetName": "улица Цар Калоян",
        "FRC": 7.0,
        "lanes": 1,
        "Length": 9.28,
        "SpeedLimit": 50.0,
        "Segment Id": "-11000000078995"
      }
    },
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
        "SpeedLimit": 50.0
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Explanation: The "Strict" Logic**

*   **Filtering Long Segments:** Notice that in this "Strict" result, long segments that cross the boundary are discarded. For example, a 200m boulevard segment that only "passes through" the corner of your box will not appear here.
*   **Data Integrity:** This mode is essential for **statistical partitioning**. If you are dividing a city into a grid and want to sum the total road length of each grid cell, using `include_boundary=false` prevents the same road segment from being counted in multiple adjacent cells.
*   **Asset Isolation:** Useful for identifying short, internal infrastructure components like small alleys, cul-de-sacs, or specifically defined segments that belong entirely to a single administrative zone.

### **Output Property List**

| Field | Type | Description |
| :--- | :--- | :--- |
| **`id`** | `integer` | The unique internal database ID. |
| **`StreetName`** | `string` | The official Bulgarian name of the street. |
| **`FRC`** | `float` | Functional Road Class (e.g., 7.0 = Local Road, 4.0 = Arterial). |
| **`lanes`** | `integer` | Number of driving lanes. |
| **`Length`** | `float` | The length of the segment as stored in the database (meters). |
| **`SpeedLimit`** | `float` | The legal speed limit (km/h). |
| **`Segment Id`** | `string` | Network graph identifier for connectivity analysis. |

---

#### **C) BBox Query - Clipped with Travel Time Metrics**

This is the most advanced analytical mode for the Streets API. It performs two key operations:
1.  **Geometric Clipping (`clip=true`)**: It physically "cuts" the street segments at the edges of the bounding box. 
2.  **Dynamic Metric Recalculation (`include_clipped_metrics=true`)**: It calculates the exact length and estimated traversal time for **only the portion of the road visible inside the box**, rather than using the full segment length.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/streets?bbox=23.3200,42.6950,23.3250,42.6975&clip=true&include_clipped_metrics=true&limit=30&simplify_m=3"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 9879,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32, 42.6964], [23.32044, 42.69632]]
      },
      "properties": {
        "Id": 9879.0,
        "StreetName": "улица Света София",
        "Length": 89.04,
        "SpeedLimit": 20.0,
        "clipped_length_m": 37.26,
        "travel_time_seconds_est": 6.70,
        "travel_time_minutes_est": 0.11,
        "travel_time_note": "Estimated from speed limit; no junction delays/turn penalties."
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Output Structure: Recalculated Property Fields**

When `include_clipped_metrics` is active, the following dynamic fields are added to the `properties` object:

| Field | Type | Description |
| :--- | :--- | :--- |
| **`clipped_length_m`** | `float` | The **actual length (meters)** of the road fragment inside the box. |
| **`travel_time_seconds_est`** | `float` | Estimated time to drive the visible portion in **seconds**. |
| **`travel_time_minutes_est`** | `float` | Estimated time to drive the visible portion in **minutes**. |
| **`Length`** | `float` | **Reference field:** The original full length of the road before it was clipped. |
| **`SpeedLimit`** | `float` | The speed limit (km/h) used to calculate the travel time estimates. |
| **`travel_time_note`** | `string` | A disclaimer explaining that these are theoretical estimates based on speed limits. |

---

### **Why use this mode?**

*   **Regional Traffic Capacity:** By summing the `clipped_length_m` or `travel_time` for all roads in a BBox, you can calculate the "Transit Pressure" of a specific neighborhood.
*   **Exact Visual Alignment:** Look at the coordinates for Feature **9879**: the first longitude is exactly **23.32**, matching the `min_lon` of the BBox. This ensures the geometry fits your map tile perfectly.
*   **Realistic Travel Estimates:** If a highway segment is 5km long but only 100m of it passes through your area of interest, using the original `Length` would skew your data. `clipped_length_m` (e.g., **37.26m**) and `travel_time_minutes_est` (e.g., **0.11 min**) provide the precise data needed for localized analysis.

---

#### **D) BBox Query - Ordered by Proximity**

This query combines a spatial filter (**Bounding Box**) with a sorting mechanism (**Distance**). By providing a reference `lat` and `lon` along with the `bbox`, the API identifies all street segments within the rectangle and sorts them starting from the one physically closest to the provided coordinates.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/streets?bbox=23.3200,42.6950,23.3250,42.6975&lat=42.6962&lon=23.3223&order_by=distance&limit=20&include_distance=true&simplify_m=3"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 34386,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32275, 42.69646], [23.32265, 42.69611]]
      },
      "properties": {
        "Id": 34386.0,
        "StreetName": "улица Цар Калоян",
        "FRC": 7.0,
        "lanes": 2,
        "Length": 39.91,
        "SpeedLimit": 50.0,
        "distance_m": 30.12
      }
    },
    {
      "type": "Feature",
      "id": 9880,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32235, 42.69653], [23.32275, 42.69646]]
      },
      "properties": {
        "Id": 9880.0,
        "StreetName": "улица Съборна",
        "FRC": 7.0,
        "lanes": 2,
        "distance_m": 36.61
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Output Structure: Proximity Property Fields**

When `order_by=distance` and `include_distance=true` are used, the results are sorted by the `distance_m` field in ascending order:

| Field | Type | Description |
| :--- | :--- | :--- |
| **`distance_m`** | `float` | **Proximity:** The exact distance (in meters) from the query `lat/lon` to the **nearest point** on the street segment. |
| **`StreetName`** | `string` | The official name of the closest street. |
| **`FRC`** | `float` | Functional Road Class (indicates road importance). |
| **`lanes`** | `integer` | Number of driving lanes. |
| **`SpeedLimit`** | `float` | Speed limit of the closest road. |
| **`Length`** | `float` | Total physical length of the segment (meters). |

---

### **Key Technical Insights**

*   **Snap-to-Road Logic:** This endpoint is the primary tool for "snapping" a coordinate to the road network. By requesting `limit=1` with this query, you can instantly find the specific road segment a user or asset is currently on.
*   **Segment Directionality:** You may notice similar distances for segments with different IDs. This often occurs because the road network represents different directions of travel or specific lane configurations as separate segments (e.g., ID `40720` and `92422` in the raw output represent the same stretch of "Tsar Kaloyan" street).
*   **Distance Precision:** The `distance_m` calculation is ellipsoidal (high accuracy), measuring the gap between your input point and the closest vertex or edge of the street's `LineString`.
*   **Filtering First, Sorting Second:** The API first finds all roads inside the `bbox`, then calculates the distances and sorts them. This ensures maximum performance for real-time map interactions.

---

#### **B) Radius Queries**

#### **E) Radius Query - Full Segments (Nearby Discovery)**

This query is the primary tool for "Point-of-Interest" (POI) discovery. It retrieves all street segments within a circular radius of a center point. By default, it returns results ordered by **proximity** (nearest first) and includes the **full geometry** of any segment that touches the search circle.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/streets?lat=42.6970&lon=23.3220&radius_m=300&limit=50&simplify_m=3"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 10030,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32198, 42.69703], [23.32146, 42.69714]]
      },
      "properties": {
        "Id": 10030.0,
        "StreetName": null,
        "FRC": 7.0,
        "lanes": 1,
        "Length": 44.25,
        "SpeedLimit": 20.0,
        "distance_m": 3.71,
        "Segment Id": "-11000000241903"
      }
    },
    {
      "type": "Feature",
      "id": 85738,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32144, 42.69731], [23.32162, 42.69742], "..."]
      },
      "properties": {
        "Id": 85738.0,
        "StreetName": "площад Света Неделя",
        "FRC": 4.0,
        "lanes": 2,
        "Length": 48.86,
        "SpeedLimit": 50.0,
        "distance_m": 55.79
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Output Structure: Property Field List**

The radius query automatically includes proximity-specific metrics in the `properties` block:

| Field | Type | Description |
| :--- | :--- | :--- |
| **`distance_m`** | `float` | **Proximity:** The exact distance (meters) from your query center to the nearest edge of the street. |
| **`StreetName`** | `string` | The official name. Note: Smaller service roads or internal alleys may return `null`. |
| **`FRC`** | `float` | Functional Road Class (e.g., `4.0` for Major collector, `7.0` for Local road). |
| **`lanes`** | `integer` | Number of driving lanes on the segment. |
| **`SpeedLimit`** | `float` | Legal speed limit (km/h). |
| **`Length`** | `float` | The **original total length** of the segment in the master database. |
| **`Segment Id`** | `string` | Unique identifier for graph connectivity. |

---

### **Analytical Observations**

*   **Proximity Ordering:** Note that the results start with a `distance_m` of **3.71m**, identifying the specific road the user is practically standing on. 
*   **Duplicate/Parallel Segments:** In the raw output, you may see segments like ID `10030` and `55928` with identical geometries. This is common in high-fidelity road networks where separate records represent different traffic directions (Digitized Forward vs. Digitized Backward).
*   **Discovery of Infrastructure:** As you move down the list, you encounter larger infrastructure like **Sveta Nedelya Square** (`площад Света Неделя`) and **Independence Square** (`площад Независимост`), allowing you to build a comprehensive list of all major landmarks reachable within a 300m walk.
*   **Traffic Calm Zones:** Small segments with a `SpeedLimit` of **20.0** and `FRC` of **7.0** are easily identified as low-speed pedestrian-priority or residential zones.

---

#### **F) Radius Query - Strict Inside Circle**

This query applies a strict spatial filter using the `include_boundary=false` parameter. The API returns only those street segments that are **entirely contained** within the 300-meter radius. Any road that crosses the edge of the circle (e.g., a long boulevard that starts at 100m but ends at 400m from the center) is completely omitted.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/streets?lat=42.6970&lon=23.3220&radius_m=300&include_boundary=false&limit=50&simplify_m=3"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 10030,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32198, 42.69703], [23.32146, 42.69714]]
      },
      "properties": {
        "Id": 10030.0,
        "StreetName": null,
        "FRC": 7.0,
        "lanes": 1,
        "Length": 44.25,
        "SpeedLimit": 20.0,
        "distance_m": 3.71,
        "Segment Id": "-11000000241903"
      }
    },
    {
      "type": "Feature",
      "id": 85738,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32144, 42.69731], [23.32162, 42.69742], "..."]
      },
      "properties": {
        "Id": 85738.0,
        "StreetName": "площад Света Неделя",
        "FRC": 4.0,
        "lanes": 2,
        "Length": 48.86,
        "SpeedLimit": 50.0,
        "distance_m": 55.79
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Output Structure: Property Field List**

In strict mode, the properties represent only the segments that fit within your specified "local bubble":

| Field | Type | Description |
| :--- | :--- | :--- |
| **`id`** | `integer` | Unique internal database identifier. |
| **`distance_m`** | `float` | Proximity from center point to the nearest part of the segment. |
| **`StreetName`** | `string` | Human-readable name. Frequently `null` for small internal square paths or service alleys. |
| **`FRC`** | `float` | Functional Road Class (e.g., `7.0` is a local access road). |
| **`Length`** | `float` | Total physical length of the segment (all of which is inside the circle). |
| **`lanes`** | `integer` | Number of driving lanes. |
| **`SpeedLimit`** | `float` | Maximum legal speed (km/h). |

---

### **Analytical Insights**

*   **Infrastructure Isolation:** Notice that the results are dominated by shorter segments (ID 10030 is **44m**, ID 9983 is **19m**). Large, continuous boulevards that "pass through" the circle are filtered out. This mode is excellent for isolating **internal neighborhood infrastructure** like local squares, alleys, and cul-de-sacs.
*   **Data Consistency:** By setting `include_boundary=false`, you ensure that the `Length` property of every returned feature represents road length that is 100% available within the 300m walk-shed.
*   **Use Case - Neighborhood Safety:** Use this to find only the internal residential roads within a radius to analyze local traffic calming (e.g., finding all roads with a 20 km/h limit that exist entirely within a school zone).

---

#### **G) Radius Query - Clipped with Travel Time Metrics**

This is the most precise analytical configuration for point-based road network study. It combines a **Circular search** with **Geometric Clipping** (`clip=true`) and **Dynamic Metric Recalculation** (`include_clipped_metrics=true`). 

The API physically "cuts" the street lines at the exact 300m boundary and recalculates how long it takes to drive **only the portion of the road that falls inside the circle**.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/streets?lat=42.6970&lon=23.3220&radius_m=300&clip=true&include_clipped_metrics=true&limit=10&simplify_m=3"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 55928,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32146, 42.69714], [23.32198, 42.69703]]
      },
      "properties": {
        "Id": 55928.0,
        "StreetName": null,
        "SpeedLimit": 20.0,
        "distance_m": 3.71,
        "clipped_length_m": 44.37,
        "travel_time_seconds_est": 7.98,
        "travel_time_minutes_est": 0.13,
        "travel_time_note": "Estimated from speed limit; no junction delays/turn penalties."
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Output Structure: Recalculated Property Fields**

By enabling `include_clipped_metrics`, the API adds high-value navigation data based on the **visible fragment** of the road:

| Field | Type | Description |
| :--- | :--- | :--- |
| **`clipped_length_m`** | `float` | The actual length (meters) of the street portion strictly within the 300m radius. |
| **`travel_time_seconds_est`** | `float` | Estimated time to traverse the **clipped portion** at the legal speed limit. |
| **`travel_time_minutes_est`** | `float` | The travel time converted to minutes for easier UI display. |
| **`distance_m`** | `float` | Proximity from center point to the nearest part of the segment. |
| **`SpeedLimit`** | `float` | The km/h limit used as the basis for the time calculations. |
| **`Length`** | `float` | **Reference field:** The original total length of the segment before clipping. |

---

### **Why use this mode?**

*   **Realistic Local Impact:** If a 1km road passes through your 300m search circle, calculating travel time based on the full 1km would be misleading. This mode calculates the time for the **~300m portion** actually relevant to your location.
*   **Precision Dashboarding:** This data is perfect for "Neighborhood Scorecards." You can sum up the `travel_time_minutes_est` for all segments to estimate the total "Transit Capacity" of the immediate vicinity.
*   **Clean Visual Boundaries:** For map applications, `clip=true` ensures that road lines terminate exactly at the circular boundary of your search area, preventing visual clutter outside the zone of interest.
*   **Speed Analysis:** In the example above (ID 55928), the road has a **20 km/h** limit. The API correctly calculates that traversing the **44.37m** fragment at that speed takes approximately **7.98 seconds**.

---

### **Output Structure**

Returns a standard **GeoJSON FeatureCollection**:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 9751,
      "geometry": { "type": "LineString", "coordinates": [[23.3211, 42.6957], "..."] },
      "properties": {
        "StreetName": "улица Позитано",
        "FRC": 7,
        "lanes": 1,
        "Length": 112.87,
        "SpeedLimit": 50.0,
        "FormOfWay": "Single Carriageway",
        "distance_m": 15.3,  // Only if include_distance=true
        "clipped_length_m": 85.4,  // Only if clip=true
        "travel_time_min_clipped": 0.102 // Only if include_clipped_metrics=true
      }
    }
  ]
}
```

---

## 2. Streets Statistics Endpoint: `GET /datasets/streets/stats`

Provides aggregated metrics for road infrastructure within a region. This is ideal for urban intensity analysis, transport planning, and detecting "High-Speed" vs "Low-Speed" neighborhoods.

### **Statistics Request Examples**

#### **1) Stats (BBox) - Default Summary**

This endpoint provides a comprehensive analytical breakdown of the road network within a rectangular area. Instead of returning raw line coordinates, it performs complex spatial calculations to determine network density, average speed limits, lane capacity, and travel time estimates. 

The response provides a dual-perspective: **Intersecting Stats** (everything visible in the box) and **Strict Stats** (only segments entirely contained within the box).

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/streets/stats?bbox=23.3200,42.6950,23.3250,42.6975&top_n=10"
```

**Response (JSON Summary):**
```json
{
  "query": { "kind": "bbox", "bbox": [23.32, 42.695, 23.325, 42.6975] },
  "reference_point": { "lat": 42.69625, "lon": 23.3225 },
  "intersecting_stats": {
    "segment_count": 70,
    "total_length_m_in_region": 2950.76,
    "road_density_m_per_km2": 25896.13,
    "speed": {
      "mean_speed_kmh_weighted": 39.35,
      "length_share_speed_ge_50": 0.64
    },
    "lanes": { "mean_lanes_weighted": 1.58 },
    "travel_time": { "travel_time_minutes_sum": 5.42 },
    "groupings": {
      "by_frc": [{ "frc": 7.0, "count": 40, "length_m": 2096.61 }, "..."],
      "by_street_name": [
        { "street_name": "улица Съборна", "count": 5, "length_m": 380.97 },
        { "street_name": "улица Позитано", "count": 6, "length_m": 301.50 }
      ]
    }
  },
  "strict_stats": {
    "segment_count": 48,
    "total_length_m_in_region": 2206.55
  },
  "nearest_segment": {
    "id": 34386,
    "distance_m": 15.23,
    "properties": { "StreetName": "улица Цар Калоян", "SpeedLimit": 50.0 }
  },
  "boundary_effects": { "segments_touching_boundary_count": 22 }
}
```

---

### **Output Structure: Analytical Categories**

#### **1. Core Supply & Connectivity**
*   **`total_length_m_in_region`**: The sum of all road lengths (clipped to the box). 
*   **`road_density_m_per_km2`**: A density score. In this example, **25,896** is an extremely high value, indicating a very dense, historic city center grid (Sofia Center).
*   **`segment_count`**: The raw number of road segments processed.

#### **2. Flow & Speed Statistics**
*   **`mean_speed_kmh_weighted`**: The average speed limit across the box, weighted by the length of each segment. This prevents a tiny 5m alley from skewing the average of a 500m boulevard.
*   **`length_share_speed_ge_50`**: The percentage of the visible network (0.0 to 1.0) with a speed limit of 50 km/h or higher. In this area, **64%** of roads are 50+ km/h.

#### **3. Capacity & Intensity**
*   **`mean_lanes_weighted`**: The average number of lanes across the network. A value of **1.58** suggests a mix of single-lane alleys and two-lane streets.
*   **`travel_time_minutes_sum`**: The theoretical total time (**5.42 min**) it would take to drive every single meter of road visible in the box at the speed limit.

#### **4. The "Top N" Groupings**
*   **`by_frc`**: Breakdown by road importance. FRC 7 (Local roads) dominates this area with **2,096m** of total length.
*   **`by_street_name`**: Identifies the primary streets in the area. **ul. Saborna** and **ul. Pozitano** are the most prominent by total length in this viewport.

---

### **Comparing "Intersecting" vs. "Strict"**

The API provides both stats to help you understand the impact of roads passing through the area:

| Metric | Intersecting (Visible) | Strict (Entirely Inside) | Analysis |
| :--- | :--- | :--- | :--- |
| **Segment Count** | 70 | 48 | 22 segments cross the boundary. |
| **Network Length** | 2,950m | 2,206m | ~750m of road length belongs to segments that lead outside the box. |
| **Mean Speed** | 39.3 km/h | 36.7 km/h | The roads crossing the boundary (arterials) are generally faster than the purely internal local streets. |

### **Use Cases**
*   **Neighborhood Characterization:** Quickly identify if an area is a "Residential Pocket" (low speed, high FRC 7 count) or a "Transit Corridor" (High speed, high lane count, low FRC 2-3).
*   **Property Analysis:** Calculate the "Road Noise" or "Traffic Accessibility" of a parcel based on the speed and lane statistics of the surrounding box.
*   **Urban Intensity:** Use `road_density_m_per_km2` as a feature for machine learning models predicting commercial activity or land value.

---


#### **2) Stats (Radius) - Default Summary**

This endpoint provides a location-centric analytical summary. By defining a center point and a 300m radius, it assesses the road infrastructure intensity immediately surrounding a specific coordinate (e.g., a subway station, a residential building, or a proposed development site).

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/streets/stats?lat=42.6970&lon=23.3220&radius_m=300&top_n=10"
```

**Response (JSON Summary):**
```json
{
  "query": { "kind": "radius", "lat": 42.697, "lon": 23.322, "radius_m": 300.0 },
  "reference_point": { "lat": 42.697, "lon": 23.322 },
  "intersecting_stats": {
    "segment_count": 186,
    "total_length_m_in_region": 7835.09,
    "road_density_m_per_km2": 27852.40,
    "speed": {
      "mean_speed_kmh_weighted": 40.65,
      "length_share_speed_ge_50": 0.68
    },
    "lanes": { "mean_lanes_weighted": 1.56 },
    "travel_time": { "travel_time_minutes_sum": 13.75 },
    "groupings": {
      "by_street_name": [
        { "street_name": "булевард Тодор Александров", "length_m": 498.32 },
        { "street_name": "булевард Княгиня Мария Луиза", "length_m": 459.31 }
      ]
    }
  },
  "strict_stats": {
    "segment_count": 157,
    "total_length_m_in_region": 7002.44,
    "road_density_m_per_km2": 24892.46
  },
  "nearest_segment": {
    "id": 10030,
    "distance_m": 3.71,
    "properties": { "FRC": 7.0, "SpeedLimit": 20.0 }
  }
}
```

---

### **Output Structure: Statistical Breakdown**

The response aggregates data from the 186 segments found within the circle:

#### **1. Network Intensity (Connectivity)**
*   **`total_length_m_in_region`**: The sum of all road fragments inside the circle (**7.83 kilometers**).
*   **`road_density_m_per_km2`**: At **27,852**, this indicates a high-intensity urban grid. 
*   **`segment_count`**: 186 distinct road segments touch this 300m circle.

#### **2. Performance & Capacity**
*   **`mean_speed_kmh_weighted` (40.65 km/h)**: The average speed limit of the neighborhood. 
*   **`length_share_speed_ge_50` (0.68)**: **68%** of the roads in this radius are 50 km/h or higher, suggesting a high-traffic environment.
*   **`mean_lanes_weighted` (1.56)**: On average, the surrounding streets have approx. 1.5 lanes, indicating a mix of boulevards and narrow center-city streets.
*   **`travel_time_minutes_sum` (13.75 min)**: The theoretical capacity of the local network—how many "road-minutes" exist within this radius.

#### **3. Top Assets (`groupings`)**
*   **`by_frc`**: Shows that FRC 7 (Local roads) and FRC 3 (Major arterials) make up the bulk of the network.
*   **`by_street_name`**: Identifies **Blvd Todor Alexandrov** and **Blvd Knyaginya Maria Luiza** as the dominant physical infrastructure in the area.

---

### **Analytical Comparison: The "Boundary Effect"**

| Metric | Intersecting Stats | Strict Stats | Urban Insight |
| :--- | :--- | :--- | :--- |
| **Segment Count** | 186 | 157 | 29 segments are long enough to exit the 300m circle. |
| **Total Length** | 7,835m | 7,002m | 833m of road length belongs to "outgoing" arterials. |
| **Density** | 27,852 | 24,892 | The density remains high even when excluding through-traffic. |

### **Use Cases**
*   **Noise & Air Quality Modeling:** High `road_density` and high `length_share_speed_ge_50` are strong proxies for increased urban noise and lower air quality.
*   **Commercial Site Selection:** Retailers look for high `road_density` and high `mean_lanes_weighted` to identify high-visibility, high-traffic locations.
*   **Proximity Analysis:** The `nearest_segment` (3.71m away) tells you the user is practically standing on a low-speed (20 km/h) FRC 7 road, likely an internal alley or square.

---

#### **3) Stats + Nearest Geometry (Debugging/Snapping)**

This is the most data-rich request for point-based analysis. It provides the **Macro View** (neighborhood statistics) and the **Micro View** (full geometric data for the closest road) in a single response. By setting `include_nearest_geometry=true`, the `nearest_segment` object is enriched with a full GeoJSON `feature`.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/streets/stats?lat=42.6970&lon=23.3220&radius_m=300&include_nearest_geometry=true&top_n=10"
```

**Response (JSON snippet focusing on the nearest feature):**
```json
{
  "query": { "kind": "radius", "lat": 42.697, "lon": 23.322, "radius_m": 300.0 },
  "intersecting_stats": {
    "segment_count": 186,
    "road_density_m_per_km2": 27852.40,
    "speed": { "mean_speed_kmh_weighted": 40.65 }
    // ... aggregated stats ...
  },
  "nearest_segment": {
    "id": 10030,
    "distance_m": 3.71,
    "properties": {
      "StreetName": null,
      "SpeedLimit": 20.0,
      "FRC": 7.0
    },
    "feature": {
      "type": "Feature",
      "id": 10030,
      "geometry": {
        "type": "MultiLineString",
        "coordinates": [[[23.32198, 42.69703], [23.32172, 42.69708], [23.32146, 42.69714]]]
      },
      "properties": {
        "Id": 10030.0,
        "FRC": 7.0,
        "lanes": 1,
        "Length": 44.25,
        "SpeedLimit": 20.0,
        "StreetName": null,
        "Segment Id": "-11000000241903"
      }
    }
  }
}
```

---

### **Output Structure: The Embedded Feature**

The `nearest_segment.feature` follows the standard GeoJSON specification, allowing for immediate "plug-and-play" with mapping libraries like Leaflet or Mapbox.

| Field | Type | Description |
| :--- | :--- | :--- |
| **`id`** | `integer` | The unique feature ID in the database. |
| **`geometry`** | `object` | The spatial coordinates of the road. Typically a `MultiLineString`. |
| **`properties.Id`** | `float` | The original ID from the dataset source. |
| **`properties.FRC`** | `float` | **Functional Road Class.** Higher values (7.0) indicate local roads; lower values (1.0-3.0) indicate arterials. |
| **`properties.lanes`** | `integer` | Number of vehicle lanes. |
| **`properties.Length`** | `float` | The full physical length of this segment in meters. |
| **`properties.SpeedLimit`**| `float` | The maximum legal speed limit for this specific segment. |
| **`properties.StreetName`**| `string` | Human-readable name. If `null`, it often indicates an unnamed service road or intersection link. |

---

### **Why use this configuration?**

*   **Integrated Map Dashboards:** You can use the `intersecting_stats` to populate graphs (like speed distribution or lane counts for the neighborhood) while using the `feature.geometry` to draw a "highlight" line on the map representing the road the user is currently focused on.
*   **Location Integrity:** Since the `distance_m` is extremely low (**3.71m**), the embedded geometry provides visual proof that the snapping logic has correctly identified the narrow local path/alley at these coordinates.
*   **Efficiency:** This reduces the number of network requests. You get the neighborhood context and the specific object geometry in one transaction, which is crucial for high-performance mobile applications.
*   **Debugging:** Developers can use the embedded geometry to verify that the `nearest_segment` logic is matching the correct road type and location during development.

---

### **Key Metrics Explained**

#### **Infrastructure Density**
*   **`total_length_m_in_region`**: The sum of all road lengths strictly inside the query area.
*   **`road_density_m_per_km2`**: Standardized metric for urban intensity. Higher = more roads per sq km.
*   **`total_lane_length_m`**: Sum of (length × lanes) for all segments. A proxy for vehicle capacity.

#### **Network Classification (FRC)**
*   **`0-1`**: Motorway/Highway
*   **`2-3`**: Major arterial
*   **`4-5`**: Collector roads
*   **`6-7`**: Local streets

#### **Traffic & Capacity**
*   **`mean_speed_limit_kmh`**: Weighted average speed limit.
*   **`total_capacity_pcu_h`**: Estimated hourly capacity in **Passenger Car Units**.
*   **`travel_time_minutes_sum`**: Theoretical sum of traversal times based *only* on speed limits and lengths (excludes congestion).

### **Output Structure**

The response provides both `intersecting_stats` (anything touching the area) and `strict_stats` (only segments 100% inside) for comparison.

```json
{
  "query": { "kind": "radius", "lat": 42.6970, "radius_m": 300.0 },
  "intersecting_stats": {
    "segment_count": 28,
    "total_length_m": 1876.45,
    "road_density_m_per_km2": 450.2,
    "mean_speed_limit_kmh": 42.5,
    "road_type_distribution": [
      {"FRC": 7, "description": "Local Street", "total_length_m": 845.6}
    ],
    "street_name_top": [
      {"StreetName": "улица Позитано", "total_length_m": 456.7}
    ]
  },
  "strict_stats": { "segment_count": 19, "total_length_m": 1245.67 },
  "nearest_segment": {
    "id": 9751,
    "distance_m": 5.2,
    "feature": { /* GeoJSON only if requested */ }
  }
}
```

---

### **Practical Recommendations**
*   **Visualizing Tiles:** Use `bbox` + `clip=true` + `simplify_m=5` for the fastest map rendering.
*   **Safety Audits:** Use the stats endpoint to find areas where `length_share_speed_ge_50` is high near schools or parks.
*   **Snapping:** Use the radius geometry endpoint with `limit=1` and `order_by=distance` to find exactly which road a coordinate belongs to.