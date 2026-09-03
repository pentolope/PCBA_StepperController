from __future__ import annotations

import hashlib
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(REPO_ROOT, "evidence", "index.json")
DATASHEET_DIR = os.path.join(REPO_ROOT, "evidence", "datasheets")

#: Every document a claim in this repository rests on. `url` is where the
#: file came from; `document_id` is the revision the file itself states.
SOURCES = {
    "tmc2226_trinamic": {
        "file": "datasheets/tmc2226_trinamic.pdf",
        "url": "https://datasheet.lcsc.com/datasheet/pdf/"
               "52fcff4edff5277506a67bb46d8b3298.pdf",
        "retrieved": "2026-09-02",
        "document_id": "TMC2226 Datasheet Rev. 1.06 / 2020-MAY-18",
        "applies_to": ["TMC2226-SA-T"],
    },
    "tmc2209_trinamic": {
        "file": "datasheets/tmc2209_trinamic.pdf",
        "url": "https://datasheet.lcsc.com/datasheet/pdf/"
               "8a6616d50887b5979774ccef79093f9e.pdf",
        "retrieved": "2026-09-02",
        "document_id": "TMC2209 Datasheet Rev. 1.03 / 2019-JUN-26",
        "applies_to": ["TMC2209-LA-T"],
    },
    "tmc2240_trinamic": {
        "file": "datasheets/tmc2240_trinamic.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2306191621_TRINAMIC-Motion-Control-GmbH-TMC2240ATJ-T_"
               "C7429724.pdf",
        "retrieved": "2026-09-02",
        "document_id": "TMC2240 36V 2Arms+ Smart Integrated Stepper Driver, "
                       "Analog Devices 2022, preliminary",
        "applies_to": ["TMC2240ATJ+T"],
    },
    "stm32g030_st": {
        "file": "datasheets/stm32g030_st.pdf",
        "url": "https://datasheet.lcsc.com/datasheet/pdf/"
               "753f35401d4598e355b1dd55569495e1.pdf",
        "retrieved": "2026-09-02",
        "document_id": "STM32G030x6/x8 datasheet DS12991 Rev 3",
        "applies_to": ["STM32G030K8T6TR"],
    },
    "lmr51430_ti": {
        "file": "datasheets/lmr51430_ti.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2302220300_Texas-Instruments-LMR51430YFDDCR_C5219261.pdf",
        "retrieved": "2026-09-02",
        "document_id": "LMR51430 SLUSEF4A, June 2022, revised November 2022",
        "applies_to": ["LMR51430YFDDCR"],
    },
    "si9407bdy_vishay": {
        "file": "datasheets/si9407bdy_vishay.pdf",
        "url": "https://datasheet.lcsc.com/datasheet/pdf/"
               "6f58117dd5ae4abdac31a87ef526800b.pdf",
        "retrieved": "2026-09-02",
        "document_id": "Vishay Siliconix Si9407BDY, document 69902, "
                       "S09-0704-Rev. B, 27-Apr-09",
        "applies_to": ["Si9407BDY-T1-GE3"],
    },
    "smbj_littelfuse": {
        "file": "datasheets/smbj_littelfuse.pdf",
        "url": "https://datasheet.lcsc.com/datasheet/pdf/"
               "4ab84a227fae39f9eac85241b8264ead.pdf",
        "retrieved": "2026-09-02",
        "document_id": "Littelfuse SMBJ series 600 W surface mount TVS "
                       "diodes",
        "applies_to": ["SMBJ26A"],
    },
    "tpd1e10b06_ti": {
        "file": "datasheets/tpd1e10b06_ti.pdf",
        "url": "https://datasheet.lcsc.com/datasheet/pdf/"
               "338eb197fbc247888eaf2230887550ac.pdf",
        "retrieved": "2026-09-02",
        "document_id": "TPD1E10B06 SLLSEB1G",
        "applies_to": ["TPD1E10B06DPYR"],
    },
    "shunt_1206_milliohm": {
        "file": "datasheets/shunt_1206_milliohm.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2209151200_Milliohm-HoLRTX1206-1W-100mR-1-_C5123673.pdf",
        "retrieved": "2026-09-02",
        "document_id": "Milliohm HoLRTX1206 specification for approval "
                       "Ho20220913-18, edition A0, 2022-09-13",
        "applies_to": ["HoLRTX1206-1W-100mR-1%"],
    },
    "hybrid_ncc_hxc": {
        "file": "datasheets/hybrid_ncc_hxc.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2404021225_NCC-Nippon-Chemi-Con-HHXC500ARA101MJA0G_"
               "C3008515.pdf",
        "retrieved": "2026-09-02",
        "document_id": "Nippon Chemi-Con HXC series conductive polymer "
                       "hybrid aluminium electrolytic capacitors",
        "applies_to": ["HHXC500ARA101MJA0G"],
    },
    "srp4020_bourns": {
        "file": "datasheets/srp4020_bourns.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2304140030_BOURNS-SRP4020TA-220M_C1847949.pdf",
        "retrieved": "2026-09-02",
        "document_id": "Bourns SRP4020TA series shielded power inductors",
        "applies_to": ["SRP4020TA-220M"],
    },
    "res_0603_uniroyal": {
        "file": "datasheets/res_0603_uniroyal.pdf",
        "url": "https://datasheet.lcsc.com/datasheet/pdf/"
               "0a975aaa49b7c97f38a963127be4a823.pdf",
        "retrieved": "2026-09-02",
        "document_id": "Uniroyal 0603W chip resistor series specification",
        "applies_to": ["0603WAF1000T5E", "0603WAF1001T5E", "0603WAF4701T5E",
                       "0603WAF1002T5E", "0603WAF1202T5E", "0603WAF2202T5E",
                       "0603WAF1003T5E"],
    },
    "mlcc_yageo_cc": {
        "file": "datasheets/mlcc_yageo_cc.pdf",
        "url": "https://datasheet.lcsc.com/datasheet/pdf/"
               "23ccee80ee542e7cf156a772bb589942.pdf",
        "retrieved": "2026-09-02",
        "document_id": "YAGEO CC series multilayer ceramic capacitors "
                       "specification",
        "applies_to": ["CC0603KRX7R0BB104", "CC0603KRX7R9BB223",
                       "CC0805KKX7R8BB225", "CC0805KKX7R7BB106",
                       "CC1206KKX7R9BB475"],
    },
    "kt0603r_kento": {
        "file": "datasheets/kt0603r_kento.pdf",
        "url": "https://datasheet.lcsc.com/datasheet/pdf/"
               "011ec3e8cb1e825f6961d29bc4db4c7a.pdf",
        "retrieved": "2026-09-02",
        "document_id": "Hubei KENTO KT-0603R specification",
        "applies_to": ["KT-0603R"],
    },
    "kf128_cixikefa": {
        "file": "datasheets/kf128_cixikefa.pdf",
        "url": "https://datasheet.lcsc.com/datasheet/pdf/"
               "29da5b9f86f95d4ff856cbb6af0595a9.pdf",
        "retrieved": "2026-09-02",
        "document_id": "Cixi Kefa KF128-5.08 drawing",
        "applies_to": ["KF128-5.08-2P-AA"],
    },
    "jst_vh_connector": {
        "file": "datasheets/jst_vh_connector.pdf",
        "url": "https://datasheet.lcsc.com/datasheet/pdf/"
               "f2527f0a1a0b17e099f1e5ddd7cdf9f3.pdf",
        "retrieved": "2026-09-02",
        "document_id": "JST VH connector 3.96 mm pitch disconnectable crimp "
                       "style connectors",
        "applies_to": ["B4P-VH(LF)(SN)"],
    },
    "header1x3_kinghelm": {
        "file": "datasheets/header1x3_kinghelm.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2201121530_Shenzhen-Kinghelm-Elec-KH-2-54PH180-1X3P-L11-5_"
               "C2932698.pdf",
        "retrieved": "2026-09-02",
        "applies_to": ["KH-2.54PH180-1X3P-L11.5"],
    },
    "header1x5_kinghelm": {
        "file": "datasheets/header1x5_kinghelm.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2201121530_Shenzhen-Kinghelm-Elec-KH-2-54PH180-1X5P-L11-5_"
               "C2932699.pdf",
        "retrieved": "2026-09-02",
        "applies_to": ["KH-2.54PH180-1X5P-L11.5"],
    },
}


def digest(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_index():
    entries = {}
    for name in sorted(SOURCES):
        source = SOURCES[name]
        path = os.path.join(REPO_ROOT, "evidence", source["file"])
        entry = dict(source)
        entry["sha256"] = digest(path)
        entry["bytes"] = os.path.getsize(path)
        entries[name] = entry
    return {"schema_version": 1, "documents": entries}


def load_index():
    with open(INDEX_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_index():
    with open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(compute_index(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return INDEX_PATH


def verify():
    recorded = load_index()["documents"]
    present = {name for name in os.listdir(DATASHEET_DIR)
               if name.endswith((".pdf", ".json"))}
    referenced = {os.path.basename(entry["file"])
                  for entry in recorded.values()}
    problems = []
    for name in sorted(referenced - present):
        problems.append(("missing_file", name))
    for name in sorted(present - referenced):
        problems.append(("unreferenced_file", name))
    for name in sorted(recorded):
        entry = recorded[name]
        path = os.path.join(REPO_ROOT, "evidence", entry["file"])
        if not os.path.isfile(path):
            continue
        if digest(path) != entry["sha256"]:
            problems.append(("digest_mismatch", name))
    return problems


if __name__ == "__main__":
    sys.stdout.write(write_index() + "\n")
