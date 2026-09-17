"""Vertical contact against actual floor triangles, including fine mesh relief.

The apron has monotone XY rows and columns. Inverse strip lookup finds the cell;
barycentric interpolation then uses its real two triangles, not a fitted height
function. This is geometric support placement, not a rigid-body simulation.
"""
from __future__ import annotations
import numpy as np

class SupportSurface:
    def __init__(self,vertices,rows,cols):
        self.grid=np.asarray(vertices[:rows*cols],dtype=np.float64).reshape(rows,cols,3)
        self.rows=rows;self.cols=cols
        if not np.all(np.diff(self.grid[:,:,0],axis=1)>0):raise ValueError('Non-monotone floor strips')
        if not np.all(np.diff(self.grid[:,0,1])>0):raise ValueError('Non-monotone floor rows')
    def height(self,xy):
        xy=np.asarray(xy,dtype=np.float64).reshape(-1,2);out=np.empty(len(xy));g=self.grid
        for start in range(0,len(xy),1024):
            q=xy[start:start+1024]
            r=np.clip(np.searchsorted(g[:,0,1],q[:,1])-1,0,self.rows-2)
            fy=(q[:,1]-g[r,0,1])/(g[r+1,0,1]-g[r,0,1])
            xx=g[r,:,0]*(1-fy[:,None])+g[r+1,:,0]*fy[:,None]
            c=np.clip(np.sum(xx<q[:,0,None],axis=1)-1,0,self.cols-2)
            a=g[r,c];b=g[r,c+1];d=g[r+1,c+1];e=g[r+1,c]
            def triangle(a,b,c):
                A=b[:,:2]-a[:,:2];B=c[:,:2]-a[:,:2];C=q-a[:,:2]
                den=A[:,0]*B[:,1]-A[:,1]*B[:,0]
                u=(C[:,0]*B[:,1]-C[:,1]*B[:,0])/den
                v=(A[:,0]*C[:,1]-A[:,1]*C[:,0])/den
                return a[:,2]+u*(b[:,2]-a[:,2])+v*(c[:,2]-a[:,2]),(u>=-1e-6)&(v>=-1e-6)&(u+v<=1+1e-6)
            z1,in1=triangle(a,b,d);z2,in2=triangle(a,d,e)
            if not (in1|in2).all():raise ValueError('Contact sample lies outside the floor')
            out[start:start+len(q)]=np.where(in1,z1,z2)
        return out
