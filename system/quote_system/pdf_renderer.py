from __future__ import annotations

from pathlib import Path
from typing import Any
import re
import unicodedata
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image as ReportLabImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .config import RESOURCE_ROOT
from .price_pdf_parser import sales_type_display_name


FONT_REGULAR_PATH = Path(r"C:\Windows\Fonts\BIZ-UDGothicR.ttc")
FONT_BOLD_PATH = Path(r"C:\Windows\Fonts\BIZ-UDGothicB.ttc")
if FONT_REGULAR_PATH.exists() and FONT_BOLD_PATH.exists():
    FONT = "BIZUDGothic"
    FONT_BOLD = "BIZUDGothic-Bold"
    # ReportLab shaping can corrupt some BIZ UD Gothic subsets into large black glyphs.
    # Japanese quote text does not require complex-script shaping, so disable it.
    pdfmetrics.registerFont(TTFont(FONT, str(FONT_REGULAR_PATH), shapable=False))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(FONT_BOLD_PATH), shapable=False))
    pdfmetrics.registerFontFamily(FONT, normal=FONT, bold=FONT_BOLD, italic=FONT, boldItalic=FONT_BOLD)
else:
    FONT = "HeiseiKakuGo-W5"
    FONT_BOLD = FONT
    pdfmetrics.registerFont(UnicodeCIDFont(FONT))

BLUE = colors.HexColor("#4472C4")
YELLOW = colors.HexColor("#FFF76A")
LIGHT_GRAY = colors.HexColor("#F3F4F6")
RED = colors.HexColor("#E60000")


def yen(value: int) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}¥{abs(value):,}"


def _pdf_additional_discount_label(name: Any) -> str:
    """PDF上だけライト系割引名を「弊社特別割引」と表記する。"""
    text = str(name or "").strip()
    if text in {"ライト割", "スーパーライト割", "ハイパーライト割", "特別割引"}:
        return "弊社特別割引"
    return text or "弊社特別割引"


def _display_periods(periods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge months 1-12 and 13-24 when every displayed total is identical."""
    comparable_keys = (
        "device_payment",
        "monthly_total_tax_in",
        "monthly_equivalent_total_tax_in",
        "monthly_total_display_tax_ex",
        "monthly_equivalent_display_tax_ex",
    )
    if len(periods) == 3 and all(periods[0][key] == periods[1][key] for key in comparable_keys):
        merged = {**periods[0], "key": "1_24", "label": "分割支払 1～24回目"}
        return [merged, periods[2]]
    return periods


def _period_month_bounds(period: dict[str, Any]) -> tuple[int, int]:
    """Return inclusive 1-based month bounds for a period column (key preferred)."""
    key = str(period.get("key") or "")
    if "_" in key:
        left, right = key.split("_", 1)
        if left.isdigit() and right.isdigit():
            return int(left), int(right)
    label = str(period.get("label") or "")
    match = re.search(r"(\d+)\s*[～〜~\-]\s*(\d+)", label)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 1, 48


def _split_period_at_month(period: dict[str, Any], cut_end: int) -> list[dict[str, Any]]:
    """Split a period [start,end] into [start,cut_end] and [cut_end+1,end] when needed."""
    start, end = _period_month_bounds(period)
    if end <= cut_end or start > cut_end:
        return [period]
    first = {
        **period,
        "key": f"{start}_{cut_end}",
        "label": f"分割支払 {start}～{cut_end}回目",
    }
    second = {
        **period,
        "key": f"{cut_end + 1}_{end}",
        "label": f"分割支払 {cut_end + 1}～{end}回目",
    }
    return [first, second]


def _display_periods_for_quote(quote: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Period columns for PDF.

    For upfront IPS in monthly_as_running mode, split any column that crosses the
    guarantee end (e.g. 25～48 with 36-month cover → 25～36 / 37～48) so warranty
    does not look active through month 48.
    """
    displayed = _display_periods(list(quote.get("periods") or []))
    ips = ((quote.get("services") or {}).get("ips") or {})
    if (
        quote.get("ips_display_mode") != "monthly_as_running"
        or ips.get("billing_type") != "upfront"
    ):
        return displayed
    period_months = int(ips.get("period_months") or 0)
    if period_months <= 0:
        return displayed
    refined: list[dict[str, Any]] = []
    for period in displayed:
        refined.extend(_split_period_at_month(period, period_months))
    return refined


def _ips_monthly_for_period(
    period: dict[str, Any],
    *,
    ips: dict[str, Any] | None,
    ips_display_mode: str,
    ips_tax_in_monthly: int,
) -> int:
    """Monthly IPS amount for one column (0 after guarantee ends on running/upfront)."""
    if not ips or ips_tax_in_monthly <= 0:
        return 0
    if ips.get("billing_type") == "subscription":
        return ips_tax_in_monthly
    if ips_display_mode != "monthly_as_running":
        return 0
    period_months = int(ips.get("period_months") or 0)
    if period_months <= 0:
        return ips_tax_in_monthly
    _start, end = _period_month_bounds(period)
    # Column fully after guarantee → no amount; columns are pre-split at period_months.
    if end > period_months:
        return 0
    return ips_tax_in_monthly


def _ips_amount_cell(amount: int, *, active: bool) -> str:
    """Show en-dash when guarantee does not cover that column."""
    if not active:
        return "－"
    return yen(amount)


def render_quote(quote: dict[str, Any], company: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    display_model = unicodedata.normalize("NFKC", quote["model"])
    # 最悪条件（IPS一括＋安心サポート＋無制限注記など）でも1ページに収める余白設定。
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=6.5 * mm,
        bottomMargin=5.5 * mm,
        title=f"{display_model} お見積り",
        author=company["name"],
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "JapaneseBody", parent=styles["BodyText"], fontName=FONT, fontSize=7.6, leading=9.4
    )
    small = ParagraphStyle("JapaneseSmall", parent=body, fontSize=6.5, leading=8.0)
    box_small = ParagraphStyle("BoxSmall", parent=body, fontSize=6.4, leading=7.8)
    model_font_size = _model_font_size(display_model)
    model_title = ParagraphStyle(
        "ModelTitle",
        parent=body,
        fontName=FONT_BOLD,
        fontSize=model_font_size,
        leading=model_font_size * 1.08,
        alignment=TA_LEFT,
    )
    quote_label = ParagraphStyle(
        "QuoteLabel", parent=body, fontName=FONT_BOLD, fontSize=14, leading=16, alignment=TA_LEFT
    )
    right = ParagraphStyle("JapaneseRight", parent=small, alignment=TA_RIGHT)
    section_heading = ParagraphStyle(
        "SectionHeading", parent=body, fontName=FONT_BOLD, fontSize=8, leading=10, textColor=colors.white
    )

    story: list[Any] = []
    quote_info = Table(
        [[f"作成日：{quote['quote_date']}", f"見積番号：{quote['quote_id']}"]],
        colWidths=[94.5 * mm, 94.5 * mm],
    )
    quote_info.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), FONT, 7.0),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.extend([quote_info, Spacer(1, 0.8 * mm)])

    logo_path = RESOURCE_ROOT / company.get("logo_file", "assets/company_logo.png")
    company_rows: list[list[Any]] = []
    if logo_path.exists():
        logo = ReportLabImage(str(logo_path), width=48 * mm, height=18.9 * mm)
        company_rows.append([logo])
    phone, fax, address = _resolve_department_header(company)
    tel_line = f"TEL：{phone}" if phone else "TEL："
    if fax:
        tel_line = f"{tel_line}　FAX：{fax}"
    contact_lines = [
        company["department"],
        f"届出番号：{company['registration_number']}",
        address,
        tel_line,
    ]
    company_rows.append([
        Paragraph("<br/>".join(escape(line) for line in contact_lines), right)
    ])
    company_block = Table(company_rows, colWidths=[84 * mm])
    company_block.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
    ]))
    sales_type = sales_type_display_name(str(quote.get("sales_type") or ""))
    quote_heading = f"{sales_type}お見積り" if sales_type else "お見積り"
    title_block = Table(
        [
            [Paragraph(escape(display_model), model_title)],
            [Paragraph(escape(quote_heading), quote_label)],
        ],
        colWidths=[105 * mm],
    )
    title_block.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, 0), 0.4 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0.2 * mm),
        ("TOPPADDING", (0, 1), (-1, 1), 0.2 * mm),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 0.6 * mm),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    doc.title = f"{display_model} {quote_heading}"
    header = Table(
        [[
            title_block,
            company_block,
        ]],
        colWidths=[105 * mm, 84 * mm],
    )
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.extend([header, Spacer(1, 1.4 * mm)])

    ips = quote["services"]["ips"]
    support = quote["services"]["support"]
    ips_display_mode = quote.get("ips_display_mode", "lump")
    initial_fee_mode = quote.get("initial_fee_mode", "special_3000")
    show_ips_lump_in_initial = bool(
        ips and ips["billing_type"] == "upfront" and ips_display_mode != "monthly_as_running"
    )
    initial_item_rows: list[list[Any]] = []
    if initial_fee_mode == "special_3000":
        initial_item_rows.append([
            "事務手数料", yen(0), "特別特典により免除",
        ])
        initial_item_rows.append([
            "初期費用",
            yen(int(quote.get("special_initial_fee_tax_in") or 3300)),
            "税込／クレジットカードまたは振込",
        ])
    else:
        initial_item_rows.append([
            "事務手数料", yen(quote["initial_fee_tax_in"]), "税込",
        ])
    if show_ips_lump_in_initial:
        initial_item_rows.append([
            "修理保証サービス",
            yen(int(ips["upfront_total_tax_in"])),
            f"税込／契約時一括／保証{ips['period_months']}か月",
        ])
    initial_rows = [["No.", "初期導入費用／台", "金額", "備考"]]
    initial_rows.extend(_with_row_numbers(initial_item_rows))
    has_initial_total = show_ips_lump_in_initial or initial_fee_mode in {
        "special_3000", "standard",
    }
    if has_initial_total:
        initial_rows.append([
            "", "初期費用合計", yen(int(quote["initial_total_tax_in"])), "税込",
        ])
    initial = Table(initial_rows, colWidths=[10 * mm, 60 * mm, 34 * mm, 85 * mm])
    initial.setStyle(_section_table_style())
    initial.setStyle(TableStyle([
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
    ]))
    if has_initial_total:
        initial.setStyle(TableStyle([
            ("BACKGROUND", (0, -1), (-1, -1), YELLOW),
            ("FONT", (0, -1), (-1, -1), FONT_BOLD, 8.4),
        ]))
    story.extend([initial, Spacer(1, 1.6 * mm)])

    components = quote["components"]
    periods = quote["periods"]
    display_periods = _display_periods_for_quote(quote)
    period_count = len(display_periods)
    plan_item_rows: list[list[Any]] = [
        ["基本プラン（音声）", "税抜"] + [yen(components["basic_voice_tax_ex"])] * period_count,
        ["定額オプション＋", "税抜"] + [yen(components["call_option_tax_ex"])] * period_count,
        [f"データプラン {quote['data_plan']}（法人）", "税抜"]
        + [yen(components["data_before_tax_ex"])] * period_count,
        ["Bizパッケージ＋ 特別割引", "税抜"]
        + [yen(components["biz_package_discount_tax_ex"])] * period_count,
    ]
    discount_item_indexes = [len(plan_item_rows) - 1]
    if components["additional_discount_tax_ex"]:
        plan_item_rows.append(
            [_pdf_additional_discount_label(components.get("additional_discount_name")), "税抜"]
            + [yen(components["additional_discount_tax_ex"])] * period_count
        )
        discount_item_indexes.append(len(plan_item_rows) - 1)
    if components["ouchi_discount_tax_ex"]:
        plan_item_rows.append(
            ["おうち割 光セット", "税抜"]
            + [yen(components["ouchi_discount_tax_ex"])] * period_count
        )
        discount_item_indexes.append(len(plan_item_rows) - 1)
    plan_item_rows.append(
        ["機種代金（48分割）", "非課税"]
        + [yen(period["device_payment"]) for period in display_periods]
    )

    ips_tax_in_monthly = _ips_monthly_tax_in(ips)
    support_tax_ex_monthly = int(support["monthly_fee_tax_ex"]) if support else 0
    # IPS一括（lump）は初期費用表に載せ、月額内訳の修理保証行には出さない
    show_ips_monthly = bool(
        ips and (
            ips["billing_type"] == "subscription"
            or ips_display_mode == "monthly_as_running"
        )
    )
    ips_amounts = [
        _ips_monthly_for_period(
            period,
            ips=ips,
            ips_display_mode=ips_display_mode,
            ips_tax_in_monthly=ips_tax_in_monthly,
        )
        for period in display_periods
    ]
    if show_ips_monthly:
        plan_item_rows.append(
            ["修理保証サービス", "税込"]
            + [
                _ips_amount_cell(amount, active=amount > 0)
                for amount in ips_amounts
            ]
        )
    if support:
        plan_item_rows.append(
            ["安心保証サービス", "税抜"] + [yen(support_tax_ex_monthly)] * period_count
        )
    # 弊社サービス（修理保証・安心保証）の直後、月額合計の直前
    plan_item_rows.append(
        ["ユニバーサルサービス料", "税抜"]
        + [yen(components["universal_fee_tax_ex"])] * period_count
    )

    plan_rows: list[list[Any]] = [
        ["No.", "月額内訳", "税区分"] + [period["label"] for period in display_periods],
    ]
    plan_rows.extend(_with_row_numbers(plan_item_rows))
    actual_total_row = len(plan_rows)
    # 月額合計＝基本〜機種代金＋修理保証（列ごと）＋安心保証＋ユニバーサル
    plan_rows.append(
        ["", "月額合計（参考）", ""]
        + [
            yen(
                _mixed_monthly_total(
                    period,
                    components,
                    ips_amount,
                    support_tax_ex_monthly,
                )
            )
            for period, ips_amount in zip(display_periods, ips_amounts)
        ]
    )

    monthly = Table(
        plan_rows,
        colWidths=[10 * mm, 57 * mm, 16 * mm] + [(106 / period_count) * mm] * period_count,
        repeatRows=1,
    )
    # 金額列は No.(0) / 品名(1) / 税区分(2) の次から
    amount_first_col = 3
    table_commands = [
        ("FONT", (0, 0), (-1, -1), FONT, 8.2),
        ("FONT", (0, 0), (-1, 0), FONT_BOLD, 8.4),
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("ALIGN", (amount_first_col, 1), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.45, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
        ("BACKGROUND", (0, actual_total_row), (-1, actual_total_row), YELLOW),
        ("TEXTCOLOR", (amount_first_col, actual_total_row), (-1, actual_total_row), RED),
        ("FONT", (0, actual_total_row), (2, actual_total_row), FONT_BOLD, 9.0),
        ("FONT", (amount_first_col, actual_total_row), (-1, actual_total_row), FONT_BOLD, 10.8),
    ]
    for item_index in discount_item_indexes:
        # ヘッダ1行 + 番号付きアイテム行
        discount_row = item_index + 1
        table_commands.extend([
            # 品名（列1）〜金額列まで赤文字。No.列は通常色のまま。
            ("TEXTCOLOR", (1, discount_row), (-1, discount_row), RED),
            ("FONT", (1, discount_row), (-1, discount_row), FONT_BOLD, 8.2),
        ])
    monthly.setStyle(TableStyle(table_commands))
    story.extend([monthly, Spacer(1, 1.2 * mm)])

    story.append(Paragraph(
        f"機種代金総額：<b>{yen(quote['device_total_tax_in'])}</b>（非課税）", body
    ))
    story.append(Spacer(1, 1.0 * mm))

    # 付帯サービスの詳細はご注意事項へ集約（別紙仕様書案内）
    notes = _attention_notes(quote, ips=bool(ips), support=bool(support))
    note_flow = [Paragraph(f"■ {item}", box_small) for item in notes]
    notes_box = Table(
        [[Paragraph("ご注意事項", section_heading)], [note_flow]],
        colWidths=[189 * mm],
    )
    notes_box.setStyle(_boxed_section_style())
    story.append(notes_box)
    doc.build(story)


def _ips_monthly_tax_in(ips: dict[str, Any] | None) -> int:
    if not ips:
        return 0
    if ips.get("billing_type") == "subscription":
        return int(ips.get("monthly_charge_tax_in") or ips.get("monthly_fee_tax_in") or 0)
    return int(ips.get("monthly_equivalent_tax_in") or 0)


def _mixed_monthly_total(
    period: dict[str, Any],
    components: dict[str, Any],
    ips_tax_in: int,
    support_tax_ex: int,
) -> int:
    return (
        int(components["communication_tax_ex"])
        + int(period["device_payment"])
        + int(components["universal_fee_tax_ex"])
        + int(ips_tax_in)
        + int(support_tax_ex)
    )


def _attention_notes(quote: dict[str, Any], *, ips: bool, support: bool) -> list[str]:
    """ご注意事項（現場指定文言。条件付き項目あり）。"""
    notes: list[str] = [
        "料金プランは翌月から適用となりますのでご注意ください。",
        "SMS、有料通話、国際・海外利用等は別料金です。既存端末の分割残債がある場合は、本見積とは別に請求が継続します。",
        "料金は税込の記載がない限りすべて税抜価格で表示させて頂いております。",
        "Bizパッケージ＋・・・36か月更新月（自動更新）以外の解約や名義変更、又はプラン変更した場合20,000円(税抜)の違約金が発生致します"
        "<br/>※屋号名義でご契約のお客様は、機種変更後違約金対象外となります。",
    ]
    if ips:
        notes.append("Bizパッケージ＋の適用には、修理保証サービスへの加入が必要です。")
        notes.append(
            "携帯電話有料保証について・・・株式会社インフィニティ提供の修理サービスです。"
            "（詳細は別紙の仕様書をご確認ください）"
        )
        ips_svc = ((quote.get("services") or {}).get("ips") or {})
        if (
            quote.get("ips_display_mode") == "monthly_as_running"
            and ips_svc.get("billing_type") == "upfront"
        ):
            upfront = int(ips_svc.get("upfront_total_tax_in") or 0)
            period_months = int(ips_svc.get("period_months") or 0)
            period_text = f"{period_months}か月" if period_months else "保証期間"
            notes.append(
                "本見積もりにおける修理保証サービスはランニングコスト表記"
                f"（総額を保証期間（{period_text}）で割って1か月あたりの料金）です。"
                f"<br/>保証期間は契約から{period_text}です。"
                "保証終了後の分割支払回の「修理保証サービス」欄は「－」表示となります。"
                f"<br/>実際は契約時に一括で{yen(upfront)}（税込）のお支払いがあります。"
            )
        if ips_svc.get("billing_type") == "subscription":
            notes.append(
                "修理保証サービスのサブスクリプション手数料として1請求あたり165円を別途頂戴しております。"
            )
    if support:
        notes.append(
            "携帯電話機安心サポートについて・・・株式会社インフィニティ提供のサポートサービスです。"
            "お支払いはクレジットカードまたは口座振替です。"
            "（詳細は別紙の仕様書をご確認ください）"
        )
    if ips or support:
        notes.append(
            "株式会社インフィニティ提供サービスはソフトバンク請求とは別でお支払となります。"
        )
    has_ouchi = bool(
        quote.get("ouchi_discount_applied")
        or (quote.get("components") or {}).get("ouchi_discount_tax_ex")
    )
    if has_ouchi:
        notes.append(
            "おうち割光セットは、対象の光回線が開通した翌月から適用されます。"
            "（機種変更の場合も同様です）"
        )
    notes.append(
        "パケットプラン5GB、20GBでご契約の方は50GBプランへの変更は不可となります。"
        "（無制限プランにのみ変更可能）"
    )
    # 新トクするサポート＋は48回払い前提の説明のため、36回割賦の見積には載せない
    if int(quote.get("installment_months") or 48) != 36:
        notes.append(
            "新トクするサポート＋・・今回ご購入の本体機種料金を48回払いでお支払頂く契約となります"
            "<br/>※本体機種料金を24回以上お支払い後機種変更頂き、今回ご購入の端末を回収させて頂きますと残割賦が免除となります"
            "<br/>※次回端末変更の翌月末までに加入時に購入した機種を回収、査定完了する必要があります"
            "<br/>※回収した端末が査定条件を満たさなかった場合、20,000円の支払いが必要です"
            "（割賦残債務が20,000円以下の場合残割賦を上限）"
        )
    notes.extend([
        "前回ご購入時トクするサポートにご加入の場合、前回ご購入の端末を回収させて頂きますと残割賦が免除となります"
        "<br/>※端末変更の翌月末までに前回加入時に購入した機種を回収、査定完了する必要があります"
        "<br/>※回収キットはご契約住所にお届けとなります（ご契約住所に変更がある場合はご変更お願いします）",
        "現在個人名義の場合は譲渡手数料4,500円(税抜)が発生致します。",
        "法人契約ではスマートログイン（Yahoo! JAPAN ID連携、PayPayまとめて支払いでのチャージ等）をご利用いただけません。",
    ])
    if str(quote.get("model", "")).lower().startswith("iphone"):
        notes.append(
            "同梱品はUSB-C充電ケーブルのみです。ACアダプタ、イヤホンは別売りです。"
        )
    return notes


def _with_row_numbers(rows: list[list[Any]]) -> list[list[Any]]:
    """明細行の先頭に No. 列を付与する（1始まり）。"""
    return [[str(index), *row] for index, row in enumerate(rows, start=1)]


def _section_table_style() -> TableStyle:
    return TableStyle([
        ("FONT", (0, 0), (-1, -1), FONT, 8.2),
        ("FONT", (0, 0), (-1, 0), FONT_BOLD, 8.3),
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        # No.列がある初期費用表: 金額は列2
        ("ALIGN", (2, 1), (2, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.45, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ])


def _boxed_section_style() -> TableStyle:
    return TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
        ("BACKGROUND", (0, 0), (0, 0), BLUE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, 0), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2.5),
        ("TOPPADDING", (0, 1), (-1, 1), 3),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 3),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ])


def _resolve_department_header(company: dict[str, Any]) -> tuple[str, str, str]:
    """部署ごとの TEL/FAX/住所。未設定なら会社共通値へフォールバック。FAX空なら非表示用に空文字。"""
    department = str(company.get("department") or "")
    contacts = company.get("department_contacts") or {}
    entry = contacts.get(department) if isinstance(contacts, dict) else None
    if not isinstance(entry, dict):
        entry = {}
    phone = str(entry.get("phone") or company.get("phone") or "").strip()
    fax = str(entry.get("fax") or company.get("fax") or "").strip()
    address = str(
        entry.get("postal_address")
        or entry.get("address")
        or company.get("postal_address")
        or ""
    ).strip()
    return phone, fax, address


def _model_font_size(model_name: str) -> float:
    """機種名の見た目の幅に応じ、枠内で読みやすい初期サイズを選ぶ。"""
    visual_units = sum(1.0 if ord(char) > 127 else 0.56 for char in model_name)
    if visual_units <= 16:
        return 21
    if visual_units <= 23:
        return 18
    if visual_units <= 31:
        return 15.5
    if visual_units <= 40:
        return 13.5
    return 11.5
