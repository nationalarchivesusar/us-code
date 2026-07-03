import sys
sys.path.insert(0, "tools")
import rp_codifier as rc
ident = "/us/usc/t5/s7323"
print(rc.element_hash("5", ident))
open("scratch_out.txt", "w", encoding="utf-8").write(rc.get_element_xml("5", ident))
