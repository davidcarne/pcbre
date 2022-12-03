import unittest
import random
from pcbre.model.serialization import PersistentID, PersistentIDClass, PersistentIDRegistry


class TestPersistentID(unittest.TestCase):
    MAX_IDCLASS = max(i.value for i in PersistentIDClass) + 1

    def test_generate_bunch(self):
        self.reg = PersistentIDRegistry()
        unique_values = set()
        REP_COUNT = 1000
        for i in range(REP_COUNT):
            idclass_numeric = i % self.MAX_IDCLASS
            idc = PersistentIDClass(idclass_numeric)
            generated = self.reg.generate(idc)
            self.assertEqual(generated.id_class, idc)
            unique_values.add(generated.as_uint32)
        self.assertEquals(len(unique_values), REP_COUNT)

    def test_roundtrip(self):
        self.reg = PersistentIDRegistry()
        v = self.reg.generate(PersistentIDClass.ImageLayer)
        numeric = v.as_uint32
        v2 = self.reg.decode_check_from_uint32(numeric)
        self.assertEqual(v, v2)

    def test_serialize_deserialize(self):
        self.reg = PersistentIDRegistry()
        a1 = self.reg.generate(PersistentIDClass.ViaPair)
        a2 = self.reg.generate(PersistentIDClass.ViaPair)

        reg2 = PersistentIDRegistry()

        self.assertRaises(KeyError, lambda: reg2.decode_check_from_uint32(a1.as_uint32))

        a1_1 = reg2.decode_add_from_uint32(a1.as_uint32)
        self.assertRaises(ValueError, lambda: reg2.decode_add_from_uint32(a1.as_uint32))
        a1_2 = reg2.decode_check_from_uint32(a1.as_uint32)
        a2_1 = reg2.decode_add_from_uint32(a2.as_uint32)
        self.assertEqual(a1, a1_1)
        self.assertEqual(a1, a1_2)
        self.assertEqual(a2, a2_1)








if __name__ == '__main__':
    unittest.main()
