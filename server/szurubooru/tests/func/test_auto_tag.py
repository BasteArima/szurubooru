from szurubooru import db
from szurubooru.func import auto_tag, auto_tag_config, booru


def test_deep_merge_overrides_and_preserves():
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    override = {"b": {"c": 20}, "e": 5}
    merged = auto_tag_config._deep_merge(base, override)
    assert merged == {"a": 1, "b": {"c": 20, "d": 3}, "e": 5}
    # original is not mutated
    assert base == {"a": 1, "b": {"c": 2, "d": 3}}


def test_path_get_set():
    cfg = {"hash": {"danbooruApiKey": "secret"}}
    assert auto_tag_config._path_get(cfg, "hash.danbooruApiKey") == "secret"
    assert auto_tag_config._path_get(cfg, "hash.missing") is None
    assert auto_tag_config._path_get(cfg, "nope.nope") is None
    auto_tag_config._path_set(cfg, "ai.token", "abc")
    assert cfg["ai"]["token"] == "abc"


def test_defaults_have_expected_shape():
    d = auto_tag_config.DEFAULTS
    assert d["typeTags"]["animatedTag"] == "animated"
    assert d["typeTags"]["videoTag"] == "video"
    assert set(d["hash"]["sources"].keys()) == {
        "rule34",
        "danbooru",
        "gelbooru",
    }
    for secret in auto_tag_config.SECRET_FIELDS:
        assert auto_tag_config._path_get(d, secret) == ""


def test_normalize_migrates_legacy_shape():
    cfg = {
        "hash": {
            "sources": ["rule34", "danbooru"],  # old list format
            "danbooruApiKey": "legacy-key",  # old top-level secret
        }
    }
    out = auto_tag_config._normalize(cfg)
    sources = out["hash"]["sources"]
    assert isinstance(sources, dict)
    assert set(sources.keys()) == {"rule34", "danbooru", "gelbooru"}
    assert sources["rule34"]["priority"] == 1
    assert sources["danbooru"]["apiKey"] == "legacy-key"
    assert "danbooruApiKey" not in out["hash"]


def test_norm_safety_mapping():
    assert booru._norm_safety("s") == "safe"
    assert booru._norm_safety("safe") == "safe"
    assert booru._norm_safety("general") == "safe"
    assert booru._norm_safety("sensitive") == "sketchy"
    assert booru._norm_safety("q") == "sketchy"
    assert booru._norm_safety("questionable") == "sketchy"
    assert booru._norm_safety("e") == "unsafe"
    assert booru._norm_safety("explicit") == "unsafe"
    assert booru._norm_safety(None) is None
    assert booru._norm_safety("weird") is None


def test_extract_posts_shapes():
    assert booru._extract_posts(None) == []
    assert booru._extract_posts([{"a": 1}]) == [{"a": 1}]
    assert booru._extract_posts({"post": [{"a": 1}]}) == [{"a": 1}]
    assert booru._extract_posts({"post": {"a": 1}}) == [{"a": 1}]
    assert booru._extract_posts({"nothing": 1}) == []


def test_gelbooru_type_map():
    assert booru._GELBOORU_TYPE[0] == "general"
    assert booru._GELBOORU_TYPE[1] == "artist"
    assert booru._GELBOORU_TYPE[3] == "copyright"
    assert booru._GELBOORU_TYPE[4] == "character"
    assert booru._GELBOORU_TYPE[5] == "meta"


def _recat_setup(
    config_injector, post_factory, tag_factory, tag_category_factory, tag_cat
):
    config_injector({"tag_name_regex": ".*"})
    default_cat = tag_category_factory(name="default", default=True)
    artist_cat = tag_category_factory(name="artist")
    db.session.add_all([default_cat, artist_cat])
    tag = tag_factory(names=["rwt4184"], category=tag_cat(default_cat, artist_cat))
    db.session.add(tag)
    post = post_factory()
    post.tags = [tag]
    db.session.add(post)
    db.session.flush()
    return post, tag


def test_apply_tags_recategorizes_neutral_existing_tag(
    config_injector, post_factory, tag_factory, tag_category_factory
):
    post, tag = _recat_setup(
        config_injector,
        post_factory,
        tag_factory,
        tag_category_factory,
        lambda d, a: d,
    )
    auto_tag._apply_tags(
        post,
        [("rwt4184", "artist")],
        recategorize_existing=True,
        neutral_categories={"default"},
    )
    assert tag.category.name == "artist"


def test_apply_tags_preserves_manual_category(
    config_injector, post_factory, tag_factory, tag_category_factory
):
    # tag already in a specific (non-neutral) category is never touched
    post, tag = _recat_setup(
        config_injector,
        post_factory,
        tag_factory,
        tag_category_factory,
        lambda d, a: a,
    )
    auto_tag._apply_tags(
        post,
        [("rwt4184", "default")],
        recategorize_existing=True,
        neutral_categories={"default"},
    )
    assert tag.category.name == "artist"


def test_apply_tags_recategorize_off_by_default(
    config_injector, post_factory, tag_factory, tag_category_factory
):
    post, tag = _recat_setup(
        config_injector,
        post_factory,
        tag_factory,
        tag_category_factory,
        lambda d, a: d,
    )
    auto_tag._apply_tags(post, [("rwt4184", "artist")])
    assert tag.category.name == "default"


def test_tag_display_name_uses_names_when_first_name_none():
    # a freshly-created tag has first_name (a deferred SQL column_property) None
    # until it is flushed, but its `names` relationship is populated in memory;
    # reading first_name there used to crash on None.lower()
    class _Name:
        def __init__(self, name):
            self.name = name

    class _Tag:
        names = [_Name("firefly_(honkai:_star_rail)")]
        first_name = None

    assert (
        auto_tag._tag_display_name(_Tag())
        == "firefly_(honkai:_star_rail)"
    )


def test_tag_display_name_falls_back_to_first_name():
    class _Tag:
        names = []
        first_name = "existing_tag"

    assert auto_tag._tag_display_name(_Tag()) == "existing_tag"


def test_parse_tag_types_rule34_xml():
    # rule34.xxx returns XML even with json=1
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?><tags type="array">'
        '<tag type="0" count="1" name="1girl" id="1"/>'
        '<tag type="4" count="1" name="firefly_(honkai:_star_rail)" id="2"/>'
        '<tag type="3" count="1" name="honkai:_star_rail" id="3"/>'
        "</tags>"
    )
    assert booru._parse_tag_types(xml.encode()) == {
        "1girl": "general",
        "firefly_(honkai:_star_rail)": "character",
        "honkai:_star_rail": "copyright",
    }


def test_parse_tag_types_json_shapes():
    # gelbooru.com returns JSON: a bare list or wrapped in {"tag": [...]}
    as_list = b'[{"type":1,"name":"artist_x"},{"type":5,"name":"highres"}]'
    assert booru._parse_tag_types(as_list) == {
        "artist_x": "artist",
        "highres": "meta",
    }
    wrapped = b'{"tag":[{"type":4,"name":"char_y"}]}'
    assert booru._parse_tag_types(wrapped) == {"char_y": "character"}


def test_parse_tag_types_garbage_and_empty():
    # auth errors / empty bodies must not raise, just yield nothing
    assert booru._parse_tag_types(b"") == {}
    assert booru._parse_tag_types(b"Missing authentication.") == {}
    assert booru._parse_tag_types(b"<not-valid-xml") == {}
    # unknown numeric type falls back to general
    assert booru._parse_tag_types(b'[{"type":99,"name":"t"}]') == {
        "t": "general"
    }


def test_tag_batch_support_flags():
    # rule34 has no batch tag endpoint (per-tag XML); gelbooru.com does
    assert booru._TAG_BATCH_SUPPORT.get("rule34") is False
    assert booru._TAG_BATCH_SUPPORT.get("gelbooru") is True
    # unknown source defaults to per-tag (safe)
    assert booru._TAG_BATCH_SUPPORT.get("whatever", False) is False


def test_tag_category_cache_skips_network_on_hit():
    class FakeCache:
        def __init__(self):
            self.data = {}

        def get(self, source, names):
            return {
                n: self.data[(source, n)]
                for n in names
                if (source, n) in self.data
            }

        def put(self, source, mapping):
            for n, c in mapping.items():
                self.data[(source, n)] = c

    calls = {"n": 0}

    def fake_fetch(url, ua, source, delay):
        calls["n"] += 1
        import urllib.parse

        params = dict(urllib.parse.parse_qsl(url.split("?", 1)[1]))
        name = params.get("name", "")
        types = {"1girl": "0", "firefly": "4"}
        if name in types:
            return (
                '<tags><tag type="%s" name="%s"/></tags>'
                % (types[name], name)
            ).encode()
        return b"<tags></tags>"

    original = booru._fetch
    booru._fetch = fake_fetch
    try:
        cfg = {"userAgent": "x", "requestDelaySeconds": 0}
        cache = FakeCache()
        first = booru._gelbooru_tag_categories(
            "http://r", ["1girl", "firefly"], cfg, "rule34", "", cache
        )
        assert first == {"1girl": "general", "firefly": "character"}
        assert calls["n"] == 2
        # second pass is served entirely from the cache
        calls["n"] = 0
        second = booru._gelbooru_tag_categories(
            "http://r", ["1girl", "firefly"], cfg, "rule34", "", cache
        )
        assert second == first
        assert calls["n"] == 0
        # an unresolved tag stays out of the cache so it can be retried later
        calls["n"] = 0
        third = booru._gelbooru_tag_categories(
            "http://r", ["1girl", "unknown"], cfg, "rule34", "", cache
        )
        assert third == {"1girl": "general", "unknown": "general"}
        assert calls["n"] == 1
        assert ("rule34", "unknown") not in cache.data
    finally:
        booru._fetch = original
