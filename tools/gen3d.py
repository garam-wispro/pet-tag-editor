# -*- coding: utf-8 -*-
"""반려동물 인식표 3D 프린트용 모델 (단위 mm). 모양 4종, L 사이즈.
구조: 판 두께 T, 앞면은 테두리(폭 RIM)와 이름·고리만 남기고 DEPTH만큼 낮춘 색면."""
import math, os, sys
import numpy as np
import trimesh
from shapely.geometry import Point, Polygon, MultiPolygon, box, LineString
from shapely.ops import unary_union
from shapely import affinity
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties

T = 2.0          # 판 두께
DEPTH = 0.2      # 색면이 테두리보다 낮은 깊이 (실제 제품은 약 0.1mm, 프린터로 보이게 0.2mm)
RIM = 1.5        # 테두리 폭
LUG_R, HOLE_R = 3.0, 1.3
RES = 48
FONT = r"C:\Windows\Fonts\ARLRDBD.TTF"   # Arial Rounded MT Bold (PC에 있는 둥근 글씨체)


def circle_shape(D):
    return Point(D / 2, D / 2).buffer(D / 2, RES * 2)


def rect_shape(W, H):
    r = H * 0.27
    return box(r, r, W - r, H - r).buffer(r, RES)


def bone_shape(W, H):
    r, g = 0.29 * H, 0.14 * H
    lobes = [Point(x, y).buffer(r, RES) for x in (r, W - r) for y in (r, H - r)]
    s = unary_union(lobes + [box(r * 0.9, g, W - r * 0.9, H - g)])
    f = 0.07 * H
    return s.buffer(f, RES).buffer(-f, RES)


def heart_shape(W, alpha_deg=53.0):
    r, d, H = 0.27 * W, 0.23 * W, 0.92 * W
    al = math.radians(alpha_deg)
    c, s, h = math.cos(al), math.sin(al), H - r
    R = (r * r - d * d - h * h) / (2 * (c * d - h * s + r))
    cxr, cyr = W / 2 - R * c, H - R * s
    n = math.hypot(W / 2 + d - cxr, r - cyr)
    yt = r + r * (r - cyr) / n
    lens = Point(cxr, cyr).buffer(R, 720).intersection(Point(W - cxr, cyr).buffer(R, 720)).intersection(box(-W, yt, 2 * W, 2 * H))
    lobes = [Point(W / 2 - d, r).buffer(r, RES * 2), Point(W / 2 + d, r).buffer(r, RES * 2)]
    s_ = unary_union(lobes + [lens, box(W / 2 - d, r, W / 2 + d, yt + 0.02 * W)])
    cl = 0.04 * W
    s_ = s_.buffer(cl, RES).buffer(-cl, RES)
    op = 0.035 * W
    return s_.buffer(-op, RES).buffer(op, RES)


def top_at_center(shape, cx):
    b = shape.bounds
    return LineString([(cx, b[1] - 1), (cx, b[3] + 1)]).intersection(shape).bounds[1]


def text_geom(s):
    """글자를 다각형으로 (짝수-홀수 채움으로 구멍 처리). y는 위쪽이 +."""
    tp = TextPath((0, 0), s, size=10, prop=FontProperties(fname=FONT))
    g = None
    for ring in tp.to_polygons(closed_only=True):
        if len(ring) < 4:
            continue
        p = Polygon(ring).buffer(0)
        g = p if g is None else g.symmetric_difference(p)
    return g


def polys(g):
    if g.is_empty:
        return []
    return [g] if g.geom_type == "Polygon" else [p for p in g.geoms if p.geom_type == "Polygon" and p.area > 1e-6]


def extrude(g, z0, z1):
    parts = []
    for p in polys(g):
        m = trimesh.creation.extrude_polygon(p, z1 - z0)
        m.apply_translation((0, 0, z0))
        parts.append(m)
    return parts


def build(kind, size, name):
    if kind == "circle":
        base = circle_shape(size)
    elif kind == "rect":
        base = rect_shape(*size)
    elif kind == "bone":
        base = bone_shape(*size)
    else:
        base = heart_shape(size)
    W, H = base.bounds[2], base.bounds[3]
    cx = W / 2
    ly = top_at_center(base, cx) - (1.7 if kind == "heart" else 1.8)
    lug, hole = Point(cx, ly).buffer(LUG_R, RES), Point(cx, ly).buffer(HOLE_R, RES)
    inner = base.buffer(-RIM, RES)
    flip = lambda g: affinity.scale(g, 1, -1, origin=(0, 0))      # 화면 좌표(y 아래)를 y 위쪽으로
    base_u, inner_u, lug_u, hole_u = flip(base), flip(inner), flip(lug), flip(hole)
    # 이름: 색면 안에 테두리와 같은 높이로 남긴다
    tg = text_geom(name)
    tb = tg.bounds
    fit = {"circle": (0.60 * W, 0.26 * H, 0.50), "rect": (0.56 * W, 0.40 * H, 0.50),
           "bone": (0.44 * W, 0.34 * H, 0.50), "heart": (0.52 * W, 0.26 * H, 0.47)}[kind]
    k = min(fit[0] / (tb[2] - tb[0]), fit[1] / (tb[3] - tb[1]))
    tg = affinity.scale(tg, k, k, origin=(0, 0))
    tb = tg.bounds
    tg = affinity.translate(tg, cx - (tb[0] + tb[2]) / 2, -H * fit[2] - (tb[1] + tb[3]) / 2)
    gap = tg.distance(base_u.difference(inner_u).union(lug_u))    # 글자와 테두리·고리 사이 최소 간격
    footprint = base_u.union(lug_u).difference(hole_u)
    top = base_u.difference(inner_u).union(lug_u).union(tg.intersection(inner_u)).difference(hole_u)
    parts = extrude(footprint, 0, T - DEPTH) + extrude(top, T - DEPTH - 0.6, T)   # 윗층은 아래로 0.6mm 겹쳐 한 덩어리로
    mesh = trimesh.boolean.union(parts, engine="manifold")
    mesh.merge_vertices()
    info = dict(W=W, H=H, text_h=tb[3] - tb[1], text_w=tb[2] - tb[0], gap=gap, lug_top=-(ly - LUG_R))
    return mesh, info


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    items = [("원형-L-30mm", "circle", 30, "Mochi"), ("하트-L-30mm", "heart", 30, "Nabi"),
             ("뼈다귀-L-40x22mm", "bone", (40, 22), "Coco"), ("라운드사각-L-40x22mm", "rect", (40, 22), "Dubu")]
    plate, x = [], 0.0
    for fn, kind, size, name in items:
        m, info = build(kind, size, name)
        b = m.bounds
        print("%s: 크기 %.2f x %.2f x %.2f mm, 본체 %.1f x %.1f, 글자 %.1f x %.1f mm, 글자-테두리 간격 %.2f mm, 부피 %.0f mm3, 닫힌 메시=%s, 덩어리 %d, 삼각형 %d"
              % (fn, b[1][0] - b[0][0], b[1][1] - b[0][1], b[1][2] - b[0][2], info["W"], info["H"], info["text_w"], info["text_h"],
                 info["gap"], m.volume, m.is_watertight, len(m.split(only_watertight=False)), len(m.faces)))
        m.export(os.path.join(out, "인식표-%s.stl" % fn))
        c = m.copy(); c.apply_translation((x - b[0][0], -b[1][1], 0)); plate.append(c)
        x += (b[1][0] - b[0][0]) + 6
    allm = trimesh.util.concatenate(plate)
    allm.export(os.path.join(out, "인식표-4종-한판.stl"))
    b = allm.bounds
    print("한판: %.1f x %.1f x %.1f mm" % tuple(b[1] - b[0]))
