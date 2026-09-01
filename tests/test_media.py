import io
import unittest

import torch
from PIL import Image

from kie.media import image_tensor_to_png_bytes, bytes_to_image_tensor


class TestMedia(unittest.TestCase):
    def test_image_round_trip_shape(self):
        source = torch.zeros((1, 8, 12, 3), dtype=torch.float32)
        source[:, :, :, 0] = 1.0
        content = image_tensor_to_png_bytes(source)
        img = Image.open(io.BytesIO(content))
        self.assertEqual(img.size, (12, 8))
        recovered = bytes_to_image_tensor(content)
        self.assertEqual(tuple(recovered.shape), (1, 8, 12, 3))
        self.assertGreater(float(recovered[0, 0, 0, 0]), 0.99)


if __name__ == "__main__":
    unittest.main()

