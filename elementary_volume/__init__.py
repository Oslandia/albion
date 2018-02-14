import os
import random
from itertools import combinations
from math import pi as PI, inf as INF, sin
from numpy import array, cross, argmin, argmax, dot, average
from numpy.linalg import norm
from collections import defaultdict
from itertools import product
from shapely.geometry import MultiPolygon, Polygon, LineString, MultiLineString, Point, MultiPoint
from shapely import wkb
from shapely.ops import unary_union, polygonize
from shapely.ops import transform 
from shapely import geos
geos.WKBWriter.defaults['include_srid'] = True

from cgal import delaunay as triangulate

def to_vtk(multiline):
    if multiline is None:
        return ''
    m = wkb.loads(multiline, True)
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
    m = wkb.loads(multipoly, True)
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
    A, B, C, D = array(segment[0]), array(segment[1]), array(crossing_segment[0]), array(crossing_segment[1])
    return dot(cross(D-C, A-C), cross(D-C, B-C)) < 0


class Line(object):
    VERTICAL='vertical'
    TOP='top'
    BOTTOM='bottom'
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
            #if norm(C - array(self.points[closest_idx])) < 1: # @todo remove hardcoded value
            #    return self.points[closest_idx]
            #else:
            #    if norm(array(self.points[closest_idx]) - A) > norm(C-A):
            #        self.points.insert(closest_idx, midpoint)
            #    else:
            #        self.points.insert(closest_idx+1, midpoint)
            #    return midpoint


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
    SIN_MIN_ANGLE = 5.*PI/180
    l = line
    if len(l) <=2 :
        return False
    if l[0] != l[-1]:
        l.append(l[0])
    for a, b, c in zip(l[:-1], l[1:], l[2:]+[l[1]]):
        u = array((a[0], a[1])) - array((b[0], b[1]))
        v = array((c[0], c[1])) - array((b[0], b[1]))
        if dot(u, v) > 0:
            u /= norm(u)
            v /= norm(v)
            if norm(cross(u,v)) < SIN_MIN_ANGLE:
                #print(line)
                #print("u x v  u.v", cross(u,v), dot(u, v))
                return False
    return LineString(l).is_ring

    

def elementary_volumes(holes_, starts_, ends_, hole_ids_, node_ids_, nodes_, end_ids_, end_geoms_, srid_=32632):

    DEBUG = True
    PRECI = 9
    debug_files = []

    nodes = {id_: wkb.loads(geom, True) for id_, geom in zip(node_ids_, nodes_)}
    ends = defaultdict(list)
    for id_, geom in zip(end_ids_, end_geoms_):
        ends[id_].append(wkb.loads(geom, True))
    holes = {n: h for n, h in zip(node_ids_, hole_ids_)}
    edges = [(s, e) for s, e in zip(starts_, ends_)]
    assert(len(edges) == len(set(edges)))

    graph = defaultdict(set) # undirected (edge in both directions)
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
    for e in edges:
        common_neigbors = graph[e[0]].intersection(graph[e[1]])
        for n in common_neigbors:
            tri = tuple((i for _, i in sorted(zip((holes[e[0]], holes[e[1]], holes[n]), (e[0], e[1], n)))))
            triangles.add(tri)
            triangle_edges.add(tri[0:2])
            triangle_edges.add(tri[1:3])
            triangle_edges.add(tri[0:1]+tri[2:3])

    result = []
    term = []

    sorted_holes = sorted(holes_)
    face_idx = -1
    lines = []
    for hl, hr in ((sorted_holes[0], sorted_holes[1]), 
                   (sorted_holes[1], sorted_holes[2]),
                   (sorted_holes[0], sorted_holes[2])):
        face_idx += 1
        direct_orientation = (hl, hr) == (holes_[0], holes_[1]) or (hl, hr) == (holes_[1], holes_[2]) or (hl, hr) == (holes_[2], holes_[0])

        face_edges = list(set([(s, e) if holes[s] == hl else (e, s) 
            for s in graph.keys() for e in graph[s] if holes[s] in (hl, hr) and holes[e] in (hl, hr)]))

        if not len(face_edges):
            continue

        face_lines = []
        for e in face_edges:
            face_lines.append(Line([nodes[e[0]].coords[0], nodes[e[1]].coords[0]], Line.TOP))
            face_lines.append(Line([nodes[e[0]].coords[1], nodes[e[1]].coords[1]], Line.BOTTOM))

        # split lines 
        for i, j in combinations(range(len(face_lines)), 2):
            assert(face_lines[i].side != Line.VERTICAL and face_lines[j].side != Line.VERTICAL)
            sym_split(face_lines[i].points, face_lines[j].points)

        # split in middle
        vertical_midline = []
        for i in range(len(face_lines)):
            assert(face_lines[i].side != Line.VERTICAL)
            vertical_midline.append(face_lines[i].midpoint_split())
        assert(len(vertical_midline)>=2)
        vertical_midline = [p for _, p in sorted(zip([x[2] for x in vertical_midline], vertical_midline), reverse=True)]
        for sp, ep in zip(vertical_midline[:-1], vertical_midline[1:]):
            if sp != ep:
                face_lines.append(Line([sp, ep], Line.VERTICAL))

        for k, n in nodes.items():
            if holes[k] in (hl, hr):
                face_lines.append(Line([n.coords[0], n.coords[1]], Line.VERTICAL))

        origin = array(nodes[face_edges[0][0]].coords[0])
        u = array(nodes[face_edges[0][1]].coords[0]) - origin
        z = array((0, 0, 1))
        w = cross(z, u)
        w /= norm(w)
        v = cross(w, z)

        for id_, es in ends.items():
            for e in es:
                if abs(dot(array(e.coords[0])-origin, w)) < 1: # if end is in face @todo replace that with actual edge in input
                    face_lines.append(Line([e.coords[0], nodes[id_].coords[0]], Line.TOP))
                    face_lines.append(Line([e.coords[1], nodes[id_].coords[1]], Line.BOTTOM))
                    face_lines.append(Line([e.coords[0], e.coords[1]], Line.VERTICAL))


        
        lines += face_lines 

        linework = [array((s,e)) for l in face_lines for s, e in zip(l.points[:-1], l.points[1:])]

        if DEBUG:
            open("/tmp/face_{}.vtk".format(face_idx), 'w').write(to_vtk(MultiLineString([LineString(l) for l in linework]).wkb_hex))
            debug_files.append("/tmp/face_{}.vtk".format(face_idx))

        node_map = {(round(dot(p-origin, v), PRECI), round(dot(p-origin, z), PRECI)): p for e in linework for p in e}
        linework = [LineString([(round(dot(e[0]-origin, v), PRECI), round(dot(e[0]-origin, z), PRECI)),
                                (round(dot(e[1]-origin, v), PRECI), round(dot(e[1]-origin, z), PRECI))])
                   for e in linework]

        bug = False
        for i, li in enumerate(linework):
            if li.length <= 0:
                print('zero length line', i, li.wkt)
                bug = True
                break
            found = False
            for j, lj in enumerate(linework):
                if i!=j and (not (lj.coords[0] != li.coords[0] or lj.coords[1] != li.coords[1]) \
                        or not (lj.coords[0] != li.coords[1] or lj.coords[1] != li.coords[0])):
                            print('duplicate line', li.wkt, lj.wkt)
                            bug=True
                if i!=j and li.coords[1] == lj.coords[0] or  li.coords[1] == lj.coords[1]:
                    found = True
            if not found:
                print(MultiLineString(linework).wkt)
                bug = True
        if bug:
            print('open', MultiLineString(linework).wkt)
            return None
            


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
            triangulation = triangulate(list(p.exterior.coords))
            for tri in triangulation:
                q = Polygon([node_map[tri[0]], node_map[tri[1]], node_map[tri[2]]]) \
                    if direct_orientation else \
                    Polygon([node_map[tri[2]], node_map[tri[1]], node_map[tri[0]]])
                if Point(average(tri, (0,))).intersects(domain):
                    domain_tri.append(q)
                else:
                    term_tri.append(q)

        result += domain_tri

        for t in term_tri:
            result.append(t)
            for d in domain_tri:
                if share_an_edge(t, d):
                    result.pop(-1)
                    break
    if DEBUG:
        open("/tmp/faces.obj", 'w').write(to_obj(MultiPolygon(result).wkb_hex))

    if len(result):
        
        top_lines = [l for l in lines if l.side==Line.TOP]
        bottom_lines = [l for l in lines if l.side==Line.BOTTOM]
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
            open("/tmp/linework_top_unm.vtk", 'w').write(to_vtk(MultiLineString([LineString(e) for e in top_linework]).wkb_hex))
            open("/tmp/linework_bottom_unm.vtk", 'w').write(to_vtk(MultiLineString([LineString(e) for e in bottom_linework]).wkb_hex))

        # linemerge top and bottom, there will be open rings that need to be closed
        # since we did only add linework for faces
        for face, side in zip(('top', 'bottom'), (top_linework, bottom_linework)):
            merged = linemerge(side) 

            #open("/tmp/debug.txt", "a").write(str(merged))
            if DEBUG:
                open("/tmp/linework_%s.vtk"%(face), 'w').write(to_vtk(MultiLineString([LineString(e) for e in merged]).wkb_hex))
            for m in merged:
                if has_proper_2d_topology(m):
                    node_map = {(round(x[0], PRECI), round(x[1], PRECI)): x for x in m}
                    p = Polygon([(round(x[0], PRECI), round(x[1], PRECI)) for x in m])
                    open('/tmp/polygon_bug.txt', 'w').write(p.wkt+'\n')
                    p = p if p.exterior.is_ccw else Polygon(p.exterior.coords[::-1])
                    assert(p.exterior.is_ccw)
                    for tri in triangulate(list(p.exterior.coords)):
                        q = Polygon([node_map[tri[0]], node_map[tri[1]], node_map[tri[2]]]) \
                            if face == 'bottom' else \
                            Polygon([node_map[tri[2]], node_map[tri[1]], node_map[tri[0]]])
                        result.append(q)

    open("/tmp/debug_volume.obj", 'w').write(to_obj(MultiPolygon(result).wkb_hex))
          
    # check that generated volume is closed
    edges = set()
    for p in result:
        for s, e in zip(p.exterior.coords[:-1], p.exterior.coords[1:]):
            if (e, s) in edges:
                edges.remove((e, s))
            else:
                edges.add((s, e))

    # close terminations that are rings
    edges = list(edges)
    merged = linemerge(edges)
    for m in merged:
        if m[0] == m[-1] and len(m) == 5:
            result.append(Polygon([m[2], m[1], m[0]]))
            result.append(Polygon([m[3], m[2], m[0]]))

    # decompose volume in connected components
    edges = {}
    graph = {i:set() for i in range(len(result))}
    for ip, p in enumerate(result):
        for s, e in zip(p.exterior.coords[:-1], p.exterior.coords[1:]):
            if (e, s) in edges:
                o = edges[(e,s)]
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
        n = next(iter(graph.keys()))
        connected.append(pop_connected(n, graph))

    for c in connected:
        r = MultiPolygon([result[i] for i in c])
        geos.lgeos.GEOSSetSRID(r._geom, srid_)
        yield r.wkb_hex

    #if (len(edges)):
    #    if DEBUG:
    #        open("/tmp/unclosed_volume.obj", 'w').write(to_obj(MultiPolygon(result).wkb_hex))
    #    #raise RuntimeError("elementary volume is not closed")

    for f in debug_files:
        os.remove(f)
 
