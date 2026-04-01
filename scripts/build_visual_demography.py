from __future__ import annotations

import argparse
import math
from html import escape
from pathlib import Path

import pandas as pd


WIDTH = 1100
HEIGHT = 420
MARGIN_LEFT = 90
MARGIN_RIGHT = 30
MARGIN_TOP = 30
MARGIN_BOTTOM = 70


def format_money(value: float) -> str:
    return f"{value:,.0f} руб.".replace(",", " ")


def format_int(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def normalize_text(series: pd.Series) -> pd.Series:
    return series.astype("string").fillna("").str.strip()


def money_short(value: float) -> str:
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f} млрд"
    if abs_value >= 1_000_000:
        return f"{value / 1_000_000:.1f} млн"
    if abs_value >= 1_000:
        return f"{value / 1_000:.1f} тыс."
    return f"{value:.0f}"


def bar_chart_svg(
    title: str,
    labels: list[str],
    values: list[float],
    *,
    color: str = "#155eef",
    value_formatter=money_short,
) -> str:
    chart_width = WIDTH - MARGIN_LEFT - MARGIN_RIGHT
    chart_height = HEIGHT - MARGIN_TOP - MARGIN_BOTTOM
    max_value = max(values) if values else 1.0
    bar_space = chart_width / max(len(values), 1)
    bar_width = max(min(bar_space * 0.65, 60), 14)

    bars = []
    ticks = []
    labels_svg = []
    value_labels = []
    for index, (label, value) in enumerate(zip(labels, values)):
        x = MARGIN_LEFT + index * bar_space + (bar_space - bar_width) / 2
        height = 0 if max_value == 0 else (value / max_value) * chart_height
        y = MARGIN_TOP + chart_height - height
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{height:.1f}" rx="6" fill="{color}" />')
        labels_svg.append(
            f'<text x="{x + bar_width / 2:.1f}" y="{HEIGHT - 22}" text-anchor="end" transform="rotate(-35 {x + bar_width / 2:.1f},{HEIGHT - 22})"'
            ' font-size="12" fill="#344054">'
            f'{escape(label)}</text>'
        )
        value_labels.append(
            f'<text x="{x + bar_width / 2:.1f}" y="{max(y - 8, 16):.1f}" text-anchor="middle" font-size="11" fill="#101828">'
            f'{escape(value_formatter(value))}</text>'
        )

    for step in range(5):
        ratio = step / 4 if 4 else 0
        y = MARGIN_TOP + chart_height - ratio * chart_height
        val = ratio * max_value
        ticks.append(f'<line x1="{MARGIN_LEFT}" y1="{y:.1f}" x2="{WIDTH - MARGIN_RIGHT}" y2="{y:.1f}" stroke="#eaecf0" />')
        ticks.append(
            f'<text x="{MARGIN_LEFT - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="#667085">{escape(value_formatter(val))}</text>'
        )

    return (
        f'<svg viewBox="0 0 {WIDTH} {HEIGHT}" xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="white" rx="16" />'
        f'<text x="{MARGIN_LEFT}" y="22" font-size="22" font-weight="700" fill="#101828">{escape(title)}</text>'
        + "".join(ticks + bars + value_labels + labels_svg)
        + "</svg>"
    )


def line_chart_svg(title: str, labels: list[str], values: list[float], *, color: str = "#039855") -> str:
    chart_width = WIDTH - MARGIN_LEFT - MARGIN_RIGHT
    chart_height = HEIGHT - MARGIN_TOP - MARGIN_BOTTOM
    max_value = max(values) if values else 1.0
    min_value = 0.0
    step_x = chart_width / max(len(values) - 1, 1)

    points = []
    for index, value in enumerate(values):
        x = MARGIN_LEFT + index * step_x
        y = MARGIN_TOP + chart_height if max_value == min_value else MARGIN_TOP + chart_height - ((value - min_value) / (max_value - min_value)) * chart_height
        points.append((x, y, value))

    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in points)
    dots = []
    text = []
    xlabels = []
    grid = []
    for step in range(5):
        ratio = step / 4 if 4 else 0
        y = MARGIN_TOP + chart_height - ratio * chart_height
        val = ratio * max_value
        grid.append(f'<line x1="{MARGIN_LEFT}" y1="{y:.1f}" x2="{WIDTH - MARGIN_RIGHT}" y2="{y:.1f}" stroke="#eaecf0" />')
        grid.append(f'<text x="{MARGIN_LEFT - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="#667085">{escape(money_short(val))}</text>')

    for x, y, value in points:
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{color}" stroke="white" stroke-width="2" />')
        text.append(f'<text x="{x:.1f}" y="{max(y - 10, 16):.1f}" text-anchor="middle" font-size="11" fill="#101828">{escape(money_short(value))}</text>')
    for index, label in enumerate(labels):
        x = MARGIN_LEFT + index * step_x
        xlabels.append(f'<text x="{x:.1f}" y="{HEIGHT - 20}" text-anchor="middle" font-size="12" fill="#344054">{escape(label)}</text>')

    return (
        f'<svg viewBox="0 0 {WIDTH} {HEIGHT}" xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="white" rx="16" />'
        f'<text x="{MARGIN_LEFT}" y="22" font-size="22" font-weight="700" fill="#101828">{escape(title)}</text>'
        + "".join(grid)
        + f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" />'
        + "".join(dots + text + xlabels)
        + "</svg>"
    )


def histogram_svg(title: str, values: list[float], *, bins: int = 12, color: str = "#dc6803") -> str:
    values = [v for v in values if pd.notna(v) and v >= 0]
    if not values:
        return "<svg></svg>"
    max_value = max(values)
    bins = max(bins, 1)
    if max_value == 0:
        edges = [0, 1]
        counts = [len(values)]
    else:
        width = max_value / bins
        counts = [0] * bins
        for value in values:
            idx = min(int(value / width), bins - 1)
            counts[idx] += 1
        edges = [i * width for i in range(bins + 1)]

    labels = []
    for i in range(len(counts)):
        labels.append(f"{money_short(edges[i])}-{money_short(edges[i + 1])}")
    return bar_chart_svg(title, labels, counts, color=color, value_formatter=lambda v: format_int(int(v)))


def table_html(frame: pd.DataFrame) -> str:
    headers = "".join(f"<th>{escape(str(c))}</th>" for c in frame.columns)
    rows = []
    for _, row in frame.iterrows():
        cells = []
        for value in row.tolist():
            if isinstance(value, float):
                if value >= 1000:
                    cells.append(f"<td>{escape(format_money(value))}</td>")
                else:
                    cells.append(f"<td>{escape(f'{value:.2f}')}</td>")
            else:
                cells.append(f"<td>{escape(str(value))}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def build_report(data: pd.DataFrame, output_path: Path) -> None:
    work = data.copy()
    for col in [
        "registrator_status_name",
        "kontragenti_naimenovanie",
        "bit_stati_oborotov_naimenovanie",
        "organizacii_naimenovanie",
    ]:
        if col in work.columns:
            work[col] = normalize_text(work[col])
    work["period"] = pd.to_datetime(work["period"], errors="coerce")
    work["year_month"] = work["period"].dt.strftime("%Y-%m")

    monthly = (
        work.groupby("year_month", dropna=False)
        .agg(total_amount=("summa", "sum"), rows=("id", "size"))
        .reset_index()
        .sort_values("year_month")
    )
    status = (
        work.groupby("registrator_status_name", dropna=False)["summa"]
        .sum()
        .sort_values(ascending=False)
        .head(8)
        .reset_index()
    )
    vendors = (
        work.groupby("kontragenti_naimenovanie", dropna=False)["summa"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
    )
    categories = (
        work.groupby("bit_stati_oborotov_naimenovanie", dropna=False)["summa"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
    )
    orgs = (
        work.groupby("organizacii_naimenovanie", dropna=False)["summa"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
    )

    cards = [
        ("Строк после очистки", format_int(len(work))),
        ("Общая сумма", format_money(float(work["summa"].sum()))),
        ("Медианная сумма", format_money(float(work["summa"].median()))),
        ("P99 суммы", format_money(float(work["summa"].quantile(0.99)))),
    ]

    html = f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>Visual Demography</title>
  <style>
    :root {{
      --bg: #f5f7fb;
      --card: #ffffff;
      --text: #101828;
      --muted: #475467;
      --line: #d0d5dd;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      background: linear-gradient(180deg, #eef4ff 0%, #f8fafc 35%, #f5f7fb 100%);
      color: var(--text);
    }}
    .wrap {{
      max-width: 1240px;
      margin: 0 auto;
      padding: 28px 20px 40px;
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 34px;
    }}
    p.lead {{
      margin: 0 0 22px;
      color: var(--muted);
      font-size: 16px;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }}
    .card, .panel {{
      background: var(--card);
      border: 1px solid #e4e7ec;
      border-radius: 18px;
      box-shadow: 0 10px 30px rgba(16, 24, 40, 0.06);
    }}
    .card {{
      padding: 16px 18px;
    }}
    .card .label {{
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 8px;
    }}
    .card .value {{
      font-size: 28px;
      font-weight: 700;
      line-height: 1.1;
    }}
    .panel {{
      padding: 14px;
      margin-bottom: 18px;
      overflow: hidden;
    }}
    .grid2 {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      padding: 10px 8px;
      border-bottom: 1px solid #eaecf0;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-weight: 600;
    }}
    @media (max-width: 1024px) {{
      .cards, .grid2 {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Визуальная демография данных</h1>
    <p class="lead">Очищенная выгрузка без явных дублей по ключу <code>registrator_guid + nomer_stroki</code>.</p>
    <div class="cards">
      {''.join(f'<div class="card"><div class="label">{escape(label)}</div><div class="value">{escape(value)}</div></div>' for label, value in cards)}
    </div>
    <div class="panel">{line_chart_svg('Динамика суммы по месяцам', monthly['year_month'].fillna('NA').tolist(), monthly['total_amount'].tolist())}</div>
    <div class="grid2">
      <div class="panel">{bar_chart_svg('Сумма по статусам', status['registrator_status_name'].replace('', 'NA').tolist(), status['summa'].tolist(), color='#1570ef')}</div>
      <div class="panel">{histogram_svg('Распределение сумм заявок', work['summa'].tolist(), color='#f79009')}</div>
    </div>
    <div class="panel">{bar_chart_svg('Топ-10 поставщиков', vendors['kontragenti_naimenovanie'].replace('', 'NA').tolist(), vendors['summa'].tolist(), color='#12b76a')}</div>
    <div class="panel">{bar_chart_svg('Топ-10 статей затрат', categories['bit_stati_oborotov_naimenovanie'].replace('', 'NA').tolist(), categories['summa'].tolist(), color='#7a5af8')}</div>
    <div class="panel">{bar_chart_svg('Топ-10 организаций', orgs['organizacii_naimenovanie'].replace('', 'NA').tolist(), orgs['summa'].tolist(), color='#ef6820')}</div>
    <div class="panel">
      <h2 style="margin:4px 0 14px;font-size:24px;">Сводная таблица поставщиков</h2>
      {table_html(vendors.rename(columns={'kontragenti_naimenovanie': 'Поставщик', 'summa': 'Сумма'}))}
    </div>
  </div>
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    df = pd.read_csv(args.input, encoding="utf-8-sig")
    build_report(df, args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
