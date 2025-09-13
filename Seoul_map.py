# cd "C:\Python Custom Programs\Seoul Map"
# https://pythonee1.github.io/Seoul-Map/


# --- Seoul dong hover map with Excel stats + thick GU borders ---
# pip install pandas geopandas folium shapely pyproj requests openpyxl

import io, json, requests, webbrowser
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import Search, MiniMap, Fullscreen
from branca.colormap import LinearColormap
from branca.element import Element

# 1) Paths
EXCEL_PATH = r"Seoul DB.xlsx"   # <-- your Excel file
EXCEL_SHEET = 0                         # sheet name or index
out_html = "index.html"

# 2) Source GeoJSON for Seoul administrative dongs
GEO_URL = ("https://raw.githubusercontent.com/raqoon886/Local_HangJeongDong/master/"
           "hangjeongdong_%EC%84%9C%EC%9A%B8%ED%8A%B9%EB%B3%84%EC%8B%9C.geojson")

def fetch_geojson(url: str):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return gpd.read_file(io.BytesIO(r.content))

def extract_gu_dong(adm_nm: str):
    # adm_nm example: "서울특별시 강남구 역삼동"
    parts = str(adm_nm).split()
    gu = next((p for p in parts if p.endswith("구")), None)
    dong = None
    if parts:
        cand = parts[-1]
        if cand.endswith(("동", "가")):
            dong = cand
        else:
            for p in reversed(parts):
                if p.endswith(("동", "가")):
                    dong = p
                    break
    return gu, dong

def format_int(n):
    try:
        return f"{int(round(float(n))):,}"
    except Exception:
        return ""

def main():
    # A) Load polygons (dong)
    gdf = fetch_geojson(GEO_URL).copy()
    gdf[["구","행정동"]] = gdf["adm_nm"].apply(lambda s: pd.Series(extract_gu_dong(s)))

    # B) Load Excel stats
    df = pd.read_excel(EXCEL_PATH, sheet_name=EXCEL_SHEET)

    # Normalize join keys
    for col in ["구","행정동"]:
        if col in df.columns: df[col] = df[col].astype(str).str.strip()
    for col in ["구","행정동"]:
        gdf[col] = gdf[col].astype(str).str.strip()

    # Compute density if missing/blanks
    if "km2당 인구" not in df.columns:
        df["km2당 인구"] = df["인구 (2024)"] / df["면적 (km2)"]
    else:
        df["km2당 인구"] = df["km2당 인구"].where(
            df["km2당 인구"].notna(),
            df["인구 (2024)"] / df["면적 (km2)"]
        )

    # C) Merge stats onto polygons (dong-level)
    cols_needed = ["구","행정동","면적 (km2)","인구 (2024)","km2당 인구"]
    missing = [c for c in cols_needed if c not in df.columns]
    if missing:
        raise ValueError(f"Excel is missing required columns: {missing}")

    mg = gdf.merge(df[cols_needed], on=["구","행정동"], how="left", validate="m:1")
    try:
        mg["geometry"] = mg.buffer(0)
    except Exception:
        pass

    # Display-friendly strings
    mg["면적_disp"] = mg["면적 (km2)"].astype(float).round(3).astype(str)
    mg["인구_disp"] = mg["인구 (2024)"].apply(format_int)
    mg["밀도_disp"] = mg["km2당 인구"].astype(float).round(1).map(lambda x: f"{x:,.0f}")

    # D) Map base
    m = folium.Map(location=[37.5665, 126.9780], zoom_start=11,
                   tiles="CartoDB positron", control_scale=True)

    # Dong layer (thin)
    def style_fn(_):
        return {"fillColor": "#ffffff", "color": "#666666", "weight": 0.6, "fillOpacity": 0.15}
    def highlight_fn(_):
        return {"weight": 2.2, "color": "#000000", "fillOpacity": 0.45}

    tooltip = folium.features.GeoJsonTooltip(
        fields=["구", "행정동", "면적_disp", "인구_disp", "밀도_disp"],
        aliases=["구", "행정동", "면적 (km2)", "인구 (2024)", "km2당 인구"],
        sticky=False, opacity=0.95, direction="auto"
    )


    breaks = list(range(5000, 60001, 5000))
    base_cmap = LinearColormap(
        colors=["#ffffff", "#ffe5e5", "#ffb3b3", "#ff8080", "#ff4d4d", "#ff1a1a", "#e60000", "#b30000"],
        vmin=min(breaks), vmax=max(breaks),
    )
    cmap = base_cmap.to_step(index=breaks)
    cmap.caption = "인구밀도 (명 / km²)"

    def style_choro(feature):
        val = feature["properties"].get("km2당 인구")
        color = "#dddddd" if val is None else cmap(val)
        return {
            "fillColor": color,
            "color": "#aaaaaa",          # border color
            "weight": 0.4,               # border thickness
            "fillOpacity": 0.75          # THIS is what fills the polygon
        }



    layer_choro = folium.FeatureGroup(name="인구밀도 (색상)", overlay=True, show=True)
    folium.GeoJson(
        data=json.loads(mg.to_json()),
        name="인구밀도 (색상)",
        style_function=style_choro,
        highlight_function=None,
        tooltip=None,
        zoom_on_click=False,
        smooth_factor=0.2
    ).add_to(layer_choro)
    layer_choro.add_to(m)


    # E) **GU borders (thick) — this is the integration you asked for**
    gdf_gu = mg.dissolve(by="구", as_index=False)
    folium.GeoJson(
        data=json.loads(gdf_gu.to_json()),
        name="구 경계",
        style_function=lambda x: {"fillOpacity": 0, "color": "#001F3F", "weight": 2.8},
        highlight_function=lambda x: {"weight": 3.6, "color": "#FF0000"},
        tooltip=folium.GeoJsonTooltip(fields=["구"], aliases=["구"])
    ).add_to(m)

    gj_dong = folium.GeoJson(
        data=json.loads(mg.to_json()),
        name="행정동",
        style_function=style_fn,
        highlight_function=highlight_fn,
        tooltip=tooltip,
        zoom_on_click=False,
        smooth_factor=0.2
    ).add_to(m)



    # 4. Add color legend
    cmap.add_to(m)

    # Extras
    Search(layer=gj_dong, geom_type="Polygon", search_label="행정동",
           placeholder="동 이름 검색", collapsed=False).add_to(m)
    MiniMap(toggle_display=True, position="bottomright").add_to(m)
    Fullscreen().add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)

    css = """
    <style>
    .leaflet-tooltip { font-size: 16px; font-weight: bold; color: #111111; }
    </style>
    """

    m.get_root().header.add_child(Element(css))

    m.save(out_html)
    print(f"[OK] Saved {out_html}")
    try:
        webbrowser.open(out_html)
    except Exception:
        pass

if __name__ == "__main__":
    main()
