# coding = utf-8
from pysfcgal import sfcgal
from builtins import next
from builtins import str
from builtins import zip
from builtins import range
from builtins import object
import os
import random
from itertools import combinations
from math import pi as PI, inf as INF, sin
from numpy import array, cross, argmin, argmax, dot, average
from numpy.linalg import norm
from collections import defaultdict
from itertools import product
from shapely.geometry import (MultiPolygon, Polygon, LineString, MultiLineString,
                              Point, MultiPoint, mapping)
from shapely import wkb
from shapely.ops import unary_union, polygonize
from shapely.ops import transform
from shapely import geos
from shapely.affinity import translate
geos.WKBWriter.defaults['include_srid'] = True


def to_vtk(multiline):
    if multiline is None:
        return ''
    m = wkb.loads(bytes.fromhex(multiline))
    res = "# vtk DataFile Version 4.0\nvtk output\nASCII\nDATASET POLYDATA\n"
    node_map = {}
    nodes = ""
    elem = []
    n = 0
    for l in m:
        elem.append([])
        for c in l.coords:
            sc = "%f %f %f" % (tuple(c))
            if sc not in node_map:
                nodes += sc+"\n"
                node_map[sc] = n
                elem[-1].append(str(n))
                n += 1
            else:
                elem[-1].append(str(node_map[sc]))

    res += "POINTS {} float\n".format(len(node_map))
    res += nodes

    res += "\n"
    res += "LINES {} {}\n".format(len(elem), sum([len(e)+1 for e in elem]))

    for e in elem:
        res += "{} {}\n".format(len(e), " ".join(e))
    return res


def to_obj(multipoly):
    if multipoly is None:
        return ''
    m = wkb.loads(bytes.fromhex(multipoly))
    res = ""
    node_map = {}
    elem = []
    n = 0
    for p in m:
        elem.append([])
        for c in p.exterior.coords[:-1]:
            sc = "%f %f %f" % (tuple(c))
            if sc not in node_map:
                res += "v {}\n".format(sc)
                n += 1
                node_map[sc] = n
                elem[-1].append(str(n))
            else:
                elem[-1].append(str(node_map[sc]))
    for e in elem:
        res += "f {}\n".format(" ".join(e))
    return res


def interpolate_point(A, B, C, D):
    l = norm(A-B)
    r = norm(C-D)
    i = (r*A+r*B+l*C+l*D)/(2*(r+l))
    return i


def sym_split(l1, l2):
    if (l1[0][2] < l2[0][2] and l1[-1][2] > l2[-1][2]) \
            or (l1[0][2] > l2[0][2] and l1[-1][2] < l2[-1][2]):
        A, B, C, D = array(l1[0]), array(l2[0]), array(l1[-1]), array(l2[-1])
        interpolated = interpolate_point(A, B, C, D)
        for i, p in enumerate(reversed(l1)):
            if norm(interpolated - A) > norm(array(p) - A):
                l1.insert(-i, tuple(interpolated))
                break
        for i, p in enumerate(reversed(l2)):
            if norm(interpolated - B) > norm(array(p) - B):
                l2.insert(-i, tuple(interpolated))
                break
        return tuple(interpolated)
    return None


def share_an_edge(t, f):
    return 2 == len(set([tuple(x) for x in t.exterior.coords[:3]]
                        ).intersection(set([tuple(x) for x in f.exterior.coords[:3]])))


def face_edge_intersects(segment, crossing_segment):
    A, B, C, D = array(segment[0]), array(segment[1]), array(
        crossing_segment[0]), array(crossing_segment[1])
    return dot(cross(D-C, A-C), cross(D-C, B-C)) < 0


class Line(object):
    VERTICAL = 'vertical'
    TOP = 'top'
    BOTTOM = 'bottom'

    def __init__(self, points, side):
        self.side = side
        self.points = points
        for p in points:
            assert(isinstance(p, tuple))

    def midpoint_split(self):
        # split line at center if line has 2 points or closest point to center except end points
        # if line has more than two points
        A, B = self.points[0], self.points[-1]
        midpoint = (.5*(A[0]+B[0]), .5*(A[1]+B[1]), .5*(A[2]+B[2]))
        if len(self.points) == 2:
            self.points = [self.points[0], midpoint, self.points[-1]]
            return midpoint
        else:
            A, B, C = array(A), array(B), array(midpoint)
            distsq = dot(array(self.points[1:len(self.points)-1]), C)
            closest_idx = 1+argmin(distsq)
            return self.points[closest_idx]

    def has_segment(self, segment):
        for s, e in zip(self.points[:-1], self.points[1:]):
            if (s, e) == segment or (e, s) == segment:
                return True
        return False


def is_segment(segment, lines):
    for l in lines:
        if l.has_segment(segment):
            return True
    return False


def linemerge(lines):
    "3d linemerge, merges segments are removed from lines"
    merged = [list(lines.pop())] if len(lines) else []
    while len(lines):
        handled = False
        for j, b in enumerate(lines):
            if merged[-1][-1] == b[0]:
                merged[-1].append(b[1])
                handled = True
            elif merged[-1][0] == b[1]:
                merged[-1].insert(0, b[0])
                handled = True
            if handled:
                del lines[j]
                break
        if not handled:
            merged.append(list(lines.pop()))
    return merged


def has_proper_2d_topology(line):
    SIN_MIN_ANGLE = .01*PI/180
    l = line
    if len(l) <= 2:
        return False
    if l[0] != l[-1]:
        l.append(l[0])
    for a, b, c in zip(l[:-1], l[1:], l[2:]+[l[1]]):
        u = array((a[0], a[1])) - array((b[0], b[1]))
        v = array((c[0], c[1])) - array((b[0], b[1]))
        if dot(u, v) > 0:
            u /= norm(u)
            v /= norm(v)
            if norm(cross(u, v)) < SIN_MIN_ANGLE:
                return False
    return LineString(l).is_ring


def pair_of_non_coplanar_neighbors(n, graph, holes):
    if len(graph[n]) >= 2:
        neighbors = list(graph[n])
        for e in neighbors[1:]:
            if holes[e] != holes[neighbors[0]]:
                return (neighbors[0], e)
    return None


def normalized(u):
    return u/norm(u)


def offset_coords(offsets, coords):
    return [offsets[c] if c in offsets else c for c in coords]


def elementary_volumes(holes_, starts_, ends_, hole_ids_, node_ids_, nodes_, end_ids_, end_geoms_, end_holes_, srid_=32632, end_node_relative_distance=0.3, end_node_relative_thickness=.3):

    DEBUG = False
    PRECI = 6
    debug_files = []

    nodes = {id_: wkb.loads(bytes.fromhex(geom))
             for id_, geom in zip(node_ids_, nodes_)}
    ends = defaultdict(list)
    end_holes = defaultdict(list)
    for id_, geom, hole_id in zip(end_ids_, end_geoms_, end_holes_):
        ends[id_].append(wkb.loads(bytes.fromhex(geom)))
        end_holes[id_].append(hole_id)
    holes = {n: h for n, h in zip(node_ids_, hole_ids_)}
    edges = [(s, e) for s, e in zip(starts_, ends_)]
    #assert(len(edges) == len(set(edges)))
    #assert(len(holes_) == 3)
    #assert(set(hole_ids_).intersection(set(holes_)) == set(hole_ids_))
    #assert(set(end_holes_).intersection(set(holes_)) == set(end_holes_))

    # translate everything close to origin to avoid numerical issues
    translation = None
    for id_ in nodes.keys():
        if translation is None:
            translation = nodes[id_].coords[0]
        nodes[id_] = translate(
            nodes[id_], -translation[0], -translation[1], -translation[2])

    for id_ in ends.keys():
        for i in range(len(ends[id_])):
            ends[id_][i] = translate(
                ends[id_][i],  -translation[0], -translation[1], -translation[2])

    graph = defaultdict(set)  # undirected (edge in both directions)
    for e in edges:
        graph[e[0]].add(e[1])
        graph[e[1]].add(e[0])

    # two connected edges form a ring
    # /!\ do not do that for complex trousers configuration, this will
    # connect things that should not be connected
    #
    # indead it is stupid to do that here DO NOT TRY IT AGAIN
    #

    triangles = set()
    triangle_edges = set()
    triangle_nodes = set()
    for e in edges:
        common_neigbors = graph[e[0]].intersection(graph[e[1]])
        for n in common_neigbors:
            tri = tuple((i for _, i in sorted(
                zip((holes[e[0]], holes[e[1]], holes[n]), (e[0], e[1], n)))))
            triangles.add(tri)
            triangle_edges.add(tri[0:2])
            triangle_edges.add(tri[1:3])
            triangle_edges.add(tri[0:1]+tri[2:3])
            triangle_nodes.update(tri)

    # compute face offset direction for termination corners
    # termination coners are nodes that are not part of a triangle
    # and that have at leat 2 incident edges that are not in the same
    # face (i.e. different holes)
    unused_nodes = set(nodes.keys()).difference(triangle_nodes)
    offsets = {nodes[n].coords[0]: ends[n][0].coords[0]
               for n, l in list(ends.items()) if len(l) == 1}
    offsets.update({nodes[n].coords[-1]: ends[n][0].coords[-1]
                    for n, l in list(ends.items()) if len(l) == 1})
    for n in unused_nodes:
        p = pair_of_non_coplanar_neighbors(n, graph, holes)
        if p:
            A, B, C = array(nodes[n].coords[0][:2]), array(
                nodes[p[0]].coords[0][:2]), array(nodes[p[1]].coords[0][:2])
            c = average(array(nodes[n].coords), (0,))
            u = .5*(normalized(B-A)+normalized(C-A)) * \
                end_node_relative_distance*.5*(norm(B-A)+norm(C-A))
            thickness = abs(nodes[n].coords[0][2] - nodes[n].coords[-1][2])
            end_node_thickness = end_node_relative_thickness*thickness
            offsets[nodes[n].coords[0]] = tuple(
                c+array((u[0], u[1], +.5*end_node_thickness)))
            offsets[nodes[n].coords[-1]
                    ] = tuple(c+array((u[0], u[1], -.5*end_node_thickness)))

    if DEBUG:
        open('/tmp/offsets.vtk', 'w').write(
            to_vtk(MultiLineString([n for l in list(ends.values()) for n in l]).wkb_hex))

    sorted_holes = sorted(holes_)
    # face origin is the lowest bottom of the node in the first hole
    # face normal is

    face_idx = -1
    lines = []
    faces = defaultdict(list)
    result = []
    termination = []
    for hl, hr, other_hole in (
        (sorted_holes[0], sorted_holes[1], sorted_holes[2]),
        (sorted_holes[1], sorted_holes[2], sorted_holes[0]),
            (sorted_holes[0], sorted_holes[2], sorted_holes[1])):
        face_idx += 1
        direct_orientation = (hl, hr) == (holes_[0], holes_[1]) or (hl, hr) == (
            holes_[1], holes_[2]) or (hl, hr) == (holes_[2], holes_[0])

        face_edges = list(set([(s, e) if holes[s] == hl else (e, s)
                               for s in list(graph.keys()) for e in graph[s] if holes[s] in (hl, hr) and holes[e] in (hl, hr)]))

        if not len(face_edges):
            continue

        face_lines = []
        for e in face_edges:
            face_lines.append(
                Line([nodes[e[0]].coords[0], nodes[e[1]].coords[0]], Line.TOP))
            face_lines.append(
                Line([nodes[e[0]].coords[1], nodes[e[1]].coords[1]], Line.BOTTOM))

        # split lines
        for i, j in combinations(list(range(len(face_lines))), 2):
            assert(
                face_lines[i].side != Line.VERTICAL and face_lines[j].side != Line.VERTICAL)
            p = sym_split(face_lines[i].points, face_lines[j].points)
            if p and p not in offsets:
                if face_lines[i].points[0] in offsets and face_lines[i].points[-1] in offsets\
                        and face_lines[j].points[0] in offsets and face_lines[j].points[-1] in offsets:
                    splt = sym_split(
                        offset_coords(
                            offsets, [face_lines[i].points[0], face_lines[i].points[-1]]),
                        offset_coords(offsets, [face_lines[j].points[0], face_lines[j].points[-1]]))
                    offsets[p] = splt if splt else p
                else:
                    offsets[p] = p

        # split in middle
        for i in range(len(face_lines)):
            assert(face_lines[i].side != Line.VERTICAL)
            p = face_lines[i].midpoint_split()
            if p and p not in offsets:
                if face_lines[i].points[0] in offsets and face_lines[i].points[-1] in offsets:
                    offsets[p] = tuple(.5*(array(offsets[face_lines[i].points[0]]
                                                 ) + array(offsets[face_lines[i].points[-1]])))
                else:
                    offsets[p] = p

        for k, n in list(nodes.items()):
            if holes[k] in (hl, hr):
                face_lines.append(
                    Line([n.coords[0], n.coords[1]], Line.VERTICAL))

        # select the topmost edge:
        top_altitude = -INF
        top_edge = None
        for s, e in face_edges:
            alt = .5*(nodes[s].coords[0][2]+nodes[e].coords[0][1])
            if alt > top_altitude:
                top_edge = LineString([nodes[s].coords[0], nodes[e].coords[0]])

        origin = array(top_edge.coords[0])
        u = array(top_edge.coords[1]) - origin
        z = array((0, 0, 1))
        w = cross(z, u)
        w /= norm(w)
        v = cross(w, z)

        lines += face_lines

        linework = [array((s, e)) for l in face_lines for s,
                    e in zip(l.points[:-1], l.points[1:])]
        linework_sav = linework

        if DEBUG:
            open("/tmp/face_{}.vtk".format(face_idx), 'w').write(
                to_vtk(MultiLineString([LineString(l) for l in linework]).wkb_hex))
            debug_files.append("/tmp/face_{}.vtk".format(face_idx))

        node_map = {(round(dot(p-origin, v), PRECI), round(dot(p -
                                                               origin, z), PRECI)): p for e in linework for p in e}
        linework = [LineString([(round(dot(e[0]-origin, v), PRECI), round(dot(e[0]-origin, z), PRECI)),
                                (round(dot(e[1]-origin, v), PRECI), round(dot(e[1]-origin, z), PRECI))])
                    for e in linework]

        if DEBUG:
            bug = 0
            for i, li in enumerate(linework):
                if li.length <= 0:
                    # fix_print_with_import
                    print(('zero length line', i, li.wkt))
                    bug = True
                    break
                found = False
                for j, lj in enumerate(linework):
                    if i != j and (not (lj.coords[0] != li.coords[0] or lj.coords[1] != li.coords[1])
                                   or not (lj.coords[0] != li.coords[1] or lj.coords[1] != li.coords[0])):
                        open("/tmp/dup_line_{}_face_{}.vtk".format(bug, face_idx), 'w').write(
                            to_vtk(MultiLineString([LineString(linework_sav[j])]).wkb_hex))
                        # fix_print_with_import
                        print(('duplicate line', li.wkt, lj.wkt))
                        bug += 1
                    if i != j and li.coords[1] == lj.coords[0] or li.coords[1] == lj.coords[1]:
                        found = True
                if not found:
                    print(MultiLineString(linework).wkt)
                    bug += 1
            if bug:
                # fix_print_with_import
                print(('open', MultiLineString(linework).wkt))
                assert(False)

        domain = [Polygon([nodes[e[0]].coords[0], nodes[e[0]].coords[1],
                           nodes[e[1]].coords[1], nodes[e[1]].coords[0]]) for e in triangle_edges if e in face_edges]
        domain = unary_union([Polygon([(round(dot(p-origin, v), PRECI), round(dot(p-origin, z), PRECI))
                                       for p in array(dom.exterior.coords)]) for dom in domain])

        polygons = list(polygonize(linework))
        domain_tri = []
        term_tri = []
        for p in polygons:
            p = p if p.exterior.is_ccw else Polygon(p.exterior.coords[::-1])
            assert(p.exterior.is_ccw)
            t_sfcgal = sfcgal.shape(mapping(p)).tessellate()
            for t in t_sfcgal.geoms:
                tri = t.coords
                q = Polygon([node_map[tri[0]], node_map[tri[1]], node_map[tri[2]]]) \
                    if direct_orientation else \
                    Polygon(
                        [node_map[tri[2]], node_map[tri[1]], node_map[tri[0]]])
                if Point(average(tri, (0,))).intersects(domain):
                    domain_tri.append(q)
                else:
                    term_tri.append(q)

        result += domain_tri
        faces[(hl, hr)] += domain_tri

        top_lines = [l for l in face_lines if l.side == Line.TOP]
        bottom_lines = [l for l in face_lines if l.side == Line.BOTTOM]
        end_lines = {tuple(nodes[n].coords): holes[n]
                     for n in list(ends.keys())}
        if DEBUG:
            open('/tmp/top_lines_face_{}.vtk'.format(face_idx),
                 'w').write(to_vtk(MultiLineString([l.points for l in top_lines]).wkb_hex))
            open('/tmp/bottom_lines_face_{}.vtk'.format(face_idx), 'w').write(
                to_vtk(MultiLineString([l.points for l in bottom_lines]).wkb_hex))
            open('/tmp/offsets_bis.vtk', 'w').write(
                to_vtk(MultiLineString([LineString([k, v]) for k, v in list(offsets.items())]).wkb_hex))

        # create terminations
        terms = []
        edges = set()
        for t in term_tri:
            for s, e in zip(t.exterior.coords[:-1], t.exterior.coords[1:]):
                if (e, s) in edges:
                    edges.remove((e, s))
                else:
                    edges.add((s, e))
        for t in term_tri:
            share = False
            for d in domain_tri:
                if share_an_edge(t, d):
                    share = True
                    break
            if share:
                continue
            terms.append(t)
            faces[(hl, hr)] += [t]
            terms.append(Polygon(offset_coords(
                offsets, t.exterior.coords[::-1])))
            for s in zip(t.exterior.coords[:-1], t.exterior.coords[1:]):
                if s in edges:
                    if (is_segment(s, top_lines) or is_segment(s, bottom_lines) or s in end_lines)\
                            and s[0] in offsets and s[1] in offsets:
                        terms.append(Polygon([offsets[s[0]], s[1], s[0]]))
                        terms.append(
                            Polygon([offsets[s[0]], offsets[s[1]], s[1]]))
                    if (s[1], s[0]) in end_lines:
                        terms.append(Polygon([s[1], s[0], offsets[s[1]]]))
                        terms.append(
                            Polygon([s[0], offsets[s[0]], offsets[s[1]]]))
                        faces[tuple(
                            sorted((end_lines[(s[1], s[0])], other_hole)))] += terms[-2:]
        termination += terms

    if DEBUG:
        open("/tmp/faces.obj", 'w').write(to_obj(MultiPolygon(result).wkb_hex))
        open("/tmp/termination.obj",
             'w').write(to_obj(MultiPolygon(termination).wkb_hex))

    if len(result):

        top_lines = [l for l in lines if l.side == Line.TOP]
        bottom_lines = [l for l in lines if l.side == Line.BOTTOM]
        # find openfaces (top and bottom)
        edges = set()
        for t in result:
            for s, e in zip(t.exterior.coords[:-1], t.exterior.coords[1:]):
                if (e, s) in edges:
                    edges.remove((e, s))
                else:
                    edges.add((s, e))
        top_linework = []
        bottom_linework = []
        for e in edges:
            if is_segment(e, top_lines):
                bottom_linework.append((tuple(e[0]), tuple(e[1])))
            elif is_segment(e, bottom_lines):
                top_linework.append((tuple(e[0]), tuple(e[1])))

        if DEBUG:
            open("/tmp/linework_top_unm.vtk", 'w').write(
                to_vtk(MultiLineString([LineString(e) for e in top_linework]).wkb_hex))
            open("/tmp/linework_bottom_unm.vtk", 'w').write(
                to_vtk(MultiLineString([LineString(e) for e in bottom_linework]).wkb_hex))

        # linemerge top and bottom, there will be open rings that need to be closed
        # since we did only add linework for faces
        for face, side in zip(('top', 'bottom'), (top_linework, bottom_linework)):
            merged = linemerge(side)

            if DEBUG:
                open("/tmp/linework_%s.vtk" % (face), 'w').write(
                    to_vtk(MultiLineString([LineString(e) for e in merged]).wkb_hex))
            face_triangles = []
            for m in merged:
                if has_proper_2d_topology(m):
                    node_map = {
                        (round(x[0], PRECI), round(x[1], PRECI)): x for x in m}
                    p = Polygon(
                        [(round(x[0], PRECI), round(x[1], PRECI)) for x in m])
                    p = p if p.exterior.is_ccw else Polygon(
                        p.exterior.coords[::-1])
                    assert(p.exterior.is_ccw)
                    t_sfcgal = sfcgal.shape(
                        mapping(p)).tessellate()
                    for t in t_sfcgal.geoms:
                        tri = t.coords
                        q = Polygon([node_map[tri[0]], node_map[tri[1]], node_map[tri[2]]]) \
                            if face == 'bottom' else \
                            Polygon(
                                [node_map[tri[2]], node_map[tri[1]], node_map[tri[0]]])
                        result.append(q)
                        face_triangles.append(q)
            if DEBUG:
                open("/tmp/face_{}.obj".format(face),
                     'w').write(to_obj(MultiPolygon(face_triangles).wkb_hex))

    # adds isolated nodes terminations
    for n, l in list(ends.items()):
        if len(l) == 2:
            node = nodes[n]
            A, B, C = array(node.coords[0]), array(
                l[0].coords[0]), array(l[1].coords[0])
            k1, k2 = tuple(sorted((holes[n], end_holes[n][0]))), tuple(
                sorted((holes[n], end_holes[n][1])))
            l = l
            if dot(cross(B-A, C-A), array((0., 0., 1.))) <= 0:
                l = list(reversed(l))
                k1, k2 = k2, k1
            termination += [
                Polygon([node.coords[0], l[0].coords[0], l[1].coords[0]]),
                Polygon([l[1].coords[-1], l[0].coords[-1], node.coords[-1]]),
                Polygon([node.coords[0], node.coords[1], l[0].coords[0]]),
                Polygon([node.coords[1], l[0].coords[1], l[0].coords[0]]),
                Polygon([l[1].coords[0], node.coords[1], node.coords[0]]),
                Polygon([l[1].coords[0], l[1].coords[1], node.coords[1]]),
                Polygon([l[0].coords[0], l[0].coords[1], l[1].coords[0]]),
                Polygon([l[0].coords[1], l[1].coords[1], l[1].coords[0]])
            ]
            assert(len(end_holes[n]) == 2)
            faces[k1] += [
                Polygon([node.coords[0], node.coords[1], l[0].coords[0]]),
                Polygon([node.coords[1], l[0].coords[1], l[0].coords[0]]),
            ]
            faces[k2] += [
                Polygon([l[1].coords[0], node.coords[1], node.coords[0]]),
                Polygon([l[1].coords[0], l[1].coords[1], node.coords[1]]),
            ]

    result += termination

    if DEBUG:
        for hp, tri in faces.items():
            open("/tmp/face_{}_{}.obj".format(hp[0], hp[1]), 'w').write(
                to_obj(MultiPolygon([t for t in tri]).wkb_hex))

    # decompose volume in connected components
    edges = {}
    graph = {i: set() for i in range(len(result))}
    for ip, p in enumerate(result):
        for s, e in zip(p.exterior.coords[:-1], p.exterior.coords[1:]):
            if (e, s) in edges:
                o = edges[(e, s)]
                graph[o].add(ip)
                graph[ip].add(o)
                del edges[(e, s)]
            else:
                edges[(s, e)] = ip

    def pop_connected(n, graph):
        connected = set([n])
        if n in graph:
            for ng in graph.pop(n):
                connected = connected.union(pop_connected(ng, graph))
        return connected

    connected = []
    while len(graph):
        n = next(iter(list(graph.keys())))
        connected.append(pop_connected(n, graph))

    i = 0
    for c in connected:
        i += 1
        face1 = []
        face2 = []
        face3 = []
        triangles = [result[i] for i in c]
        res = MultiPolygon(triangles)

        for f in faces[(sorted_holes[0], sorted_holes[1])]:
            if f in triangles:
                face1.append(f)
        for f in faces[(sorted_holes[1], sorted_holes[2])]:
            if f in triangles:
                face2.append(f)
        for f in faces[(sorted_holes[0], sorted_holes[2])]:
            if f in triangles:
                face3.append(f)

        if DEBUG:
            open("/tmp/face1_tr_%d.obj" %
                 (i), 'w').write(to_obj(face1.wkb_hex))
            open("/tmp/face2_tr_%d.obj" %
                 (i), 'w').write(to_obj(face2.wkb_hex))
            open("/tmp/face3_tr_%d.obj" %
                 (i), 'w').write(to_obj(face3.wkb_hex))
            open("/tmp/volume_tr.obj", 'w').write(to_obj(res.wkb_hex))
            # check volume is closed
            edges = set()
            for p in res:
                for s, e in zip(p.exterior.coords[:-1], p.exterior.coords[1:]):
                    if (e, s) in edges:
                        edges.remove((e, s))
                    else:
                        edges.add((s, e))
            if len(edges):
                print("volume is not closed", edges)
                open("/tmp/unconnected_edge.vtk", 'w').write(
                    to_vtk(MultiLineString([LineString(e) for e in edges]).wkb_hex))

            # check volume is positive
            volume = 0
            for p in res:
                r = p.exterior.coords
                v210 = r[2][0]*r[1][1]*r[0][2]
                v120 = r[1][0]*r[2][1]*r[0][2]
                v201 = r[2][0]*r[0][1]*r[1][2]
                v021 = r[0][0]*r[2][1]*r[1][2]
                v102 = r[1][0]*r[0][1]*r[2][2]
                v012 = r[0][0]*r[1][1]*r[2][2]
                volume += (1./6.)*(-v210 + v120 + v201 - v021 - v102 + v012)
            if volume <= 0:
                print("volume is", volume)

        res = translate(res, translation[0], translation[1], translation[2])
        geos.lgeos.GEOSSetSRID(res._geom, srid_)

        face1 = translate(MultiPolygon(face1),
                          translation[0], translation[1], translation[2])
        geos.lgeos.GEOSSetSRID(face1._geom, srid_)

        face2 = translate(MultiPolygon(face2),
                          translation[0], translation[1], translation[2])
        geos.lgeos.GEOSSetSRID(face2._geom, srid_)

        face3 = translate(MultiPolygon(face3),
                          translation[0], translation[1], translation[2])
        geos.lgeos.GEOSSetSRID(face3._geom, srid_)

        empty_mp = "SRID={} ;MULTIPOLYGONZ EMPTY".format(srid_)
        yield (res.wkb_hex if not res.is_empty else empty_mp, face1.wkb_hex if not face1.is_empty else empty_mp,
               face2.wkb_hex if not face2.is_empty else empty_mp, face3.wkb_hex if not face3.is_empty else empty_mp)

    for f in debug_files:
        os.remove(f)
