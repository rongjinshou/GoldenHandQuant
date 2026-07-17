"""ST 前缀单一事实源: 判定/双向修正(设计 0711-st-honesty §4.4)。"""
from src.domain.market.value_objects.st_prefixes import (
    ST_NAME_PREFIXES,
    correct_st_name,
    is_st_name,
)


class TestIsStName:
    def test_all_prefixes_and_case(self):
        assert is_st_name("ST海虹")
        assert is_st_name("*ST金科")
        assert is_st_name("SST前锋")
        assert is_st_name("S*ST北亚")
        assert is_st_name("st小写")  # 与 filter_st 既有 upper() 口径一致

    def test_normal_names(self):
        assert not is_st_name("海虹控股")
        assert not is_st_name("金科股份")


class TestCorrectStName:
    def test_add_prefix_when_registry_says_st(self):
        assert correct_st_name("金科股份", is_st=True) == "ST金科股份"

    def test_strip_longest_prefix_when_registry_says_clean(self):
        assert correct_st_name("*ST金科", is_st=False) == "金科"
        assert correct_st_name("S*ST北亚", is_st=False) == "北亚"

    def test_noop_when_already_consistent(self):
        assert correct_st_name("ST海虹", is_st=True) == "ST海虹"
        assert correct_st_name("海虹控股", is_st=False) == "海虹控股"


def test_prefixes_longest_first():
    assert ST_NAME_PREFIXES == ("S*ST", "*ST", "SST", "ST")
