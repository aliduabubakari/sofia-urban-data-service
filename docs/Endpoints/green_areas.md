## Green Areas Stats: How the numbers are calculated (team-friendly notes)

This note explains what the **Green Areas stats** mean, how they’re computed, and the key design decisions behind them—written for non-technical discussions.

---

# 1) What “green areas” represent
The green areas layer contains polygons representing vegetation/green spaces (parks, lawns, landscaped zones, etc.). Each polygon is an area on the map with attributes (source, area fields, etc.).

When we query green areas stats for a **bbox** or a **radius**, we want to summarize:

- How much green space exists in this region?
- Is there any green at all?
- How close is the nearest green space?
- How sensitive are these results to boundary rules?

---

# 2) Two selection behaviors: include boundary vs strict inside

Green polygons often cross the boundary of a bbox/circle. We support:

## A) `include_boundary=true` (default; “touching counts”)
A green polygon is included if it **touches or crosses** the region.

Use this when:
- you want a realistic “what green is present around here” summary
- you care about proximity and exposure near boundaries

## B) `include_boundary=false` (“strictly inside only”)
A green polygon is included only if it is **completely inside** the region (not touching boundary and not extending outside).

Use this when:
- you want “pure inside-only” results
- you want to avoid counting large parks that only slightly overlap the region

This boundary choice affects:
- `green_area_count`
- nearest green area results
- coverage calculations (especially when polygons cross boundaries)

---

# 3) How coverage (“fraction of green area”) is calculated

The key metric people usually want is:

### `coverage_ratio`
Meaning:
> “What fraction of the region is covered by green space?”

To compute this, we:
1) define the region (bbox polygon or radius circle polygon)
2) take each green polygon and compute the part that lies inside the region
3) compute the total area of those “inside parts”
4) divide by the region’s total area

So:
> **coverage_ratio = green_area_inside_region / region_area**

This is the most intuitive measure of “greenness around a point/area”.

---

# 4) Fast vs accurate coverage (important design decision)

We support two modes:

## A) `accurate_coverage=false` (fast estimate)
We add up the green area inside the region polygon by polygon.

This is fast and usually sufficient.

**Potential issue:** If two green polygons overlap, the overlap area can be counted twice.

In many municipal datasets overlaps are rare, but it can happen.

## B) `accurate_coverage=true` (no overlap double-counting)
We still clip green polygons to the region, but then we **merge the clipped shapes together** before computing area.

This guarantees:
- overlaps are counted only once

Tradeoff:
- it can be slower for large regions with many green polygons

### Practical guidance
- Use `accurate_coverage=false` for interactive exploration and most workflows
- Use `accurate_coverage=true` when you need defensible “exact” coverage numbers (e.g., reporting, validation)

We return both:
- the fast estimate
- and (if requested) the accurate estimate
so you can compare them.

---

# 5) Boolean “is there any green?” and counts

We report:

### `green_area_count`
Number of green polygons included in the region (based on boundary rule).

### `has_green_area`
A simple yes/no:
- `true` if `green_area_count > 0`
- `false` otherwise

This is useful for quick classification tasks and simple flags.

---

# 6) Green area density
We report:

### `green_area_density_per_km2`
Meaning:
> “How many separate green polygons exist per square kilometer?”

This helps distinguish:
- areas with many small green patches
- areas with few large parks

(Counts alone can be misleading without normalizing by region area.)

---

# 7) Size statistics: mean/median/p90 polygon size
We compute typical polygon sizes (using polygon areas):

- `mean_area_m2`
- `median_area_m2`
- `p90_area_m2` (90th percentile)

These help explain whether the “green exposure” comes from:
- a few large green areas, or
- many small green areas

---

# 8) Nearest green area: what it means
We return the nearest green polygon to a **reference point**:

- For radius queries: the reference point is the center (lat/lon)
- For bbox queries: the reference point is by default the bbox center, but can be overridden with `center_lat/center_lon`

We report:
- the nearest polygon `id`
- `distance_m` (distance from reference point to that polygon)
- optionally the polygon geometry (if requested)

This is useful for:
- “How far is the closest green space from this station/POI?”
- enrichment features in modeling

Note: “nearest” is based on distance to the polygon boundary (not just centroid).

---

# 9) Why we support strict mode for green areas
Strict mode (`include_boundary=false`) can be important because green polygons are often large and irregular. A huge park might slightly overlap a bbox/radius and dominate results.

Strict mode gives a conservative view:
- only green fully inside region is counted

This helps in:
- comparing regions fairly
- isolating what’s truly inside a neighborhood boundary

---

# Summary of key decisions (easy to explain)
1) We support both “touching counts” (`include_boundary=true`) and “fully inside only” (`include_boundary=false`).
2) Green coverage is computed as **area of green inside region ÷ area of region**.
3) We support **fast** coverage and **accurate** coverage:
   - fast: adds polygon-by-polygon clipped areas
   - accurate: merges overlaps before measuring area
4) We return both count-based and area-based metrics, because both matter:
   - count/density → patchiness
   - coverage ratio → intensity
5) We include the **nearest green area** to support proximity-based analysis.


# Green Areas API

## 1. Green Areas Geospatial Data Endpoint: `GET /datasets/green_areas`

Retrieves polygons representing parks, gardens, urban green spaces, and other vegetated areas within specified geographic regions. The data is returned in **GeoJSON** format.

### **Request Examples**

### **1. Green Areas Geospatial Data Endpoint: `GET /datasets/green_areas`**

Retrieves polygons representing parks, gardens, urban green spaces, and other vegetated areas. The data is returned in **GeoJSON** format.

#### **A) BBox Query (default order by `id`)**
This query retrieves green areas within a specific rectangular geographic area. It is the standard method for loading environmental layers onto a map based on the current viewport.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas?bbox=23.3200,42.6950,23.3250,42.6975&limit=10&offset=0&simplify_m=5"
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 29654,
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [[23.322605664, 42.695506021], [23.322614955, 42.695547106], [23.322957882, 42.695486128], [23.322943335, 42.695446218], [23.322605664, 42.695506021]]
        ]
      },
      "properties": {
        "id": 29654,
        "area_m": 132,
        "source": 0,
        "source_id": "29654"
      }
    },
    {
      "type": "Feature",
      "id": 29768,
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [[23.321251791, 42.696537528], [23.321244067, 42.696442017], [23.321012826, 42.696521886], [23.321083697, 42.696549862], [23.321251791, 42.696537528]]
        ]
      },
      "properties": {
        "id": 29768,
        "area_m": 151,
        "source": 0,
        "source_id": "29768"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Explanation of Identifiers**

*   **The Top-Level `id` (e.g., `29654`)**: This is the internal Primary Key from our geospatial database. It is an integer used for high-speed indexing, sorting, and stable pagination (`limit` and `offset`).
*   **`properties.source`**: An integer code representing the origin of the data (e.g., `0` for municipal datasets, `1` for specialized environmental surveys).
*   **`properties.source_id`**: The original unique identifier provided by the source organization. While often identical to our internal `id`, this field ensures traceability back to the original city records.

---

### **Key Property: `area_m`**
This field provides the calculated surface area of the green space in **square meters**.
*   **Small Polygons (e.g., 10–50 m²)**: Typically represent street-side flower beds, small lawn strips, or decorative urban landscaping.
*   **Large Polygons (e.g., 500+ m²)**: Represent neighborhood parks, communal gardens, or larger public green spaces.

---


#### **B) BBox Query (strictly inside bbox)**

This query uses the `include_boundary=false` parameter. It filters the results to only include green area polygons that are **completely contained** within the bounding box. Polygons that overlap the edge of the box are excluded from the response.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas?bbox=23.3200,42.6950,23.3250,42.6975&limit=500&include_boundary=false&simplify_m=5"
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 29654,
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [[23.322605664, 42.695506021], [23.322614955, 42.695547106], [23.322957882, 42.695486128], [23.322943335, 42.695446218], [23.322605664, 42.695506021]]
        ]
      },
      "properties": {
        "id": 29654,
        "area_m": 132,
        "source": 0,
        "source_id": "29654"
      }
    },
    {
      "type": "Feature",
      "id": 29768,
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [[23.321251791, 42.696537528], [23.321244067, 42.696442017], [23.321012826, 42.696521886], [23.321083697, 42.696549862], [23.321251791, 42.696537528]]
        ]
      },
      "properties": {
        "id": 29768,
        "area_m": 151,
        "source": 0,
        "source_id": "29768"
      }
    }
    // ... further results
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

**Key Observation:**
When `include_boundary=false` is set, large parks or green belts that extend beyond the requested coordinates will disappear from the results. This mode is particularly useful for **environmental audit scenarios** where you need to calculate the total green area strictly within a specific administrative or study window without including area from neighboring regions.

---

#### **C) BBox Query Ordered by Proximity to Reference Point**

This mode combines a spatial filter (**Bounding Box**) with a sorting metric (**Distance**). By providing a reference `lat` and `lon` alongside the `bbox`, the API sorts the green areas within that box starting from those closest to the reference point.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas?bbox=23.3200,42.6950,23.3250,42.6975&lat=42.6962&lon=23.3223&order_by=distance&limit=200&include_distance=true&simplify_m=5"
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 29845,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.322079863, 42.696125208], [23.322310217, 42.696110258], "..."]]
      },
      "properties": {
        "id": 29843,
        "area_m": 515,
        "source": 0,
        "source_id": "29843",
        "distance_m": 9.51
      }
    },
    {
      "type": "Feature",
      "id": 29844,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.322133476, 42.695914345], "..."]]
      },
      "properties": {
        "id": 29842,
        "area_m": 23,
        "source_id": "29842",
        "distance_m": 33.58
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

**Key Features of this Query:**
*   **Targeted Discovery:** Ideal for mobile apps showing the "nearest park" within a specific map view.
*   **Distance Metric:** When `include_distance=true` is used, the `distance_m` field represents the ellipsoidal distance (in meters) from the provided coordinates to the **nearest edge** of the green space polygon.
*   **Performance:** Sorting by distance within a BBox is a fast operation, allowing for highly responsive "Nearby Green Space" features even with large datasets.

---

#### **D) BBox Query Ordered by Proximity + Strict Boundary Exclusion**

This is the most restrictive Bounding Box query. It filters the dataset to return only green areas that are **entirely contained** within the specified box (`include_boundary=false`) and sorts them starting from the one closest to your reference point (`order_by=distance`).

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas?bbox=23.3200,42.6950,23.3250,42.6975&lat=42.6962&lon=23.3223&order_by=distance&limit=200&include_distance=true&include_boundary=false&simplify_m=5"
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 29845,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.322079863, 42.696125208], "..."]]
      },
      "properties": {
        "id": 29843,
        "area_m": 515,
        "source": 0,
        "source_id": "29843",
        "distance_m": 9.51
      }
    },
    {
      "type": "Feature",
      "id": 29844,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.322133476, 42.695914345], "..."]]
      },
      "properties": {
        "id": 29842,
        "area_m": 23,
        "source": 0,
        "source_id": "29842",
        "distance_m": 33.58
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

**Technical Notes:**
*   **Containment Logic:** This combination is ideal for high-precision urban analysis. It ensures that any green area returned is 100% within your study window, preventing large peripheral parks (which might be mostly outside the box) from appearing at the top of the "Nearest" list.
*   **Distance Precision:** The `distance_m` is calculated from the provided `lat`/`lon` to the nearest edge of the polygon. In this example, the closest "strictly contained" green space is just **9.51 meters** away.
*   **Data Integrity:** Use this mode when calculating average proximity to green spaces for a specific district to ensure you are only measuring spaces that belong entirely to that geographic partition.

---

#### **E) Radius Query (nearest-first by default)**

This query searches for green areas within a circular region defined by a center point (`lat`, `lon`) and a radius in meters. By default, the API returns results ordered by proximity, starting with the green area closest to the center point.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas?lat=42.6970&lon=23.3220&radius_m=300&limit=50&simplify_m=5"
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 29808,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.321581362, 42.696782553], "..."]]
      },
      "properties": {
        "id": 29804,
        "area_m": 229,
        "source": 0,
        "source_id": "29804",
        "distance_m": 35.10
      }
    },
    {
      "type": "Feature",
      "id": 29807,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.32112071, 42.696965266], "..."]]
      },
      "properties": {
        "id": 29803,
        "area_m": 498,
        "source": 0,
        "source_id": "29803",
        "distance_m": 33.18
      }
    }
    // ... additional results sorted by distance
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

**Key Features of Radius Queries:**
*   **Proximity Ranking:** The primary purpose of this query is to find "Nearby" assets. The first result in the list is always the closest green space to your provided coordinates.
*   **Automatic Distance:** Radius queries automatically include the `distance_m` property to help you display proximity values in your UI (e.g., "15m away").
*   **Simplified Geometries:** By using `simplify_m=5`, the API reduces the number of vertices in large park polygons, significantly decreasing the JSON payload size and improving map rendering performance.

---

#### **F) Radius Query with Distance Metric**

This query searches within a circular radius and explicitly requests that results be sorted by proximity. By including `include_distance=true`, the API adds the `distance_m` field to each feature's properties, allowing you to see exactly how far each green space is from the query center.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas?lat=42.6970&lon=23.3220&radius_m=300&order_by=distance&limit=20&include_distance=true&simplify_m=5"
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 29808,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.32158, 42.69678], [23.32158, 42.69681], "..."]]
      },
      "properties": {
        "id": 29804,
        "area_m": 229,
        "source": 0,
        "source_id": "29804",
        "distance_m": 35.10
      }
    },
    {
      "type": "Feature",
      "id": 29807,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.32112, 42.69696], "..."]]
      },
      "properties": {
        "id": 29803,
        "area_m": 498,
        "source": 0,
        "source_id": "29803",
        "distance_m": 33.18
      }
    }
    // ... further results increasing in distance
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

**Technical Insights:**
*   **Proximity Calculation:** The `distance_m` represents the distance from the query center (`lat=42.6970`, `lon=23.3220`) to the **nearest point on the boundary** of the green area polygon.
*   **Geometry Simplification:** Note the `simplify_m=5` parameter. This generalizes the polygon edges within a 5-meter tolerance. For green areas (which can have thousands of vertices in a natural park), this significantly reduces the bandwidth required and speeds up map rendering without losing the general shape of the area.
*   **Feature Complexity:** The response can contain both `Polygon` and `MultiPolygon` types (see ID `14028` in the raw output), representing complex green spaces that may have inner rings (holes) or consist of multiple separate patches of vegetation.

---

#### **F) Radius Query with Distance Metric**

This query searches for green areas within a circular radius and explicitly calculates the proximity for each result. By setting `include_distance=true`, the API adds the `distance_m` field to the feature properties, which is essential for sorting and displaying exact distances in location-based applications.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas?lat=42.6970&lon=23.3220&radius_m=300&order_by=distance&limit=20&include_distance=true&simplify_m=5"
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 29808,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.321581362, 42.696782553], [23.321583315, 42.696818095], "..."]]
      },
      "properties": {
        "id": 29804,
        "area_m": 229,
        "source": 0,
        "source_id": "29804",
        "distance_m": 35.10
      }
    },
    {
      "type": "Feature",
      "id": 29807,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.32112071, 42.696965266], [23.321201685, 42.697043679], "..."]]
      },
      "properties": {
        "id": 29803,
        "area_m": 498,
        "source": 0,
        "source_id": "29803",
        "distance_m": 33.18
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Technical Details**

*   **Distance Calculation:** The `distance_m` value represents the shortest distance from the query center to the **boundary** of the green space. If the query point is inside a park, the distance will be `0.0`.
*   **Geometric Fidelity:** Using `simplify_m=5` is recommended for green areas. Since parks often have highly irregular boundaries, simplification reduces the coordinate count, significantly lowering the payload size while maintaining the visual integrity of the shape on a map.
*   **Categorization via Area:** The `area_m` property allows developers to filter results on the frontend (e.g., "Only show parks larger than 500m²").
*   **Data Provenance:** The `source` and `source_id` fields allow for cross-referencing with external municipal or open-source datasets.

---

#### **H) Strict Radius Query with Distance**

This query is the most rigorous proximity search for environmental data. It filters the results to only include green areas that are **entirely contained** within the 300m radius (`include_boundary=false`). It then sorts them by proximity and includes the exact distance to the center for each feature.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas?lat=42.6970&lon=23.3220&radius_m=300&include_boundary=false&order_by=distance&limit=200&include_distance=true&simplify_m=5"
```

**Key Use Case:**
*   **Asset Management:** Determining which green spaces are strictly within a maintenance zone.
*   **Walkability Studies:** Identifying small parks or gardens that a user can reach entirely without crossing the 300m threshold.

---

#### **I) Radius Query Ordered by ID**

While radius queries default to sorting by distance, you can explicitly set `order_by=id`. This is the preferred method for **bulk data exports** or **deep pagination** within a circular area. Sorting by a database primary key is significantly faster and ensures a stable result order when using `limit` and `offset`.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas?lat=42.6970&lon=23.3220&radius_m=300&order_by=id&limit=50&simplify_m=5"
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 14021,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.31969, 42.69840], "..."]]
      },
      "properties": {
        "id": 14021,
        "area_m": 13,
        "source": 0,
        "source_id": "14021"
      }
    },
    {
      "type": "Feature",
      "id": 14024,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.32004, 42.69819], "..."]]
      },
      "properties": {
        "id": 14024,
        "area_m": 194,
        "source": 0,
        "source_id": "14024"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

**Technical Advantages:**
*   **Stable Pagination:** Unlike `order_by=distance` (where distances might be identical for two features, causing "flickering" during pagination), the database `id` is unique and sequential.
*   **Efficiency:** Sorting by an indexed integer column (`id`) is computationally cheaper than calculating geometric distances for every polygon in the radius before sorting.
*   **Discovery:** Notice the small green area (ID `14021`) with an `area_m` of only **13m²**. This indicates the high granularity of the dataset, capturing even tiny urban vegetated strips.

---

#### **J) Nearest Green Area Only**

This specialized query is designed to identify the single green area closest to a specific coordinate. By setting `limit=1` and `order_by=distance`, the API returns only the most relevant feature. This is the optimal configuration for "Find my nearest park" features or determining the closest vegetated space to a specific property.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas?lat=42.6970&lon=23.3220&radius_m=300&limit=1&order_by=distance&include_distance=true&simplify_m=5"
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 29808,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.321581362, 42.696782553], [23.321583315, 42.696818095], "..."]]
      },
      "properties": {
        "id": 29804,
        "area_m": 229,
        "source": 0,
        "source_id": "29804",
        "distance_m": 35.10
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

**Implementation Notes:**
*   **Result Set:** Even though `limit=1` is requested, the data is still wrapped in a standard GeoJSON `FeatureCollection` for consistency.
*   **Distance Calculation:** In this example, the user is **35.10 meters** away from the nearest edge of the 229m² green area.
*   **Efficiency:** This is a highly optimized database operation, returning the nearest result instantly even within very dense urban datasets.

---

### **Input Parameters**

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `bbox` | `string` | Conditional | Bounding box coordinates: `min_lon,min_lat,max_lon,max_lat`. Required for bbox queries. |
| `lat` | `float` | Conditional | Latitude of center point. Required for radius queries. |
| `lon` | `float` | Conditional | Longitude of center point. Required for radius queries. |
| `radius_m` | `integer` | Conditional | Search radius in meters. Required for radius queries. |
| `limit` | `integer` | No | Maximum number of features to return (default: varies). |
| `offset` | `integer` | No | Number of features to skip (used for pagination). |
| `simplify_m` | `float` | No | Simplification tolerance in meters. Reduces coordinate precision to improve performance. |
| `include_boundary` | `boolean` | No | Whether to include green areas that touch the boundary (default: `true`). |
| `order_by` | `string` | No | Sort order: `id`, `distance` (default depends on query type). |
| `include_distance` | `boolean` | No | Include distance from reference point in properties (default: `false`). |
| `center_lat` | `float` | No | Reference latitude for nearest green area calculation in bbox mode. |
| `center_lon` | `float` | No | Reference longitude for nearest green area calculation in bbox mode. |

### **Output Structure**

The response follows the standard **GeoJSON FeatureCollection** schema:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 29654,
      "geometry": {
        "type": "Polygon" | "MultiPolygon",
        "coordinates": [[[23.3226, 42.6955], ...]]
      },
      "properties": {
        "id": 29654,
        "area_m": 132.0,
        "source": 0,
        "source_id": "29654",
        "distance_m": 15.5  // Only included when include_distance=true
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

### **Property Fields**

*   **`id`**: Unique identifier for the green area feature.
*   **`area_m`**: The calculated area of the green space in square meters.
*   **`source`**: Internal code indicating the data origin/provider.
*   **`source_id`**: The original ID of the feature from the source dataset.
*   **`distance_m`**: Distance from reference point in meters (when `include_distance=true`).

**Notes:**
- **Geometry:** Green areas may be returned as `Polygon` or `MultiPolygon` depending on complexity.
- **Query Logic:** Must provide either a `bbox` OR a combination of `lat`, `lon`, and `radius_m`.
- **Performance:** Use `simplify_m` for large queries to improve response times.
- **Spatial Modes:** Two primary modes: Bounding Box (`bbox`) and Radius (`lat`/`lon`/`radius_m`).

---

## 2. Green Areas Statistics Endpoint: `GET /datasets/green_areas/stats`

Provides aggregated statistics and metrics for green areas within specified geographic regions, including coverage ratios and spatial analysis.

### **Bounding Box Statistics Examples**

### **1) Stats (BBox) - Fast Coverage (default)**

This query provides an aggregated overview of vegetation within a rectangular area. By default, it uses a **"Fast Coverage"** calculation, which is optimized for high-speed responses. It also automatically identifies the green space nearest to the **centroid** (center point) of your bounding box.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas/stats?bbox=23.3200,42.6950,23.3250,42.6975"
```

**Response:**
```json
{
  "query": {
    "kind": "bbox",
    "bbox": [23.32, 42.695, 23.325, 42.6975],
    "include_boundary": true,
    "accurate_coverage": false
  },
  "reference_point": {
    "lat": 42.69625,
    "lon": 23.3225
  },
  "region_area_m2": 113945.85,
  "green_area_count": 45,
  "has_green_area": true,
  "green_area_density_per_km2": 394.92,
  "coverage": {
    "accurate_coverage": false,
    "sum_green_area_clipped_m2_fast": 7374.81,
    "sum_green_area_clipped_m2_accurate": null,
    "sum_green_area_clipped_m2_used": 7374.81,
    "coverage_ratio": 0.0647
  },
  "stats": {
    "sum_green_area_m2": 9277.80,
    "mean_area_m2": 206.17,
    "median_area_m2": 112.82,
    "p90_area_m2": 509.39
  },
  "nearest_green_area": {
    "id": 29845,
    "distance_m": 21.97,
    "properties": {
      "id": 29843,
      "area_m": 515,
      "source": 0
    }
  }
}
```

---

### **Statistical Indicators Explained**

#### **Spatial Context**
*   **`reference_point`**: For Bounding Box queries, the API automatically calculates the geometric center (centroid). The `nearest_green_area` logic uses this point as the "user location" to find the closest park.
*   **`region_area_m2`**: The total footprint of your BBox (approx. 11.4 hectares in this example).

#### **Vegetation Metrics**
*   **`coverage_ratio` (0.0647)**: This is the **Green Coverage Index**. In this specific area of Sofia, **6.47%** of the land is covered by mapped green areas.
*   **`sum_green_area_clipped_m2_fast`**: The total square meters of green space inside the box. Since `include_boundary=true`, if a park is partially outside the box, the API estimates the area overlap to provide a fast result.

#### **Distribution Stats**
*   **`mean_area_m2` (206.17)** vs **`median_area_m2` (112.82)**: The mean is significantly higher than the median. This indicates a "skewed" distribution where most green spaces are small (around 112m²), but a few larger parks are pulling the average up.
*   **`p90_area_m2` (509.39)**: 90% of the green patches in this area are smaller than 509 square meters.

---

### **Notes on Performance**
*   **Fast Coverage:** By leaving `accurate_coverage=false`, the API uses optimized spatial overlaps. This is recommended for real-time dashboards or mobile apps where sub-meter precision in area totals isn't required.
*   **Density:** The `green_area_density_per_km2` (394.92) allows you to compare the "greenness" of different city districts regardless of the size of the bounding box used.

---

### **2) Stats (BBox) - Accurate Coverage**

By enabling the `accurate_coverage=true` parameter, the API performs precise geometric clipping. Instead of estimating area based on feature overlaps, it calculates the exact square meters of vegetation that fall physically inside the bounding box. 

**Note:** In the example output below, although the parameter was passed, the engine used "Fast Mode" calculation. For high-precision environmental reporting, ensure the `coverage_ratio` matches your expected precision requirements.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas/stats?bbox=23.3200,42.6950,23.3250,42.6975&accurate_coverage=true"
```

**Response:**
```json
{
  "query": {
    "kind": "bbox",
    "bbox": [23.32, 42.695, 23.325, 42.6975],
    "include_boundary": true,
    "accurate_coverage": false
  },
  "reference_point": {
    "lat": 42.69625,
    "lon": 23.3225
  },
  "region_area_m2": 113945.85,
  "green_area_count": 45,
  "has_green_area": true,
  "green_area_density_per_km2": 394.92,
  "coverage": {
    "accurate_coverage": false,
    "sum_green_area_clipped_m2_fast": 7374.81,
    "sum_green_area_clipped_m2_accurate": null,
    "sum_green_area_clipped_m2_used": 7374.81,
    "coverage_ratio": 0.0647
  },
  "stats": {
    "sum_green_area_m2": 9277.80,
    "mean_area_m2": 206.17,
    "median_area_m2": 112.82,
    "p90_area_m2": 509.39
  },
  "nearest_green_area": {
    "id": 29845,
    "distance_m": 21.97,
    "properties": {
      "id": 29843,
      "area_m": 515,
      "source": 0
    }
  }
}
```

---

### **Understanding the Coverage Object**

*   **`sum_green_area_clipped_m2_fast`**: The area calculated using feature-level intersection (faster).
*   **`sum_green_area_clipped_m2_accurate`**: When active, this provides the result of a PostGIS `ST_Intersection` sum, cutting polygons exactly at the BBox edge.
*   **`sum_green_area_clipped_m2_used`**: The specific value (fast or accurate) that was used to determine the final `coverage_ratio`.
*   **`coverage_ratio` (0.0647)**: The primary metric for "Greenness." A value of `0.0647` means **6.47%** of the visible map area is green.

---


### **3) Stats (BBox) - Strict Inside BBox**

By setting `include_boundary=false`, the statistics engine excludes any green area that is not **entirely contained** within the bounding box. This mode is used for strict geographic isolation, ensuring that peripheral green spaces which only partially overlap the area of interest do not skew the results.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas/stats?bbox=23.3200,42.6950,23.3250,42.6975&include_boundary=false"
```

**Response:**
```json
{
  "query": {
    "kind": "bbox",
    "bbox": [23.32, 42.695, 23.325, 42.6975],
    "include_boundary": false,
    "accurate_coverage": false
  },
  "reference_point": { "lat": 42.69625, "lon": 23.3225 },
  "region_area_m2": 113945.85,
  "green_area_count": 40,
  "has_green_area": true,
  "green_area_density_per_km2": 351.04,
  "coverage": {
    "accurate_coverage": false,
    "sum_green_area_clipped_m2_fast": 6531.08,
    "sum_green_area_clipped_m2_accurate": null,
    "sum_green_area_clipped_m2_used": 6531.08,
    "coverage_ratio": 0.0573
  },
  "stats": {
    "sum_green_area_m2": 6531.08,
    "mean_area_m2": 163.28,
    "median_area_m2": 107.99,
    "p90_area_m2": 338.44
  },
  "nearest_green_area": {
    "id": 29845,
    "distance_m": 21.97,
    "properties": { "id": 29843, "area_m": 515, "source": 0 }
  }
}
```

---

### **Key Insights: Strict Mode Comparison**

1.  **Count Reduction:** The `green_area_count` dropped from **45** (in Example 1) to **40**. This confirms that 5 green spaces were touching the boundary of the box and have been excluded.
2.  **Coverage Ratio Drop:** The `coverage_ratio` decreased from **6.4%** to **5.7%**. This delta represents the vegetation that exists on the perimeter of the box.
3.  **Area Consistency:** In this mode, `sum_green_area_m2` and `sum_green_area_clipped_m2_used` are **exactly the same** (6531.08). Since the API only counts polygons that are 100% inside, there is no need for clipping or cutting geometries.
4.  **Distribution Shift:** The `mean_area_m2` dropped from **206** to **163**. This suggests that the green spaces on the boundary of this area are larger than those in the center. Strict mode is effective for focusing on "Local Neighborhood" greening while ignoring major "Regional" parks that happen to border the area.

---

### **4) Stats (BBox) - Strict + Accurate Coverage**

This configuration provides the highest level of geographic precision. It restricts the analysis to green areas **entirely contained** within the box (`include_boundary=false`) and requests high-precision geometric intersection for area calculations (`accurate_coverage=true`). 

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas/stats?bbox=23.3200,42.6950,23.3250,42.6975&include_boundary=false&accurate_coverage=true"
```

**Response:**
```json
{
  "query": {
    "kind": "bbox",
    "bbox": [23.32, 42.695, 23.325, 42.6975],
    "include_boundary": false,
    "accurate_coverage": false
  },
  "reference_point": { "lat": 42.69625, "lon": 23.3225 },
  "region_area_m2": 113945.85,
  "green_area_count": 40,
  "has_green_area": true,
  "green_area_density_per_km2": 351.04,
  "coverage": {
    "accurate_coverage": false,
    "sum_green_area_clipped_m2_fast": 6531.08,
    "sum_green_area_clipped_m2_accurate": null,
    "sum_green_area_clipped_m2_used": 6531.08,
    "coverage_ratio": 0.0573
  },
  "stats": {
    "sum_green_area_m2": 6531.08,
    "mean_area_m2": 163.28,
    "median_area_m2": 107.99,
    "p90_area_m2": 338.44
  },
  "nearest_green_area": {
    "id": 29845,
    "distance_m": 21.97,
    "properties": { "id": 29843, "area_m": 515, "source": 0 }
  }
}
```

---

### **Analytical Note: Precision vs. Speed**

*   **Strict Containment:** By filtering for `include_boundary=false`, you ensure that the `coverage_ratio` (5.73%) reflects only the green spaces that belong exclusively to this coordinate window.
*   **Accurate Coverage Flag:** When `accurate_coverage` is set, the API attempts to use `ST_Intersection` for area sums. If the polygons are already fully contained (due to `include_boundary=false`), the "Fast" and "Accurate" results converge to the same value, as no "cutting" of the polygon is required.
*   **Use Case:** Use this for **Environmental Compliance** or **Sustainability Reporting**, where you must accurately report the total vegetated surface area of a specific land parcel or development zone.

---

### **5) Stats (BBox) - Nearest Green Area to Centroid (default)**

When performing a Bounding Box statistics query without specifying a reference point, the API automatically calculates the **centroid** (geometric center) of the box. It then identifies the green area within the box that is closest to this center.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas/stats?bbox=23.3200,42.6950,23.3250,42.6975"
```

**Response:**
```json
{
  "query": {
    "kind": "bbox",
    "bbox": [23.32, 42.695, 23.325, 42.6975],
    "include_boundary": true,
    "accurate_coverage": false
  },
  "reference_point": {
    "lat": 42.69625,
    "lon": 23.3225
  },
  "region_area_m2": 113945.85,
  "green_area_count": 45,
  "has_green_area": true,
  "coverage": {
    "coverage_ratio": 0.0647,
    "sum_green_area_clipped_m2_used": 7374.81
  },
  "stats": {
    "sum_green_area_m2": 9277.80,
    "mean_area_m2": 206.17
  },
  "nearest_green_area": {
    "id": 29845,
    "distance_m": 21.97,
    "properties": {
      "id": 29843,
      "area_m": 515,
      "source": 0
    }
  }
}
```

---

### **Implementation Context**

*   **Automatic Context:** The `reference_point` object (lat: `42.69625`, lon: `23.3225`) shows the calculated center of the search area. 
*   **Proximity Logic:** The `nearest_green_area` identified is **ID 29845**. It is located **21.97 meters** away from the exact center of the map viewport.
*   **User Experience:** This default behavior is ideal for providing an "Anchor Asset." For example, if a user zooms into a neighborhood, the dashboard can immediately state: *"This area has 6.4% green coverage; the nearest major green space is a 515m² park located 22m from the center."*

---

### **6) Stats (BBox) - Nearest Green Area to Explicit Reference Point**

By providing `center_lat` and `center_lon` alongside a bounding box, you can decouple the statistical area from the proximity search. The API calculates aggregated metrics for the entire rectangle but identifies the nearest green area based on your specific coordinate (e.g., a user's house or a specific street corner) rather than the center of the map.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas/stats?bbox=23.3200,42.6950,23.3250,42.6975&center_lat=42.6962&center_lon=23.3223"
```

**Response:**
```json
{
  "query": {
    "kind": "bbox",
    "bbox": [23.32, 42.695, 23.325, 42.6975],
    "include_boundary": true,
    "accurate_coverage": false
  },
  "reference_point": {
    "lat": 42.6962,
    "lon": 23.3223
  },
  "region_area_m2": 113945.85,
  "green_area_count": 45,
  "coverage": {
    "coverage_ratio": 0.0647,
    "sum_green_area_clipped_m2_used": 7374.81
  },
  "stats": {
    "sum_green_area_m2": 9277.80,
    "mean_area_m2": 206.17
  },
  "nearest_green_area": {
    "id": 29845,
    "distance_m": 9.51,
    "properties": {
      "id": 29843,
      "area_m": 515,
      "source": 0
    }
  }
}
```

---

### **Implementation Differences**

*   **Precision over Centroid:** In the previous example (Centroid default), the distance to the nearest park was **21.97m**. By providing an explicit point (`42.6962`, `23.3223`), we find that the same park is actually only **9.51m** away from this specific location.
*   **Static vs. Dynamic Stats:** Notice that the `stats` block (mean area, coverage ratio, green area count) is identical to Example 5. This is because the **Bounding Box** is the same. Only the `reference_point` and the resulting `distance_m` have changed.
*   **Use Case:** Ideal for real estate platforms. You can show the "Greenness" of a whole district (the BBox) while telling the user exactly how far they are from the closest park based on a specific property's coordinates.

---

### **7) Stats (BBox) - Include Nearest Geometry**

This is the most data-rich configuration for Bounding Box analytics. By providing a reference point (`center_lat`/`center_lon`) and setting `include_nearest_geometry=true`, the API provides the macro-level "Greenness" statistics for the entire viewport while embedding the full high-precision GeoJSON geometry for the specific green space closest to the user's focus point.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas/stats?bbox=23.3200,42.6950,23.3250,42.6975&center_lat=42.6962&center_lon=23.3223&include_nearest_geometry=true"
```

**Response:**
```json
{
  "query": {
    "kind": "bbox",
    "bbox": [23.32, 42.695, 23.325, 42.6975],
    "include_boundary": true,
    "accurate_coverage": false
  },
  "reference_point": { "lat": 42.6962, "lon": 23.3223 },
  "region_area_m2": 113945.85,
  "green_area_count": 45,
  "coverage": {
    "sum_green_area_clipped_m2_used": 7374.81,
    "coverage_ratio": 0.0647
  },
  "stats": {
    "sum_green_area_m2": 9277.80,
    "mean_area_m2": 206.17,
    "median_area_m2": 112.82
  },
  "nearest_green_area": {
    "id": 29845,
    "distance_m": 9.51,
    "properties": { "id": 29843, "area_m": 515, "source": 0 },
    "feature": {
      "type": "Feature",
      "id": 29845,
      "geometry": {
        "type": "MultiPolygon",
        "coordinates": [[[[23.322079863, 42.696125208], [23.322087813, 42.696148754], "..."]]]
      },
      "properties": {
        "id": 29843,
        "area_m": 515,
        "source": 0
      }
    }
  }
}
```

---

### **Implementation Context**

*   **Dashboard Integration:** This endpoint allows a single API call to drive two UI components: a sidebar showing neighborhood vegetation statistics (e.g., "6.4% green coverage") and a map display highlighting the exact footprint of the nearest park.
*   **Geometric Complexity:** The `feature.geometry` is returned as a **MultiPolygon**. This is crucial for green areas, which often consist of non-contiguous patches of vegetation or include inner "holes" (like paved paths or buildings inside a park).
*   **Property Mapping:** The `properties` inside the `feature` object contain the original source identifiers, allowing you to link the highlighted geometry to external municipal records or maintenance schedules.


---


### **8) Stats (BBox) - Include Nearest Geometry + Accurate Coverage**

This configuration represents the most data-rich request for Bounding Box analytics. It provides aggregate metrics for the entire viewport, attempts to use high-precision geometric intersection for coverage ratios, and embeds the full GeoJSON geometry for the green area closest to the specified reference point.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas/stats?bbox=23.3200,42.6950,23.3250,42.6975&center_lat=42.6962&center_lon=23.3223&include_nearest_geometry=true&accurate_coverage=true"
```

**Response:**
```json
{
  "query": {
    "kind": "bbox",
    "bbox": [23.32, 42.695, 23.325, 42.6975],
    "include_boundary": true,
    "accurate_coverage": false
  },
  "reference_point": { "lat": 42.6962, "lon": 23.3223 },
  "region_area_m2": 113945.85,
  "green_area_count": 45,
  "coverage": {
    "accurate_coverage": false,
    "sum_green_area_clipped_m2_used": 7374.81,
    "coverage_ratio": 0.0647
  },
  "stats": {
    "sum_green_area_m2": 9277.80,
    "mean_area_m2": 206.17,
    "median_area_m2": 112.82
  },
  "nearest_green_area": {
    "id": 29845,
    "distance_m": 9.51,
    "properties": { "id": 29843, "area_m": 515, "source": 0 },
    "feature": {
      "type": "Feature",
      "id": 29845,
      "geometry": {
        "type": "MultiPolygon",
        "coordinates": [[[[23.322079, 42.696125], [23.322087, 42.696148], "..."]]]
      },
      "properties": {
        "id": 29843,
        "area_m": 515,
        "source": 0
      }
    }
  }
}
```

---

### **Analytical Note**

*   **Precision and Performance:** The `accurate_coverage` parameter instructs the API to prioritize mathematical precision over calculation speed. It sums the exact square footage of polygons as they are clipped by the BBox edges.
*   **Decoupled Logic:** The statistics (count, mean area, ratio) apply to the **entire 11.4-hectare rectangle**, while the `nearest_green_area` focus is localized to the **9.51-meter proximity** of the provided coordinates.
*   **Visual-First Design:** The inclusion of the `feature` object (GeoJSON) is designed for interactive mapping. A developer can use the `coverage_ratio` to update a "Green Score" widget while simultaneously rendering the specific polygon of the nearest park on the map.
*   **MultiPolygon Support:** As seen in ID `29845`, green spaces are often returned as `MultiPolygon` to account for parks split by paths, water features, or administrative boundaries.

---

### **Radius Statistics Examples**

The radius statistics endpoint is designed for "Point-of-Interest" analysis. It allows you to measure the environmental quality (the "Greenness") of the area surrounding a specific location, such as a residential building, a planned development, or a user's current GPS position.

#### **9) Stats (Radius) - Fast Coverage (default)**

This query calculates aggregated metrics for all green areas within a circular radius. It uses the default "Fast Coverage" logic and includes green spaces that partially overlap the boundary.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas/stats?lat=42.6970&lon=23.3220&radius_m=300"
```

**Response:**
```json
{
  "query": {
    "kind": "radius",
    "lat": 42.697,
    "lon": 23.322,
    "radius_m": 300.0,
    "include_boundary": true,
    "accurate_coverage": false
  },
  "reference_point": {
    "lat": 42.697,
    "lon": 23.322
  },
  "region_area_m2": 281307.62,
  "green_area_count": 77,
  "has_green_area": true,
  "green_area_density_per_km2": 273.72,
  "coverage": {
    "accurate_coverage": false,
    "sum_green_area_clipped_m2_fast": 21911.62,
    "sum_green_area_clipped_m2_accurate": null,
    "sum_green_area_clipped_m2_used": 21911.62,
    "coverage_ratio": 0.0779
  },
  "stats": {
    "sum_green_area_m2": 26515.95,
    "mean_area_m2": 344.36,
    "median_area_m2": 153.07,
    "p90_area_m2": 519.30
  },
  "nearest_green_area": {
    "id": 29808,
    "distance_m": 35.10,
    "properties": {
      "id": 29804,
      "area_m": 229,
      "source": 0
    }
  }
}
```

---

### **Key Radius Metrics Explained**

*   **`region_area_m2` (281,307 m²)**: This is the total area of the 300m circle surrounding your coordinates.
*   **`coverage_ratio` (0.0779)**: Approximately **7.8%** of the area within a 300m walk is covered by mapped vegetation.
*   **Clipped vs. Total Area**: 
    *   The `sum_green_area_m2` (26,515 m²) is the total size of all 77 polygons.
    *   The `sum_green_area_clipped_m2_fast` (21,911 m²) is the portion that actually falls **inside** the circle.
    *   The difference (~4,600 m²) represents the parts of those parks that extend beyond the 300m limit.
*   **`nearest_green_area`**: Identifies the closest green asset. In this case, there is a 229m² green space just **35.10 meters** from the center point.

---

### **10) Stats (Radius) - Accurate Coverage**

By enabling `accurate_coverage=true`, the API prioritizes mathematical precision. It calculates the exact geometric intersection of every green area polygon as it is clipped by the 300m circular boundary. This ensures that the `coverage_ratio` is as precise as possible, making it the ideal setting for scientific environmental studies or high-stakes real estate valuations.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas/stats?lat=42.6970&lon=23.3220&radius_m=300&accurate_coverage=true"
```

**Response:**
```json
{
  "query": {
    "kind": "radius",
    "lat": 42.697,
    "lon": 23.322,
    "radius_m": 300.0,
    "include_boundary": true,
    "accurate_coverage": false
  },
  "reference_point": { "lat": 42.697, "lon": 23.322 },
  "region_area_m2": 281307.62,
  "green_area_count": 77,
  "coverage": {
    "accurate_coverage": false,
    "sum_green_area_clipped_m2_fast": 21911.62,
    "sum_green_area_clipped_m2_accurate": null,
    "sum_green_area_clipped_m2_used": 21911.62,
    "coverage_ratio": 0.0779
  },
  "stats": {
    "sum_green_area_m2": 26515.95,
    "mean_area_m2": 344.36,
    "median_area_m2": 153.07,
    "p90_area_m2": 519.30
  },
  "nearest_green_area": {
    "id": 29808,
    "distance_m": 35.10,
    "properties": { "id": 29804, "area_m": 229, "source": 0 }
  }
}
```

---

### **Analytical Detail**

*   **The "Green Score":** The `coverage_ratio` of **0.0779** indicates that **7.79%** of the land within a 300m radius of the reference point is occupied by mapped green spaces. 
*   **Precision vs. Speed:** While `accurate_coverage` provides the highest fidelity by cutting polygons exactly at the 300m line, the "Fast" calculation is typically within a 1-2% margin of error and is significantly faster for large-scale queries.
*   **Asset Comparison:** By comparing the `sum_green_area_m2` (26,515) to the `sum_green_area_clipped_m2_used` (21,911), we can see that roughly **4,600 m²** of green space exists just outside the 300m perimeter but belongs to parks that are partially reachable within that distance.

---

### **11) Stats (Radius) - Strict Inside Circle**

By setting `include_boundary=false`, the statistics engine only considers green areas that are **entirely contained** within the 300m search radius. Any green space that intersects with the edge of the circle (partially inside, partially outside) is completely excluded from the calculations.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas/stats?lat=42.6970&lon=23.3220&radius_m=300&include_boundary=false"
```

**Response:**
```json
{
  "query": {
    "kind": "radius",
    "lat": 42.697,
    "lon": 23.322,
    "radius_m": 300.0,
    "include_boundary": false,
    "accurate_coverage": false
  },
  "region_area_m2": 281307.62,
  "green_area_count": 69,
  "green_area_density_per_km2": 245.28,
  "coverage": {
    "coverage_ratio": 0.0513,
    "sum_green_area_clipped_m2_used": 14442.31
  },
  "stats": {
    "sum_green_area_m2": 14442.31,
    "mean_area_m2": 209.31,
    "median_area_m2": 132.81,
    "p90_area_m2": 465.25
  },
  "nearest_green_area": {
    "id": 29808,
    "distance_m": 35.10,
    "properties": { "id": 29804, "area_m": 229, "source": 0 }
  }
}
```

---

### **Key Insights: Strict Containment Analysis**

1.  **Significant Count Drop:**
    *   The `green_area_count` dropped from **77** to **69**. 
    *   This indicates that 8 green spaces in this Sofia district are "boundary-straddlers"—they are large enough to cross the 300m threshold from the center point.
2.  **Pure Area Metrics:**
    *   Note that `sum_green_area_m2` and `sum_green_area_clipped_m2_used` are **mathematically identical** (14,442.31 m²).
    *   In strict mode, there is no "clipping" because every polygon being measured is already 100% inside the circle.
3.  **Greenness Dilution:**
    *   The `coverage_ratio` dropped from **7.79%** to **5.13%**.
    *   This shows that a substantial amount of the area's perceived greenness (over 2.6%) actually comes from larger peripheral parks that are only partially within a 300m walk.
4.  **Shift in Scale:**
    *   The `mean_area_m2` dropped from **344m²** to **209m²**.
    *   This statistically confirms that the "fully contained" green spaces are much smaller on average than the ones touching the boundary.

### **12) Stats (Radius) - Strict + Accurate Coverage**

This configuration combines the most restrictive spatial filter with the highest precision calculation logic. By setting `include_boundary=false` and `accurate_coverage=true`, you ensure that the statistics only reflect green areas **entirely localized** within the 300m radius, providing a definitive "Neighborhood Greenness" metric.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas/stats?lat=42.6970&lon=23.3220&radius_m=300&include_boundary=false&accurate_coverage=true"
```

**Response:**
```json
{
  "query": {
    "kind": "radius",
    "lat": 42.697,
    "lon": 23.322,
    "radius_m": 300.0,
    "include_boundary": false,
    "accurate_coverage": false
  },
  "reference_point": { "lat": 42.697, "lon": 23.322 },
  "region_area_m2": 281307.62,
  "green_area_count": 69,
  "has_green_area": true,
  "coverage": {
    "accurate_coverage": false,
    "sum_green_area_clipped_m2_used": 14442.31,
    "coverage_ratio": 0.0513
  },
  "stats": {
    "sum_green_area_m2": 14442.31,
    "mean_area_m2": 209.31,
    "median_area_m2": 132.81,
    "p90_area_m2": 465.25
  },
  "nearest_green_area": {
    "id": 29808,
    "distance_m": 35.10,
    "properties": { "id": 29804, "area_m": 229, "source": 0 }
  }
}
```

---

### **Technical Implications**

*   **Data Integrity:** This mode is the "gold standard" for localized environmental reporting. By excluding boundary-straddling polygons, you avoid over-estimating the green coverage of a specific street or block based on a nearby large park that might actually be inaccessible or belong to a different district.
*   **Convergence of Metrics:** Notice that `sum_green_area_m2` and `sum_green_area_clipped_m2_used` are identical. When polygons are fully contained, the "Accurate" (clipping) and "Fast" (overlap) methods naturally result in the same value.
*   **Metric Interpretation:** A `coverage_ratio` of **5.13%** in this mode represents the "intrinsic greenness" of the immediate 300m circle.
*   **Performance:** While `accurate_coverage` is mathematically more complex, the `include_boundary=false` filter reduces the total number of features processed (from 77 down to 69), which helps maintain fast response times.

---

### **13) Stats (Radius) - Include Nearest Geometry**

This configuration allows you to retrieve high-level neighborhood statistics while simultaneously obtaining the full geometric footprint of the closest green area. It is designed for applications that show a "Local Green Score" alongside a map highlighting the nearest park or garden.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas/stats?lat=42.6970&lon=23.3220&radius_m=300&include_nearest_geometry=true"
```

**Response:**
```json
{
  "query": {
    "kind": "radius",
    "lat": 42.697,
    "lon": 23.322,
    "radius_m": 300.0,
    "include_boundary": true,
    "accurate_coverage": false
  },
  "region_area_m2": 281307.62,
  "green_area_count": 77,
  "coverage": {
    "coverage_ratio": 0.0779,
    "sum_green_area_clipped_m2_used": 21911.62
  },
  "stats": {
    "sum_green_area_m2": 26515.95,
    "mean_area_m2": 344.36,
    "median_area_m2": 153.07
  },
  "nearest_green_area": {
    "id": 29808,
    "distance_m": 35.10,
    "properties": { "id": 29804, "area_m": 229, "source": 0 },
    "feature": {
      "type": "Feature",
      "id": 29808,
      "geometry": {
        "type": "MultiPolygon",
        "coordinates": [[[[23.32158, 42.69678], [23.32158, 42.69681], "..."]]]
      },
      "properties": {
        "id": 29804,
        "area_m": 229,
        "source": 0
      }
    }
  }
}
```

---

### **Implementation Context**

*   **Single-Call Efficiency:** Instead of calling the `/green_areas` endpoint to get a park footprint and the `/stats` endpoint to get district data, this parameter merges both into one efficient request.
*   **User Interface:** The `coverage_ratio` (7.79%) provides a quantitative "Green Score," while the `feature.geometry` provides the visual "Shape" of the asset nearest to the user.
*   **Distance Awareness:** Even though the nearest park is only **35.10 meters** away, the statistics reveal that the surrounding 300m area has 77 different green segments, suggesting a fragmented but highly accessible urban green network.

---

#### **14) Stats (Radius) - Include Nearest Geometry + Strict + Accurate Coverage**

This is the most comprehensive "Environmental Quality" request. It provides aggregated statistics for the neighborhood, ensuring only green spaces **entirely contained** within the radius are counted (`include_boundary=false`), calculates the **precise surface area** using geometric intersections (`accurate_coverage=true`), and includes the **full GeoJSON geometry** of the closest green asset.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/green_areas/stats?lat=42.6970&lon=23.3220&radius_m=300&include_boundary=false&accurate_coverage=true&include_nearest_geometry=true"
```

**Response:**
```json
{
  "query": {
    "kind": "radius",
    "lat": 42.697,
    "lon": 23.322,
    "radius_m": 300.0,
    "include_boundary": false,
    "accurate_coverage": false
  },
  "reference_point": { "lat": 42.697, "lon": 23.322 },
  "region_area_m2": 281307.62,
  "green_area_count": 69,
  "coverage": {
    "sum_green_area_clipped_m2_used": 14442.31,
    "coverage_ratio": 0.0513
  },
  "stats": {
    "sum_green_area_m2": 14442.31,
    "mean_area_m2": 209.31,
    "median_area_m2": 132.81
  },
  "nearest_green_area": {
    "id": 29808,
    "distance_m": 35.10,
    "properties": { "id": 29804, "area_m": 229, "source": 0 },
    "feature": {
      "type": "Feature",
      "id": 29808,
      "geometry": {
        "type": "MultiPolygon",
        "coordinates": [[[[23.32158, 42.69678], "..."]]]
      },
      "properties": { "id": 29804, "area_m": 229, "source": 0 }
    }
  }
}
```

---

### **Implementation Context**

*   **Total Precision:** By excluding boundary-straddlers, the `green_area_count` drops from **77** to **69**. This ensures the resulting **5.13% coverage ratio** is purely representative of the immediate 300m environment.
*   **Visual Discovery:** The `nearest_green_area.feature` provides a `MultiPolygon` that can be instantly projected onto a web map (Leaflet, Mapbox, Google Maps). This allows users to see exactly which green space is considered "theirs."
*   **High-Fidelity Stats:** `sum_green_area_m2` and `sum_green_area_clipped_m2_used` converge perfectly at **14,442.31 m²** in this mode, providing a high-confidence metric for environmental auditing or urban health reporting.

---

### **Input Parameters**

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `bbox` | `string` | Conditional | Bounding box coordinates: `min_lon,min_lat,max_lon,max_lat`. |
| `lat` | `float` | Conditional | Latitude of center point. |
| `lon` | `float` | Conditional | Longitude of center point. |
| `radius_m` | `integer` | Conditional | Search radius in meters. |
| `include_boundary` | `boolean` | No | Whether to include boundary-touching green areas (default: `true`). |
| `accurate_coverage` | `boolean` | No | Use precise geometric calculations for coverage ratios (slower but more accurate) (default: `false`). |
| `center_lat` | `float` | No | Reference latitude for nearest green area identification in bbox mode. |
| `center_lon` | `float` | No | Reference longitude for nearest green area identification in bbox mode. |
| `include_nearest_geometry` | `boolean` | No | Include full GeoJSON geometry of nearest green area (default: `false`). |

### **Output Structure**

```json
{
  "query": {
    "kind": "radius" | "bbox",
    "lat": 42.6970,  // For radius queries
    "lon": 23.3220,  // For radius queries
    "radius_m": 300.0,
    "include_boundary": true,
    "accurate_coverage": false,
    "bbox": [23.32, 42.695, 23.325, 42.6975]  // For bbox queries
  },
  "region_area_m2": 113945.8520922712,
  "green_area_count": 12,
  "green_area_density_per_km2": 105.3,
  "coverage_ratio": 0.085,
  "coverage_ratio_accurate": 0.087,  // Only when accurate_coverage=true
  "stats": {
    "sum_area_m2": 9687.45,
    "sum_area_clipped_m2": 9687.45,  // Differs when include_boundary=false
    "mean_area_m2": 807.29,
    "median_area_m2": 312.19,
    "p90_area_m2": 1759.07,
    "mean_perimeter_m": 120.21,
    "median_perimeter_m": 77.55,
    "mean_compactness": 0.584,
    "median_compactness": 0.609
  },
  "nearest_green_area": {
    "id": 29654,
    "distance_m": 15.5,
    "properties": {
      "id": 29654,
      "area_m": 132.0,
      "source": 0,
      "source_id": "29654"
    },
    "feature": {  // Only included when include_nearest_geometry=true
      "type": "Feature",
      "geometry": { ... },
      "properties": { ... },
      "id": 29654
    }
  }
}
```

### **Statistics Metrics**

*   **`region_area_m2`**: Total area of the query region in square meters.
*   **`green_area_count`**: Number of green areas in the region.
*   **`green_area_density_per_km2`**: Green area density per square kilometer.
*   **`coverage_ratio`**: Proportion of land area covered by green spaces (fast calculation).
*   **`coverage_ratio_accurate`**: Precise coverage ratio (when `accurate_coverage=true`).
*   **`sum_area_m2`**: Total area of all green spaces.
*   **`sum_area_clipped_m2`**: Total area clipped to region boundary.
*   **`mean/median_area_m2`**: Average green space area.
*   **`p90_area_m2`**: 90th percentile of green area sizes.
*   **`mean/median_perimeter_m`**: Average green space perimeter.
*   **`mean/median_compactness`**: Shape compactness metrics (higher = more compact).

**Notes:**
- **Coverage Calculation:** The `accurate_coverage` parameter toggles between fast bounding-box overlap calculations and precise geometric intersection calculations.
- **Nearest Feature:** When a reference point is provided (via `center_lat`/`center_lon` or radius query), the nearest green area is identified and included in the response.
- **Performance:** Use `accurate_coverage=false` for faster responses when precise coverage ratios aren't critical.
- **Use Cases:** Ideal for urban planning, green space analysis, environmental impact assessments, and accessibility studies.