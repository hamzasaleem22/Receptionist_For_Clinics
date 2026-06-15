import numpy as np
import pytest
from livekit import rtc

from agent import Assistant


class TestVolumeAmplification:
    @pytest.fixture
    def assistant(self):
        return Assistant()

    def _make_frame(self, samples: list[int], sample_rate: int = 24000, channels: int = 1):
        data = np.array(samples, dtype=np.int16).tobytes()
        return rtc.AudioFrame(
            data=data,
            sample_rate=sample_rate,
            num_channels=channels,
            samples_per_channel=len(samples) // channels,
        )

    def test_no_clipping_at_max_volume(self, assistant):
        samples = [32000, -32000, 10000, -10000, 0] * 100
        frame = self._make_frame(samples)
        result = assistant._adjust_volume_in_frame(frame)
        result_data = np.frombuffer(result.data, dtype=np.int16)
        assert np.all(result_data >= -32768)
        assert np.all(result_data <= 32767)

    def test_silence_stays_silent(self, assistant):
        samples = [0] * 1000
        frame = self._make_frame(samples)
        result = assistant._adjust_volume_in_frame(frame)
        result_data = np.frombuffer(result.data, dtype=np.int16)
        assert np.all(result_data == 0)

    def test_amplification_scales_correctly(self, assistant):
        samples = [10000] * 100
        frame = self._make_frame(samples)
        result = assistant._adjust_volume_in_frame(frame)
        result_data = np.frombuffer(result.data, dtype=np.int16)
        expected = 10000 * assistant._volume
        assert abs(int(result_data[0]) - expected) < 2

    def test_volume_zero_silences_all(self, assistant):
        assistant._volume = 0.0
        samples = [10000] * 100
        frame = self._make_frame(samples)
        result = assistant._adjust_volume_in_frame(frame)
        result_data = np.frombuffer(result.data, dtype=np.int16)
        assert np.all(result_data == 0)

    def test_volume_clamped_to_max(self, assistant):
        assistant._volume = 10.0
        samples = [10000] * 100
        frame = self._make_frame(samples)
        result = assistant._adjust_volume_in_frame(frame)
        result_data = np.frombuffer(result.data, dtype=np.int16)
        max_possible = int(32767 * (10.0 / 5.0))
        assert np.all(result_data <= 32767)

    def test_preserves_sample_rate(self, assistant):
        samples = [1000] * 500
        frame = self._make_frame(samples, sample_rate=16000)
        result = assistant._adjust_volume_in_frame(frame)
        assert result.sample_rate == 16000
        assert result.num_channels == 1
