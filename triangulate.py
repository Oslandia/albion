from numpy import array, roll, cross, arccos, einsum, argmin, logical_not, indices, dot
from numpy.linalg import norm
from math import pi as PI, inf as INF

def triangulate(poly, debug=False, edge_swap=False):
    """
    triangulation of convex polygon, we take the flatest angle and fan frmo there
    """
    vtx = array(poly if poly[0] != poly[-1] else poly[:-1])
    n = len(vtx)
    prv = (indices((n,))[0] + n - 1) % n 
    nxt = (indices((n,))[0] + 1) % n
    angle = arccos(einsum('ij,ij->i',vtx[nxt]-vtx, vtx[prv]-vtx)/(norm(vtx[nxt]-vtx, axis=1)*norm(vtx[prv]-vtx, axis=1))) *180 / PI
    print(angle)


def triangulate_old(poly):
    """
    simple earclip implementation
    the case where a reflex vertex lies on the boundary of a condidate triangle

    algoriyjm is described in 
    Ear-clipping Based Algorithms of Generating High-quality Polygon Triangulation, Gang Mei 1 , John C.Tipper 1 and Nengxiong Xu 2

    the input polygon is assumed ccw
    """

    def is_inside(p, t):
        def sign (p1, p2, p3):
            return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
        l = max(norm(t[1]-t[0]), norm(t[2]-t[1]), norm(t[0]-t[2]))
        if norm(p-t[0])/l < 1e-6 or norm(p-t[1])/l < 1e-6 or norm(p-t[2])/l < 1e-6:
            return False
        l2 = l*l
        b1 = sign(p, t[0], t[1])/l2 > -1e-3
        b2 = sign(p, t[1], t[2])/l2 > -1e-3
        b3 = sign(p, t[2], t[0])/l2 > -1e-3
        #print(sign(p, t[0], t[1])/l2, sign(p, t[1], t[2])/l2, sign(p, t[2], t[0])/l2)
        #print(b1,b2,b3)
        return b1 and b2 and b3

    vtx = array(poly if poly[0] != poly[-1] else poly[:-1])
    n = len(vtx)
    prv = (indices((n,))[0] + n - 1) % n 
    nxt = (indices((n,))[0] + 1) % n

    reflex = cross(vtx[nxt]-vtx, vtx[prv]-vtx, 1) < 0
    
    angle = arccos(einsum('ij,ij->i',vtx[nxt]-vtx, vtx[prv]-vtx)/(norm(vtx[nxt]-vtx, axis=1)*norm(vtx[prv]-vtx, axis=1))) *180 / PI
    angle[reflex] = INF
     
    reflex_vtx = vtx[reflex]
    for i in range(n):
        if angle[i] != INF:
            for r in reflex_vtx:
                if is_inside(r, vtx[array((prv[i], i, nxt[i]))]):
                    angle[i] = INF
                    break

    print('angles', angle)
    triangles = []
    step = 0
    while len(triangles) < n-2:
        step += 1
        print('step', step)
        i = argmin(angle)
        print(i, angle[i])
        #print(prv)
        #print(nxt)
        pi, ni = prv[i], nxt[i]
        triangles.append((pi, i, ni))
        open("triangulate_test_step_{}.txt".format(step), 'w').write('\n'.join(["{} {}".format(*vtx[j]) for j in triangles[-1]+triangles[-1][0:1]]))
        # update angles
        angle[pi] = arccos(dot(vtx[prv[pi]] - vtx[pi], 
                               vtx[ni] - vtx[pi])
                        /(norm(vtx[prv[pi]] - vtx[pi])
                         *norm(vtx[ni] - vtx[pi]))) *180 / pi \
                    if cross(vtx[prv[pi]] - vtx[pi], vtx[ni] - vtx[pi]) < 0 \
                    else INF
        print("angle", pi, angle[pi], cross(vtx[prv[pi]] - vtx[pi], vtx[ni] - vtx[pi]))

        angle[i] = INF
        angle[ni] = arccos(dot(vtx[pi] - vtx[ni],
                               vtx[nxt[ni]] - vtx[ni])
                        /(norm(vtx[pi] - vtx[ni])
                         *norm(vtx[nxt[ni]] - vtx[ni]))) *180 / pi \
                    if cross(vtx[pi] - vtx[ni], vtx[nxt[ni]] - vtx[ni]) < 0 \
                    else INF
        print("angle", ni, angle[ni], cross(vtx[pi] - vtx[ni], vtx[nxt[ni]] - vtx[ni]))
        # update connectivity info
        prv[ni], nxt[pi] = pi, ni

        # udate eartip status
        for j in (pi, ni):
            for r in reflex_vtx:
                #print("update inclusion for", j,"test r", r) 
                if is_inside(r, vtx[array((prv[j], j, nxt[j]))]):
                    #print("inside")
                    angle[j] = INF
                    break
        #print(angle)
    return [(vtx[t[0]], vtx[t[1]], vtx[t[2]]) for t in triangles]

    #has_inside(vtx[reflex],  )

    #p = range(n)
    #print(vtx[reflex])
    #while len(p):
    #    # get minimum angle and create candidate
    #    i = argmin(angle)
    #    candidate = arrary(i-1, i, (i+1)%n)
    #    # test for inclusion of reflex vertex
    #    valid = True
    #    for r in vtx[reflex]:
    #        if is_inside(r, vtx[candidate]):
    #            angle[i] = inf



p = list(reversed(((0.0, 0.0),
(24.594395, -0.805645),
(24.604182, -1.805244),
(11.718975, -1.383275),
(24.616022, -2.904787),
(24.625831, -3.90436),
(-0.000552, -0.999742),
(0.0, 0.0))))

p = (
(0.0, 0.0),
(0.074302, -8.199306),
(28.458694, -8.14565),
(28.416041, -7.146585),
(25.314118, -6.370088),
(28.377353, -6.147359),
(28.257662, -3.049727),
(0.0, 0.0))

p = (
(0.0, 0.0),
(0.05822, -3.099376),
(5.058296, -3.843746),
(0.075132, -4.099219),
(0.091605, -5.199088),
(5.926158, -5.732567),
(0.111376, -6.398922),
(0.130929, -7.398724),
(36.741597, -8.52484),
(36.269241, -2.242697),
(0.0, 0.0))

p = list(reversed(((0.56620402601374009, 0.45425343959035636), (1.0, 0.0), (0.0, 0.0), (0.0092680361819599405, 0.61786907879732933))))

triangles = triangulate(p)

if True:
    from matplotlib import pyplot as plt
    from shapely.geometry.polygon import Polygon
    from descartes import PolygonPatch

    fig = plt.figure(1, figsize=(5,5), dpi=90)
    ax = fig.add_subplot(111)
    for t in triangles:
        ring_patch = PolygonPatch(Polygon(t))
        ax.add_patch(ring_patch)
        print(t, Polygon(t).area)
    ax.plot([x[0] for x in p], [x[1] for x in p])

    ax.set_title('Filled Polygon')
    xrange = [min(x[0] for x in t for t in triangles)-5, max(x[0] for x in t for t in triangles)+5]
    yrange = [min(x[1] for x in t for t in triangles)-5, max(x[1] for x in t for t in triangles)+5]
    ax.set_xlim(*xrange)
    #ax.set_xticks(range(*xrange) + [xrange[-1]])
    ax.set_ylim(*yrange)
    #ax.set_yticks(range(*yrange) + [yrange[-1]])
    ax.set_aspect(1)
    plt.show()

open("triangulate_test_poly.txt", 'w').write('\n'.join(["{} {}".format(*x) for x in p+p[0:1]]))
open("triangulate_test_res.txt", 'w').write('\n\n'.join(['\n'.join(["{} {}".format(*x) for x in p+p[0:1]]) for p in triangles]))
