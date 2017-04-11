# coding=utf-8
import unittest
from hypothesis import given, reject
from hypothesis.strategies import lists, floats

from albion.plugin import Plugin
from albion.utils import distance2
from albion.utils import length


class TestFakeGeneratriceTranslationVector(unittest.TestCase):
    def test_3_points(self):
        centroid1 = [10, 10, 10]
        centroid2 = [20, 10, 10]

        result = Plugin._compute_fake_generatrice_translation_vec(
            centroid1, centroid2, 5)

        self.assertEqual([-5, 0, 0], result)

    @given(lists(floats(max_value=1e+100, min_value=-1e+100),
                 min_size=3, max_size=3),
           lists(floats(max_value=1e+100, min_value=-1e+100),
                 min_size=3, max_size=3),
           floats(max_value=1000, min_value=1))
    def test_points(self, centroid1, centroid2, distance):
        if distance2(centroid1[0:2], centroid2[0:2]) < 1 or \
           length(centroid1) < 0.01 or length(centroid2) < 0.01:
            reject()

        result = Plugin._compute_fake_generatrice_translation_vec(
            centroid1, centroid2, distance)

        # distance only applies to xy
        self.assertTrue(abs(length(result[0:2]) - distance) < 0.00001)

        def sign(f): return 1 if f > 0 else -1

        self.assertEqual(sign(result[0]), sign(centroid1[0] - centroid2[0]))
        self.assertEqual(sign(result[1]), sign(centroid1[1] - centroid2[1]))
        self.assertEqual(sign(result[2]), sign(centroid1[2] - centroid2[2]))


if __name__ == '__main__':
    unittest.main()
