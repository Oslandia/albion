# -*- coding: UTF-8 -*-

from builtins import str
import sys
import re
import numpy

def printCompileError(e):
    m = re.match(r'\("(.*)", \[\'(.*)\'\], (.*)\)', str(e)+"\n")
    if m:
        sys.stderr.write("ERROR IN "+m.groups()[2]+"\n")
        sys.stderr.write(m.groups()[0]+"\n")
        for lno, line in enumerate(m.groups()[1].split('\\n')):
            sys.stderr.write("%8d%s\n"%(lno+1, line))

def computeNormals(vtx, idx):
    
    nrml = numpy.zeros(vtx.shape, numpy.float32)

    # compute normal per triangle
    triN = numpy.cross(vtx[idx[:,1]] - vtx[idx[:,0]], vtx[idx[:,2]] - vtx[idx[:,0]])

    # sum normals at vtx
    nrml[idx[:,0]] += triN[:]
    nrml[idx[:,1]] += triN[:]
    nrml[idx[:,2]] += triN[:]

    # compute norms
    nrmlNorm = numpy.sqrt(nrml[:,0]*nrml[:,0]+nrml[:,1]*nrml[:,1]+nrml[:,2]*nrml[:,2])
    
    return nrml/nrmlNorm.reshape(-1,1)


