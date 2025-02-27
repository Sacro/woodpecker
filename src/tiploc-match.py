#!/usr/bin/env python3

import json
import datetime as dt
import io
import os
import warnings

import networkx as nx
import pandas as pd

os.environ["USE_PYGEOS"] = "0"
import geopandas as gp
from pyogrio import read_dataframe, write_dataframe
from shapely import line_locate_point
from shapely.ops import nearest_points

pd.set_option("display.max_columns", None)

START = dt.datetime.now()

CRS = "EPSG:32630"
CENTRE2CENTRE = 3.26


def get_wnx(gx, points):
    try:
        edges = [LineString(points[np.array(i)]) for i in gx.edges]
    except KeyError:
        return get_wnx(gx, points.values)
    return gp.GeoSeries(edges).rename("geometry").set_crs(CRS)


def get_delaunay(this_nx):
    delaunay = Delaunay.from_dataframe((this_nx))
    dx = delaunay.to_networkx()
    DF2 = nx.to_pandas_edgelist(DX)[["source", "target"]]
    EDGES = gp.GeoDataFrame(get_wnx(dx, this_nx["geometry"]))
    EDGES = EDGES.join(DF2)
    EDGES["source"] = NX["em class"].values[EDGES["source"]]
    EDGES["target"] = NX["em class"].values[EDGES["target"]]
    EDGES.to_crs(CRS).to_file(FILEPATH, driver="GPKG", layer="D1")
    IDX3 = EDGES[(EDGES["source"] > -1) & (EDGES["target"] > -1)].index
    EDGES = EDGES.loc[IDX3]
    EDGES["distance"] = EDGES.length
    EDGES.to_crs(CRS).to_file(FILEPATH, driver="GPKG", layer="D2")


def fix_xmlfile(path):
    """Download data from URI and returns as a buffer"""
    r = io.StringIO()
    r.write("<fixxmltag>\n")
    r.write(open(path).read())
    r.write("</fixxmltag>\n")
    r.seek(0)
    return "".join(r)


def get_xmlstannox(inpath, file_crs="WGS84"):
    buffer = fix_xmlfile(inpath)
    stanox_code = pd.read_xml(buffer, xpath="//ea").dropna(axis=1)
    data = pd.read_xml(buffer, xpath="//e")
    data = pd.concat([stanox_code, data], axis=1)
    data["STANOX"] = stanox_code["Stanox"].astype(str).str.zfill(5)
    fields = ["longitude", "latitude"]
    points = gp.GeoSeries.from_xy(*data[fields].values.T, crs=file_crs)
    fields = data.columns.difference(fields)
    r = gp.GeoDataFrame(data=data[fields], geometry=points)
    return r.to_crs(CRS)


def get_corpus(inpath):
    with open(inpath, "r") as fin:
        data = json.load(fin)
        r = pd.json_normalize(data, "TIPLOCDATA")
    ix = r[r["STANOX"].str.strip() > ""].index
    r.loc[ix, "STANOX"] = r.loc[ix, "STANOX"].str.zfill(5)
    r["NLC"] = r["NLC"].astype(str)
    return r.drop_duplicates().reset_index(drop=True)


def get_osgb36(inpath, file_crs="EPSG:27700"):
    df = pd.read_csv(
        inpath,
        header=None,
        names=["STANOX", "northing", "easting"],
        dtype={"STANOX": "str"},
    )
    data = df["STANOX"]
    fields = ["northing", "easting"]
    points = gp.GeoSeries.from_xy(*df[fields].values.T, crs=file_crs)
    r = gp.GeoDataFrame(data=data, geometry=points, crs=file_crs)
    return r.to_crs(CRS).drop_duplicates(subset="STANOX").reset_index(drop=True)


def round_point_geometry(this_gf):
    r = this_gf["geometry"]
    return gp.points_from_xy(r.x.round(1), r.y.round(1))


def get_stanox(corpus, *stanoxes):
    r = pd.concat(stanoxes).dropna(axis=1)
    r = r.drop_duplicates(subset="STANOX")
    r = r.join(corpus.set_index("STANOX"), on="STANOX").fillna("")
    return r.sort_values("STANOX").reset_index(drop=True).set_crs(CRS)


def get_tiploc(stanox, corpus):
    r = stanox.join(corpus.set_index("STANOX"), on="STANOX").fillna("")
    return r.drop_duplicates(subset="TIPLOC")


def get_outputx(inpath, layer="osmnx"):
    r = read_dataframe(inpath, layer=layer)
    r = r.sort_values("ref", ascending=False)
    r = r.drop_duplicates(subset="geometry").sort_index()
    return r.reset_index(drop=True)


def get_buffer(gs, width=4):
    # style = {"cap_style": "square", "join_style": "mitre", "mitre_limit": length}
    style = {"cap_style": "flat"}
    gs = gs["geometry"].copy()
    return gs.buffer(width, **style)


def get_overlap(gf1, gf2):
    data = []
    gf1 = gf1.copy()
    gf1["n"] = gf1.reset_index().index
    for k, v in gf1["geometry"].items():
        n = gf1.loc[k, "n"]
        if (n % 4096) == 0:
            print(f"{k}\t{n}\t{round(n / gf1.shape[0], 3):.3f}")
            ix = gf2["geometry"].within(v)
            s = pd.Series({i: k for i in ix[ix].index})
            data.append(pd.Series(s.index, index=s))
    return pd.concat(data).rename_axis(gf1.index.name).rename(gf2.index.name)


def get_nearest_point(gs1, gs2):
    r = [nearest_points(*i)[0] for i in zip(gs1, gs2)]
    return gp.GeoSeries(r, crs=CRS).rename("geometry")


def get_offset(line, point):
    return line_locate_point(line, point)


def overlay_nx_waymark(
    network, waymarks, width=CENTRE2CENTRE, nxkey="ASSETID", wxkey="M_POST_ID"
):
    """overlay_nx_waymark: create a rectangular polygon buffer of given width
    on network line elements, and identify waymarks within the buffer
    Returns a GeoDataFrame of all line waymarks"""
    gf1 = network[[nxkey, "geometry"]]
    gf2 = waymarks[[wxkey, "geometry"]]

    this_buffer = get_buffer(gf1.set_index(nxkey), width=width)
    this_buffer = this_buffer.to_frame("geometry")
    ix = get_overlap(this_buffer, gf2.set_index(wxkey))
    ix = ix.reset_index().drop_duplicates()
    ix = ix.sort_values(nxkey).reset_index(drop=True)

    gs1 = gf1.set_index(nxkey).loc[ix[nxkey]]
    gs2 = gf2.set_index(wxkey).loc[ix[wxkey]]
    r = get_nearest_point(gs1["geometry"], gs2["geometry"]).to_frame()
    r.index = gs1.index
    r[wxkey] = gs2.index
    gf1 = gf1.set_index(nxkey)
    r["line"] = gf1.loc[r.index, "geometry"]
    r["offset"] = get_offset(r["line"], r["geometry"])
    return r.sort_values([nxkey, "offset"]).reset_index()


def get_split(v):
    line, point = v["line"], v["geometry"]
    return list(split(snap(line, point, separation), point).geoms)


def get_segment_id(v):
    p = gp.GeoSeries(v["geometry"]).to_frame("geometry").set_crs(CRS)
    return p


def drop_non_tiploc_geometry(this_gf):
    r = this_gf.copy()
    r = r.sort_values("TIPLOC").drop_duplicates(subset="geometry", keep="last")
    return r.sort_index()


def stanox_location(stanox, line):
    lx = line.to_frame("geometry")
    sx = drop_non_tiploc_geometry(stanox.copy())
    r = drop_non_tiploc_geometry(sx.sjoin_nearest(lx, distance_col="d"))
    r = r.reset_index(names="p_ix")
    r = r.rename(columns={"index_right": "ix"})
    key = "geometry"
    r[key] = get_nearest_point(lx.loc[r["ix"], key], r[key])
    field = ["STANOX", "TIPLOC", "3ALPHA", "UIC", "NLCDESC", "d", "geometry", "ix"]
    r = r.set_index("p_ix")
    return r[field]


def get_osmnx(stanox, ox):
    r = stanox_location(stanox, ox["geometry"])
    field = ["osmid", "name", "ref"]
    r = r.reset_index().set_index("ix")
    r[field] = ox.loc[ox.index, field]
    r = r.rename(columns={"ref": "ELR"}).reset_index()
    field = [
        "STANOX",
        "TIPLOC",
        "name",
        "ELR",
        "3ALPHA",
        "UIC",
        "NLCDESC",
        "osmid",
        "d",
        "geometry",
    ]
    return r[field]


def get_network(stanox, mx, *key):
    r = stanox_location(stanox, mx["geometry"])
    key = list(key)
    field = ["ASSETID", "L_SYSTEM", "ELR", "TRID", "L_M_FROM", "L_M_TO"] + key
    r = r.reset_index().set_index("ix")
    r[field] = mx.loc[r.index, field]
    r = r.reset_index()
    r["osmid"] = ""
    field = [
        "STANOX",
        "TIPLOC",
        "ELR",
        "3ALPHA",
        "UIC",
        "NLCDESC",
        "ASSETID",
        "L_SYSTEM",
        "TRID",
        "L_M_FROM",
        "L_M_TO",
        "osmid",
        "d",
        "geometry",
    ]
    return r[field + key]


def combine_network(ox, mx, *key):
    key = list(key)
    r = pd.concat([ox, mx]).sort_values(["STANOX", "d"])
    r = r.drop_duplicates(subset="STANOX")
    field = ["ASSETID", "L_SYSTEM", "TRID"] + key
    r[field] = r[field].fillna("")
    field = ["L_M_FROM", "L_M_TO"]
    r[field] = r[field].fillna(0.0)
    r = r.dropna(axis=1)
    field = [
        "STANOX",
        "TIPLOC",
        "ELR",
        "3ALPHA",
        "UIC",
        "NLCDESC",
        "ASSETID",
        "L_SYSTEM",
        "TRID",
        "L_M_FROM",
        "L_M_TO",
        "osmid",
        "d",
        "geometry",
    ]
    return r[field + key]


def main():
    print(f"STANOX start: {dt.datetime.now() - START}")
    outfile = "tiploc-location.gpkg"
    #hexagon = read_dataframe("hexagon4.gpkg", layer="hexagon4-00")
    #write_dataframe(hexagon.dissolve(), outfile, layer="hex")

    #post = read_dataframe("segmentx.gpkg", layer="post")
    segment = read_dataframe("segmentx.gpkg", layer="segment")
    corpus = get_corpus("CORPUSExtract.json")
    osmnx = get_outputx("outputx.gpkg", "osmnx")
    #write_dataframe(osmnx.to_crs(CRS), outfile, layer="osmnx")
    fullnx = get_outputx("outputx.gpkg", "fullnx")
    #write_dataframe(fullnx.to_crs(CRS), outfile, layer="fullnx")
    network = read_dataframe("outputx.gpkg", layer="network")
    #write_dataframe(network.to_crs(CRS), outfile, layer="network")

    OSGB36 = get_osgb36("stanox_to_osgb1936_2.csv")
    stanox = get_stanox(corpus, OSGB36)
    stanox["geometry"] = round_point_geometry(stanox)
    write_dataframe(stanox.to_crs(CRS), outfile, layer="STANOX")

    write_dataframe(get_osmnx(stanox, osmnx), outfile, layer="ox")
    ox = get_osmnx(stanox, fullnx)
    mx = get_network(stanox, network)
    write_dataframe(combine_network(ox, mx), outfile, layer="nx")
    mx = get_network(stanox, segment, 'segment_id', 'offset')
    ox['offset'] = 0.0
    write_dataframe(combine_network(ox, mx, 'offset'), outfile, layer="sx")
    segment = segment.set_index('segment_id')
    write_dataframe(segment.loc[mx['segment_id']], outfile, layer='segment')
    
    print(f"STANOX mapped: {dt.datetime.now() - START}")


if __name__ == "__main__":
    main()
