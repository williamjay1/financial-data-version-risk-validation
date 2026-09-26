"""Prespecified source-scale and transition-report sensitivity cohorts.

Only D: working data are read/written.  No models are fitted.  The main cohort,
facts, row eligibility, sampling weights and labels are never modified in place.
Run --self-test while awaiting the locked model cohort; run --build only after
the main cohort is final.  Default invocation is a non-writing preflight.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datasets"
OUT = ROOT / "results"
CORRECT_ACCESSION = "0001062993-16-008351"
SCALE_FACTOR = 1000.0
COMPONENTS = (
    "assets", "liabilities", "equity", "cash", "current_assets",
    "current_liabilities", "net_income", "revenue", "operating_income",
    "operating_cash", "retained_earnings",
)
NUMERATORS = (
    "liabilities", "equity", "cash", "net_income", "revenue",
    "operating_income", "operating_cash", "retained_earnings",
)
FEATURES = ("log_assets",) + tuple(k + "_to_assets" for k in NUMERATORS) + (
    "working_capital_to_assets",
)
VERSIONS = ("A", "B", "C")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_d(path: Path) -> Path:
    path = path.resolve()
    if path.drive.upper() != "D:":
        raise ValueError(f"Working inputs and outputs must be on D: {path}")
    return path


def canonical_cik(value) -> str:
    text = str(value).strip()
    if not text.isdigit():
        raise ValueError(f"CIK is not an integer identifier: {value!r}")
    return str(int(text)).zfill(10)


def ratios(values: dict[str, float]) -> dict[str, float]:
    """Exactly the formula in build_vintage_panel.ratios; no new imputation."""
    assets = values["assets"]
    valid = np.isfinite(assets) and assets > 0
    result = {"log_assets": math.log(assets) if valid else np.nan}
    for key in NUMERATORS:
        result[key + "_to_assets"] = values[key] / assets if valid else np.nan
    result["working_capital_to_assets"] = (
        (values["current_assets"] - values["current_liabilities"]) / assets
        if valid else np.nan
    )
    return result


def same_numeric(a, b) -> np.ndarray:
    # This tolerance distinguishes substantive changes from arithmetic roundoff
    # when both numerator and denominator receive the same scale correction.
    return np.isclose(a, b, rtol=1e-12, atol=1e-12, equal_nan=True)


def correct_source_scale(cohort: pd.DataFrame, facts: pd.DataFrame):
    """Patch derived features only; each component's own accession controls it."""
    required_main = {"cik", "accession", "form"}
    required_facts = {"cik", "original_accession", "feature", "A", "B", "C",
                      "B_accession", "C_accession"}
    if not required_main.issubset(cohort):
        raise ValueError(f"Missing cohort columns: {sorted(required_main - set(cohort))}")
    if not required_facts.issubset(facts):
        raise ValueError(f"Missing fact columns: {sorted(required_facts - set(facts))}")
    if cohort.duplicated(["cik", "accession"]).any():
        raise ValueError("Main cohort has duplicate CIK/accession rows")
    f = facts.copy(deep=True)
    f["_cik"] = f.cik.map(canonical_cik)
    f["_original"] = f.original_accession.astype(str)
    keys = list(zip(cohort.cik.map(canonical_cik), cohort.accession.astype(str)))
    if len(set(keys)) != len(keys):
        raise ValueError("Main cohort keys collide after CIK normalization")
    if f.duplicated(["_cik", "_original", "feature"]).any():
        raise ValueError("Fact CIK/original accession/component keys are not unique")
    if not set(f.feature).issubset(COMPONENTS):
        raise ValueError("Unrecognized component in facts")
    if "unit" in f and not f.unit.eq("USD").all():
        raise ValueError("Expected the original selected USD component contexts")
    if "accn" in f:
        if not f.accn.astype(str).eq(f._original).all():
            raise ValueError("A accn disagrees with original_accession")
        source_a = f.accn.astype(str)
    else:
        source_a = f._original
    source_columns = {"A": source_a, "B": f.B_accession.astype(str),
                      "C": f.C_accession.astype(str)}
    before = {v: pd.to_numeric(f[v], errors="raise").to_numpy(dtype=float)
              for v in VERSIONS}
    after = {v: x.copy() for v, x in before.items()}
    matches = {}
    fact_keys = list(zip(f._cik, f._original))
    relevant_keys = set(keys)
    audit = {"correction_accession": CORRECT_ACCESSION, "factor": SCALE_FACTOR,
             "source_assumption": "Original HTML review confirmed all 11 selected monetary components in this accession are 1000 times the API values; correction is accession-specific, not company-wide.",
             "A_source": "accn (asserted equal to original_accession)" if "accn" in f else "original_accession",
             "B_source": "B_accession", "C_source": "C_accession",
             "versions": {}, "affected_rows": []}
    for version in VERSIONS:
        match = source_columns[version].eq(CORRECT_ACCESSION).to_numpy()
        finite = np.isfinite(before[version])
        if np.isinf(before[version]).any():
            raise ValueError(f"Infinite raw monetary component in {version}")
        matches[version] = match & finite
        after[version][matches[version]] *= SCALE_FACTOR
        if np.isinf(after[version]).any():
            raise ValueError(f"Scale correction overflow in {version}")
        audit["versions"][version] = {
            "accession_matched_fact_rows": int(match.sum()),
            "finite_components_multiplied": int(matches[version].sum()),
            "missing_components_not_multiplied": int((match & ~finite).sum()),
            "matched_components_in_main_cohort": sum(bool(m) and k in relevant_keys
                                                       for m, k in zip(matches[version], fact_keys)),
            "affected_cohort_rows": 0, "changed_feature_cells": 0,
            "changed_features": {feature: 0 for feature in FEATURES},
        }
    f["_position"] = np.arange(len(f), dtype=np.int64)
    groups = {(c, a): g for (c, a), g in f.groupby(["_cik", "_original"], sort=False)}
    result = cohort.copy(deep=True)
    patch_cols = [f"{v}_{feature}" for v in VERSIONS for feature in FEATURES
                  if f"{v}_{feature}" in cohort]
    for version in ("A", "B"):
        if any(f"{version}_{feature}" not in cohort for feature in FEATURES):
            raise ValueError(f"Incomplete {version} model feature columns")
    for version in VERSIONS:
        present = [f"{version}_{feature}" in cohort for feature in FEATURES]
        if any(present) and not all(present):
            raise ValueError(f"Partially present {version} feature group")
    affected_positions = set()
    for row_position, key in enumerate(keys):
        group = groups.get(key)
        if group is None:
            # All main-cohort rows have original positive assets. A missing fact
            # bundle therefore indicates a mismatched/incomplete source file.
            raise ValueError(f"Main cohort key absent from facts: {key}")
        positions = group._position.to_numpy(dtype=int)
        for version in VERSIONS:
            if not matches[version][positions].any():
                continue
            values_before = dict.fromkeys(COMPONENTS, np.nan)
            values_after = dict.fromkeys(COMPONENTS, np.nan)
            values_before.update(zip(group.feature, before[version][positions]))
            values_after.update(zip(group.feature, after[version][positions]))
            derived_before = ratios(values_before)
            derived_after = ratios(values_after)
            existing = f"{version}_log_assets" in cohort
            changed = []
            if existing:
                cols = [f"{version}_{feature}" for feature in FEATURES]
                old = cohort.iloc[row_position][cols].to_numpy(dtype=float)
                baseline = np.array([derived_before[feature] for feature in FEATURES])
                new = np.array([derived_after[feature] for feature in FEATURES])
                if not same_numeric(old, baseline).all():
                    raise ValueError(f"Formula/source mismatch for {key}, {version}")
                if not np.array_equal(np.isnan(old), np.isnan(new)):
                    raise ValueError(f"Correction changed missing mask for {key}, {version}")
                substantive = ~same_numeric(old, new)
                # Preserve original floating-point representation of ratios
                # unchanged by uniform scale. This avoids artificial cell edits.
                new[~substantive] = old[~substantive]
                result.iloc[row_position, result.columns.get_indexer(cols)] = new
                changed = [feature for feature, yes in zip(FEATURES, substantive) if yes]
                audit["versions"][version]["affected_cohort_rows"] += 1
                audit["versions"][version]["changed_feature_cells"] += int(substantive.sum())
                for feature in changed:
                    audit["versions"][version]["changed_features"][feature] += 1
            affected_positions.add(row_position)
            audit["affected_rows"].append({
                "cik": key[0], "original_accession": key[1], "version": version,
                "component_matches": group.loc[matches[version][positions], "feature"].tolist(),
                "version_features_present": existing, "changed_features": changed,
            })
    nonfeatures = [col for col in cohort if col not in patch_cols]
    assert_frame_equal(result[nonfeatures], cohort[nonfeatures], check_exact=True)
    if list(result.columns) != list(cohort.columns) or not result.dtypes.equals(cohort.dtypes):
        raise AssertionError("S1 must preserve column order and dtypes")
    unaffected = [i for i in range(len(cohort)) if i not in affected_positions]
    assert_frame_equal(result.iloc[unaffected], cohort.iloc[unaffected], check_exact=True)
    audit.update({"rows_in": len(cohort), "rows_out": len(result),
                  "distinct_rows_with_source_matches": len(affected_positions),
                  "all_nonfeature_cells_identical": True, "row_order_identical": True,
                  "column_order_and_dtypes_identical": True,
                  "substantive_change_tolerance": {"rtol": 1e-12, "atol": 1e-12},
                  "unchanged_ratios_keep_original_float_representation": True,
                  "not_recomputed_metadata": [c for c in ("n_coherent_changed", "n_per_tag_changed") if c in cohort],
                  "metadata_note": "Original component-change audit counts remain source metadata; do not interpret them as corrected-version descriptive counts.",
                  "training_may_be_skipped_as_equivalent": all(v["changed_feature_cells"] == 0 for k,v in audit["versions"].items() if k in ("A","B"))})
    return result, audit


def remove_transition_reports(cohort: pd.DataFrame):
    if "form" not in cohort:
        raise ValueError("Main cohort form column is required")
    mask = cohort.form.eq("10-KT")
    result = cohort.loc[~mask].copy()
    audit = {"filter": "exclude exact form == 10-KT", "rows_in": len(cohort),
             "rows_removed": int(mask.sum()), "rows_out": len(result),
             "equivalent_to_main": not bool(mask.any()),
             "skip_training": not bool(mask.any()),
             "retained_cell_values_and_order_identical": True,
             "weights_are_original_design_weights_not_renormalized": True}
    if "registry_event_365" in cohort:
        audit["positive_windows_removed"] = int(cohort.loc[mask, "registry_event_365"].sum())
    if "cik" in cohort:
        audit["distinct_ciks_with_removed_rows"] = int(cohort.loc[mask, "cik"].nunique())
    assert_frame_equal(result, cohort.loc[~mask], check_exact=True)
    return result, audit


def self_test():
    values = dict(zip(COMPONENTS, [1200., 700., 500., 100., 400., 250., -30.,
                                  1700., 80., 70., -100.]))
    initial = ratios(values)
    scaled = ratios({k: v * SCALE_FACTOR for k, v in values.items()})
    assert math.isclose(scaled["log_assets"] - initial["log_assets"], math.log(1000), abs_tol=1e-12)
    for feature in FEATURES[1:]:
        assert math.isclose(initial[feature], scaled[feature], rel_tol=1e-12, abs_tol=1e-12)
    original_other = "0000000001-15-000001"
    unaffected_accn = "0000000002-15-000001"
    entries = [("0000000001", original_other, "10-K", False, True),
               ("0000000001", CORRECT_ACCESSION, "10-KT", True, False),
               ("0000000002", unaffected_accn, "10-K", False, False)]
    rows, fact_rows = [], []
    for cik, accession, form, a_hit, b_hit in entries:
        row = {"cik": cik, "accession": accession, "form": form,
               "sample_weight": 1.0 if cik.endswith("1") else 11.5,
               "registry_event_365": int(a_hit), "cluster_id": cik,
               "decision_date": "2015-04-01", "n_original_facts": 11}
        for version in VERSIONS:
            row.update({f"{version}_{feature}": value for feature,value in initial.items()})
        rows.append(row)
        for component, value in values.items():
            # C deliberately has a mixed source: only assets uses the corrected
            # accession in the first row; correct C ratios must therefore change.
            source_c = CORRECT_ACCESSION if b_hit and component == "assets" else unaffected_accn
            fact_rows.append({"cik": cik, "original_accession": accession,
                              "accn": accession, "unit": "USD", "feature": component,
                              "A": value, "B": value, "C": value,
                              "B_accession": CORRECT_ACCESSION if b_hit else unaffected_accn,
                              "C_accession": source_c})
    cohort = pd.DataFrame(rows)
    facts = pd.DataFrame(fact_rows)
    original_cohort, original_facts = cohort.copy(deep=True), facts.copy(deep=True)
    changed, audit = correct_source_scale(cohort, facts)
    assert_frame_equal(cohort, original_cohort, check_exact=True)
    assert_frame_equal(facts, original_facts, check_exact=True)
    for index, version in [(0,"B"), (1,"A")]:
        assert math.isclose(changed.loc[index,f"{version}_log_assets"] - cohort.loc[index,f"{version}_log_assets"], math.log(1000), abs_tol=1e-12)
        for feature in FEATURES[1:]:
            assert changed.loc[index,f"{version}_{feature}"] == cohort.loc[index,f"{version}_{feature}"]
    assert changed.loc[0,"A_log_assets"] == cohort.loc[0,"A_log_assets"]
    assert changed.loc[1,"B_log_assets"] == cohort.loc[1,"B_log_assets"]
    assert math.isclose(changed.loc[0,"C_equity_to_assets"], cohort.loc[0,"C_equity_to_assets"] / 1000, rel_tol=1e-12)
    assert_frame_equal(changed.iloc[[2]], cohort.iloc[[2]], check_exact=True)
    stripped, s2 = remove_transition_reports(cohort)
    assert stripped.index.tolist() == [0,2] and s2["rows_removed"] == 1 and not s2["skip_training"]
    zero, zero_audit = remove_transition_reports(cohort.loc[cohort.form.eq("10-K")])
    assert zero_audit["skip_training"] and zero_audit["equivalent_to_main"]
    # Reject mismatched source keys rather than quietly attributing A changes.
    bad = facts.copy()
    bad.loc[0,"accn"] = "bad-source"
    try:
        correct_source_scale(cohort, bad)
    except ValueError as error:
        assert "disagrees" in str(error)
    else:
        raise AssertionError("Accession inconsistency was not rejected")
    return {"status": "pass", "real_data_models_fitted": 0,
            "checks": ["11 monetary components scaled uniformly: 9 ratios unchanged; log assets changes by ln(1000)",
                       "A and B accession sources are corrected independently", "C per-component source correction handles a hybrid bundle",
                       "untouched rows/metadata/weights and source DataFrames unchanged", "10-KT removal preserves retained rows and weights",
                       "zero-transition case marked equivalent and skip training", "inconsistent A source accession rejected"],
            "toy_changed_feature_cells": {v: audit["versions"][v]["changed_feature_cells"] for v in VERSIONS}}


def save_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def write_parquet(frame: pd.DataFrame, path: Path):
    temporary = path.with_suffix(".tmp.parquet")
    frame.to_parquet(temporary, index=False)
    roundtrip = pd.read_parquet(temporary)
    assert_frame_equal(frame.reset_index(drop=True), roundtrip, check_exact=True)
    temporary.replace(path)
    return {"path": str(path), "sha256": sha256(path), "rows": len(frame),
            "bytes": path.stat().st_size, "parquet_roundtrip_exact": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--self-test", action="store_true", help="Synthetic tests only; record the design")
    mode.add_argument("--build", action="store_true", help="Generate sensitivities from the final model cohort")
    parser.add_argument("--cohort", type=Path, default=DATA / "model_cohort.parquet")
    parser.add_argument("--facts", type=Path, default=DATA / "vintage_facts.parquet")
    args = parser.parse_args()
    cohort_path, facts_path = require_d(args.cohort), require_d(args.facts)
    require_d(DATA); require_d(OUT)
    info = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "script_path": str(Path(__file__).resolve()), "script_sha256": sha256(Path(__file__)),
            "status": "preflight_only", "models_fitted": 0,
            "cohort_exists": cohort_path.exists(), "facts_exist": facts_path.exists(),
            "planned_input_cohort": str(cohort_path), "planned_input_facts": str(facts_path),
            "sensitivity_S1": "Accession-specific 1000-fold source-scale correction, same main cohort and weights",
            "sensitivity_S2": "Exclude 10-KT transition annual filings, retain original design weights",
            "features": list(FEATURES), "monetary_components": list(COMPONENTS),
            "no_models_fitted": True,
            "inference_note": "Use the same locked training/evaluation rules. S1 compares the same sampled domain; S2 changes the target domain to non-transition annual reports. Neither alters the original cohort or raw facts."}
    if not args.self_test and not args.build:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return
    info["self_test"] = self_test()
    if args.self_test:
        info["status"] = "implemented_and_synthetic_tests_passed_no_real_cohorts_generated"
        # Never overwrite a completed generation record merely to rerun toys.
        existing = OUT / "sensitivity_design.json"
        if existing.exists() and json.loads(existing.read_text(encoding="utf-8")).get("status") == "complete":
            info["existing_completed_design_preserved"] = True
        else:
            save_json(existing, info)
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return
    if not cohort_path.exists() or not facts_path.exists():
        raise FileNotFoundError("Final model_cohort.parquet and vintage_facts.parquet must both exist; no sensitivity data were generated")
    if shutil.disk_usage(DATA).free < 1024**3:
        raise RuntimeError("Less than 1 GiB free on D; do not build")
    hashes = {"main_sha256": sha256(cohort_path), "facts_sha256": sha256(facts_path)}
    info["sources"] = {"main": {"path": str(cohort_path), "sha256": hashes["main_sha256"]},
                       "facts": {"path": str(facts_path), "sha256": hashes["facts_sha256"]}}
    info.update(hashes)
    main_cohort = pd.read_parquet(cohort_path)
    facts = pd.read_parquet(facts_path)
    corrected, s1 = correct_source_scale(main_cohort, facts)
    no_transition, s2 = remove_transition_reports(main_cohort)
    if hashes["main_sha256"] != sha256(cohort_path) or hashes["facts_sha256"] != sha256(facts_path):
        raise RuntimeError("An input changed during generation; outputs have not been committed")
    info["S1"] = s1
    info["S2"] = s2
    info["outputs"] = {
        "source_scale_corrected": write_parquet(corrected, DATA / "sensitivity_source_scale_corrected.parquet"),
        "no_transition": write_parquet(no_transition, DATA / "sensitivity_no_transition.parquet"),
    }
    info["status"] = "complete"
    info["source_files_unchanged"] = hashes["main_sha256"] == sha256(cohort_path) and hashes["facts_sha256"] == sha256(facts_path)
    if not info["source_files_unchanged"]:
        raise RuntimeError("Input changed before audit commit; rerun only after final cohort is stable")
    save_json(OUT / "sensitivity_design.json", info)
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
