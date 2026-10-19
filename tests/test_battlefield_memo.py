"""Intra-observation memo and masked final read checks (synthetic, not live)."""
import unittest
from hotstate.battlefield import _SelectedCensusMemory, VolskayaBattlefield
from hotstate.native import NativeUnavailable
from hotstate.positions import _RecordedMemory

class Memory:
    module_base=0x140000000
    def __init__(self):
        self.calls=[];self.data={}
    def read_memory(self,a,s):
        self.calls.append((a,s))
        return bytes(self.data.get(a+i,0) for i in range(s))

class BattlefieldMemoTests(unittest.TestCase):
    def test_core_recorded_reads_are_not_cached_only_final_checks_coalesced(self):
        raw=Memory();m=_RecordedMemory(raw)
        m.read_memory(100,4);m.read_memory(100,4)
        self.assertEqual(len(raw.calls),2)
        self.assertEqual(m.coherence_reads('torn'),[(100,bytes(4))])
        raw.data[100]=1;m.read_memory(100,4)
        with self.assertRaisesRegex(NativeUnavailable,'torn'):m.coherence_reads('torn')
        m.read_set=[(100,b'abcd'),(102,b'X')]
        with self.assertRaisesRegex(NativeUnavailable,'torn'):m.coherence_reads('torn')

    def test_header_slice_hits_are_selected_for_final_coherence(self):
        raw=Memory();m=_SelectedCensusMemory(raw);unit=0x900000
        m.census_header(unit)
        raw.calls.clear()
        self.assertEqual(m.read_memory(unit+0x3a,1),b'\0')
        self.assertEqual(raw.calls,[])
        self.assertIn((unit+0x3a,b'\0'),m.read_set)

    def test_memo_lifetime_and_fresh_reads(self):
        raw=Memory();m=_SelectedCensusMemory(raw)
        self.assertEqual(m.read_memory(100,4),bytes(4))
        raw.data[100]=7
        self.assertEqual(m.read_memory(100,4),bytes(4))
        self.assertEqual(len(raw.calls),1)
        self.assertEqual(m.fresh_read(100,4),b'\x07\0\0\0')
        self.assertEqual(_SelectedCensusMemory(raw).read_memory(100,4),b'\x07\0\0\0')
        with self.assertRaisesRegex(NativeUnavailable,'dechiree'):
            VolskayaBattlefield._coherence_reads(m.read_set)

    def test_masked_headers_recheck_used_fields_only_in_one_io(self):
        raw=Memory();m=_SelectedCensusMemory(raw);unit=0x900000
        data=m.census_header(unit)
        m.read_set.extend(((unit+0x39,data[0x29:0x2a]),(unit+0x18,data[8:16]),(unit+0x44,data[0x34:0x35])))
        raw.data[unit+0x14]=99
        checks=m.coherence_checks(VolskayaBattlefield._coherence_reads(m.read_set))
        raw.calls.clear()
        for address,size,slices in checks:
            now=raw.read_memory(address,size)
            self.assertTrue(all(now[off:off+len(old)]==old for off,old in slices))
        self.assertEqual(raw.calls,[(unit+0x10,0x38)])
        raw.data[unit+0x44]=12
        self.assertTrue(any(any(raw.read_memory(a,s)[off:off+len(old)]!=old for off,old in slices) for a,s,slices in checks))
        self.assertTrue(all(a+s<=unit+0x48 for a,s,_ in checks))

    def test_overlapping_observations_cannot_hide_a_contradiction(self):
        with self.assertRaisesRegex(NativeUnavailable,'dechiree'):
            VolskayaBattlefield._coherence_reads([(100,b'abcd'),(102,b'X')])

if __name__=='__main__':unittest.main()
