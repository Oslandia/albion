# coding=utf-8
import unittest


# from .graph_operations import build_subgraph_from_graph_in_section
from albion.utils import (sort_id_along_implicit_centroids_line)


class TestLineFromCentroid(unittest.TestCase):
    def test_3_points(self):
        centroids = {
            1: [0, 0],
            2: [10, 10],
            3: [100, 100]
        }

        result = sort_id_along_implicit_centroids_line(centroids)

        self.assertEqual([1, 2, 3], result)


    def test_3_points_reverse(self):
            centroids = {
                4: [70, 70],
                5: [10, 10],
                6: [100, 100]
            }

            result = sort_id_along_implicit_centroids_line(centroids)

            self.assertEqual([5, 4, 6], result)


    def test_real_case(self):
        c = {
            25: [326925.76, 2080622.86],
            19: [326625.34, 2080735.57],
            30: [326874.72, 2080674.8],
            70: [326699.39, 2080698.75],
            31: [326774.38, 2080674.02]
        }


        result = sort_id_along_implicit_centroids_line(c)

        self.assertEqual([25, 30, 31, 70, 19], result)



if __name__ == '__main__':
    unittest.main()
