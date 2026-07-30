import unittest

import numpy as np

from simplecast.audio import ReverbControl, SimpleReverb


class ReverbTests(unittest.TestCase):
    def test_disabled_reverb_preserves_microphone_audio(self) -> None:
        control = ReverbControl(False, 80)
        effect = SimpleReverb(48000, 1, control)
        source = np.linspace(-0.5, 0.5, 2048, dtype=np.float32).reshape(-1, 1)

        processed = effect.apply(source)

        self.assertTrue(np.array_equal(processed, source))

    def test_enabled_reverb_creates_a_delayed_tail(self) -> None:
        control = ReverbControl(True, 60)
        effect = SimpleReverb(1000, 1, control)
        impulse = np.zeros((500, 1), dtype=np.float32)
        impulse[0, 0] = 0.8

        processed = effect.apply(impulse)

        self.assertGreater(abs(float(processed[31, 0])), 0.01)
        self.assertGreater(np.count_nonzero(processed[1:]), 4)

    def test_amount_can_be_changed_while_capture_is_running(self) -> None:
        control = ReverbControl(True, 0)
        effect = SimpleReverb(1000, 1, control)
        source = np.zeros((500, 1), dtype=np.float32)
        source[0, 0] = 0.8
        self.assertTrue(np.array_equal(effect.apply(source), source))

        control.set_amount_percent(100)
        processed = effect.apply(source)

        self.assertGreater(np.count_nonzero(processed), 4)


if __name__ == "__main__":
    unittest.main()
