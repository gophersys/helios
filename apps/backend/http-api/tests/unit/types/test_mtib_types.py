"""Unit tests for MTIB request type validation (from_json)."""


# ---------------------------------------------------------------------------
# MtibRegisterRequest
# ---------------------------------------------------------------------------

class TestMtibRegisterRequest:
    """Validation tests for MtibRegisterRequest.from_json()."""

    def test_valid_full_request(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        data = {
            "name": "verdin-bench-01",
            "hostname": "verdin-imx8mm-12345",
            "mtibType": "validation",
            "features": ["joulescope", "motion"],
            "appIds": [
                {"jlink": 821009537, "appId": 108},
                {"jlink": 821009546, "appId": 109},
            ],
        }
        req, err = MtibRegisterRequest.from_json(data)
        assert err is None
        assert req.name == "verdin-bench-01"
        assert req.hostname == "verdin-imx8mm-12345"
        assert req.mtibType == "validation"
        assert req.features == ["joulescope", "motion"]
        assert len(req.appIds) == 2
        assert req.appIds[0].jlink == 821009537
        assert req.appIds[0].appId == 108

    def test_valid_minimal_request(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        data = {
            "name": "verdin-bench-01",
            "hostname": "verdin-imx8mm-12345",
            "mtibType": "manufacturing",
        }
        req, err = MtibRegisterRequest.from_json(data)
        assert err is None
        assert req.features == []
        assert req.appIds == []

    def test_null_body(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        req, err = MtibRegisterRequest.from_json(None)
        assert req is None
        assert err == "Request body must contain JSON data"

    def test_empty_body(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        req, err = MtibRegisterRequest.from_json({})
        assert req is None
        assert err == "Request body must contain JSON data"

    def test_missing_name(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        data = {"hostname": "verdin-imx8mm-12345", "mtibType": "validation"}
        req, err = MtibRegisterRequest.from_json(data)
        assert req is None
        assert "name" in err.lower()

    def test_blank_name(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        data = {"name": "   ", "hostname": "verdin-imx8mm-12345", "mtibType": "validation"}
        req, err = MtibRegisterRequest.from_json(data)
        assert req is None
        assert "name" in err.lower()

    def test_name_must_start_with_verdin(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        data = {"name": "my-mtib-01", "hostname": "verdin-imx8mm-12345", "mtibType": "validation"}
        req, err = MtibRegisterRequest.from_json(data)
        assert req is None
        assert "verdin-" in err.lower()

    def test_missing_hostname(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        data = {"name": "verdin-bench-01", "mtibType": "validation"}
        req, err = MtibRegisterRequest.from_json(data)
        assert req is None
        assert "hostname" in err.lower()

    def test_blank_hostname(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        data = {"name": "verdin-bench-01", "hostname": "  ", "mtibType": "validation"}
        req, err = MtibRegisterRequest.from_json(data)
        assert req is None
        assert "hostname" in err.lower()

    def test_missing_mtib_type(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        data = {"name": "verdin-bench-01", "hostname": "verdin-imx8mm-12345"}
        req, err = MtibRegisterRequest.from_json(data)
        assert req is None
        assert "mtibtype" in err.lower()

    def test_invalid_mtib_type(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        data = {
            "name": "verdin-bench-01",
            "hostname": "verdin-imx8mm-12345",
            "mtibType": "testing",
        }
        req, err = MtibRegisterRequest.from_json(data)
        assert req is None
        assert "validation" in err.lower()
        assert "manufacturing" in err.lower()

    def test_features_must_be_list(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        data = {
            "name": "verdin-bench-01",
            "hostname": "verdin-imx8mm-12345",
            "mtibType": "validation",
            "features": "joulescope",
        }
        req, err = MtibRegisterRequest.from_json(data)
        assert req is None
        assert "list" in err.lower()

    def test_invalid_feature(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        data = {
            "name": "verdin-bench-01",
            "hostname": "verdin-imx8mm-12345",
            "mtibType": "validation",
            "features": ["joulescope", "laser"],
        }
        req, err = MtibRegisterRequest.from_json(data)
        assert req is None
        assert "laser" in err.lower()

    def test_app_ids_must_be_list(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        data = {
            "name": "verdin-bench-01",
            "hostname": "verdin-imx8mm-12345",
            "mtibType": "validation",
            "appIds": "not-a-list",
        }
        req, err = MtibRegisterRequest.from_json(data)
        assert req is None
        assert "list" in err.lower()

    def test_app_id_mapping_must_be_object(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        data = {
            "name": "verdin-bench-01",
            "hostname": "verdin-imx8mm-12345",
            "mtibType": "validation",
            "appIds": ["not-an-object"],
        }
        req, err = MtibRegisterRequest.from_json(data)
        assert req is None
        assert "object" in err.lower()

    def test_app_id_mapping_missing_jlink(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        data = {
            "name": "verdin-bench-01",
            "hostname": "verdin-imx8mm-12345",
            "mtibType": "validation",
            "appIds": [{"appId": 108}],
        }
        req, err = MtibRegisterRequest.from_json(data)
        assert req is None
        assert "jlink" in err.lower()

    def test_app_id_mapping_missing_app_id(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        data = {
            "name": "verdin-bench-01",
            "hostname": "verdin-imx8mm-12345",
            "mtibType": "validation",
            "appIds": [{"jlink": 821009537}],
        }
        req, err = MtibRegisterRequest.from_json(data)
        assert req is None
        assert "appid" in err.lower()

    def test_app_id_mapping_jlink_must_be_int(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        data = {
            "name": "verdin-bench-01",
            "hostname": "verdin-imx8mm-12345",
            "mtibType": "validation",
            "appIds": [{"jlink": "not-a-number", "appId": 108}],
        }
        req, err = MtibRegisterRequest.from_json(data)
        assert req is None
        assert "jlink" in err.lower()

    def test_app_id_mapping_app_id_must_be_int(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        data = {
            "name": "verdin-bench-01",
            "hostname": "verdin-imx8mm-12345",
            "mtibType": "validation",
            "appIds": [{"jlink": 821009537, "appId": "str"}],
        }
        req, err = MtibRegisterRequest.from_json(data)
        assert req is None
        assert "appid" in err.lower()

    def test_name_is_stripped(self):
        from src.api.v2.mtib.types import MtibRegisterRequest

        data = {
            "name": "  verdin-bench-01  ",
            "hostname": "  verdin-imx8mm-12345  ",
            "mtibType": "  validation  ",
        }
        req, err = MtibRegisterRequest.from_json(data)
        assert err is None
        assert req.name == "verdin-bench-01"
        assert req.hostname == "verdin-imx8mm-12345"
        assert req.mtibType == "validation"


# ---------------------------------------------------------------------------
# MtibUnregisterRequest
# ---------------------------------------------------------------------------

class TestMtibUnregisterRequest:
    """Validation tests for MtibUnregisterRequest.from_json()."""

    def test_valid_request(self):
        from src.api.v2.mtib.types import MtibUnregisterRequest

        data = {"hostname": "verdin-imx8mm-12345"}
        req, err = MtibUnregisterRequest.from_json(data)
        assert err is None
        assert req.hostname == "verdin-imx8mm-12345"

    def test_null_body(self):
        from src.api.v2.mtib.types import MtibUnregisterRequest

        req, err = MtibUnregisterRequest.from_json(None)
        assert req is None
        assert err == "Request body must contain JSON data"

    def test_empty_body(self):
        from src.api.v2.mtib.types import MtibUnregisterRequest

        req, err = MtibUnregisterRequest.from_json({})
        assert req is None
        assert err == "Request body must contain JSON data"

    def test_missing_hostname(self):
        from src.api.v2.mtib.types import MtibUnregisterRequest

        req, err = MtibUnregisterRequest.from_json({"other": "data"})
        assert req is None
        assert "hostname" in err.lower()

    def test_blank_hostname(self):
        from src.api.v2.mtib.types import MtibUnregisterRequest

        req, err = MtibUnregisterRequest.from_json({"hostname": "   "})
        assert req is None
        assert "hostname" in err.lower()

    def test_hostname_is_stripped(self):
        from src.api.v2.mtib.types import MtibUnregisterRequest

        req, err = MtibUnregisterRequest.from_json({"hostname": "  verdin-imx8mm-12345  "})
        assert err is None
        assert req.hostname == "verdin-imx8mm-12345"


# ---------------------------------------------------------------------------
# MtibResponse
# ---------------------------------------------------------------------------

class TestMtibResponse:
    """Tests for MtibResponse.from_mtib()."""

    def test_from_mtib(self):
        from types import SimpleNamespace
        from src.api.v2.mtib.types import MtibResponse

        mtib = SimpleNamespace(
            id="verdin-imx8mm-12345",
            name="verdin-bench-01",
            type="VALIDATION",
            features=["JOULESCOPE", "MOTION"],
        )
        resp = MtibResponse.from_mtib(mtib)
        assert resp.hostname == "verdin-imx8mm-12345"
        assert resp.name == "verdin-bench-01"
        assert resp.type == "validation"
        assert resp.features == ["joulescope", "motion"]

    def test_from_mtib_empty_features(self):
        from types import SimpleNamespace
        from src.api.v2.mtib.types import MtibResponse

        mtib = SimpleNamespace(
            id="verdin-imx8mm-12345",
            name="verdin-bench-02",
            type="MANUFACTURING",
            features=[],
        )
        resp = MtibResponse.from_mtib(mtib)
        assert resp.type == "manufacturing"
        assert resp.features == []
