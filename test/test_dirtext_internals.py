import unittest
import pcbre.model.serialization_dirtext as dirtext


class TestDirText(unittest.TestCase):
    def check_round_trip(self, v:str):
        d = dirtext._encode_string(v)
        r = dirtext.Tokenizer(d).get_string_token()
        r_ = r.decode("utf8")
        self.assertEqual(v, r_)

    def test_string_encoding(self):
        self.check_round_trip("hello world")
        self.check_round_trip("hello\"world")
        self.check_round_trip("\"helloworld\"")
        self.check_round_trip("'helloworld")
        self.check_round_trip("123\u2b21478968w\u2b21")

    def test_decode_example(self):
        l = list(dirtext.Tokenizer(b"WORD key=value key2=-2.14 key3=7 key4=(a,\"b\\nx\",c,6)     key5 = ((7,\"foo\"))"))
        self.assertListEqual(l,
            [b"WORD",
             b"key", b"=", b"value",
             b"key2", b"=", b"-2.14",
             b"key3", b"=", b"7",
             b"key4", b"=", b"(", b"a", b",", b"b\nx", b",", b"c", b",", b"6", b")",
             b"key5", b"=", b"(", b"(", b"7", b",", b"foo", b")", b")"])

        l = dirtext.parse_line_dict(
            b"key=value key2=-2.14 key3=7 key4=(a,\"b\\nx\",c,6)     key5 = (7,(\"foo\", 2))", 0)
        self.assertDictEqual(l,
                             {
                                 b"key": b"value",
                                 b"key2": b"-2.14",
                                 b"key3": b"7",
                                 b"key4": (b"a", b"b\nx", b"c", b"6"),
                                 b"key5": (b"7", (b"foo", b"2"))
                             })



