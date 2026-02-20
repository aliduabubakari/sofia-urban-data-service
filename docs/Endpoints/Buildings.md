## Buildings Stats: How the numbers are calculated (team-friendly notes)

This note explains what the **Buildings stats** mean, how they’re computed, and the design decisions behind them—written for non-technical discussions.

---

# 1) What the buildings layer represents
The buildings layer is a set of polygons where each polygon is a building footprint (the outline of a building on the map). Each building also has attributes such as:

- number of floors (`flrcount`)
- function/type (`functype`)
- year built (`nsi2011_year_built`) when available
- other enriched fields stored in `properties`

When we compute building stats for a **bbox** or a **radius**, we are summarizing the building environment inside that region.

---

# 2) Two selection behaviors: include boundary vs strict inside

Buildings can cross the boundary of a bbox or circle. We support two ways to decide which buildings “belong” to the region.

## A) `include_boundary=true` (default; “touching counts”)
A building is included if it **touches or intersects** the region.

Examples:
- A building that crosses the bbox edge counts.
- A building that touches the circle boundary counts.

Use this when:
- you want a realistic view of what buildings are “present around” the region
- you want to include buildings that affect the area even if partly outside

## B) `include_boundary=false` (“strictly inside only”)
A building is included only if it is **completely inside** the region (not touching boundary and not extending outside).

Use this when:
- you want “pure inside-only” analysis (e.g., compare neighborhoods fairly)
- you want to avoid counting buildings that only slightly overlap the region

This choice affects:
- building count
- density
- coverage
- floor-area and volume proxies

---

# 3) Counts and density (how built-up is the area?)

### `building_count`
Number of buildings included in the region (according to boundary rule).

### `region_area_m2`
Area of the query region itself.

### `building_density_per_km2`
A normalized measure:

> building_density = building_count / region_area

This makes comparisons fair across different bbox sizes or different radii.

Interpretation:
- higher density → many buildings per area (often more urban/compact)
- lower density → fewer buildings per area (often more open/suburban)

---

# 4) Coverage (how much of the ground is covered by buildings?)

### `coverage_ratio`
Meaning:
> “What fraction of the region’s ground area is covered by building footprints?”

This is calculated as:

> coverage_ratio = (total building footprint area inside region) / (region area)

Key detail: **we use the footprint area inside the region**, not necessarily the full footprint if the building crosses the boundary.  
So boundary-crossing buildings contribute only the portion that lies inside the region (this avoids over-counting).

This is one of the most useful urban intensity features.

---

# 5) Building size and shape statistics

We compute typical footprint sizes inside the region:

- `mean_area_m2`
- `median_area_m2`
- `p90_area_m2` (90th percentile footprint size)

These help answer:
- Are buildings mostly small or large?
- Is there a mix of sizes?

### Perimeter statistics
- `mean_perimeter_m`
- `median_perimeter_m`

Perimeter relates to shape complexity (longer perimeter for same area often means a more complex outline).

---

# 6) Compactness (a shape “regularity” indicator)

### `compactness` concept
Compactness is a score between 0 and 1 where:
- closer to 1 → more “compact” (closer to a circle-like footprint)
- lower values → more elongated or irregular shapes

We report:
- `mean_compactness`
- `median_compactness`

This can be useful when comparing urban form patterns.

Important note:
- Compactness is not “good/bad”; it’s a descriptive feature.

---

# 7) Floors and “built volume” proxies (useful for urban intensity)

Many buildings include `flrcount` (floor count). Using this, we estimate:

### `sum_gfa_est_m2` (estimated gross floor area)
We approximate:

> estimated floor area ≈ footprint_area * floors

Then we sum across the region.

This is a useful proxy for:
- how much built space exists in the area (not just ground footprint)
- approximating density in a way closer to “how much building mass”

We also report:
- `mean_flrcount`
- `median_flrcount`
- `p90_flrcount`

Note:
- This is an estimate. Real floor area depends on building design.

---

# 8) Year built statistics (where available)

We use `nsi2011_year_built` when present.

We report:
- `year_built_known_count` (how many buildings have year built data)
- `mean_year_built`
- `median_year_built`

Interpretation:
- newer mean/median → more recent development
- older mean/median → older building stock

Important note:
- Not all buildings have year built values. That’s why we report “known count”.

---

# 9) Functional mix (building use categories)

Buildings may have a function category (e.g., residential, public, industrial) under `functype`.

We return:
- `functype_top` = top N categories with counts (N default is 10)

This helps answer:
- Is the area mostly residential?
- Is it mixed use?

If you later want a single “mix score”, we can add an entropy-based metric, but top categories are more interpretable for most stakeholders.

---

# 10) Nearest building (for point-based workflows)

When you provide a reference point (lat/lon, or bbox center / explicit center), we return:

### `nearest_building`
- the nearest building id
- distance in meters
- its properties
- optionally its geometry (if requested)

Use cases:
- “What building is closest to this station?”
- snapping POIs to nearby buildings
- sanity checking the spatial query

---

# Summary of key decisions (easy to explain)
1) We support both:
   - **include boundary** (touching buildings count)
   - **strict inside** (only fully inside buildings count)
2) Coverage is based on the **building footprint area inside the region**, not full footprints when buildings cross boundaries.
3) Floors are used to estimate “built intensity” via an estimated total floor area.
4) Year built and function mix are reported when available, with transparency about missing data.
5) Nearest building is included to support point-based analysis and debugging.


# Buildings API

### **1. Buildings Geospatial Data Endpoint: `GET /datasets/buildings`**

Retrieves building footprints and metadata. The data is returned in **GeoJSON** format.

#### **A) BBox Query (default order by `id`)**
**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings?bbox=23.3200,42.6950,23.3250,42.6975&limit=10&offset=0&simplify_m=2"
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 899,
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [[23.319378213, 42.695968001], [23.320412874, 42.695800696], [23.32074451, 42.695723819], "..."]
        ]
      },
      "properties": {
        "cadnum": "68134.1001.22.1",
        "immaddr": "гр. София, район Триадица, бул. Витоша №2",
        "functype": "Административна, делова сграда",
        "flrcount": 6,
        "_area": 8175.70,
        "_perim": 948.33,
        "dtm2m_median": 552.0,
        "regname": "район Триадица",
        "strename": "бул. Витоша",
        "strnum": "2",
        "nsi2011_year_built": null,
        "_bldg_shape": "complex"
      }
    },
    {
      "type": "Feature",
      "id": 42443,
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [[23.325833286, 42.697675526], [23.325857023, 42.697543127], "..."]
        ]
      },
      "properties": {
        "cadnum": "68134.405.3.4",
        "immaddr": "гр. София, район Оборище, пл. Княз Александър I №1",
        "functype": "Административна, делова сграда",
        "flrcount": 7,
        "_area": 6692.44,
        "_perim": 610.94,
        "dtm2m_median": 545.31,
        "regname": "район Оборище",
        "strename": "пл. Княз Александър I",
        "strnum": "1"
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

### **Explanation of the `id` field**

In the Buildings API, you will notice two types of identifiers: the top-level `id` and the `properties.cadnum`.

#### **1. The Top-Level `id` (e.g., `899`, `42443`)**
*   **Source:** Database Indexing.
*   **What it is:** This is the **Primary Key (Serial ID)** from our spatial database.
*   **Purpose:** It is used for high-performance sorting, pagination (`offset`), and direct record retrieval.
*   **Stability:** It is unique within this specific API instance. If you need to "bookmark" a specific record to find it again quickly in this API, use this integer `id`.

#### **2. The `properties.cadnum` (e.g., `"68134.1001.22.1"`)**
*   **Source:** Original Dataset (AGKK - Bulgarian Cartography, Geodesy and Cadastre Agency).
*   **What it is:** The **Official Cadastral Identifier**.
*   **Structure:** `EKATTE (Settlement code) . Cadastral Region . Property ID . Building ID`.
*   **Purpose:** This is the "Universal ID" used across all Bulgarian government institutions. If you need to cross-reference our data with official property deeds, tax records, or other government datasets, you must use `cadnum`.

#### **Summary Table**

| ID Type | Location | Format | Best Use Case |
| :--- | :--- | :--- | :--- |
| **Internal ID** | `feature.id` | `Integer` | API Pagination, fast database lookups, local caching. |
| **Cadastral ID** | `feature.properties.cadnum` | `String` | Legal identification, matching with external Bulgarian Gov data. |

---

**Note for Documentation:**
It is recommended to use `id` for technical operations (like "get the next 10 buildings after ID 899") and `cadnum` for business/real-estate logic (like "find the height of the building at Vitoshka 2").

### **B) BBox Query (strictly inside bbox)**

This query uses the `include_boundary=false` parameter. It filters the results to only include buildings whose geometries are **entirely contained** within the specified bounding box. Buildings that cross the edge of the box are excluded.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings?bbox=23.3200,42.6950,23.3250,42.6975&limit=10&include_boundary=false&simplify_m=2"
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 178845,
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [[23.32280979, 42.695993389], [23.322905815, 42.695969142], "..."]
        ]
      },
      "properties": {
        "cadnum": "68134.100.33.2",
        "immaddr": "гр. София, район Средец, ул. Цар Калоян №8",
        "functype": "Култова, религиозна сграда",
        "flrcount": 1,
        "_area": 77.87,
        "_perim": 37.50,
        "dtm2m_median": 549.35,
        "strename": "ул. Цар Калоян",
        "strnum": "8"
      }
    },
    {
      "type": "Feature",
      "id": 178846,
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [[23.321280816, 42.695783738], [23.321331144, 42.695987995], "..."]
        ]
      },
      "properties": {
        "cadnum": "68134.100.13.1",
        "immaddr": "гр. София, район Средец, пл.\"Света Неделя\" №19",
        "functype": "Сграда за образование",
        "flrcount": 4,
        "_area": 1166.24,
        "dtm2m_median": 551.25
      }
    }
    // ... additional results
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

**Key Observation:**
Notice that Building **ID 899** (from example A) is missing here. Because its footprint partially sits outside the coordinates `23.3200, 42.6950`, it is excluded when `include_boundary` is set to `false`. This is useful for statistical analysis where you want to avoid double-counting buildings that span multiple grid cells.

---

#### **C) BBox Query Ordered by Proximity to Reference Point**

This mode combines a spatial filter (**Bounding Box**) with a sorting metric (**Distance**). By providing a reference `lat` and `lon` alongside the `bbox`, the API sorts the buildings within that box starting from the ones closest to the reference point.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings?bbox=23.3200,42.6950,23.3250,42.6975&lat=42.6962&lon=23.3223&order_by=distance&limit=10&include_distance=true&simplify_m=2"
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 181373,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.322667056, 42.696380798], "..."]]
      },
      "properties": {
        "cadnum": "68134.100.12.15",
        "immaddr": "гр. София, район Средец, ул. \"Цар Калоян\" №7",
        "functype": "Сграда със смесено предназначение",
        "flrcount": 7,
        "_area": 1907.15,
        "distance_m": 0.0
      }
    },
    {
      "type": "Feature",
      "id": 181372,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.322443478, 42.696233252], "..."]]
      },
      "properties": {
        "cadnum": "68134.100.12.9",
        "immaddr": "гр. София, район Средец, пл. \"Света Неделя\" №16",
        "functype": "Сграда за енергопроизводство",
        "flrcount": 1,
        "distance_m": 7.88
      }
    },
    {
      "type": "Feature",
      "id": 180190,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.322064274, 42.696037604], "..."]]
      },
      "properties": {
        "cadnum": "68134.100.12.10",
        "immaddr": "гр. София, район Средец, пл.\"Света Неделя\" №16",
        "functype": "Култова, религиозна сграда",
        "flrcount": 1,
        "distance_m": 20.29
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

**Key Features of this Query:**
*   **Targeted Sorting:** Useful for finding the "nearest entrance" or "closest facility" within a specific neighborhood or district.
*   **`distance_m` Property:** When `include_distance=true` is passed, the API calculates the ellipsoidal distance (in meters) from the reference point to the **closest point on the building's geometry**.
*   **Coordinate Context:** If the reference point (`lat`/`lon`) is inside a building, the `distance_m` will be `0.0` (as seen in ID `181373`).

---

#### **D) Radius Query (nearest-first by default)**

This query searches within a circular region. It is the most common method for "find buildings near me" functionality. By default, the API returns results sorted by distance from the center point (nearest to farthest).

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings?lat=42.6958&lon=23.3219&radius_m=300&limit=10&simplify_m=2"
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 178846,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.321280816, 42.695783738], "..."]]
      },
      "properties": {
        "cadnum": "68134.100.13.1",
        "immaddr": "гр. София, район Средец, пл.\"Света Неделя\" №19",
        "functype": "Сграда за образование",
        "flrcount": 4,
        "_area": 1166.25,
        "distance_m": 0.0
      }
    },
    {
      "type": "Feature",
      "id": 180205,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.321901346, 42.695793788], "..."]]
      },
      "properties": {
        "cadnum": "68134.100.12.12",
        "immaddr": "гр. София, район Средец, пл.\"Света Неделя\" №19",
        "functype": "Култова, религиозна сграда",
        "distance_m": 0.26
      }
    },
    {
      "type": "Feature",
      "id": 180208,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.321890873, 42.695759836], "..."]]
      },
      "properties": {
        "cadnum": "68134.100.13.2",
        "distance_m": 0.70
      }
    }
    // ... further results increasing in distance
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

**Key Features of Radius Queries:**
*   **Automatic Sorting:** Unlike `bbox` queries (which default to `id`), radius queries automatically use `order_by=distance` unless specified otherwise.
*   **Distance Inclusion:** The `distance_m` property is automatically included in the output for radius queries to help developers verify proximity.
*   **Efficiency:** This is the most performant endpoint for mobile applications or location-aware services where only the immediate surroundings matter.
*   **Precision:** The distance is calculated from the provided `lat`/`lon` to the nearest edge of the building polygon.

---

#### **E) Radius Query with Distance Metric**

This example explicitly requests the results to be ordered by distance and includes the specific distance calculation in the response properties. While radius queries default to this behavior, being explicit allows you to maintain the `distance_m` field even if you decide to change the sorting logic.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings?lat=42.6958&lon=23.3219&radius_m=300&order_by=distance&limit=10&include_distance=true&simplify_m=2"
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 178846,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.321280816, 42.695783738], [23.321331144, 42.695987995], "..."]]
      },
      "properties": {
        "cadnum": "68134.100.13.1",
        "immaddr": "гр. София, район Средец, пл.\"Света Неделя\" №19",
        "functype": "Сграда за образование",
        "flrcount": 4,
        "_area": 1166.25,
        "distance_m": 0.0
      }
    },
    {
      "type": "Feature",
      "id": 180205,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.321901346, 42.695793788], [23.321918099, 42.695848212], "..."]]
      },
      "properties": {
        "cadnum": "68134.100.12.12",
        "immaddr": "гр. София, район Средец, пл.\"Света Неделя\" №19",
        "functype": "Култова, религиозна сграда",
        "distance_m": 0.26
      }
    },
    {
      "type": "Feature",
      "id": 180208,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.321890873, 42.695759836], "..."]]
      },
      "properties": {
        "cadnum": "68134.100.13.2",
        "distance_m": 0.70
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

**Technical Details:**
*   **Explicit Control:** Use `order_by=distance` to ensure that the closest buildings appear first in the array.
*   **Metadata Enrichment:** The `include_distance=true` flag adds the `distance_m` property. This value represents the distance from the provided query coordinates to the nearest point of the building's footprint.
*   **Geometric Context:** A `distance_m` of `0.0` indicates that the query point is located either exactly on the building's boundary or inside the building's polygon.

---

#### **F) Radius Query (strictly inside circle)**

This query utilizes the `include_boundary=false` parameter to filter results. It ensures that only buildings **entirely contained** within the search radius are returned. If any part of a building footprint lies outside the specified distance, it is excluded from the results.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings?lat=42.6958&lon=23.3219&radius_m=300&include_boundary=false&limit=10&simplify_m=2"
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 178846,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.321280816, 42.695783738], [23.321331144, 42.695987995], "..."]]
      },
      "properties": {
        "cadnum": "68134.100.13.1",
        "immaddr": "гр. София, район Средец, пл.\"Света Неделя\" №19",
        "functype": "Сграда за образование",
        "flrcount": 4,
        "_area": 1166.25,
        "distance_m": 0.0
      }
    },
    {
      "type": "Feature",
      "id": 180205,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.321901346, 42.695793788], [23.321918099, 42.695848212], "..."]]
      },
      "properties": {
        "cadnum": "68134.100.12.12",
        "functype": "Култова, религиозна сграда",
        "distance_m": 0.26
      }
    },
    {
      "type": "Feature",
      "id": 180208,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.321890873, 42.695759836], "..."]]
      },
      "properties": {
        "cadnum": "68134.100.13.2",
        "distance_m": 0.69
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

**Why use `include_boundary=false`?**
*   **Precision Analysis:** Ideal for neighborhood-level statistics where you want to ensure that every building counted is fully within the study area.
*   **Asset Management:** Useful when determining which properties are strictly within a designated safety or service zone (e.g., within 300m of a fire station).
*   **Exclusion Logic:** This effectively filters out large structures that might only "clip" the edge of your search circle.

---

#### **G) Strict Radius Query with Distance**

This query is the most specific search type available. It combines strict geometric containment (`include_boundary=false`) with proximity sorting (`order_by=distance`) and explicitly includes the distance value for each result (`include_distance=true`).

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings?lat=42.6958&lon=23.3219&radius_m=300&include_boundary=false&order_by=distance&limit=10&include_distance=true&simplify_m=2"
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 178846,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.321280816, 42.695783738], "..."]]
      },
      "properties": {
        "cadnum": "68134.100.13.1",
        "immaddr": "гр. София, район Средец, пл.\"Света Неделя\" №19",
        "functype": "Сграда за образование",
        "flrcount": 4,
        "_area": 1166.25,
        "distance_m": 0.0
      }
    },
    {
      "type": "Feature",
      "id": 180205,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.321901346, 42.695793788], "..."]]
      },
      "properties": {
        "cadnum": "68134.100.12.12",
        "functype": "Култова, религиозна сграда",
        "distance_m": 0.26
      }
    },
    {
      "type": "Feature",
      "id": 180208,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[23.321890873, 42.695759836], "..."]]
      },
      "properties": {
        "cadnum": "68134.100.13.2",
        "distance_m": 0.70
      }
    }
    // ... further results strictly within 300m
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

**Use Case:**
*   **Exact Buffer Analysis:** Use this when you need to know exactly which buildings are within a specific walking distance (e.g., a "300m walking zone") and you want to exclude any buildings that are partially outside that boundary to ensure data integrity for localized reports.
*   **Proximity Ranking:** The `distance_m` field allows your application to display labels such as "Building A (15m away)" while the containment logic ensures you aren't showing buildings that are technically 305m away but merely "touch" the 300m line.

---

#### **H) Radius Query Ordered by ID**

By default, radius queries are optimized for proximity, meaning they sort results by distance. However, you can explicitly set `order_by=id`. This is particularly useful for **stable pagination** (using `limit` and `offset`) when you need to iterate through every building in a large circular region without the order shifting as you move the reference point slightly.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings?lat=42.6958&lon=23.3219&radius_m=300&order_by=id&limit=10&simplify_m=2"
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 721,
      "geometry": { "type": "Polygon", "coordinates": [...] },
      "properties": {
        "cadnum": "68134.1001.120.2",
        "immaddr": "гр. София, район Триадица, ул. Цар Асен №6",
        "functype": "Жилищна сграда - многофамилна",
        "flrcount": 3
      }
    },
    {
      "type": "Feature",
      "id": 899,
      "geometry": { "type": "Polygon", "coordinates": [...] },
      "properties": {
        "cadnum": "68134.1001.22.1",
        "immaddr": "гр. София, район Триадица, бул. Витоша №2",
        "functype": "Административна, делова сграда",
        "flrcount": 6
      }
    },
    {
      "type": "Feature",
      "id": 6343,
      "geometry": { "type": "Polygon", "coordinates": [...] },
      "properties": {
        "cadnum": "68134.402.148.1",
        "immaddr": "гр. София, район Оборище, бул. княз АЛ.ДОНДУКОВ-КОРСАКОВ",
        "functype": "Сграда за търговия",
        "flrcount": 1
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

**Key Advantages:**
*   **Performance:** Sorting by a database primary key (`id`) is significantly faster than calculating and sorting by ellipsoidal distance, especially when the search radius contains thousands of buildings.
*   **Consistency:** If you are performing a bulk export of data within a radius, using `order_by=id` with `limit` and `offset` ensures that you do not miss buildings or process the same building twice during the pagination process.
*   **Distance Metric:** Even when sorting by ID, you can still include the `include_distance=true` parameter if you need to know how far each building is from the center, while keeping the ID-based sort order.

---

#### **I) Nearest Building Only**

This specialized query is designed to identify the single building closest to a specific coordinate. By setting `limit=1` and `order_by=distance`, the API returns only the most relevant feature. This is the optimal configuration for "Snap-to-Building" features or determining which building a user is currently at.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings?lat=42.6958&lon=23.3219&radius_m=300&limit=1&order_by=distance&include_distance=true"
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 178846,
      "geometry": {
        "type": "MultiPolygon",
        "coordinates": [[[[23.321280816, 42.695783738], [23.321331144, 42.695987995], "..."]]]
      },
      "properties": {
        "cadnum": "68134.100.13.1",
        "immaddr": "гр. София, район Средец, пл.\"Света Неделя\" №19",
        "functype": "Сграда за образование",
        "flrcount": 4,
        "_area": 1166.25,
        "_perim": 152.90,
        "dtm2m_median": 551.25,
        "distance_m": 0.0
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

**Implementation Notes:**
*   **Geometric Types:** Note that geometry can be returned as either **`Polygon`** or **`MultiPolygon`** depending on the complexity of the building structure.
*   **Distance 0.0:** A distance of `0.0` indicates that the reference point (`lat`/`lon`) is located inside the building's footprint.
*   **Radius Safety:** Always provide a `radius_m`. If no building is found within that radius, the `features` array will be empty (`[]`). This prevents the API from searching the entire country for the "nearest" building if the coordinate is in the middle of a forest or sea.
*   **Efficiency:** This is the most efficient way to perform a "Reverse Geocode to Building" lookup.

---

### **Input Parameters**

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `bbox` | `string` | Conditional | Bounding box coordinates: `min_lon,min_lat,max_lon,max_lat`. Required for bbox queries. |
| `lat` | `float` | Conditional | Latitude of center point. Required for radius queries. |
| `lon` | `float` | Conditional | Longitude of center point. Required for radius queries. |
| `radius_m` | `integer` | Conditional | Search radius in meters. Required for radius queries. |
| `limit` | `integer` | No | Maximum number of features to return (default: varies, e.g., `500` max). |
| `offset` | `integer` | No | Number of features to skip (used for pagination). |
| `simplify_m` | `float` | No | Simplification tolerance in meters. Reduces coordinate precision to improve performance. |
| `include_boundary` | `boolean` | No | Whether to include buildings that touch the boundary (default: `true`). |
| `order_by` | `string` | No | Sort order: `id`, `distance` (default depends on query type). |
| `include_distance` | `boolean` | No | Include distance from reference point in properties (default: `false`). |
| `center_lat` | `float` | No | Reference latitude for nearest building calculation in bbox mode. |
| `center_lon` | `float` | No | Reference longitude for nearest building calculation in bbox mode. |

### **Output Structure**

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
        "coordinates": [[[23.319378213,42.695968001], ...]]
      },
      "properties": {
        "cadnum": "68134.1001.22.1",
        "immaddr": "гр. София, район Триадица, бул. Витоша №2",
        "functype": "Административна, делова сграда",
        "flrcount": 6,
        "_area": 8175.70,
        "_perim": 948.33,
        "dtm2m_median": 552.0,
        "nsi2011_year_built": null,
        "distance_m": 0.0  // Only included when include_distance=true
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

### **Complete Property Fields**

*   **`cadnum`**: The official cadastral identification number.
*   **`immaddr`**: Full physical address (in Bulgarian).
*   **`functype`**: Primary functional use (e.g., Administrative, Residential, Religious).
*   **`flrcount`**: Total number of floors above ground.
*   **`_area` / `_perim`**: Calculated geometric area (sq. meters) and perimeter (meters).
*   **`dtm2m_median`**: Median elevation/height coordinate for the building base.
*   **`nsi2011_year_built`**: Year the building was constructed (based on 2011 census data).
*   **`cadimm`**: Cadastral immutable identifier.
*   **`cadreg`**: Cadastral region code.
*   **`ekatte`**: Unified Classifier of Administrative-Territorial Units.
*   **`regname`**: Administrative district name.
*   **`strename`**: Street name.
*   **`strnum`**: Street number.
*   **`funccode`**: Functional code (numeric classification).
*   **`propcode`**: Property type code.
*   **`proptype`**: Property ownership type.
*   **`validate`**: Validation/documentation details.
*   **`_bldg_shape`**: Building shape classification (complex, rectangle, etc.).
*   **`_row_neighbour_nr`**: Row/neighborhood identifier.
*   **`distance_m`**: Distance from reference point in meters (when `include_distance=true`).

**Notes:**
- **Geometry:** Returns high-precision polygons. Use `simplify_m` for large queries to prevent slow rendering.
- **Pagination:** Use `limit` and `offset` for large result sets.
- **Spatial Modes:** Two primary modes: Bounding Box (`bbox`) and Radius (`lat`/`lon`/`radius_m`).
- **Distance Calculation:** When `order_by=distance` is specified, results are ordered by proximity to the reference point.

---

## 2. Buildings Statistics Endpoint: `GET /datasets/buildings/stats`

Provides aggregated statistics and metrics for buildings within specified geographic areas.

### **Request Examples**

## 2. Buildings Statistics Endpoint: `GET /datasets/buildings/stats`

Provides aggregated spatial statistics and urban metrics for buildings within a specified geographic area. This endpoint is ideal for urban planning, real estate market analysis, and density studies.

### **1) Buildings Stats (Radius) - Include Boundary (default)**

This query calculates statistics for all buildings within a circular radius. By default, it includes buildings that are partially overlapping the boundary of the circle.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings/stats?lat=42.6958&lon=23.3219&radius_m=300"
```

**Response:**
```json
{
  "query": {
    "kind": "radius",
    "lat": 42.6958,
    "lon": 23.3219,
    "radius_m": 300.0,
    "include_boundary": true
  },
  "region_area_m2": 281307.69,
  "building_count": 329,
  "building_density_per_km2": 1169.54,
  "coverage_ratio": 0.47,
  "stats": {
    "sum_building_area_m2": 160036.38,
    "sum_building_area_clipped_m2": 132247.66,
    "mean_area_m2": 486.43,
    "median_area_m2": 239.04,
    "p90_area_m2": 865.45,
    "mean_perimeter_m": 88.86,
    "median_perimeter_m": 68.37,
    "mean_compactness": 0.61,
    "median_compactness": 0.63,
    "mean_flrcount": 4.26,
    "median_flrcount": 5.0,
    "p90_flrcount": 7.0,
    "sum_gfa_est_m2": 853026.30,
    "year_built_known_count": 122,
    "mean_year_built": 1940.84,
    "median_year_built": 1938.0,
    "functype_top": [
      {"functype": "Жилищна сграда - многофамилна", "count": 100},
      {"functype": "Административна, делова сграда", "count": 93},
      {"functype": "Жилищна сграда - еднофамилна", "count": 21},
      "..."
    ]
  },
  "nearest_building": {
    "id": 178846,
    "distance_m": 0.0,
    "properties": {
      "cadnum": "68134.100.13.1",
      "immaddr": "гр. София, район Средец, пл.\"Света Неделя\" №19",
      "functype": "Сграда за образование",
      "flrcount": 4,
      "dtm2m_median": 551.25
    }
  }
}
```

---

### **Key Metrics Explained**

#### **Spatial Coverage**
*   **`region_area_m2`**: The total surface area of the query geometry (the 300m circle).
*   **`building_density_per_km2`**: Extrapolated number of buildings if this density were applied to a full square kilometer.
*   **`coverage_ratio`**: The "Footprint Ratio." A value of `0.47` means 47% of the land area is covered by building footprints.
*   **`sum_building_area_clipped_m2`**: The total area of buildings **contained strictly inside** the circle. For buildings crossing the edge, only the portion inside the circle is summed.

#### **Building Dimensions & Volume**
*   **`sum_building_area_m2`**: The total footprint area of all buildings involved in the query (unclipped).
*   **`sum_gfa_est_m2`**: **Estimated Gross Floor Area.** Calculated as `footprint_area * flrcount`. This is a primary metric for estimating total floor space in a district.
*   **`mean/median_compactness`**: A measure of how "circular" or "square" a building is (Polsby-Popper score). Values closer to `1.0` indicate simple shapes (rectangles/squares), while lower values indicate complex, irregular, or "spiky" footprints.

#### **Demographics & Usage**
*   **`year_built_known_count`**: The number of buildings in the set that have constructed-year data available (often sourced from NSI census data).
*   **`functype_top`**: A categorical breakdown showing the dominant land use. In this example, the area is primarily **Multi-family Residential** and **Administrative**.

#### **Proximity Context**
*   **`nearest_building`**: Automatically identifies and provides full metadata for the building closest to the center of your query. This provides immediate context for the "anchor" of the search area.

---

### **Notes on Statistical Accuracy**
1.  **Clipped vs. Unclipped:** When `include_boundary=true`, statistics like `mean_area_m2` use the full building size, whereas `coverage_ratio` uses clipped geometries to ensure the ratio never exceeds 1.0.
2.  **Floor Counts:** `sum_gfa_est_m2` relies on the `flrcount` property. If a building has `null` floors, it is treated as a 1-story structure for the estimation.
3.  **Performance:** This endpoint performs complex spatial aggregations. For very large radii (>2000m), response times may increase.

### **2) Buildings Stats (Radius) - Strict Inside Circle**

By setting `include_boundary=false`, the statistics engine only considers buildings that are **entirely contained** within the search radius. Any building footprint that intersects with the edge of the circle is completely ignored. 

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings/stats?lat=42.6958&lon=23.3219&radius_m=300&include_boundary=false"
```

**Response:**
```json
{
  "query": {
    "kind": "radius",
    "lat": 42.6958,
    "lon": 23.3219,
    "radius_m": 300.0,
    "include_boundary": false
  },
  "region_area_m2": 281307.69,
  "building_count": 267,
  "building_density_per_km2": 949.14,
  "coverage_ratio": 0.35,
  "stats": {
    "sum_building_area_m2": 99684.39,
    "sum_building_area_clipped_m2": 99684.39,
    "mean_area_m2": 373.35,
    "median_area_m2": 233.46,
    "p90_area_m2": 721.66,
    "mean_perimeter_m": 78.29,
    "mean_compactness": 0.62,
    "mean_flrcount": 4.14,
    "sum_gfa_est_m2": 541047.88,
    "year_built_known_count": 93,
    "mean_year_built": 1941.47,
    "functype_top": [
      {"functype": "Административна, делова сграда", "count": 80},
      {"functype": "Жилищна сграда - многофамилна", "count": 74},
      "..."
    ]
  },
  "nearest_building": {
    "id": 178846,
    "distance_m": 0.0,
    "properties": { "cadnum": "68134.100.13.1", "..." }
  }
}
```

---

### **Key Differences from Default (Boundary Included)**

1.  **Lower Counts & Ratios:**
    *   The `building_count` dropped from **329** to **267**. 
    *   The `coverage_ratio` dropped from **0.47** (47%) to **0.35** (35%).
    *   This indicates that 62 buildings were partially crossing the 300m threshold and were excluded in this "strict" mode.

2.  **Identical Sums:**
    *   In Example 1 (Include Boundary), `sum_building_area_m2` was different from `sum_building_area_clipped_m2` because buildings were being cut by the circle.
    *   In this query, `sum_building_area_m2` and `sum_building_area_clipped_m2` are **exactly the same**. Since all buildings are fully inside, no clipping is performed.

3.  **Shift in Mean/Median:**
    *   The `mean_area_m2` dropped from **486** to **373**. This suggests that in this specific area of Sofia, the buildings near the boundary of the 300m circle happen to be larger structures (like the Central Department Store or Government buildings). By excluding them, the average size of the "fully contained" buildings is smaller.

### **Use Case**
Use this mode when you need **pure statistical isolation**. If you are comparing two different 300m circles and want to ensure that no single building is being counted in both sets (double-counting), `include_boundary=false` is the mathematically correct choice for non-overlapping spatial partitions.

### **3) Buildings Stats (Radius) - Include Nearest Building Geometry**

By adding the `include_nearest_geometry=true` parameter, the API enriches the `nearest_building` object with a full GeoJSON `feature`. This allows you to visualize the specific building at the center of the query on a map while simultaneously viewing the aggregated statistics for the surrounding area.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings/stats?lat=42.6958&lon=23.3219&radius_m=300&include_boundary=false&include_nearest_geometry=true"
```

**Response:**
```json
{
  "query": {
    "kind": "radius",
    "lat": 42.6958,
    "lon": 23.3219,
    "radius_m": 300.0,
    "include_boundary": false
  },
  "region_area_m2": 281307.69,
  "building_count": 267,
  "stats": {
    "sum_building_area_m2": 99684.39,
    "mean_area_m2": 373.35,
    "sum_gfa_est_m2": 541047.88,
    "functype_top": [...]
  },
  "nearest_building": {
    "id": 178846,
    "distance_m": 0.0,
    "properties": {
      "cadnum": "68134.100.13.1",
      "immaddr": "гр. София, район Средец, пл.\"Света Неделя\" №19",
      "functype": "Сграда за образование",
      "flrcount": 4
    },
    "feature": {
      "type": "Feature",
      "id": 178846,
      "geometry": {
        "type": "MultiPolygon",
        "coordinates": [[[[23.321280816, 42.695783738], "..."]]]
      },
      "properties": {
        "cadnum": "68134.100.13.1",
        "immaddr": "гр. София, район Средец, пл.\"Света Неделя\" №19",
        "_area": 1166.25,
        "dtm2m_median": 551.25
      }
    }
  }
}
```

---

### **Key Value Additions**

*   **Mapping Integration:** Traditionally, getting the footprint of the "target" building and the statistics for its "neighbors" would require two separate API calls. This parameter combines them into a single high-performance request.
*   **Geometric Verification:** The `feature.geometry` allows frontend applications to highlight or "select" the nearest building on a map automatically.
*   **Full Metadata:** While the `nearest_building.properties` block provides a quick summary, the `nearest_building.feature.properties` block contains the full set of cadastral and geometric attributes (e.g., elevation data, shape classification).

---

### **4) Buildings Stats (BBox) - Include Boundary (default)**

You can also retrieve urban statistics for a rectangular area using a Bounding Box. Like the radius query, the default behavior is to include buildings that cross the perimeter of the box.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings/stats?bbox=23.3200,42.6950,23.3250,42.6975"
```

**Note:** This is the ideal endpoint for generating "Dashboard" views for specific map viewports. Every time a user pans the map, you can retrieve the urban density and floor area stats for the visible area.

### **4) Buildings Stats (BBox) - Include Boundary (default)**

This query calculates statistics for all buildings within a rectangular bounding box. By default, it includes buildings that partially overlap the boundary. This is the most efficient way to generate urban analytics for a specific map viewport.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings/stats?bbox=23.3200,42.6950,23.3250,42.6975"
```

**Response:**
```json
{
  "query": {
    "kind": "bbox",
    "bbox": [23.32, 42.695, 23.325, 42.6975],
    "include_boundary": true
  },
  "region_area_m2": 113945.85,
  "building_count": 85,
  "building_density_per_km2": 745.97,
  "coverage_ratio": 0.4137,
  "stats": {
    "sum_building_area_m2": 68618.33,
    "sum_building_area_clipped_m2": 47135.67,
    "mean_area_m2": 807.27,
    "median_area_m2": 312.19,
    "p90_area_m2": 1759.07,
    "mean_perimeter_m": 120.21,
    "mean_compactness": 0.58,
    "mean_flrcount": 4.68,
    "sum_gfa_est_m2": 379377.92,
    "year_built_known_count": 15,
    "functype_top": [
      {"functype": "Административна, делова сграда", "count": 39},
      {"functype": "Жилищна сграда - многофамилна", "count": 10},
      "..."
    ]
  },
  "nearest_building": null
}
```

---

### **Important Notes for BBox Stats**

1.  **Clipped Area vs. Full Area:**
    *   **`sum_building_area_m2` (68,618 m²):** The total footprint area of all 85 buildings.
    *   **`sum_building_area_clipped_m2` (47,135 m²):** The area of those buildings that actually falls **inside** the rectangle.
    *   The significant difference (~21,000 m²) indicates that several large buildings are partially outside the selected box. The `coverage_ratio` (0.41) correctly uses the **clipped** area to show that 41% of this specific rectangle is covered by structures.

2.  **`nearest_building: null`**:
    *   In a BBox query, there is no "center point" by default. Therefore, the API does not calculate a nearest building unless you explicitly provide `center_lat` and `center_lon` parameters.

3.  **Urban Profile:**
    *   With an average floor count of **4.68** and a high concentration of **Administrative/Business buildings** (39 out of 85), this area is statistically identified as a high-density commercial/government district.

---

### **5) Buildings Stats (BBox) - Strict Inside BBox**

If you want to exclude buildings that are cut off by the edges of your map or study area, set `include_boundary=false`. This ensures that every building contributing to the statistics is fully visualized within the coordinates.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings/stats?bbox=23.3200,42.6950,23.3250,42.6975&include_boundary=false"
```

**Note:** This is useful for high-precision architectural studies where "partial" buildings would skew the average area or perimeter metrics.


### **5) Buildings Stats (BBox) - Strict Inside BBox**

By setting `include_boundary=false`, the statistics engine filters out any building that is not **entirely contained** within the bounding box coordinates. This ensures that the metrics reflect only complete structures, which is critical for precise urban analysis and site-specific planning.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings/stats?bbox=23.3200,42.6950,23.3250,42.6975&include_boundary=false"
```

**Response:**
```json
{
  "query": {
    "kind": "bbox",
    "bbox": [23.32, 42.695, 23.325, 42.6975],
    "include_boundary": false
  },
  "region_area_m2": 113945.85,
  "building_count": 62,
  "building_density_per_km2": 544.12,
  "coverage_ratio": 0.2776,
  "stats": {
    "sum_building_area_m2": 31632.47,
    "sum_building_area_clipped_m2": 31632.47,
    "mean_area_m2": 510.20,
    "median_area_m2": 284.67,
    "p90_area_m2": 1258.90,
    "mean_perimeter_m": 91.21,
    "mean_compactness": 0.61,
    "mean_flrcount": 4.44,
    "sum_gfa_est_m2": 182551.10,
    "year_built_known_count": 8,
    "mean_year_built": 1947.75,
    "functype_top": [
      {"functype": "Административна, делова сграда", "count": 24},
      {"functype": "Култова, религиозна сграда", "count": 7},
      {"functype": "Жилищна сграда - многофамилна", "count": 7}
    ]
  },
  "nearest_building": null
}
```

---

### **Key Analysis: Strict vs. Boundary Included**

1.  **Count Reduction:**
    *   The `building_count` dropped from **85** to **62**. This confirms that 23 buildings were crossing the edges of the box and were excluded.
    
2.  **Area Convergence:**
    *   `sum_building_area_m2` and `sum_building_area_clipped_m2` are now **identical** (31,632.47). 
    *   Because the API only selects buildings that are 100% inside the box, there is no need to "clip" or cut any geometries. The footprint area of the buildings is preserved exactly as it exists in the database.

3.  **Density & Coverage:**
    *   The `coverage_ratio` dropped from **41.3%** down to **27.7%**. This reveals that a significant portion of the land coverage in this specific viewport comes from large buildings that sit on the edges of the box.

4.  **Use Case:**
    *   **Zoning Analysis:** Use this to calculate the exact floor-area-ratio (FAR) of a specific block where you do not want data from neighboring blocks to bleed in.
    *   **Grid-Based Modeling:** Useful when processing city data in non-overlapping "tiles" or grids.

---

### **6) Buildings Stats (BBox) + Nearest Building to Centroid**

In BBox mode, you can still find the "closest" building by providing a reference point (`center_lat` and `center_lon`). This identifies the building within the box that is nearest to your specific point of interest (e.g., a cursor click or a center point).

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings/stats?bbox=23.3200,42.6950,23.3250,42.6975&center_lat=42.6962&center_lon=23.3223"
```

**Note:** This is perfect for "Map Click" interactions where you want to show stats for the whole neighborhood but highlight the specific building the user clicked on.

### **6) Buildings Stats (BBox) + Nearest Building to Centroid**

While Bounding Box queries typically provide aggregate data for a region, adding `center_lat` and `center_lon` parameters allows the API to identify a specific building of interest within that box. This is highly useful for "Contextual Analytics," where you want to see the stats for a neighborhood while simultaneously identifying the building at a specific coordinate (e.g., a user's click or the center of the screen).

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings/stats?bbox=23.3200,42.6950,23.3250,42.6975&center_lat=42.6962&center_lon=23.3223"
```

**Response:**
```json
{
  "query": {
    "kind": "bbox",
    "bbox": [23.32, 42.695, 23.325, 42.6975],
    "include_boundary": true
  },
  "region_area_m2": 113945.85,
  "building_count": 85,
  "stats": {
    "sum_building_area_m2": 68618.33,
    "mean_area_m2": 807.27,
    "sum_gfa_est_m2": 379377.92,
    "functype_top": [
      {"functype": "Административна, делова сграда", "count": 39},
      {"functype": "Жилищна сграда - многофамилна", "count": 10},
      "..."
    ]
  },
  "nearest_building": {
    "id": 181373,
    "distance_m": 0.0,
    "properties": {
      "cadnum": "68134.100.12.15",
      "immaddr": "гр. София, район Средец, ул. \"Цар Калоян\" №7",
      "functype": "Сграда със смесено предназначение",
      "flrcount": 7,
      "_area": 1907.15,
      "dtm2m_median": 549.99
    }
  }
}
```

---

### **Technical Breakdown**

*   **Dual-Purpose Response:** The top half of the JSON provides the **Macro view** (density and usage of the 85 buildings in the box), while the `nearest_building` block provides the **Micro view** (details of the specific target building).
*   **Distance 0.0:** In this example, the provided center point (`42.6962`, `23.3223`) falls exactly inside building **ID 181373**. 
*   **Property Enrichment:** The `nearest_building.properties` includes high-value fields such as `_area` and `flrcount`, allowing for an immediate comparison between the specific building and the neighborhood averages (e.g., this building has 7 floors vs. the neighborhood mean of 4.68).

---

### **7) Buildings Stats (BBox) + Nearest Building Geometry**

This configuration is the most comprehensive data package for Bounding Box analytics. By providing a reference point (`center_lat`/`center_lon`) and enabling `include_nearest_geometry=true`, the API returns the aggregate urban metrics for the entire viewport while embedding the full high-precision GeoJSON geometry for the specific building at the center.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings/stats?bbox=23.3200,42.6950,23.3250,42.6975&center_lat=42.6962&center_lon=23.3223&include_nearest_geometry=true"
```

**Response:**
```json
{
  "query": {
    "kind": "bbox",
    "bbox": [23.32, 42.695, 23.325, 42.6975],
    "include_boundary": true
  },
  "region_area_m2": 113945.85,
  "building_count": 85,
  "stats": {
    "sum_building_area_m2": 68618.32,
    "coverage_ratio": 0.41,
    "mean_flrcount": 4.68,
    "functype_top": [
      {"functype": "Административна, делова сграда", "count": 39},
      "..."
    ]
  },
  "nearest_building": {
    "id": 181373,
    "distance_m": 0.0,
    "properties": {
      "cadnum": "68134.100.12.15",
      "immaddr": "гр. София, район Средец, ул. \"Цар Калоян\" №7",
      "functype": "Сграда със смесено предназначение"
    },
    "feature": {
      "type": "Feature",
      "id": 181373,
      "geometry": {
        "type": "MultiPolygon",
        "coordinates": [[[[23.322667056, 42.696380798], "..."]]]
      },
      "properties": {
        "cadnum": "68134.100.12.15",
        "_area": 1907.15,
        "dtm2m_median": 549.99,
        "_bldg_shape": "complex"
      }
    }
  }
}
```

---

### **Implementation Context**

*   **UI/UX Optimization:** This endpoint is designed for single-load dashboard interactions. You can render the statistical charts (pie charts for `functype`, bars for `flrcount`) while simultaneously drawing the precise boundary of the "clicked" building on the map using the `feature` object.
*   **High-Precision Geometries:** The `MultiPolygon` format ensures that complex buildings with inner courtyards (holes) or multiple separate wings are represented accurately.
*   **Data Redundancy:** The `properties` are included both in the summary `nearest_building.properties` and the full GeoJSON `feature.properties` to satisfy both lightweight UI labels and deep data inspections.

---

### **8) Buildings Stats with Top N Function Type Categories**

By default, the `functype_top` list returns the top 10 categories. By using the `top_n_functype` parameter, you can increase this limit (up to 50) to gain a much more granular understanding of the urban fabric. This is essential for identifying low-frequency but high-importance land uses like schools, medical facilities, or infrastructure buildings that might otherwise be hidden.

**Request:**
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/buildings/stats?lat=42.6958&lon=23.3219&radius_m=300&top_n_functype=20"
```

**Response:**
```json
{
  "query": {
    "kind": "radius",
    "lat": 42.6958,
    "lon": 23.3219,
    "radius_m": 300.0,
    "include_boundary": true
  },
  "region_area_m2": 281307.69,
  "building_count": 329,
  "stats": {
    "sum_building_area_m2": 160036.38,
    "mean_area_m2": 486.43,
    "sum_gfa_est_m2": 853026.30,
    "functype_top": [
      {"functype": "Жилищна сграда - многофамилна", "count": 100},
      {"functype": "Административна, делова сграда", "count": 93},
      {"functype": "Жилищна сграда - еднофамилна", "count": 21},
      {"functype": "Сграда за търговия", "count": 17},
      {"functype": "Друг вид производствена, складова, инфраструктурна сграда", "count": 14},
      {"functype": "Постройка на допълващото застрояване", "count": 11},
      {"functype": "Друг вид обществена сграда", "count": 9},
      {"functype": "Култова, религиозна сграда", "count": 9},
      {"functype": "Сграда за култура и изкуство", "count": 8},
      {"functype": "Сграда за енергопроизводство", "count": 7},
      {"functype": "Сграда със смесено предназначение", "count": 6},
      {"functype": "Друг вид сграда за обитаване", "count": 6},
      {"functype": "Хотел", "count": 5},
      {"functype": "Сграда за обществено хранене", "count": 5},
      {"functype": "Жилищна сграда със смесено предназначение", "count": 4},
      {"functype": "Сграда на транспорта", "count": 4},
      {"functype": "Гараж", "count": 3},
      {"functype": "Сграда на съобщенията", "count": 2},
      {"functype": "Сграда за образование", "count": 1},
      {"functype": "Сграда за детско заведение", "count": 1}
    ]
  },
  "nearest_building": { ... }
}
```

---

### **Analytical Insight**

*   **Discovering Rare Assets:** In the default Top 10 list, you would only see broad categories like "Residential" and "Administrative." By expanding to Top 20, we reveal that this specific 300m radius contains exactly **one school** (`Сграда за образование`) and **one childcare facility** (`Сграда за детско заведение`).
*   **Infrastructure Granularity:** We can now see specific utility buildings like **Garages**, **Transport buildings**, and **Communication buildings** (`Сграда на съобщенията`) which provide a much clearer picture of the neighborhood's service infrastructure.
*   **Residential Variety:** The expanded list separates standard multi-family housing from **Mixed-use residential** buildings, which is a key indicator of urban vibrancy and commercial activity at the street level.

### **Parameter Details**

| Parameter | Default | Max | Description |
| :--- | :--- | :--- | :--- |
| `top_n_functype` | 10 | 50 | Number of categories to return in the `functype_top` list. |

**Note:** For general reporting, Top 10 is sufficient. For detailed urban planning or site selection (e.g., finding areas with low educational coverage), Top 20 or higher is recommended.

---

### **Input Parameters**

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `bbox` | `string` | Conditional | Bounding box coordinates: `min_lon,min_lat,max_lon,max_lat`. |
| `lat` | `float` | Conditional | Latitude of center point. |
| `lon` | `float` | Conditional | Longitude of center point. |
| `radius_m` | `integer` | Conditional | Search radius in meters. |
| `include_boundary` | `boolean` | No | Whether to include boundary-touching buildings (default: `true`). |
| `center_lat` | `float` | No | Reference latitude for nearest building identification. |
| `center_lon` | `float` | No | Reference longitude for nearest building identification. |
| `include_nearest_geometry` | `boolean` | No | Include full GeoJSON geometry of nearest building (default: `false`). |
| `top_n_functype` | `integer` | No | Number of top function types to return (default: 10, max: 50). |

### **Output Structure**

```json
{
  "query": {
    "kind": "radius" | "bbox",
    "lat": 42.6958,  // For radius queries
    "lon": 23.3219,  // For radius queries
    "radius_m": 300.0,
    "include_boundary": true,
    "bbox": [23.32, 42.695, 23.325, 42.6975]  // For bbox queries
  },
  "region_area_m2": 281307.6929366558,
  "building_count": 329,
  "building_density_per_km2": 1169.5378699582293,
  "coverage_ratio": 0.47011747829157824,
  "stats": {
    "sum_building_area_m2": 160036.3817709517,
    "sum_building_area_clipped_m2": 132247.66322740223,
    "mean_area_m2": 486.43277134027875,
    "median_area_m2": 239.0426136107945,
    "p90_area_m2": 865.4549069752134,
    "mean_perimeter_m": 88.85988694602747,
    "median_perimeter_m": 68.37064199326144,
    "mean_compactness": 0.6134015804743117,
    "median_compactness": 0.6351030383460656,
    "mean_flrcount": 4.264437689969605,
    "median_flrcount": 5.0,
    "p90_flrcount": 7.0,
    "sum_gfa_est_m2": 853026.3007817777,
    "year_built_known_count": 122,
    "mean_year_built": 1940.8360655737704,
    "median_year_built": 1938.0,
    "functype_top": [
      {"functype": "Жилищна сграда - многофамилна", "count": 100},
      {"functype": "Административна, делова сграда", "count": 93},
      {"functype": "Жилищна сграда - еднофамилна", "count": 21}
    ]
  },
  "nearest_building": {
    "id": 178846,
    "distance_m": 0.0,
    "properties": {
      "_area": 1166.2483320161,
      "_perim": 152.90276123226,
      "cadnum": "68134.100.13.1",
      "immaddr": "гр. София, район Средец, пл.\"Света Неделя\" №19",
      "functype": "Сграда за образование",
      "flrcount": 4
    },
    "feature": {  // Only included when include_nearest_geometry=true
      "type": "Feature",
      "geometry": { ... },
      "properties": { ... },
      "id": 178846
    }
  }
}
```

### **Statistics Metrics**

*   **`region_area_m2`**: Total area of the query region in square meters.
*   **`building_count`**: Number of buildings in the region.
*   **`building_density_per_km2`**: Building density per square kilometer.
*   **`coverage_ratio`**: Proportion of land area covered by buildings.
*   **`sum_building_area_m2`**: Total footprint area of all buildings.
*   **`sum_building_area_clipped_m2`**: Total area clipped to region boundary.
*   **`mean/median_area_m2`**: Average building footprint area.
*   **`p90_area_m2`**: 90th percentile of building areas.
*   **`mean/median_perimeter_m`**: Average building perimeter.
*   **`mean/median_compactness`**: Shape compactness metrics (higher = more compact).
*   **`mean/median_flrcount`**: Average number of floors.
*   **`sum_gfa_est_m2`**: Estimated Gross Floor Area.
*   **`year_built_*`**: Construction year statistics.
*   **`functype_top`**: Top building function types with counts.

**Notes:**
- The statistics endpoint provides comprehensive urban metrics for planning and analysis.
- Use `include_nearest_geometry=true` to get the full GeoJSON of the nearest building.
- The `functype_top` list can be customized with `top_n_functype` parameter.