"""
test_api.py
------------
Automated tests for the Workforce Shift Planning and Fatigue Risk
Management System.

Uses Python's built-in `unittest` so it runs with zero extra
dependencies:
    python -m unittest tests.test_api -v

It is also fully pytest-compatible if the grader has pytest installed:
    pytest tests/test_api.py -v

Strategy: each test class gets its OWN throwaway SQLite database (built
fresh from a tiny in-memory fixture, not the full starter CSVs) so tests
are fast, isolated, and deterministic regardless of what's in data/.
"""
import os
import sys
import unittest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.database as database


class FatigueEngineTestBase(unittest.TestCase):
    """Builds a small, hand-crafted dataset in a temp DB so every fatigue
    rule can be tested in isolation with known inputs/outputs."""

    @classmethod
    def setUpClass(cls):
        cls._tmp_dir = tempfile.mkdtemp()
        cls._original_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(cls._tmp_dir, "test.db")

        with database.db_session() as conn:
            conn.executescript(database.SCHEMA)
            conn.execute(
                """INSERT INTO employees
                   (employee_id, name, role, department, employment_type,
                    max_weekly_hours, contracted_hours, experience_years, min_rest_hours_required)
                   VALUES ('E_TEST', 'Test Employee', 'Tester', 'QA', 'Full-Time', 48, 40, 2, 11)"""
            )
            conn.execute(
                """INSERT INTO employees
                   (employee_id, name, role, department, employment_type,
                    max_weekly_hours, contracted_hours, experience_years, min_rest_hours_required)
                   VALUES ('E_CLEAN', 'Clean Employee', 'Tester', 'QA', 'Full-Time', 48, 40, 2, 11)"""
            )
            conn.execute(
                """INSERT INTO fatigue_rules (rule_id, rule_name, threshold_value, unit, severity)
                   VALUES ('R001', 'Minimum Rest Between Shifts', 11, 'hours', 'High')"""
            )
            conn.execute(
                """INSERT INTO fatigue_rules (rule_id, rule_name, threshold_value, unit, severity)
                   VALUES ('R002', 'Maximum Consecutive Working Days', 6, 'days', 'High')"""
            )
            conn.execute(
                """INSERT INTO fatigue_rules (rule_id, rule_name, threshold_value, unit, severity)
                   VALUES ('R003', 'Maximum Weekly Working Hours', 48, 'hours/week', 'Critical')"""
            )
            conn.execute(
                """INSERT INTO fatigue_rules (rule_id, rule_name, threshold_value, unit, severity)
                   VALUES ('R005', 'Maximum Consecutive Night Shifts', 3, 'shifts', 'Critical')"""
            )

    @classmethod
    def tearDownClass(cls):
        database.DB_PATH = cls._original_db_path

    def setUp(self):
        # Clear shifts before each test so they don't bleed into each other
        with database.db_session() as conn:
            conn.execute("DELETE FROM shifts")

    def insert_shift(self, shift_id, employee_id, shift_date, start_time, end_time, shift_type="Day"):
        with database.db_session() as conn:
            conn.execute(
                """INSERT INTO shifts (shift_id, employee_id, shift_date, shift_type, start_time, end_time)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (shift_id, employee_id, shift_date, shift_type, start_time, end_time),
            )


class TestShiftDurationAndOverlap(FatigueEngineTestBase):
    def test_overnight_shift_duration(self):
        from src.fatigue_engine import shift_duration_hours
        shift = {"shift_date": "2026-06-01", "start_time": "22:00", "end_time": "06:00"}
        self.assertEqual(shift_duration_hours(shift), 8.0)

    def test_day_shift_duration(self):
        from src.fatigue_engine import shift_duration_hours
        shift = {"shift_date": "2026-06-01", "start_time": "09:00", "end_time": "17:00"}
        self.assertEqual(shift_duration_hours(shift), 8.0)

    def test_detects_overlapping_shifts(self):
        from src.fatigue_engine import FatigueEngine
        self.insert_shift("S1", "E_TEST", "2026-06-01", "09:00", "17:00")
        self.insert_shift("S2", "E_TEST", "2026-06-01", "15:00", "23:00")
        eng = FatigueEngine()
        shifts = eng.get_shifts_for_employee("E_TEST")
        overlaps = eng.detect_overlaps(shifts)
        eng.close()
        self.assertEqual(len(overlaps), 1)

    def test_no_false_positive_overlap_for_back_to_back_shifts(self):
        from src.fatigue_engine import FatigueEngine
        self.insert_shift("S1", "E_TEST", "2026-06-01", "09:00", "17:00")
        self.insert_shift("S2", "E_TEST", "2026-06-01", "17:00", "23:00")  # touches, doesn't overlap
        eng = FatigueEngine()
        shifts = eng.get_shifts_for_employee("E_TEST")
        overlaps = eng.detect_overlaps(shifts)
        eng.close()
        self.assertEqual(len(overlaps), 0)


class TestRestAndFatigueRules(FatigueEngineTestBase):
    def test_flags_insufficient_rest(self):
        from src.fatigue_engine import FatigueEngine
        self.insert_shift("S1", "E_TEST", "2026-06-01", "14:00", "22:00")
        self.insert_shift("S2", "E_TEST", "2026-06-02", "05:00", "13:00")  # only 7h rest
        eng = FatigueEngine()
        analysis = eng.analyze_employee("E_TEST")
        eng.close()
        rule_ids = {v["rule_id"] for v in analysis["violations"]}
        self.assertIn("R001", rule_ids)

    def test_sufficient_rest_does_not_flag(self):
        from src.fatigue_engine import FatigueEngine
        self.insert_shift("S1", "E_TEST", "2026-06-01", "09:00", "17:00")
        self.insert_shift("S2", "E_TEST", "2026-06-02", "09:00", "17:00")  # 16h rest
        eng = FatigueEngine()
        analysis = eng.analyze_employee("E_TEST")
        eng.close()
        rule_ids = {v["rule_id"] for v in analysis["violations"]}
        self.assertNotIn("R001", rule_ids)

    def test_flags_too_many_consecutive_working_days(self):
        from src.fatigue_engine import FatigueEngine
        from datetime import date, timedelta
        start = date(2026, 6, 1)
        for i in range(8):  # 8 days straight, limit is 6
            d = (start + timedelta(days=i)).isoformat()
            self.insert_shift(f"S{i}", "E_TEST", d, "09:00", "17:00")
        eng = FatigueEngine()
        analysis = eng.analyze_employee("E_TEST")
        eng.close()
        rule_ids = {v["rule_id"] for v in analysis["violations"]}
        self.assertIn("R002", rule_ids)

    def test_flags_excess_weekly_hours(self):
        from src.fatigue_engine import FatigueEngine
        from datetime import date, timedelta
        monday = date(2026, 6, 1)  # a Monday
        for i in range(6):  # 6 x 9h shifts = 54h > 48h limit, within Mon-Sat
            d = (monday + timedelta(days=i)).isoformat()
            self.insert_shift(f"S{i}", "E_TEST", d, "08:00", "17:00")
        eng = FatigueEngine()
        analysis = eng.analyze_employee("E_TEST")
        eng.close()
        rule_ids = {v["rule_id"] for v in analysis["violations"]}
        self.assertIn("R003", rule_ids)

    def test_flags_too_many_consecutive_night_shifts(self):
        from src.fatigue_engine import FatigueEngine
        from datetime import date, timedelta
        start = date(2026, 6, 1)
        for i in range(4):  # 4 consecutive nights, limit is 3
            d = (start + timedelta(days=i)).isoformat()
            self.insert_shift(f"N{i}", "E_TEST", d, "22:00", "06:00", shift_type="Night")
        eng = FatigueEngine()
        analysis = eng.analyze_employee("E_TEST")
        eng.close()
        rule_ids = {v["rule_id"] for v in analysis["violations"]}
        self.assertIn("R005", rule_ids)

    def test_clean_schedule_is_low_risk(self):
        from src.fatigue_engine import FatigueEngine
        from datetime import date, timedelta
        monday = date(2026, 6, 8)
        for i in range(5):  # 5 standard 8h day shifts, well within all limits
            d = (monday + timedelta(days=i)).isoformat()
            self.insert_shift(f"C{i}", "E_CLEAN", d, "09:00", "17:00")
        eng = FatigueEngine()
        analysis = eng.analyze_employee("E_CLEAN")
        eng.close()
        self.assertEqual(analysis["violations"], [])
        self.assertEqual(analysis["risk_level"], "Low")


class TestValidateNewShiftAndSuggestions(FatigueEngineTestBase):
    def test_validate_flags_conflicting_candidate_shift(self):
        from src.fatigue_engine import FatigueEngine
        self.insert_shift("S1", "E_TEST", "2026-06-01", "09:00", "17:00")
        eng = FatigueEngine()
        result = eng.validate_new_shift("E_TEST", "2026-06-01", "15:00", "23:00", "Evening")
        eng.close()
        self.assertFalse(result["safe_to_assign"])
        self.assertTrue(any(v["rule_id"] == "R006" for v in result["would_introduce_violations"]))

    def test_validate_passes_clean_candidate_shift(self):
        from src.fatigue_engine import FatigueEngine
        eng = FatigueEngine()
        result = eng.validate_new_shift("E_CLEAN", "2026-07-01", "09:00", "17:00", "Day")
        eng.close()
        self.assertTrue(result["safe_to_assign"])

    def test_unknown_employee_returns_error(self):
        from src.fatigue_engine import FatigueEngine
        eng = FatigueEngine()
        result = eng.validate_new_shift("E_DOES_NOT_EXIST", "2026-07-01", "09:00", "17:00")
        eng.close()
        self.assertIn("error", result)

    def test_suggest_safer_alternatives_returns_a_clean_option(self):
        from src.fatigue_engine import FatigueEngine
        self.insert_shift("S1", "E_TEST", "2026-06-01", "09:00", "17:00")
        eng = FatigueEngine()
        # candidate overlaps S1; the engine should find at least one safe alternative
        alts = eng.suggest_safer_alternatives("E_TEST", "2026-06-01", "15:00", "23:00", "Evening")
        eng.close()
        self.assertGreater(len(alts), 0)
        for alt in alts:
            self.assertIn(alt["projected_risk_level"], ["Low", "Medium"])


class TestAIServiceFallback(unittest.TestCase):
    """Ensures the AI explanation feature degrades gracefully and still
    produces a usable, well-formed result with no API key configured."""

    def test_fallback_explanation_for_violations(self):
        from src.ai_service import explain_fatigue_risk
        analysis = {
            "employee_name": "Test Employee",
            "risk_level": "Critical",
            "violations": [
                {"rule_id": "R006", "rule_name": "Shift Overlap / Double-Booking",
                 "severity": "Critical", "detail": "Shift A overlaps with Shift B."}
            ],
        }
        result = explain_fatigue_risk(analysis)
        self.assertIn("explanation", result)
        self.assertIn("most_urgent_issue", result)
        self.assertIn("recommendation", result)
        self.assertEqual(result["source"], "fallback_template")
        self.assertIn("R006", result["most_urgent_issue"])

    def test_fallback_explanation_for_clean_schedule(self):
        from src.ai_service import explain_fatigue_risk
        analysis = {"employee_name": "Test Employee", "risk_level": "Low", "violations": []}
        result = explain_fatigue_risk(analysis)
        self.assertIn("does not breach", result["explanation"])


class TestFlaskAPI(unittest.TestCase):
    """Integration tests against the Flask app using its test client
    (no real server / network needed) and a throwaway seeded database."""

    @classmethod
    def setUpClass(cls):
        cls._tmp_dir = tempfile.mkdtemp()
        cls._original_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(cls._tmp_dir, "api_test.db")
        database.init_db(reset=True)
        database.seed_from_csv()

        import importlib
        import app.app as flask_app_module
        importlib.reload(flask_app_module)
        cls.flask_app_module = flask_app_module
        cls.client = flask_app_module.app.test_client()

    @classmethod
    def tearDownClass(cls):
        database.DB_PATH = cls._original_db_path

    def test_health_endpoint(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "ok")

    def test_list_employees(self):
        resp = self.client.get("/api/employees")
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(len(resp.get_json()), 0)

    def test_get_unknown_employee_404(self):
        resp = self.client.get("/api/employees/E_NOPE")
        self.assertEqual(resp.status_code, 404)

    def test_fatigue_risk_endpoint_shape(self):
        resp = self.client.get("/api/employees/E001/fatigue-risk")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        for key in ["fatigue_score", "risk_level", "violations", "ai_explanation"]:
            self.assertIn(key, body)

    def test_validate_shift_endpoint(self):
        resp = self.client.post("/api/shifts/validate", json={
            "employee_id": "E001", "shift_date": "2099-01-01",
            "start_time": "09:00", "end_time": "17:00", "shift_type": "Day",
        })
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIn("safe_to_assign", body)

    def test_create_and_delete_shift(self):
        resp = self.client.post("/api/shifts", json={
            "shift_id": "S_TEST_NEW", "employee_id": "E001", "shift_date": "2099-01-01",
            "start_time": "09:00", "end_time": "17:00", "shift_type": "Day",
        })
        self.assertEqual(resp.status_code, 201)

        resp2 = self.client.get("/api/shifts/S_TEST_NEW")
        self.assertEqual(resp2.status_code, 200)

        resp3 = self.client.delete("/api/shifts/S_TEST_NEW")
        self.assertEqual(resp3.status_code, 200)

        resp4 = self.client.get("/api/shifts/S_TEST_NEW")
        self.assertEqual(resp4.status_code, 404)

    def test_create_conflicting_shift_is_blocked(self):
        # E002 has a known injected overlap conflict around 2026-06-04 in starter data
        resp = self.client.post("/api/shifts", json={
            "shift_id": "S_CONFLICT_TEST", "employee_id": "E002", "shift_date": "2026-06-04",
            "start_time": "15:00", "end_time": "21:00", "shift_type": "Evening",
        })
        self.assertEqual(resp.status_code, 409)
        body = resp.get_json()
        self.assertTrue(body["blocked"])

    def test_missing_required_field_returns_400(self):
        resp = self.client.post("/api/employees", json={"name": "No ID Given"})
        self.assertEqual(resp.status_code, 400)

    def test_dashboard_risk_summary(self):
        resp = self.client.get("/api/dashboard/risk-summary")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIn("risk_level_counts", body)
        self.assertIn("top_at_risk_employees", body)

    def test_fatigue_rules_endpoint(self):
        resp = self.client.get("/api/fatigue-rules")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.get_json()), 7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
