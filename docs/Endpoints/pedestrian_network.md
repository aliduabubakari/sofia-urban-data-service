## Pedestrian Network Stats: How the numbers are calculated (team-friendly notes)

This note explains what the **Pedestrian Network stats** mean, how they’re computed, and the design decisions behind them—without getting into database/geometry implementation details.

---

# 1) What the pedestrian network represents
The pedestrian network is a set of line segments describing walkable paths:
- sidewalks, crossings, park alleys, underpasses, etc.

Each segment has:
- a geometry (a line on the map)
- attributes such as type/class, length, slope, and a time/cost field.

When we ask for stats within a **bbox** or a **radius**, we are summarizing what walkable infrastructure exists inside that region.

---

# 2) Two “views” of the same region: intersecting vs strict
When you query `/datasets/pedestrian_network/stats`, the response always includes **two versions** of the stats:

## A) `intersecting_stats` (“touching counts”)
This includes **any segment that touches or crosses the region**.

Example:
- A long sidewalk that passes through the edge of the bbox counts.
- A segment that crosses the circle boundary counts.

This view is good when you want to understand what infrastructure is “connected to” or “reachable from” that region.

## B) `strict_stats` (“fully inside only”)
This includes **only segments that are completely inside the region**.

Example:
- A segment that crosses the bbox boundary is excluded.
- A segment that reaches outside the circle is excluded.

This view is good when you want “pure inside-only” measurements that aren’t affected by lines that only partially appear inside your selection.

---

# 3) Boundary effects: what it means and why it matters
We compute:

### `segments_touching_boundary_count`
This is:

> **(number of segments that intersect the region)**  
> minus  
> **(number of segments strictly inside the region)**

This helps answer:
- “How many segments are only partially inside my region?”
- “Is my area strongly connected to surrounding walkways?”

It is especially useful for:
- comparing regions of different size
- understanding how sensitive a result is to boundary rules

---

# 4) How “length inside the region” is calculated (clipping)
For length-based stats, we don’t just count whole segments. Many segments cross the boundary.

So we compute:

> **the portion of each segment that lies inside the region**,  
and use that portion for length totals.

This produces:

### `total_length_m_in_region`
Meaning:
- “How many meters of walkable path exist *inside* this area?”

This is more accurate than summing full segment lengths, because:
- A 200m segment that barely touches the region shouldn’t contribute 200m to the local network supply.

---

# 5) Network density: putting length into context
We compute:

### `network_density_m_per_km2`
Meaning:
- “How dense is the pedestrian network inside the region?”
- It normalizes by area (so different bbox/radius sizes can be compared).

Intuition:
- Higher density = more walkable routes per area
- Lower density = fewer walkable routes per area

---

# 6) Time scaling (important design decision)
Each segment has:
- `segment_le` = segment length (meters)
- `minutes` = a “time/cost” value for traversing the segment

However, when a segment crosses the boundary, only part of it is inside the region.  
So we estimate the “time/cost inside region” by proportional scaling:

### Time scaling rule
> **time_inside ≈ segment_time * (length_inside / full_segment_length)**

So if:
- a segment has `minutes = 10`
- its full length is 100m
- only 30m is inside the region

Then:
- estimated `time_inside ≈ 10 * (30/100) = 3`

### Why we do this
- It keeps time totals consistent with clipped length totals.
- It prevents boundary-crossing segments from inflating the “time in region”.

### Important note about units
Despite the field being called `minutes`, in your sample data it often matches the segment length very closely, which suggests it might actually be a *cost* value or *seconds* (not literal minutes).  
So in the stats we treat it as **time_raw** and provide a convenience conversion:

- `time_raw_sum_in_region`
- `time_minutes_if_seconds_sum_in_region = time_raw_sum_in_region / 60`

This is deliberately cautious so we don’t mislead users.

---

# 7) Slope metrics (accessibility-focused)
Each segment has a slope value (`slope_perc`) which can be negative or positive depending on direction.

For accessibility, direction is less important than steepness.  
So we use:

### `abs(slope_perc)` (absolute slope)
Meaning:
- a segment with slope `-6%` is treated as `6% steepness`

### Length-weighted slope (key design choice)
Longer segments matter more than tiny segments, so we compute slope statistics weighted by segment length inside the region.

For example:
- a 5m steep ramp should not dominate the average compared to 500m of flat sidewalk.

So:

### `mean_abs_slope_weighted`
Meaning:
- “Average steepness of the pedestrian network inside this region, where long segments count more.”

We also compute steepness shares:

- `length_share_slope_gt_5pct`
- `length_share_slope_gt_8pct`
- `length_share_slope_gt_10pct`

These answer questions like:
- “What fraction of walkable network is steeper than 8% (often relevant for wheelchair difficulty)?”

---

# 8) Groupings by type and surface class
We provide top-N summaries for:

- `by_type` (functional role, e.g., crossing, local alley)
- `by_str_class` (physical class, e.g., sidewalk, underpass, paved alley)

For each category we return:
- **count of segments**
- **total length inside region**

Why both?
- Count answers “how many pieces”
- Length answers “how much walkable infrastructure”

Often length is the more meaningful indicator.

---

# 9) Nearest segment (for snapping and routing preparation)
We return the nearest network segment to a reference point:

- for radius queries: the reference is the center point
- for bbox queries: the reference is by default the bbox center (or a user-supplied center point)

This supports workflows like:
- “Given a station/POI, what’s the closest place on the pedestrian network to connect to?”

---

# 10) Why we return both intersecting + strict in one response
Because both are useful, and comparing them highlights boundary sensitivity:

- intersecting: better for connectivity/reachability thinking
- strict: better for “pure inside” measurements
- difference: tells you how much the boundary influences results

This avoids the confusion of “why did counts change?” across separate requests.

---

# Summary of key decisions (easy to communicate)
1) We report **both intersecting and strict** stats to make boundary behavior transparent.
2) Length metrics are based on the **portion of each segment inside the region**.
3) Time metrics are **scaled proportionally** to the inside portion of the segment.
4) Slope metrics are based on **absolute steepness** and are **length-weighted**.
5) We provide top-N breakdowns by **type** and **surface class**, using both counts and length.
6) We include the **nearest segment** to help connect points (stations/POIs) to the network.



# Pedestrian Network API

## 1. Pedestrian Network Geospatial Data Endpoint: `GET /datasets/pedestrian_network`

Retrieves line segments representing the walkable urban network, including sidewalks, pedestrian crossings, park alleys, and underpasses. This data is essential for accessibility analysis, pedestrian routing, and urban mobility studies. The endpoint supports both full segment retrieval and clipped geometry modes.

### **Request Examples**

#### **Full Segment Queries (BBox Mode)**

### **1. Pedestrian Network Geospatial Data Endpoint: `GET /datasets/pedestrian_network`**

This endpoint retrieves the "walkable skeleton" of the urban environment. It includes sidewalks, pedestrian crossings, park paths, and underground passages. This data is critical for calculating accessibility scores, identifying "broken links" in the pedestrian network, and performing slope-aware routing for mobility-impaired users.

#### **A) BBox Query - Full Segments (default)**

Retrieves every pedestrian segment that either falls within or touches the specified bounding box. In this default mode, if a long sidewalk partially enters the box, the **entire segment geometry** is returned.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network?bbox=23.3200,42.6950,23.3250,42.6975&limit=1000&offset=0&simplify_m=3"
```

**Response (GeoJSON):**
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
        "altitude_b": 6.05,
        "altitude_e": 2.96,
        "source_id": "461"
      }
    },
    {
      "type": "Feature",
      "id": 173,
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [23.324186448, 42.697460688],
          [23.324165299, 42.697400244]
        ]
      },
      "properties": {
        "id": 459,
        "name": "341",
        "type": "Пресичане",
        "str_class": "Подлез",
        "segment_le": 6.93,
        "slope_perc": 0.15,
        "minutes": 0.20,
        "source_id": "459"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Segment Property Fields**

Each feature contains metadata describing both the physical characteristics and the navigability of the path:

| Field | Type | Description |
| :--- | :--- | :--- |
| **`id`** | `integer` | The internal primary key in our spatial database. |
| **`type`** | `string` | The functional use of the path (e.g., `Локална алея` - Local path, `Пресичане` - Crossing, `Тротоар` - Sidewalk). |
| **`str_class`** | `string` | The physical infrastructure type (e.g., `Алея с настилка` - Paved path, `Подлез` - Underpass, `Надлез` - Overpass). |
| **`segment_le`** | `float` | The calculated length of the segment in **meters**. |
| **`slope_perc`** | `float` | The average slope percentage. Values above **5.0** or below **-5.0** typically indicate segments that are difficult for wheelchair users. |
| **`minutes`** | `float` | Estimated time required to walk the segment at a standard pace (approx. 4 km/h). |
| **`altitude_b / e`** | `float` | Elevation relative to the local datum at the beginning (**b**) and end (**e**) of the line string. |
| **`source_id`** | `string` | The original unique identifier from the source dataset (e.g., Sofia Municipality GIS). |

---

### **Key Technical Notes**

1.  **Topology:** Segments are topologically connected. The end coordinates of one segment (e.g., a sidewalk) precisely match the start coordinates of the next (e.g., a crossing), making this data suitable for building routing graphs.
2.  **Simplification (`simplify_m`):** The `simplify_m=3` parameter reduces coordinate density. This is recommended for zoomed-out visualisations to keep the payload size manageable without losing the general alignment of the streets.
3.  **Slope Signage:** A **negative** `slope_perc` indicates a downhill direction relative to the digitized direction of the line string, while a **positive** value indicates an uphill climb.

#### **B) BBox Query - Full Segments, Strict Inside BBox**

This query utilizes the `include_boundary=false` parameter. It restricts the results to only those pedestrian segments that are **entirely contained** within the specified bounding box. If a sidewalk or path crosses the edge of the box (i.e., one coordinate is inside and the other is outside), it is excluded from the response.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network?bbox=23.3200,42.6950,23.3250,42.6975&include_boundary=false&limit=1000&simplify_m=3"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 173,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.324186448, 42.697460688], [23.324165299, 42.697400244]]
      },
      "properties": {
        "id": 459,
        "type": "Пресичане",
        "str_class": "Подлез",
        "segment_le": 6.93,
        "slope_perc": 0.15,
        "minutes": 0.20,
        "altitude_b": 2.33,
        "altitude_e": 2.34,
        "source_id": "459"
      }
    },
    {
      "type": "Feature",
      "id": 235,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.324209611, 42.697412547], [23.324221576, 42.6974946]]
      },
      "properties": {
        "id": 460,
        "type": "Пресичане",
        "str_class": "Подлез",
        "segment_le": 9.16,
        "slope_perc": 0.91,
        "minutes": 0.27,
        "altitude_b": 2.44,
        "altitude_e": 2.52,
        "source_id": "460"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Key Characteristics of Strict BBox Queries**

*   **Logic of Exclusion:** Notice that the "Local Alley" (ID 37) from the previous example is **missing**. Because that segment (length 56.98m) physically extends beyond the coordinates of this box, strict mode filters it out.
*   **Infrastructure Focus:** This mode is ideal for identifying short, internal infrastructure components like **underpasses** (`Подлез`) or **internal crosswalks** that belong purely to a specific square or intersection.
*   **Data Integrity for Localized Audits:** Use this when you need to calculate the total length of the pedestrian network within a specific property boundary without "inheriting" parts of long streets that pass through the area.
*   **Consistent Results:**
    *   **Geometric Type:** Returns `LineString`.
    *   **Properties:** Includes full navigation metrics (`slope_perc`, `minutes`).
    *   **Filtering:** Filters at the database level using `ST_Within` logic.

---

#### **C) BBox Query - Full Segments, Ordered by Proximity**

This query combines a spatial filter (**Bounding Box**) with a sorting mechanism (**Distance**). By providing a reference `lat` and `lon` along with the `bbox`, the API identifies all pedestrian segments within the rectangle and sorts them starting from the one closest to the provided coordinates.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network?bbox=23.3200,42.6950,23.3250,42.6975&lat=42.6962&lon=23.3223&order_by=distance&limit=200&include_distance=true&simplify_m=3"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 37,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32194, 42.69701], [23.32207, 42.69751]]
      },
      "properties": {
        "id": 461,
        "type": "Локална алея",
        "str_class": "Алея с настилка",
        "segment_le": 56.98,
        "slope_perc": -5.41,
        "distance_m": 95.36,
        "source_id": "461"
      }
    },
    {
      "type": "Feature",
      "id": 173,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32418, 42.69746], [23.32416, 42.69740]]
      },
      "properties": {
        "id": 459,
        "type": "Пресичане",
        "str_class": "Подлез",
        "segment_le": 6.93,
        "slope_perc": 0.15,
        "distance_m": 202.82,
        "source_id": "459"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Output Structure: Property Fields**

When `order_by=distance` and `include_distance=true` are used, the following fields are of primary importance:

| Field | Type | Description |
| :--- | :--- | :--- |
| **`distance_m`** | `float` | **The calculated distance (meters)** from the provided reference point to the nearest point on the segment. |
| **`type`** | `string` | Functional classification (e.g., Local alley, Sidewalk). |
| **`str_class`** | `string` | Physical infrastructure (e.g., Paved alley, Underpass). |
| **`segment_le`** | `float` | The total physical length of the segment in meters. |
| **`slope_perc`** | `float` | Vertical gradient. Used to determine if the path is too steep for certain users. |
| **`minutes`** | `float` | Estimated time to traverse the **entire** segment at a standard walking speed. |

---

### **Technical Use Cases**

*   **Snap-to-Network:** Find the nearest walkable path to a user's GPS coordinates within their current map view.
*   **Accessibility Routing:** Identify the closest accessible path (low `slope_perc`) within a neighborhood.
*   **Contextual UI:** Display a list of nearby pedestrian features (e.g., "Nearest Underpass: 202m away") while showing the map.

**Note:** The `distance_m` is measured using ellipsoidal distance to the closest point of the `LineString`. If the user coordinate is exactly on the sidewalk, this value will be `0.0`.

---

#### **D) BBox Query - Full Segments, Proximity + Strict**

This is the most restrictive BBox query mode. It combines three powerful filters:
1.  **Spatial Filter:** Limits results to a specific rectangular area.
2.  **Strict Containment:** Uses `include_boundary=false` to discard any path that crosses the edge of the box, returning only segments that are **100% internal**.
3.  **Proximity Sorting:** Orders these internal segments based on their distance to a reference point (`lat`/`lon`).

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network?bbox=23.3200,42.6950,23.3250,42.6975&lat=42.6962&lon=23.3223&order_by=distance&include_boundary=false&limit=200&include_distance=true&simplify_m=3"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 173,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32418, 42.69746], [23.32416, 42.69740]]
      },
      "properties": {
        "id": 459,
        "type": "Пресичане",
        "str_class": "Подлез",
        "segment_le": 6.93,
        "slope_perc": 0.15,
        "distance_m": 202.82,
        "source_id": "459"
      }
    },
    {
      "type": "Feature",
      "id": 235,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32420, 42.69741], [23.32422, 42.69749]]
      },
      "properties": {
        "id": 460,
        "type": "Пресичане",
        "str_class": "Подлез",
        "segment_le": 9.16,
        "slope_perc": 0.91,
        "distance_m": 206.46,
        "source_id": "460"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Why use this mode?**

In Example C (Proximity without Strict), the "Local Alley" (ID 37) was the nearest result. However, in this mode, it is **excluded** because it physically crosses the boundary of the box. 

*   **Audit-Ready Data:** Ideal for scenarios where you need to find the nearest *internal* infrastructure (like an underpass or internal park path) without results being "polluted" by long sidewalks that primarily exist outside the bounding box.
*   **Infrastructure Isolation:** Useful for identifying purely local pedestrian features within a specific plaza or city block.

### **Output Property List**

| Field | Type | Description |
| :--- | :--- | :--- |
| **`id`** | `integer` | Database primary key. |
| **`distance_m`** | `float` | Distance from your `lat`/`lon` to the nearest point of the path. |
| **`segment_le`** | `float` | Full length of the segment (meters). |
| **`slope_perc`** | `float` | Average incline. Critical for determining wheelchair/stroller accessibility. |
| **`str_class`** | `string` | Infrastructure type (e.g., `Подлез` indicates an underpass). |
| **`type`** | `string` | Functional type (e.g., `Пресичане` indicates a crossing). |

---

#### **E) BBox Query - Clipped to BBox**

This query uses the `clip=true` parameter. Unlike the previous examples that return the "Full Segment" (even the parts outside the box), this mode performing a **"cookie-cutter"** operation. Any line segment crossing the edge of the BBox is physically cut at the boundary. 

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network?bbox=23.3200,42.6950,23.3250,42.6975&clip=true&limit=1000&simplify_m=3"
```

**Response (GeoJSON):**
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
          [23.322072353, 42.6975] 
        ]
      },
      "properties": {
        "id": 461,
        "type": "Локална алея",
        "str_class": "Алея с настилка",
        "segment_le": 56.98,
        "slope_perc": -5.41,
        "source_id": "461"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Why use Clipping?**

*   **Clean Map Rendering:** When building a tiled map interface, you often want lines to stop exactly at the edge of the tile. `clip=true` ensures no line "bleeds" into the neighboring area.
*   **Geometric Precision:** Look at the second coordinate of Feature **37**: `[23.322072353, 42.6975]`. The latitude is exactly **42.6975**, which is the `max_lat` of your BBox. In the non-clipped Example A, this coordinate was `42.697519846`. The API has dynamically recalculated the intersection point.
*   **Efficient Data Transfer:** By cutting the lines, you are not sending coordinate data for paths that are hundreds of meters away and invisible to the current user view.

### **Output Structure: Property Fields**

| Field | Type | Description |
| :--- | :--- | :--- |
| **`id`** | `integer` | Internal DB index for this segment. |
| **`geometry`** | `LineString` | The coordinates, modified to stop exactly at the BBox boundary. |
| **`segment_le`** | `float` | **Important:** In this specific mode, this field still represents the **Original Full Length** of the segment before it was cut. |
| **`type`** | `string` | Functional type (e.g., Local Alley). |
| **`str_class`** | `string` | Material/Infrastructure class (e.g., Paved Alley). |
| **`slope_perc`** | `float` | The average slope of the full original segment. |

---

**Crucial Note:** 
If you need to know the length or walking time of **only the part of the line that is visible inside the box**, you must add the `include_clipped_metrics=true` flag. This is demonstrated in the next example (**F**).

#### **F) BBox Query - Clipped with Per-Feature Metrics**

This is the most advanced geometry mode for the Pedestrian Network API. It combines the **"Cookie-Cutter"** clipping of the previous example with **Dynamic Metric Recalculation**. 

When `include_clipped_metrics=true` is used, the API calculates new values for length and walking time based **only on the portion of the segment that remains inside the box**.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network?bbox=23.3200,42.6950,23.3250,42.6975&clip=true&include_clipped_metrics=true&limit=500&simplify_m=3"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 37,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32194, 42.69701], [23.32207, 42.6975]]
      },
      "properties": {
        "id": 461,
        "type": "Локална алея",
        "segment_le": 56.98,
        "slope_perc": -5.41,
        "clipped_length_m": 54.77,
        "time_minutes_if_seconds_clipped_est": 0.91,
        "source_id": "461"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Recalculated Property Fields**

By enabling `include_clipped_metrics`, three critical new fields are added to the `properties` object:

| Field | Type | Description |
| :--- | :--- | :--- |
| **`clipped_length_m`** | `float` | The **actual length (meters)** of the line inside the box. Unlike `segment_le` (the total length), this value changes as you pan the map. |
| **`time_minutes_if_seconds_clipped_est`** | `float` | The **estimated walking time** for only the visible portion of the segment. |
| **`time_raw_clipped_est`** | `float` | The proportional "time weight" used for internal calculations. |
| **`time_note`** | `string` | A disclaimer explaining the source of the time estimates. |

---

### **Comparative Analysis: Full vs. Clipped**

To understand the power of this endpoint, look at Feature **ID 37** (the Local Alley):
*   **Original Total Length (`segment_le`)**: 56.98 meters.
*   **Visible Length inside your Box (`clipped_length_m`)**: 54.77 meters.
*   **Analysis**: This tells you that ~2.2 meters of this specific sidewalk exists outside your current map view.

### **Use Cases**
1.  **Walkability Density Dashboards**: If you want to sum up the "Total walkable meters in the visible area," you should iterate through the features and sum `clipped_length_m`. Summing `segment_le` would result in an over-estimation.
2.  **Precise Route Costing**: Calculate exactly how many seconds it takes to traverse the portion of a path visible on the screen.
3.  **Urban Tiling**: Perfectly fit network data into a grid system for advanced spatial analysis.

---

#### **G) BBox Query - Clipped + Strict**

This query combines **Strict Containment** (`include_boundary=false`) with **Clipped Metrics** (`include_clipped_metrics=true`). This results in a "high-integrity" dataset where only pedestrian segments that are **100% contained within the bounding box** are returned. 

Even though the segments are fully inside, the API still provides the `clipped_length_m` and `time` estimates to ensure consistency for analytical tools that expect the clipped property schema.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network?bbox=23.3200,42.6950,23.3250,42.6975&include_boundary=false&clip=true&include_clipped_metrics=true&limit=500&simplify_m=3"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 173,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32418, 42.69746], [23.32416, 42.69740]]
      },
      "properties": {
        "id": 459,
        "type": "Пресичане",
        "str_class": "Подлез",
        "segment_le": 6.93,
        "clipped_length_m": 6.93,
        "time_minutes_if_seconds_clipped_est": 0.11,
        "slope_perc": 0.15,
        "source_id": "459"
      }
    },
    {
      "type": "Feature",
      "id": 235,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32420, 42.69741], [23.32422, 42.69749]]
      },
      "properties": {
        "id": 460,
        "type": "Пресичане",
        "str_class": "Подлез",
        "segment_le": 9.16,
        "clipped_length_m": 9.17,
        "time_minutes_if_seconds_clipped_est": 0.15,
        "slope_perc": 0.91,
        "source_id": "460"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Why use this mode?**

*   **Small-Scale Asset Isolation:** This is the best way to isolate specific, self-contained infrastructure like **underpasses** (`Подлез`), internal courtyard paths, or specific crosswalks.
*   **Zero Noise:** Long sidewalks that only "pass through" the area are removed, leaving you with only the paths that truly belong to the specific square or intersection you are auditing.
*   **Metric Accuracy:** In this mode, `clipped_length_m` will match `segment_le` (within rounding margins), confirming that the entire path is being measured and visualized.

### **Output Property List**

| Field | Type | Description |
| :--- | :--- | :--- |
| **`id`** | `integer` | Unique database identifier. |
| **`type`** | `string` | Functional type (e.g., `Пресичане` - Crossing). |
| **`str_class`** | `string` | Material classification (e.g., `Подлез` - Underpass). |
| **`segment_le`** | `float` | Original length in the master database. |
| **`clipped_length_m`** | `float` | Precise length within the box (equal to `segment_le` here). |
| **`time_minutes_...`** | `float` | Estimated minutes to walk this specific segment. |
| **`slope_perc`** | `float` | Incline percentage. Essential for ADA/Wheelchair compliance checks. |

---

#### **H) BBox Query - Clipped + Proximity Ordered**

This configuration is the "Location-Aware Map Tile" mode. It provides the most relevant data for a user looking at a specific map area. It performs three main tasks:
1. **Clipping:** It cuts all pedestrian segments at the map boundary (`clip=true`).
2. **Sorting:** It orders these visible path fragments based on their proximity to the user's focus point (`order_by=distance`).
3. **Recalculation:** It provides specific metrics for only the visible portion of the path (`include_clipped_metrics=true`).

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network?bbox=23.3200,42.6950,23.3250,42.6975&lat=42.6962&lon=23.3223&order_by=distance&clip=true&include_clipped_metrics=true&limit=200&include_distance=true&simplify_m=3"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 37,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32194, 42.69701], [23.32207, 42.6975]]
      },
      "properties": {
        "id": 461,
        "type": "Локална алея",
        "str_class": "Алея с настилка",
        "distance_m": 95.36,
        "clipped_length_m": 54.77,
        "time_minutes_if_seconds_clipped_est": 0.91,
        "segment_le": 56.98,
        "slope_perc": -5.41
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Output Structure: Dynamic Property Fields**

This mode introduces a rich set of properties that distinguish between the "original" path and the "visible" path fragment:

| Field | Type | Description |
| :--- | :--- | :--- |
| **`distance_m`** | `float` | Distance from the reference `lat/lon` to the nearest point on this path fragment. |
| **`clipped_length_m`** | `float` | **New length:** The measurement of the segment strictly within the box. |
| **`time_minutes_..._est`** | `float` | **New time:** Recalculated walk time for only the visible portion. |
| **`segment_le`** | `float` | **Old length:** The total length of the path in the master database. |
| **`slope_perc`** | `float` | The average slope of the path (inherited from the master segment). |

---

### **Analytical Insights**

*   **Dynamic Clipping Context:** Look at Feature **ID 37**. The `distance_m` is **95.36m**, which helps with "Search Nearby" sorting. However, because `clip=true`, the geometry and the `clipped_length_m` (**54.77m**) are modified to fit the viewport perfectly.
*   **Time-to-Traverse:** The `time_minutes_if_seconds_clipped_est` (**0.91 min**) allows your application to tell the user: *"The part of the park alley you see on your screen takes about 55 seconds to walk."*
*   **Data Optimization:** By combining `simplify_m=3` and `clip=true`, you minimize the coordinate data sent over the network, ensuring the map remains responsive even with hundreds of path segments.

---

#### **Full Segment Queries (Radius Mode)**

#### **I) Radius Query - Full Segments (nearest-first default)**

This query retrieves pedestrian network segments within a circular radius of a specific point. It is the primary method for "Nearby" searches, such as finding the closest sidewalk or crossing to a user's current GPS location. By default, radius queries return results sorted by distance (closest first) and return the **entire geometry** of any segment that touches the circle.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network?lat=42.6970&lon=23.3220&radius_m=300&limit=1000"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 37,
      "geometry": {
        "type": "MultiLineString",
        "coordinates": [[[23.321941, 42.697016], [23.322077, 42.697519]]]
      },
      "properties": {
        "id": 461,
        "type": "Локална алея",
        "str_class": "Алея с настилка",
        "segment_le": 56.98,
        "slope_perc": -5.41,
        "minutes": 0.85,
        "distance_m": 5.12,
        "source_id": "461"
      }
    },
    {
      "type": "Feature",
      "id": 197,
      "geometry": {
        "type": "MultiLineString",
        "coordinates": [[[23.321973, 42.697752], "..."]]
      },
      "properties": {
        "id": 463,
        "type": "бул. Княгиня Мария Луиза",
        "str_class": "Тротоар",
        "segment_le": 5.10,
        "slope_perc": -6.81,
        "distance_m": 83.66,
        "source_id": "463"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Output Structure: Radius Property Fields**

In radius mode, the API automatically enriches the feature properties with proximity data.

| Field | Type | Description |
| :--- | :--- | :--- |
| **`id`** | `integer` | The database primary key for the segment. |
| **`distance_m`** | `float` | **Proximity:** The distance in meters from the query center to the nearest point on the path. |
| **`type`** | `string` | The functional name or category (e.g., `Локална алея` - Local alley). |
| **`str_class`** | `string` | The physical classification (e.g., `Тротоар` - Sidewalk, `Подлез` - Underpass). |
| **`segment_le`** | `float` | The total physical length of the segment in meters. |
| **`slope_perc`** | `float` | Vertical gradient. Negative values indicate a downhill slope relative to the start point. |
| **`minutes`** | `float` | Estimated time in minutes to traverse the entire segment at standard walking speed. |

---

### **Technical Use Cases**

*   **Proximity Discovery:** Finding the closest entry point to a pedestrianized zone or a park.
*   **Accessibility Assessments:** Identifying if the closest walkable path to a user is wheelchair-friendly (e.g., checking if `slope_perc` is between -5% and 5%).
*   **Local Navigation:** Calculating which side of a boulevard a user is on by comparing the distance to the nearest sidewalk segments on either side.

**Note on Geometry:** The API often returns **`MultiLineString`** geometries even for simple segments. This ensures compatibility with complex pedestrian infrastructure that may involve split paths or non-contiguous sections stored as a single database record.

---

#### **J) Radius Query - Full Segments, Strict Inside Circle**

This query applies a strict spatial filter using `include_boundary=false`. The API returns only those pedestrian segments that are **entirely contained** within the search radius. Any path that crosses the edge of the 300m circle (i.e., part of the sidewalk is at 310m distance) is completely omitted from the results.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network?lat=42.6970&lon=23.3220&radius_m=300&include_boundary=false&limit=10"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 37,
      "geometry": {
        "type": "MultiLineString",
        "coordinates": [[[23.32194, 42.69701], [23.32207, 42.69751]]]
      },
      "properties": {
        "id": 461,
        "type": "Локална алея",
        "str_class": "Алея с настилка",
        "segment_le": 56.98,
        "slope_perc": -5.41,
        "minutes": 0.85,
        "distance_m": 5.12,
        "source_id": "461"
      }
    },
    {
      "type": "Feature",
      "id": 173,
      "geometry": {
        "type": "MultiLineString",
        "coordinates": [[[23.32418, 42.69746], [23.32416, 42.69740]]]
      },
      "properties": {
        "id": 459,
        "type": "Пресичане",
        "str_class": "Подлез",
        "segment_le": 6.93,
        "slope_perc": 0.15,
        "minutes": 0.20,
        "distance_m": 182.91,
        "source_id": "459"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Output Structure: Property Field List**

When using strict radius mode, the properties focus on the inherent characteristics of the internal segments:

| Field | Type | Description |
| :--- | :--- | :--- |
| **`id`** | `integer` | Internal database ID. |
| **`distance_m`** | `float` | Proximity from the query center to the start of the path. |
| **`segment_le`** | `float` | The total length of the segment (meters). Because of `strict` mode, the entire length is guaranteed to be within the 300m radius. |
| **`slope_perc`** | `float` | Average incline percentage. Critical for determining if a path is accessible for those with mobility challenges. |
| **`minutes`** | `float` | Estimated time to walk this specific segment. |
| **`type`** | `string` | The functional classification (e.g., `Локална алея` - Local path). |
| **`str_class`** | `string` | Physical type (e.g., `Тротоар` - Sidewalk, `Подлез` - Underpass). |

---

### **Observations & Analysis**

*   **Asset Isolation:** This query is perfect for identifying "Hyper-Local" features. For example, the `Подлез` (Underpass) with ID `459` is only 6.93 meters long. Because it is so short, it is easily contained within the 300m circle.
*   **Total Walking Time Calculation:** By summing the `minutes` field for all features in this strict result set, you can calculate the total traversable time of the *entire* local pedestrian network without including time for long boulevards that exit the neighborhood.
*   **Safety Audit:** Use this to find all steep segments (`slope_perc` > 5%) that a user would encounter within a specific localized area (e.g., around a subway entrance).

---

#### **K) Radius Query - Full Segments, Explicit Distance Ordering**

This configuration explicitly defines the sorting behavior for a radius search. By setting `order_by=distance` and `include_distance=true`, you ensure that the response starts with the pedestrian segment physically closest to your search coordinates and provides the exact proximity in meters for every feature.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network?lat=42.6970&lon=23.3220&radius_m=300&order_by=distance&limit=200&include_distance=true"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 37,
      "geometry": {
        "type": "MultiLineString",
        "coordinates": [[[23.32194, 42.69701], [23.32207, 42.69751]]]
      },
      "properties": {
        "id": 461,
        "type": "Локална алея",
        "str_class": "Алея с настилка",
        "segment_le": 56.98,
        "slope_perc": -5.41,
        "distance_m": 5.12,
        "altitude_b": 6.05,
        "altitude_e": 2.96
      }
    },
    {
      "type": "Feature",
      "id": 197,
      "geometry": {
        "type": "MultiLineString",
        "coordinates": [[[23.32197, 42.69775], "..."]]
      },
      "properties": {
        "id": 463,
        "type": "бул. Княгиня Мария Луиза",
        "str_class": "Тротоар",
        "distance_m": 83.66,
        "segment_le": 5.10
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Output Structure: Enrichment Fields**

In this mode, the properties represent a mix of original infrastructure data and calculated proximity metrics:

*   **`distance_m`**: The shortest distance (in meters) from your query center to the segment. In the example, the nearest alley (ID 37) is just **5.12m** away.
*   **`altitude_b` / `altitude_e`**: The Z-coordinate (elevation) at the start and end of the segment. 
    *   *Example Analysis:* Segment 37 drops from **6.05m** to **2.96m**, resulting in the steep **-5.41% slope**.
*   **`segment_le`**: The total length of the segment. Note that even if only 1 meter of a 100-meter segment is inside the circle, this field will show the full `100.0`.
*   **`type` & `str_class`**: Combined, these tell you both the name/function and the material of the path.

### **Use Case: Navigation & Accessibility**
This endpoint is ideal for "Find the closest safe path" logic. 
1.  **Sorting:** `order_by=distance` ensures the app processes the closest path first.
2.  **Filtering:** A developer can look at the results and pick the first segment where `abs(slope_perc) < 3.0` to find the nearest wheelchair-accessible path.
3.  **Visual Context:** Since `clip` is false, the map can draw the entire sidewalk segment even if parts of it "leak" outside the 300m search circle, providing better visual continuity for the user.

---

#### **L) Radius Query - Full Segments, Ordered by ID**

By default, radius queries are optimized for proximity and sort results by distance. However, you can explicitly set `order_by=id`. This mode is the standard for **stable pagination** (using `limit` and `offset`). If you are exporting data or building a scrollable list of paths within a radius, sorting by ID ensures that the order remains consistent even if the center coordinates shift slightly.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network?lat=42.6970&lon=23.3220&radius_m=300&order_by=id&limit=10"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 37,
      "geometry": {
        "type": "MultiLineString",
        "coordinates": [[[23.321941, 42.697016], [23.322077, 42.697519]]]
      },
      "properties": {
        "id": 461,
        "type": "Локална алея",
        "str_class": "Алея с настилка",
        "segment_le": 56.98,
        "slope_perc": -5.41,
        "minutes": 0.85,
        "altitude_b": 6.05,
        "altitude_e": 2.96,
        "source_id": "461"
      }
    },
    {
      "type": "Feature",
      "id": 173,
      "geometry": {
        "type": "MultiLineString",
        "coordinates": [[[23.324186, 42.697460], [23.324165, 42.697400]]]
      },
      "properties": {
        "id": 459,
        "type": "Пресичане",
        "str_class": "Подлез",
        "segment_le": 6.93,
        "slope_perc": 0.15,
        "source_id": "459"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Output Structure: Property Field List**

When sorting by ID, the response focuses on the static infrastructure attributes of the walkable network:

| Field | Type | Description |
| :--- | :--- | :--- |
| **`id`** | `integer` | The unique internal database identifier (Primary Key). |
| **`type`** | `string` | The functional name or category (e.g., `бул. Княгиня Мария Луиза` - a specific boulevard sidewalk or `Локална алея`). |
| **`str_class`** | `string` | The physical infrastructure type (e.g., `Тротоар` - Sidewalk, `Подлез` - Underpass). |
| **`segment_le`** | `float` | The total physical length of the segment in **meters**. |
| **`slope_perc`** | `float` | Vertical gradient. Essential for filtering paths by accessibility level. |
| **`minutes`** | `float` | The estimated walking time for the **full** segment length. |
| **`altitude_b / e`** | `float` | Elevation start/end points. |

---

### **Technical Use Cases**

*   **Bulk Data Integration:** If you need to sync all pedestrian segments within 300m of a subway station into your own database or routing engine, using `order_by=id` prevents "flickering" or duplicate records if you fetch the data in multiple pages.
*   **Performance Optimization:** Sorting by an indexed integer (`id`) is the fastest possible database operation. Use this when proximity order is not required for your frontend logic.
*   **Segment Identification:** Since the results are sorted by the internal `id`, this is the easiest way to locate a specific segment for debugging or data verification.

**Note:** Unlike radius queries sorted by distance, the `distance_m` property is **not** included by default in this mode unless you explicitly add `&include_distance=true`.

---

#### **Clipped Geometry Queries (Radius Mode)**

#### **M) Radius Query - Clipped to Circle**

This query searches within a circular radius and applies the `clip=true` parameter. The API performs a geometric intersection, "cutting" any pedestrian segments that cross the 300m boundary. The resulting GeoJSON contains line fragments that fit perfectly within the search circle.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network?lat=42.6970&lon=23.3220&radius_m=300&clip=true&limit=1000&simplify_m=3"
```

**Response (GeoJSON):**
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
        "type": "Локална алея",
        "str_class": "Алея с настилка",
        "segment_le": 56.98,
        "slope_perc": -5.41,
        "distance_m": 5.12,
        "source_id": "461"
      }
    },
    {
      "type": "Feature",
      "id": 197,
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [23.321973232, 42.69775292],
          [23.321925656, 42.697780535]
        ]
      },
      "properties": {
        "id": 463,
        "type": "бул. Княгиня Мария Луиза",
        "str_class": "Тротоар",
        "segment_le": 5.10,
        "slope_perc": -6.81,
        "distance_m": 83.66
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Output Structure: Property Fields**

In clipped radius mode, the geometry is altered, but the properties provide context for the original source:

| Field | Type | Description |
| :--- | :--- | :--- |
| **`id`** | `integer` | Internal database ID. |
| **`type`** | `string` | Functional classification (e.g., specific street name or category like `Локална алея`). |
| **`str_class`** | `string` | Physical infrastructure type (e.g., `Тротоар` - Sidewalk). |
| **`distance_m`** | `float` | Proximity from the search center (`lat/lon`) to the nearest point on the path. |
| **`segment_le`** | `float` | **Original Full Length:** The length of the segment as it exists in the database before clipping. |
| **`slope_perc`** | `float` | The vertical gradient of the original segment. |
| **`minutes`** | `float` | The walking time for the **full** segment. |

---

### **Why use Radius Clipping?**

*   **Circular Visualizations:** If your frontend UI uses a circular "search area" overlay, `clip=true` ensures that the pedestrian paths do not protrude outside the shaded circle, creating a clean, professional map.
*   **Buffer Analysis:** This is the first step in calculating the "walkable density" of a specific radius. By cutting the lines, you prepare the data for accurate length summation within the circle.
*   **Performance:** Using `simplify_m=3` in conjunction with clipping further optimizes the data for mobile devices by removing unnecessary detail from the paths.

**Note:** To get the length and walking time of the **newly cut** line fragments, you must add `&include_clipped_metrics=true`.

---

#### **N) Radius Query - Clipped with Per-Feature Metrics**

This is the ultimate query for localized pedestrian infrastructure analysis. It combines **Radius Clipping** (`clip=true`) with **Dynamic Metric Recalculation** (`include_clipped_metrics=true`). The API doesn't just cut the lines to fit the 300m circle; it also calculates the specific length and walking time for each resulting fragment.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network?lat=42.6970&lon=23.3220&radius_m=300&clip=true&include_clipped_metrics=true&limit=500&simplify_m=3"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 37,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32194, 42.69701], [23.32207, 42.69751]]
      },
      "properties": {
        "id": 461,
        "type": "Локална алея",
        "str_class": "Алея с настилка",
        "distance_m": 5.12,
        "segment_le": 56.98,
        "clipped_length_m": 57.02,
        "time_minutes_if_seconds_clipped_est": 0.95,
        "slope_perc": -5.41
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Recalculated Property Fields**

When `include_clipped_metrics` is active, the API enriches the `properties` with high-precision data about the "visible" portion of the network:

| Field | Type | Description |
| :--- | :--- | :--- |
| **`clipped_length_m`** | `float` | The **recalculated length** in meters of the segment portion that falls strictly inside the radius. |
| **`time_minutes_if_seconds_clipped_est`** | `float` | The **estimated walking time** (in minutes) for only the part of the path inside the search circle. |
| **`time_raw_clipped_est`** | `float` | A raw time weight used for internal aggregation. |
| **`distance_m`** | `float` | How far the closest point of this segment is from the center coordinates. |
| **`segment_le`** | `float` | **Reference field:** The original full length of the path before clipping. |

---

### **Why use this configuration?**

This mode provides the data necessary to answer hyper-local questions:
*   **"How many meters of sidewalk are within a 5-minute walk?"** You can sum the `clipped_length_m` of all returned features to get an exact result.
*   **"Which path fragments near me are too steep?"** By looking at the `geometry` (clipped to your radius) and the `slope_perc`, you can highlight inaccessible fragments on a map.
*   **Precision Dashboarding:** This is the most accurate way to populate a "Walkability Widget" for a specific property address, as it ignores all path length that exists outside the 300m threshold.

**Technical Tip:** Notice that for Feature **ID 37**, the `clipped_length_m` is almost identical to the `segment_le`. This indicates that this specific alley is entirely contained within the 300m circle. For longer boulevards, the `clipped_length_m` would be significantly smaller than the `segment_le`.

---

#### **O) Radius Query - Clipped + Strict Inside Circle**

This query is the most restrictive and precise method for auditing a local pedestrian environment. It combines **Strict Containment** (`include_boundary=false`) with **Clipped Metrics** (`include_clipped_metrics=true`). 

In this mode, the API returns only those pedestrian segments that are **100% contained** within the 300m radius. By excluding segments that cross the circle's boundary, you eliminate "noise" from long arterial sidewalks that primarily serve areas outside your immediate search zone.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network?lat=42.6970&lon=23.3220&radius_m=300&include_boundary=false&clip=true&include_clipped_metrics=true&limit=500&simplify_m=3"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 37,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32194, 42.69701], [23.32207, 42.69751]]
      },
      "properties": {
        "id": 461,
        "type": "Локална алея",
        "str_class": "Алея с настилка",
        "segment_le": 56.98,
        "clipped_length_m": 57.02,
        "time_minutes_if_seconds_clipped_est": 0.95,
        "slope_perc": -5.41,
        "distance_m": 5.12
      }
    },
    {
      "type": "Feature",
      "id": 173,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32418, 42.69746], [23.32416, 42.69740]]
      },
      "properties": {
        "id": 459,
        "type": "Пресичане",
        "str_class": "Подлез",
        "segment_le": 6.93,
        "clipped_length_m": 6.93,
        "time_minutes_if_seconds_clipped_est": 0.11,
        "slope_perc": 0.15,
        "distance_m": 182.91
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Output Structure: Internal-Only Metrics**

Because of the `strict` logic, the "Clipped" metrics will generally match the "Original" metrics, as the segments are already fully inside the circle:

| Field | Type | Description |
| :--- | :--- | :--- |
| **`id`** | `integer` | Internal database ID. |
| **`clipped_length_m`** | `float` | The measured length inside the circle (matches `segment_le` in this mode). |
| **`time_minutes_...`** | `float` | Walking time for the segment (e.g., `0.11` min for a short underpass). |
| **`distance_m`** | `float` | Proximity from the search center to the start of the path. |
| **`type`** | `string` | Function (e.g., `Пресичане` - Crossing, `Тротоар` - Sidewalk). |
| **`str_class`** | `string` | Infrastructure category (e.g., `Подлез` - Underpass). |

---

### **Why use this mode?**

*   **Walkable Inventory:** Use this to get an exact inventory of every self-contained pedestrian asset within 300m of a property. This is ideal for insurance or urban planning reports that require "exclusive" counts.
*   **Infrastructure Quality Analysis:** Perfect for isolating the average slope and walking time of paths that exist purely within a park or residential complex.
*   **Eliminating Arterial Bias:** By removing long sidewalks that lead to other districts, you gain a more accurate "Local Walkability" score based only on paths that characterize the immediate vicinity.

**Note:** If your goal is to calculate a total "Sum of Walkable Meters," Example **N** (Clipped without Strict) is usually better. Use this mode (Example **O**) when you need to identify **which individual assets** belong entirely to the user's localized zone.

---

#### **P) Radius Query - Clipped + Nearest-First + Distance**

This query is the "Local Network Audit" mode. It is the most precise way to analyze the immediate pedestrian environment around a specific coordinate. It performs three critical operations:
1.  **Radius Clipping:** It cuts all paths exactly at the 300m circle boundary (`clip=true`).
2.  **Proximity Sorting:** It lists the paths starting with the one closest to the center point (`order_by=distance`).
3.  **Recalculated Metrics:** It provides the exact length and walking time for only the portions of the paths that fall inside the circle (`include_clipped_metrics=true`).

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network?lat=42.6970&lon=23.3220&radius_m=300&order_by=distance&clip=true&include_clipped_metrics=true&limit=200&include_distance=true&simplify_m=3"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 37,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32194, 42.69701], [23.32207, 42.69751]]
      },
      "properties": {
        "id": 461,
        "type": "Локална алея",
        "str_class": "Алея с настилка",
        "distance_m": 5.12,
        "clipped_length_m": 57.02,
        "time_minutes_if_seconds_clipped_est": 0.95,
        "segment_le": 56.98,
        "slope_perc": -5.41,
        "source_id": "461"
      }
    },
    {
      "type": "Feature",
      "id": 197,
      "geometry": {
        "type": "LineString",
        "coordinates": [[23.32197, 42.69775], [23.32192, 42.69778]]
      },
      "properties": {
        "id": 463,
        "type": "бул. Княгиня Мария Луиза",
        "str_class": "Тротоар",
        "distance_m": 83.66,
        "clipped_length_m": 5.10,
        "time_minutes_if_seconds_clipped_est": 0.08,
        "segment_le": 5.10,
        "slope_perc": -6.81
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Output Structure: Recalculated Proximity Fields**

This mode provides a "Dual Perspective" on every pedestrian segment:

| Field | Type | Description |
| :--- | :--- | :--- |
| **`distance_m`** | `float` | **Proximity:** The distance from the center point to the nearest point of the segment. |
| **`clipped_length_m`** | `float` | **Visible Length:** The measurement of the segment portion strictly inside the 300m circle. |
| **`time_minutes_..._est`** | `float` | **Visible Time:** Walking time for only the part of the path inside the circle. |
| **`segment_le`** | `float` | **Original Length:** The total length of the segment in the master database. |
| **`slope_perc`** | `float` | Average incline of the path segment. |
| **`type` / `str_class`** | `string` | Infrastructure and functional classifications. |

---

### **Analytical Use Cases**

*   **Walkability Scoring:** Use the `clipped_length_m` and `time_minutes...` fields to calculate how many meters of sidewalk or park alleys are available within exactly a 2-minute or 5-minute radius.
*   **Accessibility Highlighting:** Since `clip=true` cuts the lines, you can highlight only the specific "fragments" of the street that are nearby and have a slope steeper than 5%.
*   **Clean Geometry for Mobile Maps:** By combining `clip` and `simplify_m=3`, you provide a visually perfect circular "local map" to the user, with no line segments sticking out of the search radius, while maintaining accurate metadata.

---

#### **Nearest Segment Queries**

#### **Q) Nearest Segment Only - Full Geometry**

This specialized query is designed for "Point-to-Network Snapping." By setting `limit=1` and `order_by=distance`, the API identifies the single pedestrian segment closest to your coordinates. This is the most efficient way to determine which sidewalk, alley, or crossing a user is currently standing on or nearest to.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network?lat=42.6970&lon=23.3220&radius_m=300&limit=1&order_by=distance&include_distance=true"
```

**Response (GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 37,
      "geometry": {
        "type": "MultiLineString",
        "coordinates": [[[23.321941, 42.697016], [23.322077, 42.697519]]]
      },
      "properties": {
        "id": 461,
        "type": "Локална алея",
        "str_class": "Алея с настилка",
        "segment_le": 56.98,
        "slope_perc": -5.41,
        "minutes": 0.85,
        "distance_m": 5.12,
        "altitude_b": 6.05,
        "altitude_e": 2.96,
        "source_id": "461"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Output Structure: Nearest Feature Properties**

| Field | Type | Description |
| :--- | :--- | :--- |
| **`id`** | `integer` | Unique database identifier. |
| **`distance_m`** | `float` | **Proximity:** The exact distance (5.12m) from the query point to the nearest coordinate of the path. |
| **`type`** | `string` | The functional use (e.g., `Локална алея` - Local park path). |
| **`str_class`** | `string` | Physical infrastructure (e.g., `Алея с настилка` - Paved path). |
| **`segment_le`** | `float` | The total length of the segment (56.98m). |
| **`slope_perc`** | `float` | The vertical gradient (-5.41%). |
| **`minutes`** | `float` | Estimated time to traverse this specific path. |

---

### **Implementation & Use Cases**

*   **Reverse Geocoding to Network:** Instead of just knowing a street address, this endpoint tells you exactly which walkable segment the user is interacting with.
*   **Routing Origin/Destination:** When a user requests a walking route, use this endpoint to "snap" their current GPS position to the nearest point on the pedestrian graph to ensure the route starts on a valid path.
*   **Infrastructure Inspection:** Perfect for field apps where a maintenance worker needs to pull up the data for the specific sidewalk segment they are currently standing on.
*   **Safety Context:** Tells you immediately if the nearest path has a high incline or an unusual infrastructure class (like an underpass), which helps in setting user expectations for the terrain.

**Technical Tip:** The `distance_m` of **5.12m** suggests the user is standing on the edge of the path or very close to it. If the distance were `0.0`, the user's coordinates would lie exactly on the line segment.

---

#### **R) Nearest Segment Only - Clipped Geometry + Metrics**

This is the most analytically precise way to look at the immediate environment. It identifies the single nearest pedestrian segment to your location, cuts it exactly at the radius boundary (`clip=true`), and calculates the metrics for only that visible portion.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network?lat=42.6970&lon=23.3220&radius_m=300&clip=true&include_clipped_metrics=true&limit=1&order_by=distance&include_distance=true"
```

**Response (GeoJSON):**
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
        "type": "Локална алея",
        "str_class": "Алея с настилка",
        "distance_m": 5.12,
        "clipped_length_m": 57.02,
        "time_minutes_if_seconds_clipped_est": 0.95,
        "segment_le": 56.98,
        "slope_perc": -5.41,
        "altitude_b": 6.05,
        "altitude_e": 2.96
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Output Structure: Property Breakdown**

This mode provides the highest density of metadata for a single feature:

| Field | Type | Description |
| :--- | :--- | :--- |
| **`distance_m`** | `float` | The proximity of the query point to the segment (e.g., 5.12m). |
| **`clipped_length_m`** | `float` | The exact length of the path fragment that stays inside the search circle. |
| **`time_minutes_..._est`** | `float` | Estimated time required to walk only the portion of the path within the radius. |
| **`segment_le`** | `float` | The total physical length of the segment as stored in the database. |
| **`slope_perc`** | `float` | Average incline. Essential for determining if the path is accessible. |
| **`type` / `str_class`** | `string` | Functional and physical classifications of the infrastructure. |

---

### **Implementation Context**

*   **"Is this path long enough?":** By comparing `clipped_length_m` and `distance_m`, you can tell if the user is standing on a short segment (like a crossing) or a long stretch of sidewalk.
*   **Localized Walking Experience:** The `time_minutes_if_seconds_clipped_est` field provides a realistic "Local Journey" estimate. If the segment is 500m long but only 50m of it are within the 300m circle, this field calculates the time for the 50m fragment, which is more relevant to the user's immediate surroundings.
*   **UI Focus:** Use this to auto-select and highlight the "Active Segment" on a user's interface, providing them with the exact slope and infrastructure details of where they are currently walking.

**Note:** In this specific example (ID 37), the `clipped_length_m` (**57.02m**) is roughly equal to the `segment_le` (**56.98m**), confirming that the entire path is situated inside the 300m radius.

---

### **Input Parameters**

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `bbox` | `string` | Conditional | Bounding box coordinates: `min_lon,min_lat,max_lon,max_lat`. |
| `lat` | `float` | Conditional | Latitude of center point. |
| `lon` | `float` | Conditional | Longitude of center point. |
| `radius_m` | `integer` | Conditional | Search radius in meters. |
| `limit` | `integer` | No | Maximum number of features to return. |
| `offset` | `integer` | No | Number of features to skip (pagination). |
| `simplify_m` | `float` | No | Simplification tolerance in meters. |
| `include_boundary` | `boolean` | No | Include segments touching boundary (default: `true`). |
| `order_by` | `string` | No | Sort order: `id`, `distance` (default depends on query type). |
| `include_distance` | `boolean` | No | Include distance from reference point (default: `false`). |
| `clip` | `boolean` | No | Clip geometries to query region (default: `false`). |
| `include_clipped_metrics` | `boolean` | No | Include clipped segment metrics (requires `clip=true`). |
| `center_lat` | `float` | No | Reference latitude for nearest segment calculation. |
| `center_lon` | `float` | No | Reference longitude for nearest segment calculation. |

### **Output Structure**

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
        "altitude_b": 547.2,
        "altitude_e": 544.5,
        "source_id": "461",
        "distance_m": 15.3,  // Only when include_distance=true
        "clipped_length_m": 45.6,  // Only when include_clipped_metrics=true
        "time_raw_clipped_est": 0.68,  // Only when include_clipped_metrics=true
        "time_minutes_if_seconds_clipped_est": 0.0113  // Only when include_clipped_metrics=true
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

### **Property Fields**

*   **`type`**: Functional type (e.g., "Локална алея", "Пресичане", "Тротоар").
*   **`str_class`**: Physical classification ("Алея с настилка", "Подлез", "Тротоар").
*   **`segment_le`**: Segment length in meters.
*   **`slope_perc`**: Incline/slope as percentage (negative = downhill).
*   **`minutes`**: Estimated walking time in minutes.
*   **`altitude_b` / `altitude_e`**: Elevation at beginning/end of segment.
*   **`distance_m`**: Distance from reference point (when `include_distance=true`).
*   **`clipped_length_m`**: Length of clipped portion (when `include_clipped_metrics=true`).
*   **`time_raw_clipped_est`**: Estimated time for clipped portion (minutes).
*   **`time_minutes_if_seconds_clipped_est`**: Clipped time converted to minutes.

**Notes:**
- **Geometry Modes:** Choose between full segments or clipped portions with `clip=true`.
- **Performance:** Use `simplify_m=2` or higher for large-scale visual maps.
- **Connectivity:** Segments share coordinates at intersections for graph-based analysis.
- **Clipped Metrics:** When `include_clipped_metrics=true`, metrics are recalculated for the clipped portion.

---

## 2. Pedestrian Network Statistics Endpoint: `GET /datasets/pedestrian_network/stats`

Provides comprehensive statistics for pedestrian infrastructure within specified regions, including length distributions, walking time estimates, and slope analysis. Returns both `intersecting_stats` (touch/intersect boundary) and `strict_stats` (fully inside region).

### **Bounding Box Statistics**

### **2. Pedestrian Network Statistics Endpoint: `GET /datasets/pedestrian_network/stats`**

This endpoint provides a comprehensive analytical summary of the pedestrian environment within a specific area. Unlike the data endpoint which returns individual lines, this endpoint performs complex spatial aggregations to calculate total network length, average walking times, and slope distributions (critical for accessibility audits).

#### **1) Stats (BBox) - Default Top 10**

Retrieves aggregated metrics for a rectangular area. It automatically provides two sets of statistics: **Intersecting** (any path visible in the box) and **Strict** (only paths entirely inside the box).

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network/stats?bbox=23.3200,42.6950,23.3250,42.6975&top_n=10"
```

**Response (JSON Summary):**
```json
{
  "query": {
    "kind": "bbox",
    "bbox": [23.32, 42.695, 23.325, 42.6975]
  },
  "reference_point": { "lat": 42.69625, "lon": 23.3225 },
  "intersecting_stats": {
    "segment_count": 3,
    "region_area_m2": 113945.85,
    "total_length_m_in_region": 70.89,
    "network_density_m_per_km2": 622.11,
    "time": {
      "time_minutes_if_seconds_sum_in_region": 1.18,
      "time_segments_used": 3
    },
    "slope": {
      "mean_abs_slope_weighted": 4.31,
      "length_share_slope_gt_5pct": 0.77
    },
    "groupings": {
      "by_type": [
        { "type": "Локална алея", "count": 1, "length_m": 54.77 },
        { "type": "Пресичане", "count": 2, "length_m": 16.11 }
      ]
    }
  },
  "strict_stats": {
    "segment_count": 2,
    "total_length_m_in_region": 16.11,
    "network_density_m_per_km2": 141.41
  },
  "nearest_segment": {
    "id": 37,
    "distance_m": 96.68,
    "properties": { "type": "Локална алея", "str_class": "Алея с настилка" }
  },
  "boundary_effects": { "segments_touching_boundary_count": 1 }
}
```

---

### **Output Structure: Statistical Definitions**

#### **A) Spatial Metrics**
*   **`region_area_m2`**: Total footprint of the bounding box.
*   **`total_length_m_in_region`**: The sum of all pedestrian paths (meters). In `intersecting_stats`, this is the **clipped length** (only what's inside the box).
*   **`network_density_m_per_km2`**: A standardized metric representing how many meters of walkable path exist per square kilometer. High values indicate a highly "connected" urban fabric.

#### **B) Traversability & Time**
*   **`time_minutes_if_seconds_sum_in_region`**: The total estimated time (minutes) required to walk every single segment visible in the box. 
*   **`mean_abs_slope_weighted`**: The average slope of the area, weighted by segment length. 
    *   *Insight:* A short steep ramp has less impact on the score than a long steep hill.
*   **`length_share_slope_gt_5pct`**: The percentage of the network (0.0 to 1.0) that has a slope steeper than 5%. In this example, **77%** of the visible network is considered steep.

#### **C) Classification Groupings**
*   **`by_type`**: Breakdown of functional uses (e.g., `Тротоар` - Sidewalk vs `Пресичане` - Crossing).
*   **`by_str_class`**: Breakdown of physical infrastructure (e.g., `Подлез` - Underpass).

---

### **Analytical Comparison**

| Metric | Intersecting Stats | Strict Stats | Analysis |
| :--- | :--- | :--- | :--- |
| **Segment Count** | 3 | 2 | One segment (the Alley) crosses the boundary. |
| **Total Length** | 70.89m | 16.11m | Most of the area's walkability comes from paths that extend beyond this box. |
| **Density** | 622 m/km² | 141 m/km² | Shows that "Full Coverage" is much higher than "Internal-only" infrastructure. |

### **Use Case**
*   **Urban Accessibility Audit:** By looking at `length_share_slope_gt_5pct`, planners can instantly see if a neighborhood is difficult for wheelchair users.
*   **Infrastructure Investment:** Low `network_density` values identify "pedestrian deserts" where more sidewalks or paths are needed.
*   **Walkability Scores:** The `total_walking_time_min` provides a data point for "15-minute city" planning models.

---

#### **2) Stats (BBox) + Nearest Segment Geometry**

This configuration provides a powerful "Dashboard + Map" response. While the top-level fields provide aggregated metrics for the entire bounding box (macro-view), enabling `include_nearest_geometry=true` embeds the full high-precision GeoJSON geometry for the specific segment closest to the center of the box (micro-view).

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network/stats?bbox=23.3200,42.6950,23.3250,42.6975&include_nearest_geometry=true&top_n=10"
```

**Response (GeoJSON + Stats):**
```json
{
  "query": { "kind": "bbox", "bbox": [23.32, 42.695, 23.325, 42.6975] },
  "reference_point": { "lat": 42.69625, "lon": 23.3225 },
  "intersecting_stats": {
    "segment_count": 3,
    "total_length_m_in_region": 70.89,
    "time": { "time_minutes_if_seconds_sum_in_region": 1.18 },
    "slope": { "mean_abs_slope_weighted": 4.31, "length_share_slope_gt_5pct": 0.77 },
    "groupings": {
      "by_type": [{ "type": "Локална алея", "count": 1, "length_m": 54.77 }, "..."]
    },
    "nearest_segment": {
      "id": 37,
      "distance_m": 96.68,
      "feature": {
        "type": "Feature",
        "geometry": {
          "type": "MultiLineString",
          "coordinates": [[[23.32194, 42.69701], [23.32207, 42.69751]]]
        },
        "properties": { "id": 461, "type": "Локална алея", "slope_perc": -5.41 }
      }
    }
  },
  "strict_stats": {
    "segment_count": 2,
    "total_length_m_in_region": 16.11,
    "network_density_m_per_km2": 141.41
  }
}
```

---

### **Output Structure: Integrated Analytics**

This endpoint returns a dual-stat structure to help developers understand both the total infrastructure and the "clean" internal network:

#### **1. Macro Statistics (`intersecting_stats`)**
*   **`total_length_m_in_region`**: The sum of all walkable meters currently visible in the box.
*   **`network_density_m_per_km2`**: Standardized connectivity score (622.1 in this area).
*   **`time_minutes_if_seconds_sum_in_region`**: Total time (1.18 min) required to walk the entire visible network.
*   **`length_share_slope_gt_5pct`**: Proportion of the network that is steep (0.77 or 77% of this area).

#### **2. The Nearest Segment Feature**
*   **`id` / `distance_m`**: Identifies the closest path and its distance from the centroid.
*   **`feature`**: Contains standard GeoJSON fields (`type`, `geometry`, `properties`). This is identical to the output of the data endpoint, allowing you to render the path directly on a map.

#### **3. Strict Containment (`strict_stats`)**
*   Calculates the same metrics as above, but **only** for segments that do not touch the BBox boundary. 
*   *Note:* The count drops from **3** to **2**, because the 54-meter alley crosses the edge and is excluded here.

---

### **Implementation Context**

*   **Interactive Viewports:** Use this to update a "Walkability Index" sidebar as the user pans. The `feature` geometry allows you to auto-highlight the most "relevant" path (the nearest one) without needing a second API call.
*   **Weighted Slopes:** The `mean_abs_slope_weighted` (**4.31%**) provides a more accurate feel for the terrain than a simple average, as it prioritizes the slope of longer segments.
*   **Standardized Time:** The `time_raw` is automatically scaled based on how much of the segment is clipped, providing realistic walking times for the specific area being viewed.

---

#### **3) Stats (BBox) + Nearest Segment to Explicit Reference Point**

This query allows you to decouple the **Analytical Area** (the Bounding Box) from the **Proximity Search**. By providing `center_lat` and `center_lon`, the API calculates aggregated walkability statistics for the entire neighborhood while identifying the nearest pedestrian path specifically to a point of interest (e.g., a specific building entrance or a user's click location) rather than the box's center.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network/stats?bbox=23.3200,42.6950,23.3250,42.6975&center_lat=42.6962&center_lon=23.3223&top_n=10"
```

**Response (JSON Summary):**
```json
{
  "query": { "kind": "bbox", "bbox": [23.32, 42.695, 23.325, 42.6975] },
  "reference_point": { "lat": 42.6962, "lon": 23.3223 },
  "intersecting_stats": {
    "segment_count": 3,
    "total_length_m_in_region": 70.89,
    "network_density_m_per_km2": 622.11,
    "time": { "time_minutes_if_seconds_sum_in_region": 1.18 },
    "slope": { "mean_abs_slope_weighted": 4.31, "length_share_slope_gt_5pct": 0.77 },
    "groupings": {
      "by_type": [
        { "type": "Локална алея", "count": 1, "length_m": 54.77 },
        { "type": "Пресичане", "count": 2, "length_m": 16.11 }
      ]
    },
    "nearest_segment": {
      "id": 37,
      "distance_m": 95.36,
      "properties": { "type": "Локална алея", "segment_le": 56.98, "slope_perc": -5.41 }
    }
  },
  "strict_stats": {
    "segment_count": 2,
    "total_length_m_in_region": 16.11,
    "nearest_segment": {
      "id": 173,
      "distance_m": 202.83,
      "properties": { "type": "Пресичане", "str_class": "Подлез" }
    }
  }
}
```

---

### **Output Breakdown & Analysis**

#### **1. Explicit Proximity vs. Centroid**
*   **`reference_point`**: Matches the user-provided `center_lat/lon`. 
*   **`nearest_segment` (intersecting)**: Identifies segment **ID 37** as the closest, located **95.36m** from the provided point.
*   **`nearest_segment` (strict)**: Identifies segment **ID 173** (an underpass) as the closest segment *that is fully contained* within the box, located **202.83m** away.

#### **2. Slope & Accessibility Metrics**
*   **`mean_abs_slope_weighted` (4.31%)**: The average incline of the visible network.
*   **`length_share_slope_gt_5pct` (0.77)**: A critical accessibility insight indicating that **77% of the walkable path length** in this view is steeper than a 5% grade (the standard threshold for easy wheelchair/stroller use).

#### **3. Functional Groupings**
*   **`by_type`**: Shows that the majority of the visible network length (**54.77m**) is comprised of "Local Alleys" (`Локална алея`), with the remainder being "Crossings" (`Пресичане`).
*   **`by_str_class`**: Confirms the physical nature of the paths, separating paved alleys from underpasses (`Подлез`).

---

### **Implementation Use Cases**

*   **Real Estate "Walk-Shed" Reports:** Generate a report for a specific house address. The BBox provides the "Area Walkability Score" (Density/Slope Share), while the Explicit Reference Point tells the user exactly how many meters they have to walk to reach the first sidewalk.
*   **Urban Maintenance Planning:** Filter for areas where `length_share_slope_gt_5pct` is high to prioritize the installation of handrails or specialized non-slip surfaces.
*   **Navigation Context:** Display the nearest "Internal" path (via `strict_stats.nearest_segment`) to help users find the closest infrastructure that isn't a busy main road sidewalk.

---

#### **4) Stats (BBox) + Reference Point + Nearest Geometry**

This configuration represents the most comprehensive data request for Bounding Box analytics. It provides aggregate pedestrian infrastructure metrics for the entire viewport while embedding the full high-precision GeoJSON geometry for the specific segment closest to your point of interest (`center_lat`/`center_lon`).

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network/stats?bbox=23.3200,42.6950,23.3250,42.6975&center_lat=42.6962&center_lon=23.3223&include_nearest_geometry=true&top_n=10"
```

**Response (GeoJSON + Stats):**
```json
{
  "query": { "kind": "bbox", "bbox": [23.32, 42.695, 23.325, 42.6975] },
  "reference_point": { "lat": 42.6962, "lon": 23.3223 },
  "intersecting_stats": {
    "segment_count": 3,
    "total_length_m_in_region": 70.89,
    "network_density_m_per_km2": 622.11,
    "slope": {
      "mean_abs_slope_weighted": 4.31,
      "length_share_slope_gt_5pct": 0.77
    },
    "nearest_segment": {
      "id": 37,
      "distance_m": 95.36,
      "feature": {
        "type": "Feature",
        "geometry": {
          "type": "MultiLineString",
          "coordinates": [[[23.32194, 42.69701], [23.32207, 42.69751]]]
        },
        "properties": { "id": 461, "type": "Локална алея", "slope_perc": -5.41 }
      }
    }
  },
  "strict_stats": {
    "segment_count": 2,
    "total_length_m_in_region": 16.11,
    "slope": { "mean_abs_slope_weighted": 0.58 }
  }
}
```

---

### **Output Structure: Integrated Analytics**

This endpoint returns a hierarchical JSON structure designed for simultaneous mapping and data visualization:

#### **1. Aggregated Metrics (`intersecting_stats` & `strict_stats`)**
*   **`network_density_m_per_km2`**: Standardized connectivity. In this area, the intersecting density (622m) is much higher than the internal-only density (141m), suggesting many paths serve as links to outside areas.
*   **`time_minutes_if_seconds_sum_in_region`**: The total time needed to walk all visible fragments (1.18 min).
*   **`length_share_slope_gt_5pct`**: A crucial accessibility score. Here, **77%** of the paths are considered steep, posing challenges for accessibility.

#### **2. The Nearest Segment Object**
*   **`id` / `distance_m`**: Identifies the closest path (ID 37) and its proximity (95.36m).
*   **`feature`**: Contains the full **GeoJSON Feature**. This includes the `MultiLineString` coordinates, allowing you to draw the specific "nearest path" on a map instantly.

---

### **Why use this configuration?**

*   **Interactive Accessibility Maps:** You can use the `length_share_slope_gt_5pct` to color-code a neighborhood (e.g., Red for "Steep Neighborhood") while using the `feature` object to highlight the exact sidewalk a user has selected or is standing near.
*   **Single-Request Efficiency:** This eliminates the need to call the data endpoint for geometry and the stats endpoint for context. One call provides the "Greenness/Walkability" of the district and the "Shape" of the closest path.
*   **Slope Discrepancy Insight:** Notice that the `strict_stats` (internal segments) have a weighted slope of only **0.58%**, while the `intersecting_stats` have **4.31%**. This tells a planner that the steepest parts of the network are the long paths entering/exiting the area, not the short internal segments.

### **Use Case**
*   **Real Estate Dashboards:** When a user clicks a property, show the "Local Walkability Stats" for the surrounding box and highlight the "Nearest Pedestrian Connection" on the map using the embedded geometry.

---

### **Radius Statistics**

#### **5) Stats (Radius) - Default Top 10**

This query provides an aggregated walkability audit for a circular region. By defining a center point and a 300m radius, the API calculates the "Greenness" and "Walkability" of a specific neighborhood. It is the primary tool for generating "Walk Scores" or accessibility ratings for specific residential or commercial addresses.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network/stats?lat=42.6970&lon=23.3220&radius_m=300&top_n=10"
```

**Response (JSON Summary):**
```json
{
  "query": { "kind": "radius", "lat": 42.697, "lon": 23.322, "radius_m": 300.0 },
  "reference_point": { "lat": 42.697, "lon": 23.322 },
  "intersecting_stats": {
    "segment_count": 4,
    "region_area_m2": 281307.62,
    "total_length_m_in_region": 78.24,
    "network_density_m_per_km2": 278.14,
    "time": {
      "time_minutes_if_seconds_sum_in_region": 1.30,
      "time_segments_used": 4
    },
    "slope": {
      "mean_abs_slope_weighted": 4.51,
      "length_share_slope_gt_5pct": 0.79
    },
    "groupings": {
      "by_type": [
        { "type": "Локална алея", "count": 1, "length_m": 57.02 },
        { "type": "Пресичане", "count": 2, "length_m": 16.11 },
        { "type": "бул. Княгиня Мария Луиза", "count": 1, "length_m": 5.11 }
      ]
    },
    "nearest_segment": {
      "id": 37,
      "distance_m": 5.12,
      "properties": { "type": "Локална алея", "str_class": "Алея с настилка", "slope_perc": -5.41 }
    }
  },
  "strict_stats": {
    "segment_count": 4,
    "total_length_m_in_region": 78.24
  }
}
```

---

### **Output Structure: Statistical Breakdown**

The radius response is divided into three analytical blocks:

#### **A) Quantitative Connectivity**
*   **`total_length_m_in_region`**: The sum of all walkable path fragments inside the 300m circle (**78.24m**).
*   **`network_density_m_per_km2`**: Represents the intensity of the pedestrian infrastructure. A value of **278.14** suggests this specific area has relatively low pedestrian connectivity compared to dense city centers.
*   **`time_minutes_if_seconds_sum_in_region`**: It would take approx. **1.3 minutes** to walk every visible path fragment in this radius.

#### **B) Accessibility & Terrain Quality**
*   **`mean_abs_slope_weighted`**: The average incline is **4.51%**.
*   **`length_share_slope_gt_5pct`**: A critical metric. **79.4%** of the paths in this radius are steeper than a 5% grade. 
    *   *Interpretation:* This neighborhood may be challenging for wheelchair users or those with limited mobility.

#### **C) Infrastructure Categorization**
*   **`by_type`**: Lists the functional names of the paths. In this area, we see a mix of "Local Alleys," "Crossings," and a fragment of the "Princess Maria Louisa Boulevard."
*   **`by_str_class`**: Shows the physical material. The network is composed of "Paved Alleys," "Underpasses," and "Sidewalks" (`Тротоар`).

---

### **Technical Observations**

1.  **Strict vs Intersecting Convergence:** In this specific example, the `strict_stats` and `intersecting_stats` are identical. This indicates that all 4 segments found happen to be entirely contained within the 300m radius.
2.  **Nearest Segment Context:** The user is standing just **5.12m** away from a "Local Alley" (ID 37). The stats reveal this is the longest segment in the radius (57m), essentially acting as the primary walkable artery for this coordinate.
3.  **Accuracy:** The stats use "clipped" measurements. If a 1000m road passes through the circle, only the 300m (or less) inside the circle is used to calculate the `total_length` and `time`.

---

#### **6) Stats (Radius) - Include Nearest Segment Geometry**

This configuration provides the most complete dataset for location-based pedestrian analysis. By combining aggregated neighborhood statistics with the `include_nearest_geometry=true` parameter, the API returns the macro-level walkability metrics for a 300m radius while embedding the full high-precision GeoJSON geometry for the specific path segment closest to the user.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network/stats?lat=42.6970&lon=23.3220&radius_m=300&include_nearest_geometry=true&top_n=10"
```

**Response (Stats + Embedded Feature):**
```json
{
  "query": { "kind": "radius", "lat": 42.697, "lon": 23.322, "radius_m": 300.0 },
  "intersecting_stats": {
    "total_length_m_in_region": 78.24,
    "network_density_m_per_km2": 278.14,
    "slope": {
      "mean_abs_slope_weighted": 4.51,
      "length_share_slope_gt_5pct": 0.79
    },
    "nearest_segment": {
      "id": 37,
      "distance_m": 5.12,
      "feature": {
        "type": "Feature",
        "geometry": {
          "type": "MultiLineString",
          "coordinates": [[[23.32194, 42.69701], [23.32207, 42.69751]]]
        },
        "properties": { "id": 461, "type": "Локална алея", "slope_perc": -5.41 }
      }
    }
  }
}
```

---

### **Output Structure: Integrated Data Components**

This response is designed to feed both a map visualization and a data dashboard simultaneously:

#### **1. Macro-Level Statistics (`intersecting_stats`)**
*   **`total_length_m_in_region`**: The total walkable meters within the 300m circle (**78.24m**).
*   **`network_density_m_per_km2`**: Standardized density metric (**278.14**). Higher values indicate a "finer grain" of walkable paths.
*   **`length_share_slope_gt_5pct`**: A critical accessibility score (**0.79**). This reveals that **79%** of the paths in this 300m radius are considered steep (over 5% grade).

#### **2. Micro-Level Target Asset (`nearest_segment`)**
*   **`distance_m`**: Proximity from center coordinates to the closest path (**5.12m**).
*   **`feature`**: The full GeoJSON object for the nearest path. 
    *   **Geometry:** Typically a `MultiLineString` or `LineString`.
    *   **Properties:** Includes the specific segment length, slope, and functional type.

---

### **Implementation Context**

*   **Interactive Snap-to-Path:** When a user searches for a location, you can use the `feature` object to draw the nearest sidewalk on the map in a highlighted color, while using the `intersecting_stats` to populate an "Accessibility" badge (e.g., *"Steep Area: 79% slope share"*).
*   **Weighted Slope Logic:** The `mean_abs_slope_weighted` (**4.51%**) ensures that longer paths have a greater impact on the neighborhood's difficulty rating than short ramps or steps.
*   **Time-to-Cover:** The `time_minutes_if_seconds_sum_in_region` (**1.3 min**) allows for "5-minute city" analytics, telling the user how much of the network is reachable within their immediate vicinity.

---

#### **7) Stats (Radius) - Larger Radius**

This query expands the search area to a **600-meter radius**, covering approximately **1.12 square kilometers**. Increasing the radius is essential for understanding the broader urban context, shifting the focus from "immediate doorstep proximity" to "district-level walkability."

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network/stats?lat=42.6970&lon=23.3220&radius_m=600&top_n=10"
```

**Response (JSON Summary):**
```json
{
  "query": { "kind": "radius", "lat": 42.697, "lon": 23.322, "radius_m": 600.0 },
  "region_area_m2": 1125230.49,
  "intersecting_stats": {
    "segment_count": 6,
    "total_length_m_in_region": 106.64,
    "network_density_m_per_km2": 94.77,
    "time": { "time_minutes_if_seconds_sum_in_region": 1.78 },
    "slope": {
      "mean_abs_slope_weighted": 3.86,
      "length_share_slope_gt_5pct": 0.58
    },
    "groupings": {
      "by_type": [
        { "type": "Локална алея", "count": 1, "length_m": 57.02 },
        { "type": "пл. Райко Даскалов", "count": 1, "length_m": 16.39 },
        { "type": "Пресичане", "count": 2, "length_m": 16.11 },
        { "type": "ул. Солунска", "count": 1, "length_m": 12.00 },
        { "type": "бул. Княгиня Мария Луиза", "count": 1, "length_m": 5.11 }
      ]
    }
  },
  "nearest_segment": { "id": 37, "distance_m": 5.12 }
}
```

---

### **Output Structure: District-Wide Metrics**

The properties in this larger radius provide a macro-level view of urban mobility:

*   **`network_density_m_per_km2` (94.77)**: Notice that density dropped significantly compared to the 300m query (**278.14**). This suggests that the core center is highly connected, but as we expand to 600m, we encounter larger blocks or less-mapped peripheral paths, lowering the average connectivity of the district.
*   **`length_share_slope_gt_5pct` (0.58)**: In the 300m view, 79% of paths were steep. In this 600m view, only **58%** are steep. This reveals that the surrounding neighborhood is generally flatter than the immediate area around the reference point.
*   **`time_minutes_if_seconds_sum_in_region` (1.78 min)**: The total traversable time for the fragments in this expanded view.
*   **Functional Diversification (`by_type`)**: We now see new infrastructure appearing, such as segments belonging to **Rayko Daskalov Square** (`пл. Райко Даскалов`) and **Solunska Street** (`ул. Солунска`).

---

### **Analytical Comparison: 300m vs 600m**

| Metric | 300m Radius | 600m Radius | Urban Insight |
| :--- | :--- | :--- | :--- |
| **Area** | ~0.28 km² | ~1.12 km² | 4x larger study area. |
| **Density** | 278 m/km² | 94 m/km² | Pedestrian network "thins out" in the periphery. |
| **Steepness (>5%)** | 79.4% | 58.2% | The immediate center is significantly steeper than the surroundings. |
| **Avg. Slope** | 4.51% | 3.86% | General terrain becomes more accessible as we expand the radius. |

### **Use Case**
*   **District Walkability Profiles:** Municipalities use this to compare different neighborhoods.
*   **Accessibility Planning:** A developer might see that while their specific building sits on a steep slope (300m stats), the wider neighborhood (600m stats) offers flatter, more accessible routes once the user moves away from the immediate center.

---

#### **8) Stats (Radius) - Smaller Radius**

This query focuses on the **immediate 150-meter radius** (approx. a 2-minute walk). It is the most granular analytical mode, designed to evaluate "doorstep accessibility." In dense urban environments, this radius often reveals the highest infrastructure intensity and the most significant terrain challenges for a specific property or entrance.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/pedestrian_network/stats?lat=42.6970&lon=23.3220&radius_m=150&top_n=10"
```

**Response (JSON Summary):**
```json
{
  "query": { "kind": "radius", "lat": 42.697, "lon": 23.322, "radius_m": 150.0 },
  "region_area_m2": 70326.91,
  "intersecting_stats": {
    "segment_count": 2,
    "total_length_m_in_region": 62.13,
    "network_density_m_per_km2": 883.44,
    "time": { "time_minutes_if_seconds_sum_in_region": 1.04 },
    "slope": {
      "mean_abs_slope_weighted": 5.53,
      "length_share_slope_gt_5pct": 1.0
    },
    "groupings": {
      "by_type": [
        { "type": "Локална алея", "count": 1, "length_m": 57.02 },
        { "type": "бул. Княгиня Мария Луиза", "count": 1, "length_m": 5.11 }
      ]
    }
  },
  "nearest_segment": { "id": 37, "distance_m": 5.12 }
}
```

---

### **Output Structure: Hyper-Local Metrics**

The 150m radius response highlights the concentrated nature of the urban center:

*   **`network_density_m_per_km2` (883.44)**: This is significantly higher than the 600m radius (**94.77**). It proves that the pedestrian network is nearly **9 times more connected** at the immediate center than in the wider district.
*   **`length_share_slope_gt_5pct` (1.0)**: A striking metric—**100% of the walkable paths** within 150m are steeper than a 5% grade. 
    *   *Insight:* While the district (600m) seems manageable, the user’s immediate starting point is entirely surrounded by steep terrain.
*   **`mean_abs_slope_weighted` (5.53%)**: The average incline here is above the standard accessibility threshold, identifying this as a "High-Difficulty" start point for wheelchairs.
*   **`segment_count` (2)**: Only two segments define this immediate area: a major alley and a small boulevard fragment.

---

### **Analytical Comparison: The "Distance Decay" of Density**

| Radius | Total Length | Network Density | Accessibility (>5% Slope) |
| :--- | :--- | :--- | :--- |
| **150m** | 62.13m | **883 m/km²** | **100% (Very Steep)** |
| **300m** | 78.24m | 278 m/km² | 79% (Steep) |
| **600m** | 106.64m | 94 m/km² | 58% (Moderate) |

**Conclusion:** As the radius expands, the high-density, steep core of this area in Sofia is diluted by flatter, less connected blocks. 

### **Use Case**
*   **Logistics & Delivery:** Companies can use the 150m stats to estimate "last-meter" delivery difficulty. A 100% steep slope share suggests that heavy deliveries will require more time and effort.
*   **Mobility Apps:** Providing a "Neighborhood Difficulty" rating. A user can be warned that their immediate 2-minute walk is very steep, even if the city center is generally flat.
*   **Urban Greening:** Identifying that only 2 segments exist in 150m might suggest a need for more diverse path routing or pedestrian-only connections in that specific block.

---

### **Input Parameters**

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `bbox` | `string` | Conditional | Bounding box coordinates. |
| `lat` | `float` | Conditional | Latitude of center point. |
| `lon` | `float` | Conditional | Longitude of center point. |
| `radius_m` | `integer` | Conditional | Search radius in meters. |
| `top_n` | `integer` | No | Number of top segment types to return (default: 10). |
| `center_lat` | `float` | No | Reference latitude for nearest segment identification. |
| `center_lon` | `float` | No | Reference longitude for nearest segment identification. |
| `include_nearest_geometry` | `boolean` | No | Include full GeoJSON of nearest segment (default: `false`). |

### **Output Structure**

```json
{
  "query": {
    "kind": "radius" | "bbox",
    "lat": 42.6970,
    "lon": 23.3220,
    "radius_m": 300.0,
    "bbox": [23.32, 42.695, 23.325, 42.6975]
  },
  "region_area_m2": 113945.85,
  "intersecting_stats": {
    "segment_count": 45,
    "total_length_m": 2345.67,
    "total_walking_time_min": 35.2,
    "mean_length_m": 52.13,
    "median_length_m": 48.75,
    "p90_length_m": 78.92,
    "mean_slope_perc": 2.34,
    "median_slope_perc": 1.89,
    "max_slope_perc": 8.45,
    "accessibility_compliance_ratio": 0.82,
    "segment_type_top": [
      {"type": "Тротоар", "count": 18, "total_length_m": 945.6},
      {"type": "Локална алея", "count": 12, "total_length_m": 623.4},
      {"type": "Пресичане", "count": 8, "total_length_m": 156.7}
    ],
    "str_class_top": [
      {"str_class": "Алея с настилка", "count": 25},
      {"str_class": "Тротоар", "count": 15},
      {"str_class": "Подлез", "count": 5}
    ]
  },
  "strict_stats": {
    "segment_count": 32,
    "total_length_m": 1678.43,
    "total_walking_time_min": 25.18,
    "mean_length_m": 52.45,
    "median_length_m": 49.21,
    "p90_length_m": 79.34,
    "mean_slope_perc": 2.28,
    "median_slope_perc": 1.85,
    "max_slope_perc": 7.92,
    "accessibility_compliance_ratio": 0.84
  },
  "nearest_segment": {
    "id": 461,
    "distance_m": 5.2,
    "properties": {
      "id": 461,
      "type": "Локална алея",
      "str_class": "Алея с настилка",
      "segment_le": 56.98,
      "slope_perc": -5.41,
      "minutes": 0.85
    },
    "feature": {  // Only when include_nearest_geometry=true
      "type": "Feature",
      "geometry": { ... },
      "properties": { ... },
      "id": 461
    }
  }
}
```

### **Statistics Metrics**

#### **Intersecting Stats (touching/intersecting boundary):**
*   **`segment_count`**: Number of segments intersecting region.
*   **`total_length_m`**: Total length of intersecting segments.
*   **`total_walking_time_min`**: Estimated total walking time.
*   **`mean/median_length_m`**: Average segment length.
*   **`mean/median_slope_perc`**: Average slope gradient.
*   **`max_slope_perc`**: Maximum slope in region.
*   **`accessibility_compliance_ratio`**: Proportion of ADA/wheelchair-accessible segments.
*   **`segment_type_top`**: Most common segment types with counts and lengths.
*   **`str_class_top`**: Most common physical classifications.

#### **Strict Stats (fully inside region):**
Same metrics as above but for segments completely contained within the region.

#### **Nearest Segment:**
Information about the segment closest to the reference point (bbox centroid or explicit coordinates).

**Notes:**
- **Dual Statistics:** Both intersecting and strict stats are always provided for comprehensive analysis.
- **Accessibility:** Slope metrics help identify wheelchair-accessible routes (typically < 5% slope).
- **Use Cases:** Ideal for pedestrian infrastructure planning, accessibility audits, walkability studies, and route optimization.
- **Clipping Logic:** Statistics are calculated based on clipped linework within the region for accurate length/time estimates.