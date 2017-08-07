# vim: set fileencoding=utf-8 :

import operator
from functools import reduce
from .helpers import *

# point convolution
def conv(image, mask, x_position, y_position):
    s = 0.0
    for x in range(0, mask.width):
        for y in range(0, mask.height):
            m = mask(x, y)
            i = image(x + x_position, y + y_position)
            p = run_fn2(operator.mul, m, i)
            s = run_fn2(operator.add, s, p)

    return run_fn2(operator.truediv, s, mask.get_scale())

def compass(image, mask, x_position, y_position, n_rot, fn):
    acc = []
    for i in range(0, n_rot):
        result = conv(image, mask, x_position, y_position)
        result = run_fn(abs, result)
        acc.append(result)
        mask = mask.rot45()

    return reduce(lambda a, b: run_fn2(fn, a, b), acc)

class TestConvolution(PyvipsTester):

    def setUp(self):
        im = pyvips.Image.mask_ideal(100, 100, 0.5, reject = True, optical = True)
        self.colour = im * [1, 2, 3] + [2, 3, 4]
        self.colour = self.colour.copy(interpretation = pyvips.Interpretation.SRGB)
        self.mono = self.colour.extract_band(1)
        self.mono = self.mono.copy(interpretation = pyvips.Interpretation.B_W)
        self.all_images = [self.mono, self.colour]
        self.sharp = pyvips.Image.new_from_array([[-1, -1,  -1],
                                                [-1,  16, -1],
                                                [-1, -1,  -1]], scale = 8)
        self.blur = pyvips.Image.new_from_array([[1, 1, 1],
                                               [1, 1, 1],
                                               [1, 1, 1]], scale = 9)
        self.line = pyvips.Image.new_from_array([[ 1,  1,  1],
                                               [-2, -2, -2],
                                               [ 1,  1,  1]])
        self.sobel = pyvips.Image.new_from_array([[ 1,  2,  1],
                                                [ 0,  0,  0],
                                                [-1, -2, -1]])
        self.all_masks = [self.sharp, self.blur, self.line, self.sobel]

    def test_conv(self):
        for im in self.all_images:
            for msk in self.all_masks:
                for prec in [pyvips.Precision.INTEGER, pyvips.Precision.FLOAT]:
                    convolved = im.conv(msk, precision = prec)

                    result = convolved(25, 50)
                    true = conv(im, msk, 24, 49)
                    self.assertAlmostEqualObjects(result, true)

                    result = convolved(50, 50)
                    true = conv(im, msk, 49, 49)
                    self.assertAlmostEqualObjects(result, true)

    # don't test conva, it's still not done
    def dont_est_conva(self):
        for im in self.all_images:
            for msk in self.all_masks:
                print("msk:")
                msk.matrixprint()
                print("im.bands = %s" % im.bands)

                convolved = im.conv(msk, precision = pyvips.Precision.APPROXIMATE)

                result = convolved(25, 50)
                true = conv(im, msk, 24, 49)
                print("result = %s, true = %s" % (result, true))
                self.assertLessThreshold(result, true, 5)

                result = convolved(50, 50)
                true = conv(im, msk, 49, 49)
                print("result = %s, true = %s" % (result, true))
                self.assertLessThreshold(result, true, 5)

    def test_compass(self):
        for im in self.all_images:
            for msk in self.all_masks:
                for prec in [pyvips.Precision.INTEGER, pyvips.Precision.FLOAT]:
                    for times in range(1, 4):
                        convolved = im.compass(msk,
                                               times = times,
                                               angle = pyvips.Angle45.D45,
                                               combine = pyvips.Combine.MAX,
                                               precision = prec)

                        result = convolved(25, 50)
                        true = compass(im, msk, 24, 49, times, max)
                        self.assertAlmostEqualObjects(result, true)

        for im in self.all_images:
            for msk in self.all_masks:
                for prec in [pyvips.Precision.INTEGER, pyvips.Precision.FLOAT]:
                    for times in range(1, 4):
                        convolved = im.compass(msk,
                                               times = times,
                                               angle = pyvips.Angle45.D45,
                                               combine = pyvips.Combine.SUM,
                                               precision = prec)

                        result = convolved(25, 50)
                        true = compass(im, msk, 24, 49, times, operator.add)
                        self.assertAlmostEqualObjects(result, true)

    def test_convsep(self):
        for im in self.all_images:
            for prec in [pyvips.Precision.INTEGER, pyvips.Precision.FLOAT]:
                gmask = pyvips.Image.gaussmat(2, 0.1,
                                            precision = prec)
                gmask_sep = pyvips.Image.gaussmat(2, 0.1,
                                                separable = True,
                                                precision = prec)

                self.assertEqual(gmask.width, gmask.height)
                self.assertEqual(gmask_sep.width, gmask.width)
                self.assertEqual(gmask_sep.height, 1)

                a = im.conv(gmask, precision = prec)
                b = im.convsep(gmask_sep, precision = prec)

                a_point = a(25, 50)
                b_point = b(25, 50)

                self.assertAlmostEqualObjects(a_point, b_point, places = 1)

    def test_fastcor(self):
        for im in self.all_images:
            for fmt in noncomplex_formats:
                small = im.crop(20, 45, 10, 10).cast(fmt)
                cor = im.fastcor(small)
                v, x, y = cor.minpos()

                self.assertEqual(v, 0)
                self.assertEqual(x, 25)
                self.assertEqual(y, 50)

    def test_spcor(self):
        for im in self.all_images:
            for fmt in noncomplex_formats:
                small = im.crop(20, 45, 10, 10).cast(fmt)
                cor = im.spcor(small)
                v, x, y = cor.maxpos()

                self.assertEqual(v, 1.0)
                self.assertEqual(x, 25)
                self.assertEqual(y, 50)

    def test_gaussblur(self):
        for im in self.all_images:
            for prec in [pyvips.Precision.INTEGER, pyvips.Precision.FLOAT]:
                for i in range(5, 10):
                    sigma = i / 5.0
                    gmask = pyvips.Image.gaussmat(sigma, 0.2,
                                                precision = prec)

                    a = im.conv(gmask, precision = prec)
                    b = im.gaussblur(sigma, min_ampl = 0.2, precision = prec)

                    a_point = a(25, 50)
                    b_point = b(25, 50)

                    self.assertAlmostEqualObjects(a_point, b_point, places = 1)

    def test_sharpen(self):
        for im in self.all_images:
            for fmt in noncomplex_formats:
                # old vipses used "radius", check that that still works
                sharp = im.sharpen(radius = 5)

                for sigma in [0.5, 1, 1.5, 2]:
                    im = im.cast(fmt)
                    sharp = im.sharpen(sigma = sigma)

                    # hard to test much more than this
                    self.assertEqual(im.width, sharp.width)
                    self.assertEqual(im.height, sharp.height)

                    # if m1 and m2 are zero, sharpen should do nothing
                    sharp = im.sharpen(sigma = sigma, m1 = 0, m2 = 0)
                    sharp = sharp.colourspace(im.interpretation)
                    #print("testing sig = %g" % sigma)
                    #print("testing fmt = %s" % fmt)
                    #print("max diff = %g" % (im - sharp).abs().max())
                    self.assertEqual((im - sharp).abs().max(), 0)

if __name__ == '__main__':
    unittest.main()

