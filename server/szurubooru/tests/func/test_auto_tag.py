from szurubooru.func import auto_tag_config, booru


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
    assert "rule34" in d["hash"]["sources"]
    for secret in auto_tag_config.SECRET_FIELDS:
        assert auto_tag_config._path_get(d, secret) == ""


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
