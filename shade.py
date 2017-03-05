import numpy as np
from scipy.ndimage import imread
from math import pi, sqrt, sin, cos
import svgwrite as svg
from random import random
from PIL import Image

from skimage import measure
from shapely import geometry as geom
from shapely import affinity

from itertools import product


from shade_textures import *

def flatten_Polygons(polys):
    all_polys = []
    for poly in polys:
        if isinstance(poly, geom.MultiPolygon):
            all_polys.extend(list(poly))
        else:
            all_polys.append(poly)
    return all_polys

def filter_Polygons(polys):
    res = []
    try:
        for poly in polys:
            if isinstance(poly, geom.Polygon) and not poly.is_empty:
                res.append(poly)
    except TypeError: # not an iterable
        if isinstance(polys, geom.Polygon) and not polys.is_empty:
            res.append(polys)

    return geom.MultiPolygon(res)

def find_regions(image, values, min_area=9.):
    polys = []
    for val in values:
        conts = measure.find_contours(image, val) 
        for cont in conts:
            if len(cont) >= 4:
                ps = geom.Polygon(cont)

                # fix all self intersections
                ps = ps.buffer(0)

                if isinstance(ps, geom.MultiPolygon):
                    polys.extend(p for p in ps if not p.is_empty and p.area > min_area)
                elif not ps.is_empty and ps.area > min_area:
                    polys.append(ps)

    return polys

### GREYPOLYGON TYPES BELOW THIS LINE
class MultiGreyPolygon(geom.MultiPolygon):
    def __init__(self, grey, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.grey = grey
    def difference(self, other):
        polys = super().difference(other)
        if isinstance(polys, geom.Polygon):
            return MultiGreyPolygon(self.grey, [polys])
        else:
            return MultiGreyPolygon(self.grey, [p for p in polys if isinstance(p, geom.Polygon)])

class GreyPolygon(geom.Polygon):
    def __init__(self, grey, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.grey = grey
        self.container_for = []
    def buffer(self, distance, **kwargs):
        polys = super().buffer(distance, **kwargs)
        if distance > 0 or isinstance(polys, geom.Polygon):
            return GreyPolygon(self.grey, polys) # should only ever be one because it just growing
        elif isinstance(polys, geom.MultiPolygon):
            raise TypeError('GreyPolygons are not allowed to be split by buffering')

def sort_polys(polys):
    # count how many other polys each one it within
    within_n = [0] * len(polys)
    for i, poly1 in enumerate(polys):
        for j, poly2 in enumerate(polys):
            if i == j: continue
            if poly1.within(poly2):
                within_n[i] += 1
                poly2.container_for.append(poly1)

    #print([n for _, n in sorted(zip(polys, within_n), key=lambda x: x[1])])

    # simply order based on how many each one is in, smallest first to
    # obtain the correct painters algorithm order
    return [poly for poly, _ in sorted(zip(polys, within_n), key=lambda x: x[1])]

def int_spiral():
    visited = []
    facing = (0,1)
    right = {(0,1) : (1,0), 
             (1,0) : (0,-1),
             (0,-1): (-1,0),
             (-1,0): (0,1)}
    x = y = 0
    while True:
        yield x,y
        visited.insert(0, (x,y))
        look_right = right[facing]
        if (x + right[facing][0], y + right[facing][1]) not in visited:
            facing = right[facing]
        x += facing[0]
        y += facing[1]

def fix_grey(poly, image):
    minx, miny, maxx, maxy = poly.bounds
    for x,y in product(range(int(minx), int(maxx)), range(int(miny), int(maxy))):
        pt = geom.Point(x,y)
        if pt.within(poly):
            fail = False
            for p in poly.container_for:
                if pt.within(p):
                    fail = True
                    break
            if not fail:
                poly.grey = image[x,y]
                return

def fix_greys(polys, image):
    for i, poly in enumerate(polys):
        fix_grey(poly, image)

### SHADE
def shade(polys, textures):
    lines = []
    for i, poly in enumerate(polys):
        shade_lines = textures[poly.grey]
        if i % 100 == 0:
            print('/', end='', flush=True)
        elif i % 10 == 0:
            print(':', end='', flush=True)
        else:
            print('.', end='', flush=True)

        #print(poly.grey, poly.area, len(shade_lines))
        # shade lines are within the shape
        shade_lines = shade_lines.intersection(poly)

        for p in poly.container_for:
            shade_lines = shade_lines.difference(p)

        if isinstance(shade_lines, geom.LineString):
            lines.append(shade_lines)
            continue
        elif isinstance(shade_lines, geom.Point):
            continue

        for line in shade_lines:
            if line.is_empty: continue

            if isinstance(line, geom.MultiLineString) or isinstance(line, geom.GeometryCollection): 
                lines.extend(li for li in line if not li.is_empty and isinstance(li, geom.LineString))
                #print([type(li).__name__ for li in line])
            elif isinstance(line, geom.LineString) and not line.is_empty:
                lines.append(line)
                #print('Line', line.length)
            else:
                print('??', type(line).__name__)

    print()
    return lines

### WRITING FUNCTIONS
def write_svg(polys, filename, w,h, color='black', opacity=1.0):
    dwg = svg.Drawing(filename)
    for poly in polys:
        svgline = svg.shapes.Polygon(poly.exterior.coords)
        #svgline.fill('grey')
        svgline.fill('none')
        svgline.stroke(color, width=1.00)
        dwg.add(svgline)

    dwg.viewbox(minx=0, miny=0, width=w, height=h)
    dwg.save()

def write_svg_greys(polys, filename, w,h, color='black', opacity=1.0):
    dwg = svg.Drawing(filename)

    for poly in polys:
        svgline = svg.shapes.Polygon(poly.exterior.coords)
        svgline.fill('rgb(%i,%i,%i)'%(poly.grey,poly.grey,poly.grey))
        svgline.stroke('none', width=1.00)
        #svgline.fill('none')
        #svgline.fill('grey', opacity=0.4)
        svgline.stroke(color, width=1.00, opacity=1.0)
        #svgline.stroke('rgb(%i,%i,%i)'%(val,val,val), width=1.0)
        dwg.add(svgline)

    dwg.viewbox(minx=0, miny=0, width=w, height=h)
    dwg.save()

def write_svg_lines(lines, filename, w,h, color='black'):
    dwg = svg.Drawing(filename)

    for line in lines:
        svgline = svg.shapes.Polyline(line.coords)
        svgline.fill('none')
        svgline.stroke(color, width=1.00, opacity=1.0)
        dwg.add(svgline)

    dwg.viewbox(minx=0, miny=0, width=w, height=h)
    dwg.save()


def test_point(polys, point):
    poly_stack = []
    for i, poly in enumerate(polys):
        if poly.contains(point):
            poly_stack.append(poly)
            print(i, end=',')
    print()
    return poly_stack

def main():
    # Change image into nstep grey image
    image = imread('test.png')
    mini = np.min(image)
    maxi = np.max(image)
    print('min %s, max %s'%(mini, maxi))

    grey_range = maxi-mini
    nsteps = 10

    step = grey_range / nsteps

    start = mini
    mid = int(start + step / 2)
    end = start + step

    values = []
    print('Finding Greys')
    for _ in range(nsteps):
        #print((start, mid, end), end=',')
        values.append(mid)
        #values.append(int(end))

        for pix in np.nditer(image, op_flags=['readwrite']):
            if pix >= start and pix < end:
                pix[...] = mid
                #pix[...] = int(end)

        start = end
        mid = int(start + step / 2)
        end = start + step
    #print()

    print('Generating Textures')
    init_texture_data_cache()
    textures = generate_textures(values, *image.shape)
    #print([(tex, len(textures[tex])) for tex in textures])
    save_texture_data_cache()
    for val, tex in textures.items():
        write_svg_lines(tex, 'texture%s.svg'%val, *image.shape)
    return

    # for each grey value, find all the regions
    print('Finding Regions')
    image = np.pad(image, 2, 'constant', constant_values = 0)
    polys = find_regions(image, values, min_area=25) 

    #print('Cleaning region overlaps')
    #polys = clean_regions(polys)

    # No need to use non-Shapely polygon types before this
    # This is the first function that returns the GreyPolygon type
    # sort them so that they are painted in the right order
    print('Sorting')
    polys = sort_polys([GreyPolygon(0, p) for p in polys])
    print(len(polys), 'polygons')

    print('Finding Greys')
    fix_greys(polys, image)

    print('Simplifying Regions')
    polys = [poly.buffer(5).buffer(-5) for poly in polys]

    print('Re-Sorting after simplification')
    for poly in polys: poly.container_for = []
    polys = sort_polys(polys)

    print('Optimizing Polygon Stacks')
    # Turn .contained_by into a proper tree
    print(sum([len(p.container_for) for p in polys]), 'links')
    for poly in polys:
        for p in poly.container_for[:]:
            for subp in p.container_for:
                if subp in poly.container_for:
                    poly.container_for.remove(subp)
    print(sum([len(p.container_for) for p in polys]), 'links')

    #test_point(polys, geom.Point(200,285))
    # 0,1,11,24,38,46,

    print('Generating shading')
    lines = shade(polys, textures)
    #lines = textures[76]

    #try:
    #    for i, poly in enumerate(polys):
    #        if poly.container_for != []:
    #            print(i, ':', [polys.index(p) for p in poly.container_for])
    #except ValueError:
    #    pass

    print('Drawing')
    #print(len(lines), 'lines')
    write_svg_lines(lines, 'test.svg', *image.shape)
    write_svg_greys(polys, 'test_polys.svg', *image.shape)
    #write_svg(polys, 'test.svg', *image.shape)

    im = Image.fromarray(image)
    im.save('test_out.png')

if __name__ == '__main__':
    #render_svg('grey_test.svg')
    #shade_test()
    main()
