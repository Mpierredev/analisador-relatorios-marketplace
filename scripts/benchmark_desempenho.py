"""Synthetic volume and cardinality benchmark for the analysis pipeline."""

from __future__ import annotations

import argparse
import gc
import resource
import sys
import time
import tracemalloc
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from analisador.analytics import (  # noqa: E402
    ProductRankingMetric,
    TimeGranularity,
    build_time_series,
    compare_periods,
    compute_abc_curve,
    compute_kpis,
    compute_status_distribution,
    rank_products,
)
from analisador.core.enums import Marketplace  # noqa: E402
from analisador.export import export_canonical_csv  # noqa: E402
from analisador.ingestion import read_report  # noqa: E402
from analisador.normalization import NormalizationResult, normalize_report  # noqa: E402
from analisador.validation import validate_report  # noqa: E402

_STATUS_CYCLE = (
    "Entregue",
    "Entregue",
    "Entregue",
    "Entregue",
    "Entregue",
    "Entregue",
    "Entregue",
    "Cancelada pelo comprador",
    "Devolvida",
    "A caminho",
)


@dataclass(frozen=True, slots=True)
class BenchmarkScenario:
    """Volume and product cardinality configuration for one benchmark run."""

    name: str
    rows: int
    unique_skus: int


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Wall-clock latencies (s) and memory measurements (MB) for a scenario."""

    name: str
    rows: int
    unique_skus: int
    csv_mb: float
    ingest_s: float
    validate_s: float
    normalize_s: float
    analytics_s: float
    export_csv_s: float
    total_s: float
    df_mem_mb: float
    tracemalloc_peak_mb: float
    rss_mb: float


DEFAULT_SCENARIOS: tuple[BenchmarkScenario, ...] = (
    BenchmarkScenario("A_50k_250_skus", rows=50_000, unique_skus=250),
    BenchmarkScenario("B_50k_10k_skus", rows=50_000, unique_skus=10_000),
    BenchmarkScenario("C_200k_1k_skus", rows=200_000, unique_skus=1_000),
)


def _format_brl_str(cents: int) -> str:
    reais, centavos = divmod(abs(cents), 100)
    sign = "-" if cents < 0 else ""
    return (
        f"{sign}R$ {reais:,}.{centavos:02d}".replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def _build_ml_row(
    idx: int,
    date_str: str,
    sku_row: tuple[str, str, int],
) -> str:
    name, sku, unit_cents = sku_row
    qty = (idx % 4) + 1
    gross = unit_cents * qty
    status = _STATUS_CYCLE[idx % len(_STATUS_CYCLE)]
    fees = 0 if status == "Cancelada pelo comprador" else (gross * 14) // 100
    ship = 0 if status == "Cancelada pelo comprador" else 1890
    net = gross - fees - ship
    return (
        f"ML-{idx + 1:07d};{date_str};{status};{name};{sku};{qty};"
        f"{_format_brl_str(gross)};{_format_brl_str(fees)};"
        f"{_format_brl_str(ship)};{_format_brl_str(net)}"
    )


def build_synthetic_ml_csv(rows: int, unique_skus: int) -> bytes:
    """Generate deterministic Mercado Livre semicolon CSV bytes in memory."""
    header = (
        "N.º de venda;Data da venda;Estado;Título do anúncio;SKU;"
        "Unidades;Receita por produtos;Tarifa de venda e impostos;"
        "Custos de envio;Total (BRL)"
    )
    base = datetime(2025, 1, 1, 8, 0)
    dates = [
        (base + timedelta(hours=idx % 2160)).strftime("%d/%m/%Y %H:%M")
        for idx in range(2160)
    ]
    sku_rows = [
        (f"Produto Sintético {idx:05d}", f"SKU-{idx:05d}", 4990 + (idx % 200) * 150)
        for idx in range(unique_skus)
    ]
    lines = [header] + [
        _build_ml_row(i, dates[i % 2160], sku_rows[i % unique_skus])
        for i in range(rows)
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _run_analytics_bundle(normalized: NormalizationResult) -> None:
    df = normalized.dataframe
    compute_kpis(df)
    compare_periods(df)
    build_time_series(df, TimeGranularity.DAILY)
    rank_products(df, by=ProductRankingMetric.REVENUE)
    compute_abc_curve(df)
    compute_status_distribution(df)


def _measure_latency(
    csv_bytes: bytes,
) -> tuple[float, float, float, float, float, NormalizationResult]:
    t0 = time.perf_counter()
    raw_df = read_report(csv_bytes, "benchmark.csv")
    t1 = time.perf_counter()
    validation = validate_report(raw_df, Marketplace.MERCADO_LIVRE.value)
    t2 = time.perf_counter()
    normalized = normalize_report(raw_df, validation)
    t3 = time.perf_counter()
    _run_analytics_bundle(normalized)
    t4 = time.perf_counter()
    export_canonical_csv(normalized.dataframe)
    t5 = time.perf_counter()
    return t1 - t0, t2 - t1, t3 - t2, t4 - t3, t5 - t4, normalized


def _measure_memory(csv_bytes: bytes) -> tuple[float, float]:
    gc.collect()
    tracemalloc.start()
    try:
        raw_df = read_report(csv_bytes, "benchmark.csv")
        validation = validate_report(raw_df, Marketplace.MERCADO_LIVRE.value)
        normalized = normalize_report(raw_df, validation)
        _run_analytics_bundle(normalized)
        export_canonical_csv(normalized.dataframe)
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    return peak_bytes / (1024 * 1024), rss_mb


def run_scenario(scenario: BenchmarkScenario) -> BenchmarkResult:
    """Execute latency and memory measurements for a single benchmark scenario."""
    csv_bytes = build_synthetic_ml_csv(scenario.rows, scenario.unique_skus)
    gc.collect()
    ingest_s, validate_s, normalize_s, analytics_s, export_s, norm = _measure_latency(
        csv_bytes
    )
    df_mem_mb = float(norm.dataframe.memory_usage(deep=True).sum()) / (1024 * 1024)
    del norm
    peak_mb, rss_mb = _measure_memory(csv_bytes)
    total_s = ingest_s + validate_s + normalize_s + analytics_s + export_s
    return BenchmarkResult(
        name=scenario.name,
        rows=scenario.rows,
        unique_skus=scenario.unique_skus,
        csv_mb=len(csv_bytes) / (1024 * 1024),
        ingest_s=ingest_s,
        validate_s=validate_s,
        normalize_s=normalize_s,
        analytics_s=analytics_s,
        export_csv_s=export_s,
        total_s=total_s,
        df_mem_mb=df_mem_mb,
        tracemalloc_peak_mb=peak_mb,
        rss_mb=rss_mb,
    )


def _format_report_line(res: BenchmarkResult) -> str:
    return (
        f"{res.name}: rows={res.rows} skus={res.unique_skus} csv={res.csv_mb:.2f}MB | "
        f"ingest={res.ingest_s:.3f}s validate={res.validate_s:.3f}s "
        f"normalize={res.normalize_s:.3f}s analytics={res.analytics_s:.3f}s "
        f"export_csv={res.export_csv_s:.3f}s TOTAL={res.total_s:.3f}s | "
        f"df_mem={res.df_mem_mb:.2f}MB peak_py={res.tracemalloc_peak_mb:.2f}MB "
        f"rss={res.rss_mb:.1f}MB"
    )


def main() -> None:
    """Run synthetic benchmarks and print structured per-stage metrics."""
    parser = argparse.ArgumentParser(description="Benchmark de volume e cardinalidade.")
    parser.add_argument("--scale", type=float, default=1.0, help="Fator de escala.")
    args = parser.parse_args()
    for base in DEFAULT_SCENARIOS:
        scaled = BenchmarkScenario(
            base.name,
            max(100, int(base.rows * args.scale)),
            max(10, int(base.unique_skus * min(1.0, args.scale))),
        )
        sys.stdout.write(_format_report_line(run_scenario(scaled)) + "\n")


if __name__ == "__main__":
    main()
