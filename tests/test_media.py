# Copyright(C) 2019, 2020 Horus View and Explore B.V.

import unittest
import os

from horus_media import (
    Client,
    ImageRequestBuilder,
    ImageProvider,
    Grid,
    Scales,
    Rect,
    Mode,
)

path = "./tests/data/"
try:
    os.mkdir(path)
except OSError:
    pass


class TestScales(unittest.TestCase):
    def test_to_size(self):
        self.assertEqual(Scales.Px_256.size, 256)
        self.assertEqual(Scales.Px_512.size, 512)
        self.assertEqual(Scales.Px_1024.size, 1024)
        self.assertEqual(Scales.Px_2048.size, 2048)
        self.assertEqual(Scales.Px_4096.size, 4096)

    def test_from_size(self):
        self.assertEqual(Scales.Px_256, Scales.from_size(100))
        self.assertEqual(Scales.Px_256, Scales.from_size(256))
        self.assertEqual(Scales.Px_1024, Scales.from_size(570))
        self.assertEqual(Scales.Px_2048, Scales.from_size(2000))


class TestGrid(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestGrid, self).__init__(*args, **kwargs)

    def test_default_constructor(self):
        grid = Grid()
        count = 0
        result = set(range(32))
        for section in grid:
            result.remove(section.index)
            count += 1
        self.assertEqual(count, 32)
        self.assertEqual(len(result), 0)

    def test_filter(self):
        grid = Grid()
        sections = grid.filter(h_min=-44, h_max=44, w_min=-170, w_max=-1)
        count = 0
        result = {8, 9, 10, 11, 16, 17, 18, 19}
        for section in sections:
            count += 1
            result.remove(section.index)

        self.assertEqual(count, 8)
        self.assertEqual(len(result), 0)

    def test_filter_wrap_right(self):
        grid = Grid()
        sections = grid.filter(w_min=36, w_max=250)
        count = 0
        result = {
            4,
            5,
            6,
            7,
            0,
            1,
            12,
            13,
            14,
            15,
            8,
            9,
            20,
            21,
            22,
            23,
            16,
            17,
            28,
            29,
            30,
            31,
            24,
            25,
        }
        for section in sections:
            result.remove(section.index)
            count += 1
        self.assertEqual(count, 24)
        self.assertEqual(len(result), 0)

    def test_filter_wrap_left(self):
        grid = Grid()
        sections = grid.filter(h_min=-44, h_max=44, w_min=-200, w_max=-36)
        result = {15, 8, 9, 10, 11, 23, 16, 17, 18, 19}
        count = 0
        for section in sections:
            result.remove(section.index)
            count += 1
        self.assertEqual(count, 10)
        self.assertEqual(len(result), 0)


class TestClient(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestClient, self).__init__(*args, **kwargs)

        recording_id = 5
        frame_uuid = "1708a7fb-af45-41b2-a0c1-1b9962f58ac0"
        host_url = "http://pocms.horus.nu:5050/web/"

        self.grid = Grid()
        self.request_builder = ImageRequestBuilder(recording_id, frame_uuid)
        self.stitcher = ImageProvider()
        self.client = Client(host_url)

    def request_stitched_sections(self, sections, scale, path=None):
        requests = self.client.fetch_all(
            self.request_builder.build(Mode.panoramic, scale, section)
            for section in sections
        )

        result = self.stitcher.combine(requests, scale.size, scale.size)
        if path:
            with open(path, "wb") as f:
                f.write(result.image.getvalue())
            result.image.close()
        return result

    def test_client_request_pano(self):
        request = self.client.fetch(
            self.request_builder.build(Mode.panoramic, Scales.Px_1024)
        )
        with open("./tests/data/pano.jpg", "wb") as file:
            file.write(request.result())

    def test_client_request(self):
        sections = self.grid.filter(h_min=-44, h_max=44, w_min=-170, w_max=-1)
        self.request_stitched_sections(
            sections, Scales.Px_1024, "./tests/data/stitched.jpg"
        )

    def test_client_request_pano_stitched(self):
        result = self.request_stitched_sections(
            self.grid, Scales.Px_1024, "./tests/data/pano_stitched.jpg"
        )
        self.assertEqual(result.to_pixel_coordinates((0, 0)).x, 0)
        self.assertEqual(result.fov, Rect(x=-180.0, y=-90.0, width=360.0, height=180.0))

    def test_client_request_single_section_stitched(self):
        result = self.request_stitched_sections(
            (self.grid[3],), Scales.Px_1024, "./tests/data/single_section_stitched.jpg"
        )
        self.assertEqual(result.to_pixel_coordinates((170.0, 0)).x, 796)
        self.assertEqual(result.fov, Rect(x=-45.0, y=45.0, width=45.0, height=45.0))

    def test_client_request_left_wrapped(self):
        sections = self.grid.filter(h_min=-46, h_max=1, w_min=-270, w_max=-46)
        result = self.request_stitched_sections(
            sections, Scales.Px_1024, "./tests/data/stitched_lw.jpg"
        )
        self.assertEqual(result.to_pixel_coordinates((0, 0)).x, 0)

    def test_client_request_right_wrapped(self):
        sections = self.grid.filter(h_min=0, w_min=70, w_max=246)
        result = self.request_stitched_sections(
            sections, Scales.Px_1024, "./tests/data/stitched_rw.jpg"
        )
        self.assertEqual(result.to_pixel_coordinates((70.0, 0)).x, 1592)
        self.assertEqual(result.fov, Rect(x=-180.0, y=0.0, width=225.0, height=90.0))

    def test_client_request_left_right_wrapped(self):
        sections = self.grid.filter(w_min=-240, w_max=246)
        result = self.request_stitched_sections(
            sections, Scales.Px_1024, "./tests/data/stitched_lrw.jpg"
        )
        self.assertEqual(result.to_pixel_coordinates((-240.0, 0)).x, 2730)
        self.assertEqual(result.fov, Rect(x=-180.0, y=-90.0, width=180.0, height=180.0))


if __name__ == "__main__":
    unittest.main()
