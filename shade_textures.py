import numpy as np
from scipy.ndimage import imread
from math import pi, sqrt, sin, cos
import subprocess
import pickle

import svgwrite as svg

from random import random

from shapely import geometry as geom
from shapely import affinity

from itertools import product

def in_image(x,y, w,h):
    return x + w/2 < w and \
           x + w/2 >= 0 and \
           y + h/2 < h and \
           y + h/2 >= 0


def spiral(points, step_along_spiral, step_out_per_rot, max_r):
    dr = step_out_per_rot / (2*pi)
    r = step_along_spiral
    a = r / dr
    x,y = 0,0
    npoints = 0
    while r < max_r:
        if points.shape[0] <= npoints:
            points.resize((npoints + 100000, points.shape[1]), refcheck=False)
            #print('Resize to %s points for radius %s/%s'%(points.shape[0], r, max_r))

        a += step_along_spiral / r
        r = dr * a

        x = r * np.cos(a)
        y = r * np.sin(a)

        points[npoints,0] = x
        points[npoints,1] = y

        npoints += 1

    #print('%s points'%npoints)
    points.resize((npoints, points.shape[1]), refcheck=False)

def spiral_shade(step, w,h):
    points = np.empty([0,2], dtype='float64')
    spiral(points, 2, step + 0.5, sqrt(2*(max(w,h)/2)**2))
    #print(step, points.shape)
    points[:,:] += [w/2, h/2]
    if points.shape[0] < 2:
        return geom.MultiLineString([])
    lines = geom.asLineString(points)#.intersection(geom.box(0,0,w,h))
    if isinstance(lines, geom.LineString):
        return geom.MultiLineString([lines])
    else:
        return lines

def many_spirals(step, w,h):
    """Step range should be 0-1 but internally it's 1-0 because more spiral = darker"""
    spacing = 100
    points = np.empty([0,2], dtype='float64')
    spiral(points, 0.5, 2, (1-step) * spacing)
    if points.shape[0] < 2: return geom.MultiLineString([])
    little_spiral = geom.asLineString(points)
    lines = []
    print((w/spacing) * (h/spacing), 'spirals')
    for x,y in product(range(int(w/spacing)), range(int(h/spacing))):
        lines.append(affinity.translate(little_spiral, x*spacing, y*spacing))
    return geom.MultiLineString(lines)

def random_line(length, w,h):
    x = random()*w
    y = random()*h
    p1 = (x,y)
    a = random() * 2*pi
    p2 = (x + length*cos(a), y + length*sin(a))
    return geom.LineString([p1, p2])

def random_line(length, w,h):
    return geom.LineString([(random()*w, random()*h), (random()*w, random()*h)])

def random_lines(grey, w,h):
    black_lines_per_area = 0.02
    increase_area = 1.1
    woff, hoff = w*(1-increase_area) / 2, h*(1-increase_area) / 2
    w *= increase_area
    h *= increase_area

    nlines = 1 + int(black_lines_per_area * w*h * (1 - grey / 256.))
    length = sqrt(w**2 + h**2)
    return geom.MultiLineString([affinity.translate(random_line(length, w, h), woff, hoff)
                                for _ in range(nlines)])

def diagonal_lines(step, w,h):
    if step == 0: return geom.MultiLineString([])
    x = max(w,h)
    nlines = int(2 * x / step)

    lines = []
    for i in range(nlines):
        if i*step <= x:
            lines.append(geom.LineString([(i*step,0), (0,i*step)]))
        else:
            lines.append(geom.LineString([(i*step-x,x), (x,i*step-x)]))
    return geom.MultiLineString(lines)


def hatch_shade(step, w,h):
    if step == 0: return geom.MultiLineString([])
    x = max(w,h)
    nlines = 2 * x / step # you have to go twice as far to fill the whole square with hash

    lines = []
    xh = x / 2.
    for i in range(int(nlines)):
        if i*step <= x:
            line = geom.LineString([(i*step,0), (0,i*step)])
        else:
            line = geom.LineString([(i*step-x,x), (x,i*step-x)])
        lines.append(line)

        x1,y1,x2,y2 = *line.coords[0], *line.coords[1]
        x1 = (xh*2-x1)
        x2 = (xh*2-x2)
        line = geom.LineString([(x1,y1), (x2,y2)])

        lines.append(line)

    return geom.MultiLineString(lines)

def generate_textures(greys, w,h):
    return {g: many_spirals(v, w,h) for g,v in zip(greys, find_inputs_for_greys(greys, many_spirals))}
    return {g: spiral_shade(v, w,h) for g,v in zip(greys, find_inputs_for_greys(greys, spiral_shade))}
    return {g: hatch_shade(v, w,h) for g,v in zip(greys, find_inputs_for_greys(greys, hatch_shade))}
    return {g: diagonal_lines(v, w,h) for g,v in zip(greys, find_inputs_for_greys(greys, diagonal_lines))}

def shade_test():
    dwg = svg.Drawing('grey_test.svg')
    nsteps = 10
    x = 500
    for i in range(nsteps):
        grey = (i+1) * 256 / nsteps
        box = geom.box(0, i * x/nsteps, x/nsteps, (i+1) * x/nsteps)
        #lines = affinity.translate(diagonal_lines(grey, x/nsteps, x/nsteps), x/nsteps, i*x/nsteps)
        lines = affinity.translate(hatching(grey, x/nsteps, x/nsteps), x/nsteps, i*x/nsteps)

        svgbox = svg.shapes.Polygon(box.exterior.coords)
        svgbox.fill('rgb(%i,%i,%i)'%(grey,grey,grey))
        dwg.add(svgbox)
        for line in lines:
            svgline = svg.shapes.Line(line.coords[0], line.coords[1])
            svgline.fill('none')
            svgline.stroke('black', width=1.00)
            dwg.add(svgline)

    dwg.viewbox(minx=0, miny=0, width=2*x/nsteps, height=x)
    dwg.save()


grey_shade_cache = {}
grey_shade_cache_filename = 'grey_cache.pickle'
def init_texture_data_cache():
    global grey_shade_cache
    try:
        with open(grey_shade_cache_filename, 'rb') as f:
            grey_shade_cache = pickle.load(f)
    except FileNotFoundError:
        pass

def save_texture_data_cache():
    global grey_shade_cache
    with open(grey_shade_cache_filename, 'wb') as f:
        pickle.dump(grey_shade_cache, f, pickle.HIGHEST_PROTOCOL)

def test_shade_grey(shade_fn, inpt):
    global grey_shade_cache

    if inpt in grey_shade_cache:
        return grey_shade_cache[inpt]

    lines = shade_fn(inpt, 100,100)

    filename = 'temp_grey_test.svg'
    dwg = svg.Drawing(filename)
    for line in lines:
        svgline = svg.shapes.Polyline(line.coords)
        svgline.fill('none')
        svgline.stroke('black', width=1.00)
        dwg.add(svgline)

    dwg.viewbox(minx=0, miny=0, width=100, height=100)
    dwg.save()

    render_svg(filename)
    image = imread(filename + '.png')
    grey = np.sum(image) / np.product(image.shape)

    grey_shade_cache[inpt] = grey
    return grey


def within(x, tolerance, y):
    return x - tolerance < y and x + tolerance > y

def calibrate_grey(target_grey, shade_fn, tolerance=5):
    lo,hi = 0, 1#000
    mid = lo + (hi - lo) / 2

    hi_grey = test_shade_grey(shade_fn, hi)
    mid_grey = test_shade_grey(shade_fn, mid)
    lo_grey = test_shade_grey(shade_fn, lo)

    print('----', target_grey, '----')
    while not within(target_grey, tolerance, mid_grey):
        if mid_grey > target_grey:
            hi = mid
        else:
            lo = mid

        mid = lo + (hi - lo) / 2
        hi_grey = test_shade_grey(shade_fn, hi)
        mid_grey = test_shade_grey(shade_fn, mid)
        lo_grey = test_shade_grey(shade_fn, lo)
        print(mid, mid_grey)

    print(target_grey, mid)
    save_texture_data_cache()
    return mid

def render_svg(filename, width=200):
    subprocess.run(['/usr/bin/inkscape', '-z', '-f', filename, '-w', str(width), '-b', 'white', '-e', filename + '.png'], stdout=subprocess.DEVNULL)
    subprocess.run(['/usr/bin/convert', '-type', 'Grayscale', filename + '.png', filename + '.png'], stdout=subprocess.DEVNULL)

def find_inputs_for_greys(greys, shade_fn, tolerance=2):
    calculate_normalization_scale(shade_fn)
    print(list(zip(greys, [texture_data[shade_fn]["normalization_scale"](grey) for grey in greys])))
    return [calibrate_grey(texture_data[shade_fn]["normalization_scale"](grey), shade_fn, tolerance) for grey in greys] 

def calculate_normalization_scale(shade_fn):
    gmin = test_shade_grey(shade_fn, texture_data[shade_fn]["calibration_range"][0])
    gmax = test_shade_grey(shade_fn, texture_data[shade_fn]["calibration_range"][1])
    gmin, gmax = min(gmax,gmin), max(gmax,gmin)
    print(shade_fn.__name__, gmax, gmin)
    texture_data[shade_fn]["normalization_scale"] = lambda x: gmin + (x / 255.) * (gmax - gmin)

def scales():
    pass

def id(x): return x

texture_data = {
    diagonal_lines : {"calibration_range": (0,100), "normalization_scale": id },
    hatch_shade : {"calibration_range": (0,100), "normalization_scale": id},
    spiral_shade : {"calibration_range": (0,100), "normalization_scale": id},
    many_spirals : {"calibration_range": (0,1), "normalization_scale": id},
    scales : {"calibration_range": (0,100), "normalization_scale": id},
}
