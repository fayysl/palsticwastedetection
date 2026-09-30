import io

import pytest
from PIL import Image

import app as app_module
from services import ai, knowledge
from services.store import SQLiteStore, summarize

CLIENT = {"X-Client-Id": "test-client-1234"}


def png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), "green").save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    store = SQLiteStore(str(tmp_path / "t.db"))
    return app_module.create_app(store=store).test_client()


def post_image(client):
    return client.post("/api/scan", headers=CLIENT,
                       data={"image": (io.BytesIO(png_bytes()), "w.png", "image/png")},
                       content_type="multipart/form-data")


def test_pages_render(client):
    for path in ("/", "/scan", "/dashboard", "/guide"):
        assert client.get(path).status_code == 200


def test_demo_scan_saves_and_tracks(client):
    r = post_image(client)
    assert r.status_code == 200
    scan = r.get_json()
    assert scan["demo"] is True
    assert scan["analysis"]["total_items"] == 4
    assert scan["id"]

    hist = client.get("/api/history", headers=CLIENT).get_json()["scans"]
    assert len(hist) == 1
    stats = client.get("/api/stats", headers=CLIENT).get_json()
    assert stats["mine"]["scans"] == 1
    assert stats["mine"]["by_category"]["bottle"] == 2
    assert client.get(f"/scan/{scan['id']}").status_code == 200
    # Other visitors don't see this history
    assert client.get("/api/history", headers={"X-Client-Id": "someone-else-99"}).get_json()["scans"] == []


def test_real_scan_uses_ai(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setattr(ai, "detect", lambda jpeg: ({"items": [], "summary": "Just a leaf"}, "m:free"))
    scan = post_image(client).get_json()
    assert scan["demo"] is False
    assert scan["analysis"]["plastic_detected"] is False


def test_ai_failure_returns_502(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")

    def boom(jpeg):
        raise ai.AIError("All AI models failed")
    monkeypatch.setattr(ai, "detect", boom)
    r = post_image(client)
    assert r.status_code == 502 and "failed" in r.get_json()["error"]


def test_rejects_bad_uploads(client):
    assert client.post("/api/scan").status_code == 400
    r = client.post("/api/scan", data={"image": (io.BytesIO(b"not an image"), "x.png", "image/png")},
                    content_type="multipart/form-data")
    assert r.status_code == 400


def test_enrich_rules():
    a = knowledge.enrich({"items": [
        {"category": "food_container", "resin_code": 6, "count": 2},   # foam -> general
        {"category": "bag", "resin_code": "abc"},                      # bad resin -> default
        {"category": "made-up", "count": -3},                          # unknown -> other, count>=1
        "garbage",
    ]})
    assert [i["bin"]["key"] for i in a["items"]] == ["general", "drop_off", "general"]
    assert a["items"][1]["resin"]["number"] == 4
    assert a["items"][2]["category"] == "other" and a["items"][2]["count"] == 1
    assert a["total_items"] == 4 and a["level"]["key"] == "medium"
    assert a["co2_saved_kg"] > 0


def test_parse_json_handles_fences_and_chatter():
    assert ai.parse_json('```json\n{"items": []}\n```') == {"items": []}
    assert ai.parse_json('Sure! Here it is: {"items": [1]} hope that helps') == {"items": [1]}
    with pytest.raises(ValueError):
        ai.parse_json("no json here")


def test_detect_falls_back_to_next_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setattr(ai, "candidate_models", lambda: ["a:free", "b:free"])
    calls = []

    class Resp:
        def __init__(self, status, payload):
            self.status_code, self._p, self.text = status, payload, ""

        def json(self):
            return self._p

    def fake_post(url, headers, json, timeout):
        calls.append(json["model"])
        if json["model"] == "a:free":
            return Resp(429, {})
        return Resp(200, {"model": "b:free", "choices": [{"message": {"content": '{"items": []}'}}]})

    monkeypatch.setattr(ai.requests, "post", fake_post)
    detection, model = ai.detect(b"jpeg")
    assert calls == ["a:free", "b:free"] and model == "b:free"


def test_summarize_empty():
    s = summarize([])
    assert s["scans"] == 0 and s["eco_level"]["name"].startswith("Seedling")


def test_supabase_store_requests(monkeypatch):
    from services import store as store_mod
    sent = []

    class Resp:
        content = b"[]"

        def raise_for_status(self):
            pass

        def json(self):
            return []

    def fake_request(method, url, headers, params, json, timeout):
        sent.append((method, url, headers, params, json))
        return Resp()

    monkeypatch.setattr(store_mod.requests, "request", fake_request)
    s = store_mod.SupabaseStore("https://abc.supabase.co/", "service-key")
    row = s.save("client-123456", knowledge.enrich(ai.DEMO_DETECTION), "data:x", "demo", True)
    s.list("client-123456")
    method, url, headers, _, body = sent[0]
    assert method == "POST" and url == "https://abc.supabase.co/rest/v1/scans"
    assert headers["apikey"] == "service-key" and body["id"] == row["id"]
    assert sent[1][3]["client_id"] == "eq.client-123456"


def test_supabase_key_headers_and_url_normalization():
    from services.store import SupabaseStore, normalize_supabase_url
    new = SupabaseStore("https://abc.supabase.co", "sb_secret_xyz ")
    assert new.headers["apikey"] == "sb_secret_xyz" and "Authorization" not in new.headers
    legacy = SupabaseStore("https://abc.supabase.co", "eyJhbGciOi.payload.sig")
    assert legacy.headers["Authorization"] == "Bearer eyJhbGciOi.payload.sig"
    assert normalize_supabase_url("https://supabase.com/dashboard/project/ljywbv") == "https://ljywbv.supabase.co"
    assert normalize_supabase_url(" https://abc.supabase.co/rest/v1/ ") == "https://abc.supabase.co"
