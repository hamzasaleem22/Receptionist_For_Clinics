from agent import normalize_phone


class TestNormalizePhone:
    def test_strips_non_digits(self):
        assert normalize_phone("+923503070436") == "923503070436"

    def test_strips_spaces_dashes_parens(self):
        assert normalize_phone("+92 (350) 307-0436") == "923503070436"

    def test_already_clean(self):
        assert normalize_phone("923503070436") == "923503070436"

    def test_none_returns_none(self):
        assert normalize_phone(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_phone("") is None

    def test_only_non_digits(self):
        assert normalize_phone("abc-() ") == ""
