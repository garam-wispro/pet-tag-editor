# -*- coding: utf-8 -*-
"""인식표 도형 데이터(shapes.json) 생성. 단위 mm, 원점은 '고리 포함 외곽'의 왼쪽 위, y는 아래로 증가.
사용: python tools/make_shapes.py  ->  tools/shapes.json  (index.html의 SHAPES 상수에 붙여 넣는다)"""
import io, json, os, sys
from shapely.geometry import Point, LineString
from shapely import affinity
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen3d as g

RES = 48
VARS = [("circle", "S", 25, 1.2), ("circle", "L", 30, 1.5), ("heart", "S", 25, 1.2), ("heart", "L", 30, 1.5),
        ("bone", "S", (30, 18), 1.2), ("bone", "L", (40, 22), 1.5), ("rect", "S", (30, 18), 1.2), ("rect", "L", (40, 22), 1.5)]


def d_of(poly, tol=0.004):
    poly = poly.simplify(tol)
    polys = [poly] if poly.geom_type == "Polygon" else list(poly.geoms)
    out = []
    for p in polys:
        for ring in [p.exterior] + list(p.interiors):
            out.append("M" + "L".join("%.2f %.2f" % c for c in ring.coords[:-1]) + "Z")
    return "".join(out)


out = {}
for kind, sz, size, rim in VARS:
    base = {"circle": lambda: g.circle_shape(size), "heart": lambda: g.heart_shape(size),
            "bone": lambda: g.bone_shape(*size), "rect": lambda: g.rect_shape(*size)}[kind]()
    W, H = base.bounds[2], base.bounds[3]
    cx = W / 2
    ly = g.top_at_center(base, cx) - (1.7 if kind == "heart" else 1.8)
    lug, hole = Point(cx, ly).buffer(g.LUG_R, RES), Point(cx, ly).buffer(g.HOLE_R, RES)
    outline = base.union(lug)
    face = base.buffer(-rim, RES).difference(lug)
    dy = -outline.bounds[1]
    mv = lambda s: affinity.translate(s, 0, dy)
    outline, face, hole = mv(outline), mv(face), mv(hole)
    TH = outline.bounds[3]
    chords = []  # 인쇄면을 y(0.25mm 간격)에서 가로로 자른 구간 중 가운데(cx)에 가장 가까운 구간
    y = 0.0
    while y <= TH + 1e-6:
        seg = face.intersection(LineString([(-5, y), (W + 5, y)]))
        best = None
        if not seg.is_empty:
            for s in ([seg] if seg.geom_type == "LineString" else [q for q in seg.geoms if q.geom_type == "LineString"]):
                a, b = s.bounds[0], s.bounds[2]
                if a <= cx <= b and (best is None or b - a > best[1] - best[0]):
                    best = (a, b)
        chords.append([round(best[0], 2), round(best[1], 2)] if best else None)
        y += 0.25
    fb = face.bounds
    out["%s%s" % (kind, sz)] = {"w": round(W, 2), "h": round(TH, 2), "bodyTop": round(dy, 2), "bodyH": round(H, 2), "rim": rim,
                                "hole": [round(cx, 2), round(ly + dy, 2), g.HOLE_R], "outline": d_of(outline), "face": d_of(face),
                                "faceBox": [round(v, 2) for v in fb], "chordStep": 0.25, "chords": chords}
    print(kind, sz, "w %.2f h %.2f faceBox %s outline %d face %d chars" % (W, TH, [round(v, 1) for v in fb], len(d_of(outline)), len(d_of(face))))
io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "shapes.json"), "w", encoding="utf-8").write(json.dumps(out, separators=(",", ":")))
