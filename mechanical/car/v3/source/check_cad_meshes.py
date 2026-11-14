from pathlib import Path
import json
import struct
import numpy as np

root = Path(__file__).resolve().parents[1]
checks = []
for path in sorted((root / 'stl_fit_check').glob('*.stl')):
    data = path.read_bytes()
    count = struct.unpack_from('<I', data, 80)[0]
    assert len(data) == 84 + count * 50, f'Unexpected STL encoding: {path}'
    dtype = np.dtype([('normal','<f4',(3,)),('verts','<f4',(3,3)),('attr','<u2')])
    triangles = np.frombuffer(data, dtype=dtype, count=count, offset=84)['verts'].astype(float)
    points = np.round(triangles.reshape(-1,3), 5)
    vertices, inverse = np.unique(points, axis=0, return_inverse=True)
    faces = inverse.reshape(-1,3)
    edges = np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1)
    _, edge_counts = np.unique(edges, axis=0, return_counts=True)
    area2 = np.linalg.norm(np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]),axis=1)
    volume = abs(np.einsum('ij,ij->i',triangles[:,0],np.cross(triangles[:,1],triangles[:,2])).sum()/6)
    bounds = vertices.max(axis=0)-vertices.min(axis=0)
    row = dict(file=path.name, triangles=count, bounds_mm=bounds.round(4).tolist(), volume_mm3=round(float(volume),3),
               nonmanifold_edges=int((edge_counts!=2).sum()), degenerate_triangles=int((area2<1e-9).sum()),
               fits_k2_plus=bool((bounds<=350).all()))
    checks.append(row)
    assert row['nonmanifold_edges']==0, row
    assert row['degenerate_triangles']==0, row
    assert row['fits_k2_plus'], row
    print(path.name, 'PASS', row['bounds_mm'])
(root/'mesh_checks.json').write_text(json.dumps(checks,indent=2)+'\n')
print('Validated',len(checks),'STLs; dimensions assume STL export in millimetres.')

