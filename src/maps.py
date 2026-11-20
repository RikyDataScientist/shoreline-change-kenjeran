import numpy as np
import pandas as pd
import folium
from pyproj import Transformer
import os

def load_data(path):
    for dirname, _, filenames in os.walk( os.curdir):
        if path in filenames:
            return os.path.join(dirname, path)

def init_file(F_ANALISIS, F_RAMALAN, OUT_DIR):
    obs = pd.read_csv(F_ANALISIS)
    pred = pd.read_csv(F_RAMALAN)

    th = np.radians(obs["azimuth"])
    obs["ox"] = obs["Longitude_UTM"] - obs["Shoreline_Distance"] * np.sin(th)
    obs["oy"] = obs["Latitude_UTM"] - obs["Shoreline_Distance"] * np.cos(th)

    transek = (
        obs.groupby("Transect_ID")
        .agg(ox=("ox", "median"), oy=("oy", "median"), azimuth=("azimuth", "first"),
            lrr=("lrr", "first"), epr=("epr", "first"), nsm=("nsm", "first"),
            sce=("sce", "first"))
        .reset_index()
    )

    p = pred.merge(transek, on="Transect_ID", how="left", validate="m:1")
    didnt_match = p[p["ox"].isna()]["Transect_ID"].unique()
    if len(didnt_match):
        print("Transect_ID ramalan tanpa padanan di dataset analisis:", didnt_match)

    p = p.dropna(subset=["ox"]).copy()
    thp = np.radians(p["azimuth"])
    p["Shoreline_Distance"] = p["Shoreline_Distance_Pred"]
    p["Longitude_UTM"] = p["ox"] + p["Shoreline_Distance"] * np.sin(thp)
    p["Latitude_UTM"] = p["oy"] + p["Shoreline_Distance"] * np.cos(thp)
    p["Status"] = "Prediksi"

    o = obs[["Transect_ID", "Tahun", "Shoreline_Distance", "Longitude_UTM", "Latitude_UTM",
            "azimuth", "lrr", "epr", "nsm", "sce"]].copy()
    o["Status"] = "Observasi"
    cols = list(o.columns)
    merged_df = pd.concat([o, p[cols]], ignore_index=True)

    tf = Transformer.from_crs(32749, 4326, always_xy=True)
    merged_df["lon"], merged_df["lat"] = tf.transform(merged_df["Longitude_UTM"].values,
                                                merged_df["Latitude_UTM"].values)
    merged_df = merged_df.sort_values(["Tahun", "Transect_ID"]).reset_index(drop=True)
    merged_df.to_csv(os.path.join('data', "data_merged_df_pred.csv"), index=False)

    return merged_df

def create_map(df, judul, tahun_default, filename):
    pusat = [df["lat"].mean(), df["lon"].mean()]
    m = folium.Map(location=pusat, zoom_start=15, tiles=None, control_scale=True)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)
    folium.TileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Satelit (Esri)").add_to(m)

    for thn in sorted(df["Tahun"].unique()):
        d = df[df["Tahun"] == thn].sort_values("Transect_ID")
        fg = folium.FeatureGroup(name=f"Garis pantai {thn}", show=(thn == tahun_default))
        
        warna_garis = "green" if thn == 2025 else "purple"
        folium.PolyLine(d[["lat", "lon"]].values.tolist(), color=warna_garis, weight=2,
                        opacity=0.8).add_to(fg)
        
        for r in d.itertuples():
            if thn == 2025:
                warna_titik = "green" 
            else:
                warna_titik = "purple" 

            popup = (f"<b>Transect {r.Transect_ID}</b><br>Tahun: {r.Tahun} ({r.Status})<br>"
                     f"Jarak: {r.Shoreline_Distance:.2f} m<br>"
                     f"LRR: {r.lrr:.4f} | EPR: {r.epr:.4f}<br>"
                     f"NSM: {r.nsm:.2f} | SCE: {r.sce:.2f}")
            
            folium.CircleMarker([r.lat, r.lon], radius=5,
                                color="#222", weight=0.5, fill=True,
                                fill_color=warna_titik,
                                fill_opacity=0.9,
                                tooltip=f"T{r.Transect_ID} | {r.Shoreline_Distance:.1f} m",
                                popup=folium.Popup(popup, max_width=250)).add_to(fg)
        fg.add_to(m)
    
    folium.LayerControl(collapsed=False).add_to(m)
    title = (f'<div style="position:fixed;top:10px;left:50px;z-index:9999;'
                  f'background:white;padding:6px 12px;border-radius:6px;'
                  f'box-shadow:0 1px 4px rgba(0,0,0,.4);font:600 14px sans-serif">{judul}</div>')
    
    m.get_root().html.add_child(folium.Element(title))
    m.save(os.path.join(OUT_DIR, filename))
    print("Tersimpan:", filename)

def main():
    global OUT_DIR
    F_ANALISIS = load_data("dataset_analisis_pantai_kenjeran.csv")
    F_RAMALAN = load_data("hasil_ramalan_pantai_kenjeran_2026_2030.csv")
    OUT_DIR = "maps"
    os.makedirs(OUT_DIR, exist_ok=True)

    merged_df = init_file(F_ANALISIS, F_RAMALAN, OUT_DIR)
    bevor = merged_df[merged_df["Status"] == "Observasi"]
    after = merged_df[merged_df["Status"] == "Prediksi"]

    create_map(bevor, 
               "SEBELUM Prediksi - Observasi 2015-2025", 
               2025,
               "sebelum_prediksi.html")

    create_map(pd.concat([bevor[bevor["Tahun"] == 2025], after]),
               "SESUDAH Prediksi - Ramalan 2026-2030", 
               2030,
               "sesudah_prediksi.html")

main()