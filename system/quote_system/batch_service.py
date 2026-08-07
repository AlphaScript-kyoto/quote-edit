from __future__ import annotations

import csv
import hashlib
import json
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from .config import DATA_DIR, OUTPUT_DIR, UPDATE_DIR, load_json, save_json
from .pdf_renderer import render_quote
from .price_pdf_parser import SALES_COLUMNS, find_device, parse_price_pdf, sales_type_display_name
from .quote_service import (
    build_quote,
    is_device_data_plan_allowed,
    is_plan_data_plan_allowed,
    is_sales_plan_allowed,
)

STATE_PATH = DATA_DIR / "app_state.json"
DEVICE_MASTER_PATH = DATA_DIR / "device_master.json"
INCLUDED_MODELS_PATH = DATA_DIR / "included_models.json"
EXCLUDED_MODELS_PATH = DATA_DIR / "excluded_models.json"  # 移行用
CHECKPOINT_PATH = DATA_DIR / "batch_checkpoint.json"
QUOTE_OUTPUT_ROOT = OUTPUT_DIR / "見積PDF"
ProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True)
class BatchResult:
    mode: str
    source_pdf: Path
    output_dir: Path | None
    target_models: int
    generated_files: int
    discontinued_models: tuple[str, ...]
    unchanged: bool
    paused: bool = False
    total_planned: int = 0


@dataclass(frozen=True)
class IndividualResult:
    output_dir: Path
    generated_files: int


class BatchCancelled(Exception):
    """ユーザーが作成を中断した。"""


@dataclass
class BatchControl:
    """バックグラウンド一括作成の中断制御。"""
    _event: threading.Event = field(default_factory=threading.Event)

    def request_cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def clear(self) -> None:
        self._event.clear()


def latest_price_pdf() -> Path | None:
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = list(UPDATE_DIR.glob("*.pdf"))
    return max(pdfs, key=lambda path: path.stat().st_mtime) if pdfs else None


def load_excluded_model_keys() -> set[str]:
    """作成しない機種（exclude）。include から1回だけ移行する。"""
    if EXCLUDED_MODELS_PATH.exists():
        payload = load_json(EXCLUDED_MODELS_PATH)
        return {str(key) for key in payload.get("model_keys", [])}

    # 旧「作成する機種」（include）があった場合 → 除外集合へ変換
    if INCLUDED_MODELS_PATH.exists() and DEVICE_MASTER_PATH.exists():
        included = {
            str(key)
            for key in load_json(INCLUDED_MODELS_PATH).get("model_keys", [])
        }
        master = load_json(DEVICE_MASTER_PATH)
        on_sale = {
            str(device["model_key"])
            for device in master.get("devices", [])
            if device.get("status") == "販売中"
        }
        migrated = sorted(on_sale - included)
        save_excluded_model_keys(migrated)
        return set(migrated)
    return set()


def save_excluded_model_keys(model_keys: Iterable[str]) -> None:
    save_json(EXCLUDED_MODELS_PATH, {
        "model_keys": sorted({str(key) for key in model_keys}),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    })


def load_included_model_keys() -> set[str]:
    """互換用。作成対象 = 販売中 − 除外。"""
    if not DEVICE_MASTER_PATH.exists():
        if INCLUDED_MODELS_PATH.exists():
            payload = load_json(INCLUDED_MODELS_PATH)
            return {str(key) for key in payload.get("model_keys", [])}
        return set()
    master = load_json(DEVICE_MASTER_PATH)
    on_sale = {
        str(device["model_key"])
        for device in master.get("devices", [])
        if device.get("status") == "販売中"
    }
    return on_sale - load_excluded_model_keys()


def save_included_model_keys(model_keys: Iterable[str]) -> None:
    """互換用。include 指定から excluded を逆算して保存する。"""
    if DEVICE_MASTER_PATH.exists():
        master = load_json(DEVICE_MASTER_PATH)
        on_sale = {
            str(device["model_key"])
            for device in master.get("devices", [])
            if device.get("status") == "販売中"
        }
        excluded = on_sale - {str(key) for key in model_keys}
        save_excluded_model_keys(excluded)
    save_json(INCLUDED_MODELS_PATH, {
        "model_keys": sorted({str(key) for key in model_keys}),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    })


def _upfront_ips_plan_ids(device: dict[str, Any]) -> list[str]:
    """機種カテゴリに応じた通常（一括）IPSプランID一覧。"""
    category = str(device.get("category", ""))
    is_feature_phone = "ケータイ" in category or "kids" in category.lower()
    if is_feature_phone:
        return ["feature_phone_ips_24", "feature_phone_ips_36"]
    return [
        "ips_gold_24", "ips_gold_24_water", "ips_platinum_24",
        "ips_platinum_24_water", "ips_platinum_36", "ips_platinum_36_water",
    ]


def _individual_ips_variants(
    device: dict[str, Any],
    *,
    include_ips_subscription: bool,
    include_upfront_lump: bool,
    include_upfront_running: bool,
    include_no_ips: bool,
) -> list[tuple[dict[str, Any], str]]:
    """個別見積用 (ips選択, ips_display_mode) の列。"""
    variants: list[tuple[dict[str, Any], str]] = []
    if include_ips_subscription:
        variants.append(({"type": "subscription"}, "lump"))
    if include_no_ips:
        variants.append(({"type": "none"}, "lump"))
    display_modes: list[str] = []
    if include_upfront_lump:
        display_modes.append("lump")
    if include_upfront_running:
        display_modes.append("monthly_as_running")
    for plan_id in _upfront_ips_plan_ids(device) if display_modes else []:
        for mode in display_modes:
            variants.append(({"type": "upfront", "plan_id": plan_id}, mode))
    return variants


def quote_variants(
    device: dict[str, Any],
    plan_master: dict[str, Any],
    include_upfront_ips: bool = False,
    include_no_ips: bool = False,
    include_no_support: bool = False,
    include_standard_initial_fee: bool = False,
) -> Iterable[dict[str, Any]]:
    """バリアント列挙。標準は事務手数料免除＋初期費用3,000円。事務手数料ありはチェックON時のみ追加。"""
    ips_options: list[dict[str, Any]] = [{"type": "subscription"}]
    if include_no_ips:
        ips_options.append({"type": "none"})
    if include_upfront_ips:
        ips_options.extend(
            {"type": "upfront", "plan_id": plan_id}
            for plan_id in _upfront_ips_plan_ids(device)
        )

    fee_modes = ["special_3000"]
    if include_standard_initial_fee:
        fee_modes.append("standard")

    for sales_type in SALES_COLUMNS:
        payments = device["payment_48"][sales_type]
        if any(value is None for value in payments.values()):
            continue
        for plan_id, plan in plan_master["plans"].items():
            if not plan.get("enabled"):
                continue
            if not is_sales_plan_allowed(sales_type, plan_id):
                continue
            support_options: list[str | None] = ["auto"]
            if include_no_support and plan_id in _SUPPORT_AUTO_PLAN_IDS:
                support_options.append(None)
            for data_plan in plan["data_plans"]:
                if not is_plan_data_plan_allowed(plan_id, data_plan):
                    continue
                if not is_device_data_plan_allowed(device, data_plan, sales_type):
                    continue
                ouchi_amount = int(
                    plan_master["common"]
                    .get("ouchi_discount_by_data_plan_tax_ex", {})
                    .get(data_plan, 0)
                )
                # おうち割ありでは5GBと20GBが同額提示になるため、5GBは作らない。
                if ouchi_amount and data_plan == "5GB":
                    ouchi_options = [False]
                else:
                    ouchi_options = [False, True] if ouchi_amount else [False]
                for ouchi_discount_applied in ouchi_options:
                    for ips in ips_options:
                        display_modes = (
                            ["lump", "monthly_as_running"]
                            if ips.get("type") == "upfront"
                            else ["lump"]
                        )
                        for support_plan_id in support_options:
                            for fee_mode in fee_modes:
                                for ips_display_mode in display_modes:
                                    yield {
                                        "sales_type": sales_type,
                                        "plan_id": plan_id,
                                        "data_plan": data_plan,
                                        "ouchi_discount_applied": ouchi_discount_applied,
                                        "ips": ips,
                                        "support_plan_id": support_plan_id,
                                        "initial_fee_mode": fee_mode,
                                        "ips_display_mode": ips_display_mode,
                                    }


def changed_model_keys(old_master: dict[str, Any] | None, new_master: dict[str, Any]) -> set[str]:
    if old_master is None:
        return {device["model_key"] for device in new_master["devices"]}

    def signature(device: dict[str, Any]) -> str:
        relevant = {
            "category": device.get("category"),
            "status": device["status"],
            "total": device["total"],
            "payment_48": device["payment_48"],
            "payment_36": device.get("payment_36"),
            "payment_24": device.get("payment_24"),
            "eligible": device.get("eligible"),
        }
        return json.dumps(relevant, ensure_ascii=False, sort_keys=True)

    old = {device["model_key"]: signature(device) for device in old_master["devices"]}
    new = {device["model_key"]: signature(device) for device in new_master["devices"]}
    return {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}


def run_batch(
    pdf_path: Path,
    *,
    force_all: bool = False,
    include_upfront_ips: bool = False,
    include_no_ips: bool = False,
    include_no_support: bool = False,
    include_standard_initial_fee: bool = False,
    department: str | None = None,
    progress: ProgressCallback | None = None,
    control: BatchControl | None = None,
) -> BatchResult:
    plan_master = load_json(DATA_DIR / "plans.json")
    service_master = load_json(DATA_DIR / "services.json")
    company = load_json(DATA_DIR / "company.json")
    if department and department.strip():
        company["department"] = department.strip()
    old_master = load_json(DEVICE_MASTER_PATH) if DEVICE_MASTER_PATH.exists() else None
    state = load_json(STATE_PATH) if STATE_PATH.exists() else None

    if progress:
        progress(0, 1, "価格表PDFを読み取り、金額を検算しています…")
    new_master = parse_price_pdf(pdf_path)
    changed_keys = changed_model_keys(old_master, new_master)
    first_run = state is None
    mode = "初回全件" if first_run else ("全件再作成" if force_all else "差分更新")

    excluded = load_excluded_model_keys()
    active_devices = [
        device for device in new_master["devices"]
        if device["status"] == "販売中" and device["model_key"] not in excluded
    ]
    if not active_devices:
        raise ValueError(
            "作成対象の機種がありません。"
            "メイン画面の［除外する機種］で除外を減らすか確認してください。"
        )
    if first_run or force_all:
        targets = active_devices
    else:
        targets = [device for device in active_devices if device["model_key"] in changed_keys]
    discontinued = tuple(
        device["model"]
        for device in new_master["devices"]
        if device["status"] == "取扱終了" and device["model_key"] in changed_keys
    )

    save_json(DEVICE_MASTER_PATH, new_master)
    source_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    if not targets:
        save_json(STATE_PATH, {
            "initialized": True,
            "last_source_pdf": pdf_path.name,
            "last_source_sha256": source_hash,
            "last_run_at": datetime.now().isoformat(timespec="seconds"),
            "last_mode": mode,
            "last_generated_files": 0,
        })
        return BatchResult(mode, pdf_path, None, 0, 0, discontinued, True)

    return _generate_for_devices(
        targets,
        device_master=new_master,
        plan_master=plan_master,
        service_master=service_master,
        company=company,
        mode=mode,
        source_pdf=pdf_path,
        source_hash=source_hash,
        discontinued=discontinued,
        include_upfront_ips=include_upfront_ips,
        include_no_ips=include_no_ips,
        include_no_support=include_no_support,
        include_standard_initial_fee=include_standard_initial_fee,
        progress=progress,
        update_state=True,
        control=control,
        department=department,
    )


def generate_selected_models(
    *,
    models: list[str],
    output_label: str = "指定機種_全パターン",
    include_upfront_ips: bool = True,
    include_no_ips: bool = True,
    include_no_support: bool = True,
    include_standard_initial_fee: bool = False,
    department: str | None = None,
    progress: ProgressCallback | None = None,
    control: BatchControl | None = None,
) -> BatchResult:
    """既存マスターから指定機種のみ全パターン生成する。"""
    if not DEVICE_MASTER_PATH.exists():
        raise FileNotFoundError("機種マスターがありません。先に価格表PDFを取り込んでください。")
    device_master = load_json(DEVICE_MASTER_PATH)
    plan_master = load_json(DATA_DIR / "plans.json")
    service_master = load_json(DATA_DIR / "services.json")
    company = load_json(DATA_DIR / "company.json")
    if department and department.strip():
        company["department"] = department.strip()

    targets: list[dict[str, Any]] = []
    for model in models:
        device = find_device(device_master, model)
        if device["status"] != "販売中":
            raise ValueError(f"取扱終了機種です: {device['model']}")
        targets.append(device)

    return _generate_for_devices(
        targets,
        device_master=device_master,
        plan_master=plan_master,
        service_master=service_master,
        company=company,
        mode=output_label,
        source_pdf=Path(device_master.get("source_pdf", "device_master.json")),
        source_hash="",
        discontinued=(),
        include_upfront_ips=include_upfront_ips,
        include_no_ips=include_no_ips,
        include_no_support=include_no_support,
        include_standard_initial_fee=include_standard_initial_fee,
        progress=progress,
        update_state=False,
        quote_id_prefix="FULL",
        control=control,
        department=department,
    )


def checkpoint_exists() -> bool:
    if not CHECKPOINT_PATH.exists():
        return False
    try:
        payload = load_json(CHECKPOINT_PATH)
    except Exception:
        return False
    return str(payload.get("status")) == "paused" and int(payload.get("next_index", 0)) < int(
        payload.get("total", 0)
    )


def clear_checkpoint() -> None:
    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()


def _checkpoint_include_standard_fee(payload: dict[str, Any]) -> bool:
    """中断データから事務手数料あり版の要否を読む（旧キー互換）。"""
    if "include_standard_initial_fee" in payload:
        return bool(payload.get("include_standard_initial_fee"))
    # 旧版: special が追加オプション、base が standard → 両方だったときのみ standard あり
    return bool(payload.get("include_special_initial_fee"))


def resume_batch(
    *,
    progress: ProgressCallback | None = None,
    control: BatchControl | None = None,
) -> BatchResult:
    """中断チェックポイントから再開する。"""
    if not CHECKPOINT_PATH.exists():
        raise FileNotFoundError("再開できるチェックポイントがありません。")
    payload = load_json(CHECKPOINT_PATH)
    if str(payload.get("status")) != "paused":
        raise ValueError("再開可能な中断状態ではありません。")
    if not DEVICE_MASTER_PATH.exists():
        raise FileNotFoundError("機種マスターがありません。先に価格表PDFを取り込んでください。")

    device_master = load_json(DEVICE_MASTER_PATH)
    plan_master = load_json(DATA_DIR / "plans.json")
    service_master = load_json(DATA_DIR / "services.json")
    company = load_json(DATA_DIR / "company.json")
    department = payload.get("department")
    if department and str(department).strip():
        company["department"] = str(department).strip()

    keys = [str(key) for key in payload.get("target_model_keys", [])]
    by_key = {str(device["model_key"]): device for device in device_master["devices"]}
    targets = []
    for key in keys:
        device = by_key.get(key)
        if not device:
            raise ValueError(f"チェックポイントの機種が見つかりません: {key}")
        targets.append(device)

    return _generate_for_devices(
        targets,
        device_master=device_master,
        plan_master=plan_master,
        service_master=service_master,
        company=company,
        mode=str(payload.get("mode", "再開")),
        source_pdf=Path(str(payload.get("source_pdf") or "resume")),
        source_hash=str(payload.get("source_hash") or ""),
        discontinued=tuple(payload.get("discontinued") or ()),
        include_upfront_ips=bool(payload.get("include_upfront_ips")),
        include_no_ips=bool(payload.get("include_no_ips")),
        include_no_support=bool(payload.get("include_no_support")),
        include_standard_initial_fee=_checkpoint_include_standard_fee(payload),
        progress=progress,
        update_state=bool(payload.get("update_state", True)),
        quote_id_prefix=str(payload.get("quote_id_prefix") or "AUTO"),
        control=control,
        department=str(department) if department else None,
        resume_from=payload,
    )


def _save_checkpoint(payload: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    save_json(CHECKPOINT_PATH, payload)


def _generate_for_devices(
    targets: list[dict[str, Any]],
    *,
    device_master: dict[str, Any],
    plan_master: dict[str, Any],
    service_master: dict[str, Any],
    company: dict[str, Any],
    mode: str,
    source_pdf: Path,
    source_hash: str,
    discontinued: tuple[str, ...],
    include_upfront_ips: bool,
    include_no_ips: bool,
    include_no_support: bool,
    include_standard_initial_fee: bool,
    progress: ProgressCallback | None,
    update_state: bool,
    quote_id_prefix: str = "AUTO",
    control: BatchControl | None = None,
    department: str | None = None,
    resume_from: dict[str, Any] | None = None,
) -> BatchResult:
    jobs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for device in targets:
        for variant in quote_variants(
            device,
            plan_master,
            include_upfront_ips,
            include_no_ips,
            include_no_support,
            include_standard_initial_fee,
        ):
            jobs.append((device, variant))

    total = len(jobs)
    if resume_from:
        start_index = int(resume_from.get("next_index", 0))
        stamp = str(resume_from.get("stamp") or datetime.now().strftime("%Y%m%d_%H%M%S"))
        generated = int(resume_from.get("generated_so_far", start_index))
        quote_id_prefix = str(resume_from.get("quote_id_prefix") or quote_id_prefix)
    else:
        start_index = 0
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        generated = 0
        clear_checkpoint()

    if total > 0 and start_index >= total:
        clear_checkpoint()
        return BatchResult(
            mode, source_pdf, QUOTE_OUTPUT_ROOT, len(targets), generated,
            discontinued, False, False, total,
        )

    output_dir = QUOTE_OUTPUT_ROOT
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "見積一覧.csv"
    updated_rows_by_pdf: dict[str, list[str]] = {}

    base_checkpoint = {
        "mode": mode,
        "source_pdf": source_pdf.name,
        "source_hash": source_hash,
        "include_upfront_ips": include_upfront_ips,
        "include_no_ips": include_no_ips,
        "include_no_support": include_no_support,
        "include_standard_initial_fee": include_standard_initial_fee,
        "department": department,
        "target_model_keys": [device["model_key"] for device in targets],
        "discontinued": list(discontinued),
        "update_state": update_state,
        "quote_id_prefix": quote_id_prefix,
        "stamp": stamp,
        "total": total,
    }

    for index in range(start_index, total):
        if control and control.is_cancelled():
            _merge_manifest(manifest_path, updated_rows_by_pdf)
            _save_checkpoint({
                **base_checkpoint,
                "status": "paused",
                "next_index": index,
                "generated_so_far": generated,
                "paused_at": datetime.now().isoformat(timespec="seconds"),
            })
            return BatchResult(
                mode, source_pdf, output_dir, len(targets), generated,
                discontinued, False, True, total,
            )

        device, variant = jobs[index]
        generated += 1
        ips = variant["ips"]
        ips_key = ips.get("plan_id", ips["type"])
        ouchi_key = "SB光あり" if variant["ouchi_discount_applied"] else "SB光なし"
        quote_id = f"{quote_id_prefix}-{stamp}-{generated:05d}"
        request = {
            "quote_id": quote_id,
            "quote_date": datetime.now().date().isoformat(),
            "customer_name": "御中",
            "model": device["model"],
            "sales_type": variant["sales_type"],
            "plan_id": variant["plan_id"],
            "data_plan": variant["data_plan"],
            "initial_fee_mode": variant.get("initial_fee_mode", "special_3000"),
            "ips_display_mode": variant.get("ips_display_mode", "lump"),
            "services": {
                "ips": ips,
                "support_plan_id": variant.get("support_plan_id", "auto"),
            },
            "universal_fee_tax_in": int(plan_master["common"].get("universal_fee_tax_in", 4)),
            "universal_fee_tax_ex": int(plan_master["common"].get("universal_fee_tax_ex", 4)),
            "ouchi_discount_applied": variant["ouchi_discount_applied"],
            "tax_rate": 0.10,
        }
        if request["initial_fee_mode"] == "standard":
            request["initial_fee_tax_in"] = int(plan_master["common"]["initial_fee_tax_in"])
            request["initial_fee_tax_ex"] = int(plan_master["common"]["initial_fee_tax_ex"])
        quote = build_quote(request, device_master, plan_master, service_master)
        output_path = output_dir / _quote_relative_path(
            device, variant, quote, ips_key, ouchi_key,
            include_no_support=include_no_support,
            include_standard_initial_fee=include_standard_initial_fee,
        )
        render_quote(quote, company, output_path)
        relative = str(output_path.relative_to(output_dir))
        updated_rows_by_pdf[relative] = [
            quote_id,
            str(device.get("category") or ""),
            device["model"],
            sales_type_display_name(variant["sales_type"]),
            quote["plan_name"],
            variant["data_plan"],
            "あり" if variant["ouchi_discount_applied"] else "なし",
            quote["services"]["ips"]["name"] if quote["services"]["ips"] else "なし",
            quote["services"]["support"]["name"] if quote["services"]["support"] else "なし",
            _fee_mode_label(quote),
            _ips_folder_name(quote, variant),
            relative,
        ]
        if progress:
            progress(
                index + 1,
                total,
                f"{device['model']} / {sales_type_display_name(variant['sales_type'])} / "
                f"{variant['data_plan']} / {ouchi_key}",
            )

    _merge_manifest(manifest_path, updated_rows_by_pdf)
    clear_checkpoint()

    save_json(output_dir / "実行結果.json", {
        "mode": mode,
        "source_pdf": source_pdf.name,
        "target_models": [device["model"] for device in targets],
        "discontinued_models": list(discontinued),
        "generated_files": generated,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "output_root": str(output_dir),
    })
    if update_state:
        save_json(STATE_PATH, {
            "initialized": True,
            "last_source_pdf": source_pdf.name,
            "last_source_sha256": source_hash,
            "last_run_at": datetime.now().isoformat(timespec="seconds"),
            "last_mode": mode,
            "last_generated_files": generated,
            "last_output_dir": str(output_dir),
        })
    return BatchResult(
        mode, source_pdf, output_dir, len(targets), generated, discontinued, False, False, total
    )


def run_individual(
    *,
    model: str,
    sales_type: str,
    plan_id: str,
    data_plans: list[str],
    ouchi_options: list[bool],
    include_ips_subscription: bool = True,
    include_upfront_lump: bool = False,
    include_upfront_running: bool = False,
    include_no_ips: bool = False,
    support_plan_id: str | None = "auto",
    department: str | None = None,
    initial_fee_mode: str | None = None,
    initial_fee_modes: list[str] | None = None,
) -> IndividualResult:
    device_master = load_json(DEVICE_MASTER_PATH)
    plan_master = load_json(DATA_DIR / "plans.json")
    service_master = load_json(DATA_DIR / "services.json")
    company = load_json(DATA_DIR / "company.json")
    if department and department.strip():
        company["department"] = department.strip()

    device = find_device(device_master, model)
    if device["status"] != "販売中":
        raise ValueError(f"取扱終了機種です: {device['model']}")
    plan = plan_master["plans"].get(plan_id)
    if not plan or not plan.get("enabled"):
        raise ValueError("利用できない料金プランです")
    if not is_sales_plan_allowed(sales_type, plan_id):
        if plan_id == "light":
            raise ValueError(
                "機種変更では Bizパッケージ＋ライト は作成しません"
                "（50GBはスーパーライト、それ以外はハイパーライトを使用）"
            )
        raise ValueError(f"販売区分と料金プランの組み合わせが不正です: {sales_type} / {plan_id}")

    selected_data = [
        value for value in data_plans
        if value in plan["data_plans"]
        and is_plan_data_plan_allowed(plan_id, value)
        and is_device_data_plan_allowed(device, value, sales_type)
    ]
    if not selected_data:
        raise ValueError("機種と料金プランに対応するデータ容量を選択してください")
    if not ouchi_options:
        raise ValueError("SB光なし／ありを1つ以上選択してください")

    fee_modes: list[str]
    if initial_fee_modes is not None:
        fee_modes = list(dict.fromkeys(initial_fee_modes))
    elif initial_fee_mode:
        fee_modes = [initial_fee_mode]
    else:
        fee_modes = ["special_3000"]
    fee_modes = [mode for mode in fee_modes if mode in {"standard", "special_3000"}]
    if not fee_modes:
        raise ValueError("初期費用のパターンを1つ以上選択してください")

    ips_variants = _individual_ips_variants(
        device,
        include_ips_subscription=include_ips_subscription,
        include_upfront_lump=include_upfront_lump,
        include_upfront_running=include_upfront_running,
        include_no_ips=include_no_ips,
    )
    if not ips_variants:
        raise ValueError("修理保証（IPS）の作成パターンを1つ以上選択してください")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = QUOTE_OUTPUT_ROOT
    output_dir.mkdir(parents=True, exist_ok=True)
    updated_rows_by_pdf: dict[str, list[str]] = {}
    generated = 0
    for data_plan in selected_data:
        discount = int(
            plan_master["common"].get("ouchi_discount_by_data_plan_tax_ex", {}).get(data_plan, 0)
        )
        effective_ouchi = list(dict.fromkeys(
            option if discount else False for option in ouchi_options
        ))
        # おうち割あり×5GBは作成しない
        if data_plan == "5GB":
            effective_ouchi = [option for option in effective_ouchi if not option]
        if not effective_ouchi:
            continue
        for ouchi_applied in effective_ouchi:
            for fee_mode in fee_modes:
                for ips_selection, ips_display_mode in ips_variants:
                    generated += 1
                    quote_id = f"ONE-{stamp}-{generated:03d}"
                    request: dict[str, Any] = {
                        "quote_id": quote_id,
                        "quote_date": datetime.now().date().isoformat(),
                        "customer_name": "御中",
                        "model": device["model"],
                        "sales_type": sales_type,
                        "plan_id": plan_id,
                        "data_plan": data_plan,
                        "initial_fee_mode": fee_mode,
                        "ips_display_mode": ips_display_mode,
                        "services": {
                            "ips": ips_selection,
                            "support_plan_id": support_plan_id,
                        },
                        "universal_fee_tax_in": int(
                            plan_master["common"].get("universal_fee_tax_in", 4)
                        ),
                        "universal_fee_tax_ex": int(
                            plan_master["common"].get("universal_fee_tax_ex", 4)
                        ),
                        "ouchi_discount_applied": ouchi_applied,
                        "tax_rate": 0.10,
                    }
                    if fee_mode == "standard":
                        request["initial_fee_tax_in"] = int(
                            plan_master["common"]["initial_fee_tax_in"]
                        )
                        request["initial_fee_tax_ex"] = int(
                            plan_master["common"]["initial_fee_tax_ex"]
                        )
                    quote = build_quote(
                        request, device_master, plan_master, service_master
                    )
                    variant = {
                        "sales_type": sales_type,
                        "plan_id": plan_id,
                        "data_plan": data_plan,
                        "initial_fee_mode": fee_mode,
                        "ips_display_mode": ips_display_mode,
                    }
                    ouchi_key = "SB光あり" if ouchi_applied else "SB光なし"
                    ips_key = (
                        ips_selection.get("plan_id") or ips_selection.get("type", "none")
                    )
                    fee_branch = "standard" in fee_modes and "special_3000" in fee_modes
                    output_path = output_dir / _quote_relative_path(
                        device, variant, quote, str(ips_key), ouchi_key,
                        include_standard_initial_fee=fee_branch,
                    )
                    render_quote(quote, company, output_path)
                    relative = str(output_path.relative_to(output_dir))
                    ips_label = (
                        "なし"
                        if not quote["services"]["ips"]
                        else "あり"
                    )
                    updated_rows_by_pdf[relative] = [
                        quote_id,
                        str(device.get("category") or ""),
                        device["model"],
                        sales_type,
                        quote["plan_name"],
                        data_plan,
                        "あり" if ouchi_applied else "なし",
                        ips_label,
                        quote["services"]["support"]["name"]
                        if quote["services"]["support"]
                        else "なし",
                        _fee_mode_label(quote),
                        _ips_folder_name(quote, variant),
                        relative,
                    ]

    _merge_manifest(output_dir / "見積一覧.csv", updated_rows_by_pdf)
    return IndividualResult(output_dir, generated)


def _merge_manifest(manifest_path: Path, updated_rows_by_pdf: dict[str, list[str]]) -> None:
    header = [
        "見積番号", "機種カテゴリ", "機種", "販売区分", "料金プラン", "データ容量",
        "SB光（おうち割）", "IPS", "安心サポート", "初期費用区分", "IPS区分", "PDF",
    ]
    existing: dict[str, list[str]] = {}
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            rows = list(reader)
            if rows:
                for row in rows[1:]:
                    if not row:
                        continue
                    pdf_key = row[-1]
                    # 旧CSV（列が少ない）にも対応してPDF列をキーにする
                    existing[pdf_key] = row
    existing.update(updated_rows_by_pdf)
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for pdf_key in sorted(existing):
            row = existing[pdf_key]
            # 列数を揃える
            if len(row) < len(header):
                # 旧形式: 末尾PDFの前に初期費用区分・IPS区分が無い
                pdf = row[-1]
                body = row[:-1]
                while len(body) < len(header) - 1:
                    body.append("")
                row = body[: len(header) - 1] + [pdf]
            writer.writerow(row[: len(header)])


def _safe_name(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*]+', "_", value)
    return re.sub(r"\s+", "_", value).strip("._")


def _filename_model(model: str) -> str:
    """価格表上の機種名から、ファイル名用に空白だけを除いた表記を作る。"""
    compact = re.sub(r"\s+", "", model.strip())
    return _safe_name(compact)


def _ips_filename_token(ips: dict[str, Any] | None) -> str | None:
    """保証プラン略称。"""
    if not ips:
        return None
    name = str(ips.get("name") or "")
    water = "水没" in name
    digits = re.search(r"(\d+)", name)
    digit = digits.group(1) if digits else ""

    if "ガラケー" in name:
        return f"ガラ{digit}" if digit else "ガラ"

    if ips.get("billing_type") == "subscription":
        subscription_tokens = (
            ("ミディアム", "ミディアム"),
            ("スモール", "スモール"),
            ("ミニ", "ミニ"),
            ("ラージ", "ラージ"),
            ("メガ", "メガ"),
        )
        for needle, token in subscription_tokens:
            if needle in name:
                return token
        return None

    core = name.replace("IPS", "").replace("水没", "").replace("プラン", "")
    core = re.sub(r"\d+", "", core).strip()
    upfront_tokens = (
        ("ゴールド", "ゴ"),
        ("プラチナ", "プ"),
    )
    head = ""
    for needle, token in upfront_tokens:
        if needle in core:
            head = token
            break
    if not head and core:
        head = core[0]
    if not head:
        return None
    return f"{head}{digit}{'水' if water else ''}"


def _quote_filename(device: dict[str, Any], variant: dict[str, Any], quote: dict[str, Any]) -> str:
    """PDF basename: 機種_容量 のみ（IPS プラン名はフォルダで区別）。"""
    parts = [_filename_model(device["model"]), str(variant["data_plan"])]
    return _safe_name("_".join(parts)) + ".pdf"


def _fee_folder_name(
    quote: dict[str, Any],
    *,
    include_standard_initial_fee: bool = False,
) -> str | None:
    """初期費用のフォルダ名。標準 special_3000（PDF上は税込3,300円）は省略。

    - 事務手数料あり（standard）だけ分岐フォルダを付ける
    - special と standard を同時生成するとき（include_standard_initial_fee）は
      両方にフォルダを付けてパス衝突を防ぐ
    """
    mode = str(quote.get("initial_fee_mode") or "special_3000")
    if mode == "special_3000":
        if include_standard_initial_fee:
            return "初期費用3300円"
        return None
    if mode == "standard":
        return "事務手数料あり"
    return None


def _fee_mode_label(quote: dict[str, Any]) -> str:
    """見積一覧CSVなど用の初期費用区分ラベル（フォルダ有無に依存しない）。"""
    if str(quote.get("initial_fee_mode") or "special_3000") == "special_3000":
        return "初期費用3300円"
    return "事務手数料あり"


def _ips_folder_name(quote: dict[str, Any], variant: dict[str, Any] | None = None) -> str:
    ips = quote["services"]["ips"]
    if not ips:
        return "IPSなし"
    display_mode = (
        (variant or {}).get("ips_display_mode")
        or quote.get("ips_display_mode", "lump")
    )
    if ips.get("billing_type") == "upfront":
        if display_mode == "monthly_as_running":
            return "IPS一括型_月額換算"
        return "IPS一括型"
    return "IPSサブスク"


def _upfront_ips_plan_folder(quote: dict[str, Any]) -> str | None:
    """通常（一括）IPS をプラン単位で分ける日本語フォルダ名（例: ゴールド24）。"""
    ips = quote["services"]["ips"]
    if not ips or ips.get("billing_type") != "upfront":
        return None
    name = str(ips.get("name") or "").strip()
    if not name:
        return None
    # "IPSゴールド24" -> "ゴールド24", "ガラケーIPS24" -> "ガラケー24"
    display = re.sub(r"IPS", "", name).strip()
    display = re.sub(r"\s+", "", display)
    return display or None


# auto_mapping で安心サポートが付くプラン（services.json と揃える）
_SUPPORT_AUTO_PLAN_IDS = frozenset({"light", "super_light", "hyper_light"})
# スーパー／ハイパーは容量が重ならないため、全販売区分でプラン名フォルダを統合する
_MERGED_SPECIAL_DISCOUNT_PLAN_IDS = frozenset({"super_light", "hyper_light"})


def _is_merged_special_discount(plan_id: str) -> bool:
    """スーパー／ハイパー（特別割引）をプラン名フォルダなしで扱うか。"""
    return str(plan_id or "").strip() in _MERGED_SPECIAL_DISCOUNT_PLAN_IDS


def _plan_folder_name(
    quote: dict[str, Any],
    variant: dict[str, Any],
) -> str | None:
    """料金プラン用フォルダ名。

    スーパー／ハイパーはプラン名フォルダなし（容量で区別。Biz・ライトは従来どおり）。
    """
    plan_id = str(variant.get("plan_id") or quote.get("plan_id") or "").strip()
    if _is_merged_special_discount(plan_id):
        return None
    return str(quote.get("plan_name") or plan_id)


def _merged_ips_branch_folder(
    quote: dict[str, Any],
    variant: dict[str, Any],
) -> str | None:
    """スーパー／ハイパーかつ IPS ありのときの分岐フォルダ名。

    IPSあり/ 直下: IPSサブスク | IPS一括表記 | 通常IPSランニングコスト表記
    """
    plan_id = str(variant.get("plan_id") or quote.get("plan_id") or "").strip()
    if not _is_merged_special_discount(plan_id):
        return None
    ips = (quote.get("services") or {}).get("ips")
    if not ips:
        return None
    billing = ips.get("billing_type")
    if billing == "subscription":
        return "IPSサブスク"
    if billing != "upfront":
        return None
    display_mode = str(
        variant.get("ips_display_mode")
        or quote.get("ips_display_mode")
        or "lump"
    )
    if display_mode == "monthly_as_running":
        return "通常IPSランニングコスト表記"
    return "IPS一括表記"


def _support_folder_name(
    quote: dict[str, Any],
    variant: dict[str, Any] | None = None,
    *,
    include_no_support: bool = False,
) -> str | None:
    """安心サポートのフォルダ名。あり／なしの分岐があるときだけ返す。

    - ライト／スーパー／ハイパー: 標準は強制加入のためフォルダ省略。
      「なし」バリアントも作るとき（include_no_support）や、個別でなしを選んだときは
      あり／なしフォルダを付ける（パス衝突防止）。
    - その他プラン: 標準はなし固定のため省略。サポート付きだけ「安心サポートあり」。
    """
    plan_id = str((variant or {}).get("plan_id") or quote.get("plan_id") or "").strip()
    has_support = bool((quote.get("services") or {}).get("support"))

    if plan_id in _SUPPORT_AUTO_PLAN_IDS:
        if include_no_support or not has_support:
            return "安心サポートあり" if has_support else "安心サポートなし"
        return None

    if has_support:
        return "安心サポートあり"
    return None


def _quote_relative_path(
    device: dict[str, Any],
    variant: dict[str, Any],
    quote: dict[str, Any],
    ips_key: str,
    ouchi_key: str,
    *,
    include_no_support: bool = False,
    include_standard_initial_fee: bool = False,
) -> Path:
    del ips_key
    plan_id = str(variant.get("plan_id") or quote.get("plan_id") or "").strip()
    parts: list[str] = [
        _safe_name(str(device.get("category") or "未分類")),
        _safe_name(device["model"]),
        _safe_name(sales_type_display_name(variant["sales_type"])),
        _safe_name(ouchi_key),
    ]
    plan_folder = _plan_folder_name(quote, variant)
    if plan_folder:
        parts.append(_safe_name(plan_folder))

    fee_folder = _fee_folder_name(
        quote, include_standard_initial_fee=include_standard_initial_fee
    )
    if fee_folder:
        parts.append(fee_folder)

    support_folder = _support_folder_name(
        quote, variant, include_no_support=include_no_support
    )
    ips = (quote.get("services") or {}).get("ips")

    # スーパー／ハイパー: Bizパッケージ＋と並列に「IPSあり」を置き、その中で分岐
    if _is_merged_special_discount(plan_id):
        if not ips:
            parts.append("IPSなし")
            if support_folder:
                parts.append(support_folder)
            parts.append(_quote_filename(device, variant, quote))
            return Path(*parts)

        parts.append("IPSあり")
        branch = _merged_ips_branch_folder(quote, variant)
        if branch:
            parts.append(_safe_name(branch))
        plan_token_folder = _upfront_ips_plan_folder(quote)
        if plan_token_folder:
            parts.append(_safe_name(plan_token_folder))
        if support_folder:
            parts.append(support_folder)
        parts.append(_quote_filename(device, variant, quote))
        return Path(*parts)

    parts.append(_ips_folder_name(quote, variant))
    plan_token_folder = _upfront_ips_plan_folder(quote)
    if plan_token_folder:
        parts.append(_safe_name(plan_token_folder))
    if support_folder:
        parts.append(support_folder)
    parts.append(_quote_filename(device, variant, quote))
    return Path(*parts)
