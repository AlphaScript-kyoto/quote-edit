from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from .price_pdf_parser import find_device


def is_device_data_plan_allowed(device: dict[str, Any], data_plan: str) -> bool:
    """Return whether the price-list device category can use the data plan."""
    category = str(device.get("category", "")).strip()
    normalized_plan = str(data_plan).strip()
    if category == "ケータイ":
        return normalized_plan == "1GB"
    if normalized_plan == "無制限":
        return True
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*GB", normalized_plan, flags=re.IGNORECASE)
    return bool(match and float(match.group(1)) >= 5)


@dataclass(frozen=True)
class PeriodAmount:
    key: str
    label: str
    device_payment: int
    monthly_total_tax_in: int
    monthly_equivalent_total_tax_in: int
    monthly_total_display_tax_ex: int
    monthly_equivalent_display_tax_ex: int


def _select_subscription_tier(service_master: dict[str, Any], device_total: int) -> dict[str, Any]:
    for tier in service_master["ips_subscription"]["tiers"]:
        minimum = int(tier["device_total_min"])
        maximum = tier.get("device_total_max_exclusive")
        if device_total >= minimum and (maximum is None or device_total < int(maximum)):
            return tier
    raise ValueError(f"端末総額に対応するIPSサブスクプランがありません: {device_total:,}円")


def _resolve_services(
    request: dict[str, Any],
    service_master: dict[str, Any],
    device_total: int,
    plan_id: str,
) -> dict[str, Any]:
    selection = request.get("services", {})
    ips_selection = selection.get("ips")
    ips: dict[str, Any] | None = None

    if ips_selection and ips_selection.get("type") == "upfront":
        ips_plan_id = ips_selection.get("plan_id")
        plan = service_master["ips_upfront"]["plans"].get(ips_plan_id)
        if not plan:
            raise ValueError(f"IPS一括プランが不正です: {ips_plan_id}")
        upfront_total = int(plan["upfront_total_tax_in"])
        period_months = int(plan["period_months"])
        ips = {
            **plan,
            "plan_id": ips_plan_id,
            "billing_type": "upfront",
            "monthly_charge_tax_in": 0,
            "collection_fee_tax_in": 0,
            "monthly_equivalent_tax_in": math.ceil(upfront_total / period_months),
        }
    elif ips_selection and ips_selection.get("type") == "subscription":
        tier = _select_subscription_tier(service_master, device_total)
        # 料金表は税込料金をそのまま表示（別途徴収手数料は上乗せしない）
        base_monthly = int(tier["monthly_fee_tax_in"])
        ips = {
            **tier,
            "billing_type": "subscription",
            "upfront_total_tax_in": 0,
            "period_months": None,
            "collection_fee_tax_in": 0,
            "monthly_charge_tax_in": base_monthly,
            "monthly_equivalent_tax_in": base_monthly,
        }
    elif ips_selection and ips_selection.get("type") not in (None, "none"):
        raise ValueError(f"IPS徴収方式が不正です: {ips_selection.get('type')}")

    support: dict[str, Any] | None = None
    support_plan_id = selection.get("support_plan_id", "auto")
    if support_plan_id == "auto":
        support_plan_id = service_master["support_subscription"]["auto_mapping"].get(plan_id)
    if support_plan_id:
        plan = service_master["support_subscription"]["plans"].get(support_plan_id)
        if not plan:
            raise ValueError(f"安心サポート料金が未登録です: {support_plan_id}")
        support = {
            **plan,
            "plan_id": support_plan_id,
            "billing_type": "subscription",
        }

    if ips:
        ips = {**service_master.get("ips_common", {}), **ips}
    return {"ips": ips, "support": support}


def build_quote(
    request: dict[str, Any],
    device_master: dict[str, Any],
    plan_master: dict[str, Any],
    service_master: dict[str, Any],
) -> dict[str, Any]:
    device = find_device(device_master, request["model"])
    if device["status"] != "販売中":
        raise ValueError(f"取扱終了機種です: {device['model']}")

    sales_type = request["sales_type"]
    if sales_type not in device["payment_48"]:
        raise ValueError(f"販売区分が不正です: {sales_type}")

    payments = device["payment_48"][sales_type]
    if any(value is None for value in payments.values()):
        raise ValueError(f"選択区分の48回払い設定がありません: {device['model']} / {sales_type}")

    plan = plan_master["plans"].get(request["plan_id"])
    if not plan or not plan.get("enabled"):
        raise ValueError(f"利用できないプランです: {request['plan_id']}")
    data_plan = plan["data_plans"].get(request["data_plan"])
    if not data_plan:
        raise ValueError(f"プランとデータ容量の組み合わせが不正です: {request['data_plan']}")
    if not is_device_data_plan_allowed(device, request["data_plan"]):
        if str(device.get("category", "")).strip() == "ケータイ":
            condition = "1GBのみ"
        else:
            condition = "5GB以上"
        raise ValueError(
            f"機種分類とデータ容量の組み合わせが不正です: "
            f"{device['model']}（{device.get('category', '分類なし')}）は{condition}です"
        )

    tax_rate = float(request.get("tax_rate", 0.10))
    basic_voice = int(plan_master["common"]["basic_voice_tax_ex"])
    call_option = int(plan_master["common"]["flat_call_option_tax_ex"])
    package_discount = int(data_plan["package_discount_tax_ex"])
    biz_data_plan = plan_master["plans"]["biz_plus"]["data_plans"].get(request["data_plan"])
    if not biz_data_plan:
        raise ValueError(f"Bizパッケージ＋の基準割引がありません: {request['data_plan']}")
    biz_package_discount = int(biz_data_plan["package_discount_tax_ex"])
    additional_discount = int(plan.get("additional_discount_tax_ex", 0))
    if biz_package_discount + additional_discount != package_discount:
        raise ValueError("Bizパッケージ＋割引と追加割引の内訳が合計割引に一致しません")
    ouchi_schedule = plan_master["common"].get("ouchi_discount_by_data_plan_tax_ex", {})
    if request.get("ouchi_discount_applied"):
        ouchi_discount = int(ouchi_schedule.get(request["data_plan"], 0))
        if request["data_plan"] == "5GB" and ouchi_discount:
            raise ValueError(
                "おうち割（SB光）ありの場合、5GB見積は作成しません（20GBと同額のため）"
            )
    else:
        # Keep explicit input compatibility for existing individual quote requests.
        ouchi_discount = int(request.get("ouchi_discount_tax_ex", 0))
        if request["data_plan"] == "5GB" and ouchi_discount:
            raise ValueError(
                "おうち割（SB光）ありの場合、5GB見積は作成しません（20GBと同額のため）"
            )
    communication_tax_ex = (
        basic_voice
        + call_option
        + int(data_plan["data_before_tax_ex"])
        + package_discount
        + ouchi_discount
    )
    expected = basic_voice + int(data_plan["data_after_tax_ex"])
    if communication_tax_ex != expected + ouchi_discount:
        raise ValueError("プラン料金の検算に失敗しました")
    communication_tax_in = math.floor(communication_tax_ex * (1 + tax_rate))

    services = _resolve_services(request, service_master, int(device["total"]), request["plan_id"])
    ips = services["ips"]
    support = services["support"]
    ips_monthly_actual = int(ips["monthly_charge_tax_in"]) if ips else 0
    ips_monthly_equivalent = int(ips["monthly_equivalent_tax_in"]) if ips else 0
    support_monthly = int(support["monthly_fee_tax_in"]) if support else 0
    ips_monthly_tax_ex = 0
    ips_monthly_equivalent_tax_ex = 0
    if ips and ips["billing_type"] == "subscription":
        ips_monthly_tax_ex = int(
            ips.get("monthly_fee_tax_ex", round(int(ips["monthly_fee_tax_in"]) / (1 + tax_rate)))
        )
        ips_monthly_equivalent_tax_ex = ips_monthly_tax_ex
    elif ips:
        upfront_tax_ex = round(int(ips["upfront_total_tax_in"]) / (1 + tax_rate))
        ips_monthly_equivalent_tax_ex = math.ceil(upfront_tax_ex / int(ips["period_months"]))
    support_monthly_tax_ex = int(support.get("monthly_fee_tax_ex", 0)) if support else 0
    service_monthly_actual = ips_monthly_actual + support_monthly
    service_monthly_equivalent = ips_monthly_equivalent + support_monthly

    universal_fee = int(request.get("universal_fee_tax_in", 0))
    universal_fee_tax_ex = int(
        request.get("universal_fee_tax_ex", math.floor(universal_fee / (1 + tax_rate)))
    )
    period_specs = [
        ("1_12", "分割支払 1～12回目"),
        ("13_24", "分割支払 13～24回目"),
        ("25_48", "分割支払 25～48回目"),
    ]
    periods = []
    for key, label in period_specs:
        device_payment = int(payments[key])
        actual = communication_tax_in + device_payment + service_monthly_actual + universal_fee
        equivalent = communication_tax_in + device_payment + service_monthly_equivalent + universal_fee
        display_tax_ex = (
            communication_tax_ex
            + device_payment
            + ips_monthly_tax_ex
            + support_monthly_tax_ex
            + universal_fee_tax_ex
        )
        display_equivalent_tax_ex = (
            communication_tax_ex
            + device_payment
            + ips_monthly_equivalent_tax_ex
            + support_monthly_tax_ex
            + universal_fee_tax_ex
        )
        periods.append(
            PeriodAmount(
                key=key,
                label=label,
                device_payment=device_payment,
                monthly_total_tax_in=actual,
                monthly_equivalent_total_tax_in=equivalent,
                monthly_total_display_tax_ex=display_tax_ex,
                monthly_equivalent_display_tax_ex=display_equivalent_tax_ex,
            )
        )

    initial_fee_mode = str(request.get("initial_fee_mode", "standard"))
    ips_display_mode = str(request.get("ips_display_mode", "lump"))
    if ips and ips["billing_type"] != "upfront":
        ips_display_mode = "lump"

    special_initial_fee_tax_ex = 0
    if initial_fee_mode == "special_3000":
        initial_fee = 0
        initial_fee_tax_ex = 0
        special_initial_fee_tax_ex = int(
            request.get(
                "special_initial_fee_tax_ex",
                plan_master["common"].get("special_initial_fee_tax_ex", 3000),
            )
        )
    else:
        initial_fee = int(
            request.get(
                "initial_fee_tax_in",
                plan_master["common"].get("initial_fee_tax_in", 4950),
            )
        )
        initial_fee_tax_ex = int(
            request.get(
                "initial_fee_tax_ex",
                plan_master["common"].get("initial_fee_tax_ex", 4500),
            )
        )

    # 月額換算メイン表示では初期費用合計にIPS一括を含めない。
    include_ips_in_initial = bool(ips) and ips_display_mode != "monthly_as_running"
    ips_upfront = int(ips["upfront_total_tax_in"]) if include_ips_in_initial and ips else 0
    ips_upfront_tax_ex = round(ips_upfront / (1 + tax_rate)) if ips_upfront else 0
    special_initial_fee_tax_in = round(special_initial_fee_tax_ex * (1 + tax_rate))

    return {
        "quote_id": request["quote_id"],
        "quote_date": request.get("quote_date") or date.today().isoformat(),
        "customer_name": request.get("customer_name", "御中"),
        "model": device["model"],
        "device_category": device.get("category", ""),
        "sales_type": sales_type,
        "plan_name": plan["name"],
        "data_plan": request["data_plan"],
        "ouchi_discount_applied": bool(ouchi_discount),
        "contract_term_years": 3,
        "initial_fee_mode": initial_fee_mode,
        "ips_display_mode": ips_display_mode,
        "initial_fee_tax_in": initial_fee,
        "initial_fee_tax_ex": initial_fee_tax_ex,
        "special_initial_fee_tax_ex": special_initial_fee_tax_ex,
        "special_initial_fee_tax_in": special_initial_fee_tax_in,
        "special_initial_fee_note": plan_master["common"].get(
            "special_initial_fee_note",
            "弊社特別特典により事務手数料免除。初期費用はクレジットカードまたは振込。",
        ),
        "initial_total_tax_in": initial_fee + special_initial_fee_tax_in + ips_upfront,
        "initial_total_tax_ex": initial_fee_tax_ex + special_initial_fee_tax_ex + ips_upfront_tax_ex,
        "tax_rate": tax_rate,
        "components": {
            "basic_voice_tax_ex": basic_voice,
            "call_option_tax_ex": call_option,
            "data_before_tax_ex": int(data_plan["data_before_tax_ex"]),
            "package_discount_tax_ex": package_discount,
            "biz_package_discount_tax_ex": biz_package_discount,
            "additional_discount_name": plan.get("additional_discount_name"),
            "additional_discount_tax_ex": additional_discount,
            "ouchi_discount_tax_ex": ouchi_discount,
            "communication_tax_ex": communication_tax_ex,
            "communication_tax_in": communication_tax_in,
            "universal_fee_tax_in": universal_fee,
            "universal_fee_tax_ex": universal_fee_tax_ex,
        },
        "services": services,
        "periods": [period.__dict__ for period in periods],
        "device_total_tax_in": device["total"],
        "source_pdf": device_master["source_pdf"],
        "source_page": device["source_page"],
    }
