import numpy as np
from scipy.ndimage import imread
from math import pi, sqrt, sin, cos
import subprocess
import pickle

from random import random

from shapely import geometry as geom
from shapely import affinity

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

def diagonal_lines(grey, w,h):
    x = max(w,h)
    d = sqrt(x**2 * 2)
    nlines = int(d * (1. - (grey / 256.)))
    if nlines == 0: return geom.MultiLineString([])

    step = d / nlines
    xstep = sqrt(step**2 / 2) * 2
    lines = []
    for i in range(nlines):
        if i*xstep <= x:
            lines.append(geom.LineString([(i*xstep,0), (0,i*xstep)]))
        else:
            lines.append(geom.LineString([(i*xstep-x,x), (x,i*xstep-x)]))
    return geom.MultiLineString(lines)


def hatching(grey, w,h):
    x = max(w,h)
    d = sqrt(x**2 * 2)
    b = 1. - (grey / 255.) # blackenss
    nlines = 2*(x - sqrt(x**2 - b*x**2))*(120./100.)
    if nlines == 0: return geom.MultiLineString([])

    step = d / nlines
    xstep = sqrt(step**2 / 2) * 2
    lines = []

    xh = max(w,h) / 2.
    rev = True

    for i in range(int(nlines)):
        if i*xstep <= x:
            line = geom.LineString([(i*xstep,0), (0,i*xstep)])
        else:
            line = geom.LineString([(i*xstep-x,x), (x,i*xstep-x)])

        if rev:
            x1,y1,x2,y2 = *line.coords[0], *line.coords[1]
            x1 = (xh*2-x1)
            x2 = (xh*2-x2)
            line = geom.LineString([(x1,y1), (x2,y2)])

        lines.append(line)
        rev = not rev

    return geom.MultiLineString(lines)

def hatch_shade(step, w,h):
    x = max(w,h)
    nlines = 2 * x / step # you have to go twice as far to fill the whole square with hash
    if nlines == 0: return geom.MultiLineString([])

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
    return {g: hatching(g, w,h) for g in greys}
    return {g: diagonal_lines(g, w,h) for g in greys}
    return {g: random_lines(g, w,h) for g in greys}

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
def init_shade_data_cache():
    global grey_shade_cache
    try:
        with open(grey_shade_cache_filename, 'rb') as f:
            grey_shade_cache = pickle.load(f)
    except FileNotFoundError:
        pass

def save_shade_data_cache():
    global grey_shade_cache
    with open(grey_shade_cache_filename, 'wb') as f:
        pickle.dump(grey_shade_cache, f, pickle.HIGHEST_PROTOCOL)

def test_shade_grey(shade_fn, inpt):
    global grey_shade_cache

    if inpt in grey_shade_cache:
        print('Cached:', inpt, '=', grey_shade_cache[inpt])
        return grey_shade_cache[inpt]
    print('Not Cached:', inpt)

    lines = shade_fn(inpt, 100,100)

    filename = 'temp_grey_test.svg'
    dwg = svg.Drawing(filename)
    for line in lines:
        svgline = svg.shapes.Line(line.coords[0], line.coords[1])
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

def calibrate_grey(target_grey, shade_fn, tolerance=5, clear_cache=False):
    lo,hi = 1, 100
    mid = lo + (hi - lo) / 2

    hi_grey = test_shade_grey(shade_fn, hi)
    mid_grey = test_shade_grey(shade_fn, mid)
    lo_grey = test_shade_grey(shade_fn, lo)

    while not within(target_grey, tolerance, mid_grey):
        if mid_grey > target_grey:
            hi = mid
        else:
            lo = mid

        mid = lo + (hi - lo) / 2
        hi_grey = test_shade_grey(shade_fn, hi)
        mid_grey = test_shade_grey(shade_fn, mid)
        lo_grey = test_shade_grey(shade_fn, lo)

        print(lo, mid, hi, mid_grey)

def render_svg(filename, width=200):
    subprocess.run(['/usr/bin/inkscape', '-z', '-f', filename, '-w', str(width), '-b', 'white', '-e', filename + '.png'], stdout=subprocess.DEVNULL)
    subprocess.run(['/usr/bin/convert', '-type', 'Grayscale', filename + '.png', filename + '.png'], stdout=subprocess.DEVNULL)
