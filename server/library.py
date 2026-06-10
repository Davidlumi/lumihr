"""Question library access: loads the questions table into typed in-memory
structures used by the aggregation engine, API, and submission renderer."""
import re
from functools import lru_cache

from db import get_conn, uj


def slugify(label):
    return re.sub(r"[^a-z0-9]+", "_", (label or "").lower()).strip("_")


class Question(object):
    __slots__ = (
        "id", "text", "short_description", "help_text", "definition",
        "superpower", "sub_power", "sub_power_order", "type", "category",
        "options", "default_chart_type", "data_display_type", "polarity",
        "unit", "unit_display_name", "unit_type", "currency_code",
        "matrix", "matrix_rows", "lumi_tier", "na_handling",
        "benchmark_display", "is_scored", "scoring_config", "score_map",
        "validation", "tolerance", "is_required", "search_description",
        "question_order",
    )

    @property
    def display_title(self):
        return self.benchmark_display or self.short_description or self.text

    @property
    def option_labels(self):
        return [o.get("label") for o in (self.options or [])]

    def matrix_row_defs(self):
        """Ordered [(row_id, label)] for matrix questions, library order."""
        labels = self.matrix_rows or []
        if not labels and isinstance(self.matrix, dict):
            rows = self.matrix.get("rows") or []
            labels = [r.get("label") if isinstance(r, dict) else r for r in rows]
        return [(slugify(lbl), lbl) for lbl in labels]

    def unit_block(self):
        sym = ""
        if self.unit_type == "percentage":
            sym = "%"
        elif self.unit_type == "currency":
            sym = "£" if (self.currency_code or "GBP") == "GBP" else (self.currency_code or "")
        return {
            "symbol": sym,
            "type": self.unit_type or "none",
            "display_name": self.unit_display_name or "",
            "currency_code": self.currency_code or "",
        }


def _row_to_question(r):
    q = Question()
    q.id = r["id"]
    q.text = r["text"]
    q.short_description = r["short_description"]
    q.help_text = r["help_text"]
    q.definition = r["definition"]
    q.superpower = r["superpower"]
    q.sub_power = r["sub_power"]
    q.sub_power_order = r["sub_power_order"]
    q.type = r["type"]
    q.category = r["category"]
    q.options = uj(r["options_json"], [])
    q.default_chart_type = r["default_chart_type"]
    q.data_display_type = r["data_display_type"]
    q.polarity = r["polarity"] or "neutral"
    q.unit = r["unit"]
    q.unit_display_name = r["unit_display_name"]
    q.unit_type = r["unit_type"]
    q.currency_code = r["currency_code"]
    q.matrix = uj(r["matrix_json"])
    q.matrix_rows = uj(r["matrix_rows_json"], [])
    q.lumi_tier = r["lumi_tier"]
    q.na_handling = uj(r["na_handling_json"], {})
    q.benchmark_display = r["benchmark_display"]
    q.is_scored = bool(r["is_scored"])
    q.scoring_config = uj(r["scoring_config_json"], {})
    q.score_map = uj(r["score_map_json"], {})
    q.validation = uj(r["validation_json"], {})
    q.tolerance = uj(r["tolerance_json"], {})
    q.is_required = bool(r["is_required"])
    q.search_description = r["search_description"]
    q.question_order = r["question_order"]
    return q


@lru_cache(maxsize=1)
def load_questions():
    """{question_id: Question}, insertion-ordered by library file order."""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM questions ORDER BY question_order").fetchall()
    return {r["id"]: _row_to_question(r) for r in rows}


def invalidate_cache():
    load_questions.cache_clear()
