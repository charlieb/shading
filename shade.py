import numpy as np
from scipy.ndimage import imread
from math import pi, sqrt, sin, cos
import svgwrite as svg
from random import random, choice
from PIL import Image

from skimage import measure, filters, morphology
from shapely import geometry as geom
from shapely import coords

from itertools import product

from rasterio import features

# Change to grey poly
class GreyPolygon(geom.Polygon):
    def __init__(self, grey, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.grey = grey
        self.container_for = []

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
    for val in values:
        conts = measure.find_contours(image, val) 
        for cont in conts:
            if len(cont) >= 4:
                # add points 
                # check size is big enough
                ps = GreyPolygon(val, cont)
                if ps.area < 9: continue
                # fix all self intersections
                ps = ps.buffer(0)

                if isinstance(ps, geom.MultiPolygon):
                    polys.extend(GreyPolygon(val, p) for p in ps if not p.is_empty)
                elif not ps.is_empty:
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

    print([n for _, n in sorted(zip(polys, within_n), key=lambda x: x[1])])

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

def shade(polys):
    lines = []
    for poly in polys:
        step = 1 + 1 * poly.grey / 256.
        sx, sy, ex, ey = poly.bounds
        max_range = max(ex - sx, ey - sy) * 2
        shade_lines = geom.MultiLineString([geom.LineString([(sx + x * step, sy), (sx, sy + x * step)]) 
                                            for x in range(int(max_range / step))])
        # shade lines are within the shape
        shade_lines = shade_lines.intersection(poly)
        # but any contained shapes must be removed
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
    print('Ranges:')
    for _ in range(nsteps):
        print('start, mid, end', start, mid, end)
        values.append(mid)
        
        for pix in np.nditer(image, op_flags=['readwrite']):
            if pix >= start and pix < end:
                pix[...] = mid

        start = end
        mid = int(start + step / 2)
        end = start + step

    # for each grey value, find all the regions
    print('Finding regions')
    image = np.pad(image, 2, 'constant', constant_values = 0)
    polys = find_regions(image, values) 

    #print('Cleaning region overlaps')
    #polys = clean_regions(polys)

    # sort them so that they are painted in the right order
    print('Sorting')
    polys = sort_polys(polys)

    print('Generating shade')
    lines = shade(polys)
    print(len(lines))

    print('Drawing')
    print(len(lines), 'lines')
    write_svg_lines(lines, 'test.svg', *image.shape)
    #write_svg(polys, 'test.svg', *image.shape)
    #write_svg_greys(polys, 'test.svg', *image.shape)

    im = Image.fromarray(image)
    im.save('test_out.png')

def test():
    p = geom.Polygon([(0,0), (0,10), (10,10), (10,0)])

    print(p.area)
    p = p.difference(geom.Point(0,0).buffer(0.1))
    print(p.area)


if __name__ == '__main__':
    test()
    main()
