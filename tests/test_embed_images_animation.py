import unittest


class EmbedImagesAnimationTests(unittest.TestCase):
    def test_animated_image_bytes_are_preserved_when_optimizing(self):
        try:
            from PIL import Image
            import io
        except ImportError:
            self.skipTest("Pillow is not installed")

        from scripts.svg_finalize.embed_images import _optimize_image_bytes

        frame_a = Image.new("RGBA", (12, 12), (255, 0, 0, 255))
        frame_b = Image.new("RGBA", (12, 12), (0, 0, 255, 255))
        buffer = io.BytesIO()
        frame_a.save(
            buffer,
            format="GIF",
            save_all=True,
            append_images=[frame_b],
            duration=80,
            loop=0,
        )
        original = buffer.getvalue()

        optimized = _optimize_image_bytes(
            original,
            "image/gif",
            compress=True,
            max_dimension=8,
        )

        self.assertEqual(optimized, original)


if __name__ == "__main__":
    unittest.main()
