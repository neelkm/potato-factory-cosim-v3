"""Surface reconstruction of measured PhysX PBD particles for liquid rendering."""
import numpy as np
from scipy.ndimage import gaussian_filter
from skimage.measure import marching_cubes
ORIGIN=np.array((-2.05,-1.4,.8),np.float32);SPACING=.025
SHAPE=(166,114,74)
def reconstruct(points):
    field=np.zeros(SHAPE,np.float32);ijk=np.rint((np.asarray(points)-ORIGIN)/SPACING).astype(np.int32)
    ijk=ijk[np.all((ijk>=0)&(ijk<np.array(SHAPE)),axis=1)]
    if not len(ijk):return np.empty((0,3),np.float32),np.empty((0,3),np.int32),np.empty((0,3),np.float32)
    np.add.at(field,tuple(ijk.T),1.);field=gaussian_filter(field,(.9,.9,1.5))
    if field.max()<.035:return np.empty((0,3),np.float32),np.empty((0,3),np.int32),np.empty((0,3),np.float32)
    vertices,faces,normals,_=marching_cubes(field,.035,spacing=(SPACING,)*3,allow_degenerate=False)
    return (vertices+ORIGIN).astype(np.float32),faces.astype(np.int32),normals.astype(np.float32)
