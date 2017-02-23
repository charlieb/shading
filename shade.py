import numpy as np
from scipy.ndimage import imread
from math import pi, sqrt, sin, cos
import svgwrite as svg
from random import random
from PIL import Image

from skimage import measure
from shapely import geometry as geom
from shapely import coords, affinity

from itertools import product


from shade_textures import *

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
    def split_from_contained(self):
        shape = MultiGreyPolygon(self.grey, [self])
        for p in self.container_for:
            shape = shape.difference(p)
        return shape

def clean_regions(polys):
    all_clean = False
    while not all_clean:
        clean = []
        all_clean = True
        for i, p1 in enumerate(polys):
            cleaned_p1 = p1
            for p2 in polys[i+1:]:
                if p1 == p2: continue
                if p1.touches(p2):
                    cleaned_p1 = p1.difference(p2.buffer(0.1))
                    all_clean = False
                    break

            if isinstance(cleaned_p1, geom.MultiPolygon):
                clean.extend(GreyPolygon(p1.grey, p) for p in cleaned_p1 if not p.is_empty)
            elif not cleaned_p1.is_empty:
                clean.append(GreyPolygon(p1.grey, cleaned_p1))
        polys = clean

    return polys

def find_regions(image, values):
    polys = []
    min_area = 9.
    for val in values:
        conts = measure.find_contours(image, val) 
        for cont in conts:
            if len(cont) >= 4:
                ps = geom.Polygon(cont)

                # fix all self intersections
                ps = ps.buffer(0)

                if isinstance(ps, geom.MultiPolygon):
                    polys.extend(GreyPolygon(val, p) for p in ps if not p.is_empty and p.area > min_area)
                elif not ps.is_empty and ps.area > min_area:
                    polys.append(GreyPolygon(val, ps))

    return polys

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
        svgline = svg.shapes.Line(line.coords[0], line.coords[1])
        svgline.fill('none')
        svgline.stroke(color, width=1.00, opacity=1.0)
        dwg.add(svgline)

    dwg.viewbox(minx=0, miny=0, width=w, height=h)
    dwg.save()


def shade(polys, textures):
    lines = []
    for poly in polys:
        shade_lines = textures[poly.grey]

        #print(poly.grey, poly.area, len(shade_lines))
        # shade lines are within the shape
        shade_lines = shade_lines.intersection(poly)

        for p in poly.container_for:
            shade_lines = shade_lines.difference(p)
            
        if isinstance(shade_lines, geom.LineString):
            lines.append(shade_lines)
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

    return lines




def fix_greys(polys, image):
    max_trials = 200
    for i, poly in enumerate(polys):
        point_ok = False
        trials = 0
        while not point_ok and trials < max_trials:
            trials += 1
            x = int(poly.bounds[0] + random() * (poly.bounds[2] - poly.bounds[0]))
            y = int(poly.bounds[1] + random() * (poly.bounds[3] - poly.bounds[1]))
            pt = geom.Point(x,y)
            if pt.within(poly):
                fail = False
                for p in poly.container_for:
                    if pt.within(p):
                        fail = True
                        break
                if not fail:
                    point_ok = True
        if point_ok:
            poly.grey = image[x,y]

def test_point(polys, point):
    for i, poly in enumerate(polys):
        if poly.contains(point):
            print(i, end=',')
    print()



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
    print('Finding Ranges: ', end='')
    for _ in range(nsteps):
        print((start, mid, end), end=',')
        values.append(mid)
        
        for pix in np.nditer(image, op_flags=['readwrite']):
            if pix >= start and pix < end:
                pix[...] = mid

        start = end
        mid = int(start + step / 2)
        end = start + step
    print()

    print('Generating Textures')
    textures = generate_textures(values, *image.shape)
    print([(tex, len(textures[tex])) for tex in textures])
    #write_svg_lines(textures[list(textures)[-2]], 'test.svg', *image.shape)
    #return

    # for each grey value, find all the regions
    print('Finding Regions')
    image = np.pad(image, 2, 'constant', constant_values = 0)
    polys = find_regions(image, values) 

    #print('Simplifying Regions')
    #simplifed = []
    #for poly in sorted(polys, key=lambda x: x.area):
    #    simple = GreyPolygon(poly.grey, poly.simplify(0.1, preserve_topology=False))
    #    simplifed.append(simple)
    #polys = simplifed

    #print('Cleaning region overlaps')
    #polys = clean_regions(polys)

    # sort them so that they are painted in the right order
    print('Sorting')
    polys = sort_polys(polys)
    print(len(polys), 'polygons')

    print('Fixing Greys')
    fix_greys(polys, image)


    print('Generating shade')
    lines = shade(polys, textures)

    print('Drawing')
    print(len(lines), 'lines')
    write_svg_lines(lines, 'test.svg', *image.shape)
    write_svg_greys(polys, 'test_polys.svg', *image.shape)
    #write_svg(polys, 'test.svg', *image.shape)

    im = Image.fromarray(image)
    im.save('test_out.png')

def test():
    p = geom.Polygon([(0,0), (0,10), (10,10), (10,0)])

    print(p.area)
    p = p.difference(geom.Point(0,0).buffer(0.1))
    print(p.area)


if __name__ == '__main__':
    init_shade_data_cache()
    calibrate_grey(64, hatch_shade, tolerance=1)
    save_shade_data_cache()
    exit()
    render_svg('grey_test.svg')
    shade_test()
    test()
    main()
