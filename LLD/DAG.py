from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import wave
from typing import Any, Dict
import hashlib
from collections import defaultdict

import numpy as np


ExecutionContext = Dict[str, Any]


@dataclass(frozen=True)
class Peak:
    frame_index: int
    bin_index: int
    frequency_hz: float
    magnitude: float


@dataclass(frozen=True)
class Fingerprint:
    anchor_frame: int
    target_frame: int
    anchor_bin: int
    target_bin: int
    delta_frames: int
    hash_value: str

@dataclass
class Node(ABC):
    id: str
    title: str
    metaTags: list[str] = field(default_factory=list)
    neighbours: list["Node"] = field(default_factory=list)

    def add_neighbour(self, node: "Node") -> None:
        self.neighbours.append(node)

    @abstractmethod
    def process(self, context: ExecutionContext) -> Any:
        """Run the node-specific business logic."""
        raise NotImplementedError


@dataclass
class LoadAudioNode(Node):
    path: str = ""
    mono: bool = True

    def _load_wav(self, path: str) -> tuple[np.ndarray, int]:
        with wave.open(path, "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            num_channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            frame_count = wav_file.getnframes()
            raw_bytes = wav_file.readframes(frame_count)

        if sample_width == 1:
            audio = np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float32)
            audio = (audio - 128.0) / 128.0
        elif sample_width == 2:
            audio = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)
            audio = audio / 32768.0
        elif sample_width == 4:
            audio = np.frombuffer(raw_bytes, dtype=np.int32).astype(np.float32)
            audio = audio / 2147483648.0
        else:
            raise NotImplementedError(
                f"Unsupported WAV sample width: {sample_width} bytes"
            )

        if num_channels > 1:
            audio = audio.reshape(-1, num_channels)
            if self.mono:
                audio = audio.mean(axis=1)

        return audio, sample_rate

    def process(self, context: ExecutionContext) -> Any:
        audio_path = self.path or context.get("audio_path")
        if not audio_path:
            raise ValueError("LoadAudioNode requires a path or context['audio_path']")

        samples, sample_rate = self._load_wav(audio_path)
        context["audio_path"] = audio_path
        context["samples"] = samples
        context["sample_rate"] = sample_rate
        context["num_samples"] = int(samples.shape[0])
        return context

@dataclass
class FFTNode(Node):
    window_size: int = 2048
    hop_size: int = 512

    def process(self, context: ExecutionContext) -> Any:
        samples = context.get("samples")
        sample_rate = context.get("sample_rate")

        if samples is None: 
            raise ValueError("FFT node requires context['samples']")
        if sample_rate is None:
            raise ValueError("FFTNode requires context['sample_rate']")
        
        samples = np.asarray(samples, dtype=np.float32)

        if samples.ndim != 1:
            raise ValueError("FFTNode expects mono audio samples")

        window_size = self.window_size
        hop_size = self.hop_size

        if window_size <= 0:
            raise ValueError("window_size must be positive")
        if hop_size <= 0:
            raise ValueError("hop_size must be positive")
        if window_size > len(samples):
            raise ValueError("window_size cannot exceed total sample length")
        
        window = np.hanning(window_size)

        frames = []
        mags = []
        freqs = np.fft.rfftfreq(window_size, d=1.0/sample_rate)

        for start in range(0, len(samples) - window_size + 1, hop_size):
            frame = samples[start: start + window_size]
            windowed_frame = frame * window

            spectrum = np.fft.rfft(windowed_frame)

            mag = np.abs(spectrum)

            frames.append(frame)
            mags.append(mag)
        
        context["fft_frames"] = np.array(frames)
        context["fft_magnitudes"] = np.array(mags)
        context["fft_frequencies"] = freqs
        context["fft_window_size"] = window_size
        context["fft_hop_size"] = hop_size
        return context


@dataclass
class PeakPickNode(Node):
    threshold: float = 0.1

    def process(self, context: ExecutionContext) -> Any:
        fft_mags = context.get("fft_magnitudes")
        fft_freqs = context.get("fft_frequencies")
        frames = context.get("fft_frames")

        if fft_mags is None:
            raise ValueError("PeakPickNode requires context['fft_magnitudes']")
        if fft_freqs is None:
            raise ValueError("PeakPickNode requires context['fft_frequencies']")
        if frames is None:
            raise ValueError("PeakPickNode requires context['fft_frames']")

        coords = []

        for i in range(len(frames)):
            mags = fft_mags[i]
            for j in range(1, len(mags) - 1):
                # local maxi
                if mags[j] > mags[j - 1] and mags[j] > mags[j + 1] and mags[j] >= self.threshold:
                    # frame i, bin j, freq_j, mag_j
                    stateInfo = (i, j, fft_freqs[j], mags[j])
                    coords.append(stateInfo)
        
        coords.sort(key = lambda x: (x[0], x[1]))
        context["peaks"] = coords
        return context


@dataclass
class ConstellationNode(Node):
    max_peaks_per_frame: int = 20

    def process(self, context: ExecutionContext) -> Any:
        peaks = context.get("peaks")

        if peaks is None:
            raise ValueError("ConstellationNode requires context['peaks']")

        constellation_by_frame: dict[int, list[Peak]] = defaultdict(list)

        for peak in peaks:
            frame_index, bin_index, frequency_hz, magnitude = peak
            constellation_by_frame[frame_index].append(
                Peak(
                    frame_index=frame_index,
                    bin_index=bin_index,
                    frequency_hz=frequency_hz,
                    magnitude=magnitude,
                )
            )

        for frame_index, frame_peaks in constellation_by_frame.items():
            frame_peaks.sort(key=lambda peak: peak.magnitude, reverse=True)
            constellation_by_frame[frame_index] = frame_peaks[: self.max_peaks_per_frame]

        context["constellation"] = dict(sorted(constellation_by_frame.items()))
        return context


@dataclass
class FingerPrintNode(Node):
    min_delta: int = 1
    max_delta: int = 20
    fanout: int = 5

    def process(self, context: ExecutionContext) -> Any:
        constellation = context.get("constellation")

        if constellation is None:
            raise ValueError("FingerPrintNode requires context['constellation']")

        fingerPrintsHashed = []
        rawFingerPrints = []

        frame_indices = sorted(constellation.keys())

        for anchor_frame_index in frame_indices:
            anchor_peaks = constellation[anchor_frame_index]

            for anchor_peak in anchor_peaks:
                # future frames within the allowed delta window
                future_frames = []
                for frame_index in frame_indices:
                    # make sure you only compare to the future
                    if anchor_frame_index < frame_index:
                        future_frames.append(frame_index)

                for target_frame_index in future_frames[: self.fanout]:
                    delta = target_frame_index - anchor_frame_index
                    if self.min_delta <= delta <= self.max_delta:
                        for target_peak in constellation[target_frame_index]:
                            fingerprint = (anchor_peak.bin_index, target_peak.bin_index, delta)
                            rawFingerPrints.append(
                                Fingerprint(
                                    anchor_frame=anchor_frame_index,
                                    target_frame=target_frame_index,
                                    anchor_bin=anchor_peak.bin_index,
                                    target_bin=target_peak.bin_index,
                                    delta_frames=delta,
                                    hash_value=hashlib.md5(
                                        f"{fingerprint[0]}|{fingerprint[1]}|{fingerprint[2]}".encode("utf-8")
                                    ).hexdigest(),
                                )
                            )
                            fingerPrintsHashed.append(
                                hashlib.md5(
                                    f"{fingerprint[0]}|{fingerprint[1]}|{fingerprint[2]}".encode("utf-8")
                                ).hexdigest()
                            )
        
        context["finger_prints_hashed"] = fingerPrintsHashed
        context["finger_prints_raw"] = rawFingerPrints

        return context

class DAG:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}

    def add_node(self, node: Node) -> None:
        if node.id in self.nodes:
            raise ValueError(f"Node with id {node.id!r} already exists")
        self.nodes[node.id] = node

    def add_edge(self, from_node_id: str, to_node_id: str) -> None:
        if from_node_id not in self.nodes or to_node_id not in self.nodes:
            raise ValueError(f"Node not existent")
        
        from_node = self.nodes[from_node_id]
        to_node = self.nodes[to_node_id]
        from_node.add_neighbour(to_node)

    def validate(self) -> None:
        
        seen = set()
        pathSeen = set()
        def hasCycle(node: Node):
            if node.id in pathSeen:
                return True
        
            if node.id in seen:
                return False
            
            pathSeen.add(node.id)

            for neigh in node.neighbours:
                if neigh.id not in self.nodes:
                    raise ValueError(f"Unknown node referenced: {neigh.id}")

                if hasCycle(neigh):
                    return True
            
            seen.add(node.id)
            pathSeen.remove(node.id)
            return False

        for node in self.nodes.values():
            if node.id not in seen:
                if hasCycle(node):
                    raise ValueError("Invalid graph contains cycle")
        

    def topological_sort(self) -> list[Node]:
        self.validate()

        ordering = []
        seen = set()
        currPath = set()

        def dfs(node: Node):
            if node.id in currPath:
                raise ValueError("Invalid graph contains cycle")

            if node.id in seen:
                return

            currPath.add(node.id)

            for neigh in node.neighbours:
                dfs(neigh)
            
            currPath.remove(node.id)
            seen.add(node.id)
            ordering.append(node)

        for node in sorted(self.nodes.values(), key = lambda n: n.id):
            if node.id not in seen:
                dfs(node)
        
        ordering.reverse()
        return ordering


    def execute(self, context: ExecutionContext) -> dict[str, Any]:
        ordering = self.topological_sort()
        node_outputs: dict[str, Any] = {}

        for node in ordering:
            result = node.process(context)
            node_outputs[node.id] = result

            if isinstance(result, dict) and result is not context:
                context = result

        return {
            "context": context,
            "outputs": node_outputs,
            "order": [node.id for node in ordering],
        }


if __name__ == "__main__":
    dag = DAG()

    load_node = LoadAudioNode(
        id="load",
        title="Load Audio",
        path="dag_test_tone.wav",
    )
    fft_node = FFTNode(
        id="fft",
        title="FFT",
        window_size=2048,
        hop_size=512,
    )
    peak_node = PeakPickNode(
        id="peaks",
        title="Peak Pick",
        threshold=0.1,
    )
    constellation_node = ConstellationNode(
        id="const",
        title="Constellation",
        max_peaks_per_frame=10,
    )
    fingerprint_node = FingerPrintNode(
        id="fp",
        title="Fingerprint",
        min_delta=1,
        max_delta=20,
        fanout=5,
    )

    dag.add_node(load_node)
    dag.add_node(fft_node)
    dag.add_node(peak_node)
    dag.add_node(constellation_node)
    dag.add_node(fingerprint_node)

    dag.add_edge("load", "fft")
    dag.add_edge("fft", "peaks")
    dag.add_edge("peaks", "const")
    dag.add_edge("const", "fp")

    result = dag.execute({})
    context = result["context"]

    print("order:", result["order"])
    print("samples:", context.get("num_samples"))
    print("fft_frames:", None if context.get("fft_frames") is None else context["fft_frames"].shape)
    print("fft_magnitudes:", None if context.get("fft_magnitudes") is None else context["fft_magnitudes"].shape)
    print("peaks:", len(context.get("peaks", [])))
    print("constellation frames:", len(context.get("constellation", {})))
    print("raw fingerprints:", len(context.get("finger_prints_raw", [])))
    print("hashed fingerprints:", len(context.get("finger_prints_hashed", [])))
