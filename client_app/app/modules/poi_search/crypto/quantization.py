# client_app/app/modules/poi_search/crypto/quantization.py
from dataclasses import dataclass


@dataclass(frozen=True)
class QuantizationConfig:
    scale_divisor: int = 100


def quantize_metric_coordinate(value_m: float, config: QuantizationConfig) -> int:
    return int(round(value_m / config.scale_divisor))


def dequantize_squared_distance_to_km(dist2_quantized: int, config: QuantizationConfig) -> float:
    distance_m = (max(dist2_quantized, 0) ** 0.5) * config.scale_divisor
    return round(distance_m / 1000.0, 4)