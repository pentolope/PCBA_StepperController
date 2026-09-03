from __future__ import annotations

import os
import sys

from . import netlist

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIBRARY_NAME = netlist.LIBRARY_NAME
SYMBOL_LIB_PATH = os.path.join(REPO_ROOT, "library",
                               LIBRARY_NAME + ".kicad_sym")
FOOTPRINT_DIR = os.path.join(REPO_ROOT, "library", LIBRARY_NAME + ".pretty")
SYM_LIB_TABLE = os.path.join(REPO_ROOT, "sym-lib-table")
FP_LIB_TABLE = os.path.join(REPO_ROOT, "fp-lib-table")

SYMBOL_LIB_VERSION = "20251024"
FOOTPRINT_VERSION = "20260206"
GENERATOR = "stepper-controller-design-source"

BUCK_SYMBOL_NAME = "LMR51430"
BUCK_PINS = [("3", "VIN", "power_in", "left"),
             ("5", "EN", "input", "left"),
             ("4", "FB", "input", "left"),
             ("2", "SW", "output", "right"),
             ("6", "CB", "passive", "right"),
             ("1", "GND", "power_in", "bottom")]
BUCK_DATASHEET = "https://www.ti.com/lit/ds/symlink/lmr51430.pdf"

PFET_SYMBOL_NAME = "Si9407BDY"
PFET_DATASHEET = "https://www.vishay.com/docs/69902/si9407bdy.pdf"

TVS_SYMBOL_NAME = "TVS_Unidirectional"
ESD_SYMBOL_NAME = "TPD1E10B06"
ESD_DATASHEET = "https://www.ti.com/lit/ds/symlink/tpd1e10b06.pdf"
TERMINAL_SYMBOL_NAME = "ScrewTerminal_1x02"
TERMINAL_FOOTPRINT_FILTER = "TerminalBlock*"

#: TI DPY0002A, drawing 4224561/C (SLLSEB1G): two 0.30 x 0.50 lands on
#: 0.70 centres; package outline 1.10 x 0.70.
X1SON_FOOTPRINT_NAME = "TI_X1SON-2_1.0x0.6mm_P0.65mm"
X1SON_PAD_SIZE_MM = (0.30, 0.50)
X1SON_PAD_PITCH_MM = 0.70
X1SON_BODY_MM = (1.10, 0.70)
X1SON_COURTYARD_MARGIN_MM = 0.15

#: Cixi Kefa KF128-5.08 drawing rev A: two 1.40 +0.10/-0.00 holes on
#: 5.08 +/-0.03 centres; body 10.70 deep with the pin row 5.40 from the
#: wire-entry face.
KF128_FOOTPRINT_NAME = "TerminalBlock_KF128-5.08_1x02_P5.08mm"
KF128_PITCH_MM = 5.08
KF128_DRILL_MM = 1.40
KF128_PAD_DIAMETER_MM = 2.60
KF128_BODY_DEPTH_MM = 10.70
KF128_PIN_TO_ENTRY_FACE_MM = 5.40
KF128_COURTYARD_MARGIN_MM = 0.25

#: Bourns SRP4020TA recommended layout: two 2.20 x 2.40 lands, 5.20 overall.
#: Body 4.45 x 4.06.
INDUCTOR_FOOTPRINT_NAME = "L_Bourns_SRP4020TA"
INDUCTOR_PAD_MM = (2.20, 2.40)
INDUCTOR_LAND_SPAN_MM = 5.20
INDUCTOR_BODY_MM = (4.45, 4.06)
INDUCTOR_COURTYARD_MARGIN_MM = 0.25

#: HTSSOP-28 land pattern for the driver. The signal lands are the standard
#: ones; the exposed pad carries copper with no mask, and the mask and paste
#: are cut into windows so that every thermal via lands on a mask dam.
HTSSOP_FOOTPRINT_NAME = (
    "HTSSOP-28-1EP_4.4x9.7mm_P0.65mm_EP2.75x6.2mm_SegmentedMask")
HTSSOP_PIN_COUNT = 28
HTSSOP_PITCH_MM = 0.65
HTSSOP_PAD_MM = (1.55, 0.40)
HTSSOP_ROW_OFFSET_MM = 2.875
HTSSOP_BODY_MM = (4.40, 9.70)
HTSSOP_EP_MM = (2.75, 6.20)
HTSSOP_MASK_WINDOWS = 4
HTSSOP_MASK_DAM_MM = 1.00
HTSSOP_VIA_PAD_MM = netlist.THERMAL_VIA_PAD_MM
HTSSOP_VIA_DRILL_MM = netlist.THERMAL_VIA_DRILL_MM
HTSSOP_VIA_COLUMNS_MM = (-0.9, 0.0, 0.9)
HTSSOP_COURTYARD_MARGIN_MM = 0.25


def mask_window_height_mm():
    return ((HTSSOP_EP_MM[1] - HTSSOP_MASK_DAM_MM * (HTSSOP_MASK_WINDOWS - 1))
            / HTSSOP_MASK_WINDOWS)


def mask_window_centres_mm():
    height = mask_window_height_mm()
    pitch = height + HTSSOP_MASK_DAM_MM
    first = -(HTSSOP_EP_MM[1] - height) / 2.0
    return tuple(first + pitch * index
                 for index in range(HTSSOP_MASK_WINDOWS))


def thermal_via_rows_mm():
    centres = mask_window_centres_mm()
    return tuple((centres[index] + centres[index + 1]) / 2.0
                 for index in range(len(centres) - 1))


def thermal_via_positions_mm():
    return tuple((x, y) for y in thermal_via_rows_mm()
                 for x in HTSSOP_VIA_COLUMNS_MM)


def paste_coverage_fraction():
    area = (HTSSOP_EP_MM[0] * mask_window_height_mm() * HTSSOP_MASK_WINDOWS)
    return area / (HTSSOP_EP_MM[0] * HTSSOP_EP_MM[1])


def thermal_via_to_mask_clearance_mm():
    return ((HTSSOP_MASK_DAM_MM - HTSSOP_VIA_PAD_MM) / 2.0)


def htssop_pad_positions_mm():
    span = HTSSOP_PITCH_MM * (HTSSOP_PIN_COUNT // 2 - 1)
    positions = {}
    for index in range(HTSSOP_PIN_COUNT // 2):
        y = -span / 2.0 + HTSSOP_PITCH_MM * index
        positions[str(index + 1)] = (-HTSSOP_ROW_OFFSET_MM, y)
        positions[str(HTSSOP_PIN_COUNT - index)] = (HTSSOP_ROW_OFFSET_MM, y)
    return positions


# ---------------------------------------------------------------------------
# symbols

def _effects():
    return ("\n\t\t\t\t(effects\n\t\t\t\t\t(font\n"
            "\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t)\n\t\t\t\t)")


def _symbol_property(key, value, index, hide):
    hidden = "\n\t\t\t(hide yes)" if hide else ""
    return ('\t\t(property "%s" "%s"\n\t\t\t(at 0 %.2f 0)%s\n'
            '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
            '\t\t\t\t)\n\t\t\t)\n\t\t)\n'
            % (key, value, 17.78 - 2.54 * index, hidden))


def _pin_text(kind, x, y, angle, name, number):
    return ('\t\t\t(pin %s line\n\t\t\t\t(at %.2f %.2f %d)\n'
            '\t\t\t\t(length 2.54)\n'
            '\t\t\t\t(name "%s"%s\n\t\t\t\t)\n'
            '\t\t\t\t(number "%s"%s\n\t\t\t\t)\n\t\t\t)'
            % (kind, x, y, angle, name, _effects(), number, _effects()))


def _rectangle(half_x, half_y):
    return ['\t\t\t(rectangle',
            '\t\t\t\t(start %.2f %.2f)' % (-half_x, half_y),
            '\t\t\t\t(end %.2f %.2f)' % (half_x, -half_y),
            '\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n'
            '\t\t\t\t\t(type default)\n\t\t\t\t)',
            '\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)',
            '\t\t\t)']


def _placed_pin(number, pin_name, kind, side, placed_pins, half_x, half_y):
    same_side = [entry for entry in placed_pins if entry[3] == side]
    index = same_side.index((number, pin_name, kind, side))
    span = 2.54 * (len(same_side) - 1) / 2.0
    if side == "left":
        return _pin_text(kind, -half_x - 2.54, span - 2.54 * index, 0,
                         pin_name, number)
    if side == "right":
        return _pin_text(kind, half_x + 2.54, span - 2.54 * index, 180,
                         pin_name, number)
    if side == "bottom":
        return _pin_text(kind, 2.54 * index - span, -half_y - 2.54, 90,
                         pin_name, number)
    return _pin_text(kind, 2.54 * index - span, half_y + 2.54, 270,
                     pin_name, number)


def _boxed_symbol(name, reference_prefix, value, footprint, datasheet,
                  placed_pins, half_x, half_y, footprint_filter=None):
    lines = ['\t(symbol "%s"' % name,
             '\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t)',
             '\t\t(exclude_from_sim no)',
             '\t\t(in_bom yes)',
             '\t\t(on_board yes)',
             _symbol_property("Reference", reference_prefix, 0,
                              False).rstrip("\n"),
             _symbol_property("Value", value, 1, False).rstrip("\n"),
             _symbol_property("Footprint", footprint, 2, True).rstrip("\n"),
             _symbol_property("Datasheet", datasheet, 3, True).rstrip("\n")]
    if footprint_filter is not None:
        lines.append(_symbol_property("ki_fp_filters", footprint_filter, 4,
                                      True).rstrip("\n"))
    lines.append('\t\t(symbol "%s_0_1"' % name)
    lines.extend(_rectangle(half_x, half_y))
    lines.append('\t\t)')
    lines.append('\t\t(symbol "%s_1_1"' % name)
    for number, pin_name, kind, side in placed_pins:
        lines.append(_placed_pin(number, pin_name, kind, side, placed_pins,
                                 half_x, half_y))
    lines.append('\t\t)')
    lines.append('\t)')
    return "\n".join(lines)


def buck_symbol_text():
    return _boxed_symbol(
        BUCK_SYMBOL_NAME, "U", BUCK_SYMBOL_NAME,
        "Package_TO_SOT_SMD:SOT-23-6", BUCK_DATASHEET, list(BUCK_PINS),
        5.08, 5.08, footprint_filter="SOT?23*")


def pfet_symbol_text():
    placed = [(number, "S", "passive", "left")
              for number in netlist.PFET_SOURCE_PINS]
    placed.append((netlist.PFET_GATE_PIN, "G", "input", "bottom"))
    placed.extend((number, "D", "passive", "right")
                  for number in netlist.PFET_DRAIN_PINS)
    return _boxed_symbol(
        PFET_SYMBOL_NAME, "Q", PFET_SYMBOL_NAME,
        "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", PFET_DATASHEET, placed,
        5.08, 6.35, footprint_filter="SOIC*3.9x4.9mm*P1.27mm*")


def tvs_symbol_text():
    return "\n".join([
        '\t(symbol "%s"' % TVS_SYMBOL_NAME,
        '\t\t(pin_numbers\n\t\t\t(hide yes)\n\t\t)',
        '\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t)',
        '\t\t(exclude_from_sim no)',
        '\t\t(in_bom yes)',
        '\t\t(on_board yes)',
        _symbol_property("Reference", "D", 0, False).rstrip("\n"),
        _symbol_property("Value", TVS_SYMBOL_NAME, 1, False).rstrip("\n"),
        _symbol_property("Footprint", "Diode_SMD:D_SMB", 2,
                         True).rstrip("\n"),
        _symbol_property("Datasheet", "", 3, True).rstrip("\n"),
        _symbol_property("ki_fp_filters", "D?SMB*", 4, True).rstrip("\n"),
        '\t\t(symbol "%s_0_1"' % TVS_SYMBOL_NAME,
        '\t\t\t(rectangle',
        '\t\t\t\t(start -1.27 1.27)',
        '\t\t\t\t(end 1.27 -1.27)',
        '\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n'
        '\t\t\t\t\t(type default)\n\t\t\t\t)',
        '\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)',
        '\t\t\t)',
        '\t\t)',
        '\t\t(symbol "%s_1_1"' % TVS_SYMBOL_NAME,
        _pin_text("passive", 0.0, 3.81, 270, "K", "1"),
        _pin_text("passive", 0.0, -3.81, 90, "A", "2"),
        '\t\t)',
        '\t)',
    ])


def esd_symbol_text():
    return "\n".join([
        '\t(symbol "%s"' % ESD_SYMBOL_NAME,
        '\t\t(pin_numbers\n\t\t\t(hide yes)\n\t\t)',
        '\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t\t(hide yes)\n\t\t)',
        '\t\t(exclude_from_sim no)',
        '\t\t(in_bom yes)',
        '\t\t(on_board yes)',
        _symbol_property("Reference", "D", 0, False).rstrip("\n"),
        _symbol_property("Value", ESD_SYMBOL_NAME, 1, False).rstrip("\n"),
        _symbol_property("Footprint", "%s:%s" % (LIBRARY_NAME,
                                                 X1SON_FOOTPRINT_NAME),
                         2, True).rstrip("\n"),
        _symbol_property("Datasheet", ESD_DATASHEET, 3, True).rstrip("\n"),
        _symbol_property("ki_fp_filters", X1SON_FOOTPRINT_NAME, 4,
                         True).rstrip("\n"),
        '\t\t(symbol "%s_0_1"' % ESD_SYMBOL_NAME,
        '\t\t\t(rectangle',
        '\t\t\t\t(start -1.27 1.27)',
        '\t\t\t\t(end 1.27 -1.27)',
        '\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n'
        '\t\t\t\t\t(type default)\n\t\t\t\t)',
        '\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)',
        '\t\t\t)',
        '\t\t)',
        '\t\t(symbol "%s_1_1"' % ESD_SYMBOL_NAME,
        _pin_text("passive", 0.0, 3.81, 270, "IO1", "1"),
        _pin_text("passive", 0.0, -3.81, 90, "IO2", "2"),
        '\t\t)',
        '\t)',
    ])


def terminal_symbol_text():
    lines = ['\t(symbol "%s"' % TERMINAL_SYMBOL_NAME,
             '\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t)',
             '\t\t(exclude_from_sim yes)',
             '\t\t(in_bom yes)',
             '\t\t(on_board yes)',
             _symbol_property("Reference", "J", 0, False).rstrip("\n"),
             _symbol_property("Value", TERMINAL_SYMBOL_NAME, 1,
                              False).rstrip("\n"),
             _symbol_property("Footprint", "%s:%s" % (LIBRARY_NAME,
                                                      KF128_FOOTPRINT_NAME),
                              2, True).rstrip("\n"),
             _symbol_property("Datasheet", "", 3, True).rstrip("\n"),
             _symbol_property("ki_fp_filters", TERMINAL_FOOTPRINT_FILTER, 4,
                              True).rstrip("\n"),
             '\t\t(symbol "%s_0_1"' % TERMINAL_SYMBOL_NAME]
    lines.extend(_rectangle(2.54, 3.81))
    lines.append('\t\t)')
    lines.append('\t\t(symbol "%s_1_1"' % TERMINAL_SYMBOL_NAME)
    for index, pin_name in enumerate(("1", "2")):
        lines.append(_pin_text("passive", -5.08, 1.27 - 2.54 * index, 0,
                               pin_name, str(index + 1)))
    lines.append('\t\t)')
    lines.append('\t)')
    return "\n".join(lines)


def symbol_library_text():
    body = [buck_symbol_text(), esd_symbol_text(), pfet_symbol_text(),
            terminal_symbol_text(), tvs_symbol_text()]
    return "\n".join([
        '(kicad_symbol_lib',
        '\t(version %s)' % SYMBOL_LIB_VERSION,
        '\t(generator "%s")' % GENERATOR,
        '\t(generator_version "10.0")',
    ] + body + [')']) + "\n"


# ---------------------------------------------------------------------------
# footprints

def _outline(layer, half_x, half_y, thickness, start_y=None, end_y=None):
    top = half_y if start_y is None else start_y
    bottom = -half_y if end_y is None else end_y
    return ('\t(fp_rect\n\t\t(start %.3f %.3f)\n\t\t(end %.3f %.3f)\n'
            '\t\t(stroke\n\t\t\t(width %.2f)\n\t\t\t(type default)\n\t\t)\n'
            '\t\t(fill none)\n\t\t(layer "%s")\n\t)'
            % (-half_x, top, half_x, bottom, thickness, layer))


def _footprint_header(name, descr, tags, attr, ref_y, value_y, size,
                      thickness, uid):
    return [
        '(footprint "%s"' % name,
        '\t(version %s)' % FOOTPRINT_VERSION,
        '\t(generator "%s")' % GENERATOR,
        '\t(generator_version "10.0")',
        '\t(layer "F.Cu")',
        '\t(descr "%s")' % descr,
        '\t(tags "%s")' % tags,
        '\t(attr %s)' % attr,
        '\t(property "Reference" "REF**"\n\t\t(at 0 %.2f 0)\n'
        '\t\t(layer "F.SilkS")\n\t\t(uuid "00000000-0000-0000-0000-'
        '0000000000%02d")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size %.1f %.1f)'
        '\n\t\t\t\t(thickness %.2f)\n\t\t\t)\n\t\t)\n\t)'
        % (ref_y, uid, size, size, thickness),
        '\t(property "Value" "%s"\n\t\t(at 0 %.2f 0)\n'
        '\t\t(layer "F.Fab")\n\t\t(uuid "00000000-0000-0000-0000-'
        '0000000000%02d")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size %.1f %.1f)'
        '\n\t\t\t\t(thickness %.2f)\n\t\t\t)\n\t\t)\n\t)'
        % (name, value_y, uid + 1, size, size, thickness),
    ]


def x1son_footprint_text():
    width, height = X1SON_PAD_SIZE_MM
    offset = X1SON_PAD_PITCH_MM / 2.0
    body_x, body_y = (value / 2.0 for value in X1SON_BODY_MM)
    court_x = body_x + X1SON_COURTYARD_MARGIN_MM
    court_y = body_y + X1SON_COURTYARD_MARGIN_MM
    pads = []
    for number, sign in (("1", -1.0), ("2", 1.0)):
        pads.append(
            '\t(pad "%s" smd roundrect\n\t\t(at %.3f 0)\n'
            '\t\t(size %.3f %.3f)\n\t\t(layers "F.Cu" "F.Paste" "F.Mask")\n'
            '\t\t(roundrect_rratio 0.1667)\n\t)'
            % (number, sign * offset, width, height))
    outline = [_outline("F.CrtYd", court_x, court_y, 0.05),
               _outline("F.Fab", body_x, body_y, 0.1)]
    return "\n".join(_footprint_header(
        X1SON_FOOTPRINT_NAME,
        "TI DPY0002A land pattern, SLLSEB1G drawing 4224561/C",
        "X1SON DPY TVS", "smd", -1.2, 1.2, 0.6, 0.1, 1)
        + outline + pads + [')']) + "\n"


def kf128_footprint_text():
    half_pitch = KF128_PITCH_MM / 2.0
    front = -KF128_PIN_TO_ENTRY_FACE_MM
    back = KF128_BODY_DEPTH_MM - KF128_PIN_TO_ENTRY_FACE_MM
    half_width = KF128_PITCH_MM
    margin = KF128_COURTYARD_MARGIN_MM
    pads = []
    for number, sign in (("1", -1.0), ("2", 1.0)):
        pads.append(
            '\t(pad "%s" thru_hole %s\n\t\t(at %.3f 0)\n'
            '\t\t(size %.3f %.3f)\n\t\t(drill %.3f)\n'
            '\t\t(layers "*.Cu" "*.Mask")\n\t)'
            % (number, "rect" if number == "1" else "circle",
               sign * half_pitch, KF128_PAD_DIAMETER_MM,
               KF128_PAD_DIAMETER_MM, KF128_DRILL_MM))
    outline = [
        _outline("F.CrtYd", half_width + margin, 0, 0.05,
                 start_y=back + margin, end_y=front - margin),
        _outline("F.Fab", half_width, 0, 0.1, start_y=back, end_y=front),
    ]
    return "\n".join(_footprint_header(
        KF128_FOOTPRINT_NAME,
        "Cixi Kefa KF128-5.08 2-pole screw terminal, PCB layout from drawing "
        "KF128-5.08 rev A",
        "terminal block screw 5.08mm", "through_hole",
        front - 1.2, back + 1.2, 1.0, 0.15, 11)
        + outline + pads + [')']) + "\n"


def inductor_footprint_text():
    pad_x, pad_y = INDUCTOR_PAD_MM
    offset = (INDUCTOR_LAND_SPAN_MM - pad_x) / 2.0
    body_x, body_y = (value / 2.0 for value in INDUCTOR_BODY_MM)
    court_x = max(offset + pad_x / 2.0, body_x) + INDUCTOR_COURTYARD_MARGIN_MM
    court_y = max(pad_y / 2.0, body_y) + INDUCTOR_COURTYARD_MARGIN_MM
    pads = []
    for number, sign in (("1", -1.0), ("2", 1.0)):
        pads.append(
            '\t(pad "%s" smd rect\n\t\t(at %.3f 0)\n'
            '\t\t(size %.3f %.3f)\n\t\t(layers "F.Cu" "F.Paste" "F.Mask")\n\t)'
            % (number, sign * offset, pad_x, pad_y))
    outline = [_outline("F.CrtYd", court_x, court_y, 0.05),
               _outline("F.Fab", body_x, body_y, 0.1)]
    return "\n".join(_footprint_header(
        INDUCTOR_FOOTPRINT_NAME,
        "Bourns SRP4020TA shielded power inductor, recommended layout from "
        "the SRP4020TA series datasheet",
        "inductor shielded SRP4020", "smd", -court_y - 0.8, court_y + 0.8,
        0.8, 0.12, 21) + outline + pads + [')']) + "\n"


def htssop_footprint_text():
    pad_x, pad_y = HTSSOP_PAD_MM
    ep_x, ep_y = HTSSOP_EP_MM
    body_x, body_y = (value / 2.0 for value in HTSSOP_BODY_MM)
    court_x = HTSSOP_ROW_OFFSET_MM + pad_x / 2.0 + HTSSOP_COURTYARD_MARGIN_MM
    court_y = body_y + HTSSOP_COURTYARD_MARGIN_MM
    pads = []
    for number, (x, y) in sorted(htssop_pad_positions_mm().items(),
                                 key=lambda item: int(item[0])):
        pads.append(
            '\t(pad "%s" smd roundrect\n\t\t(at %.4f %.4f)\n'
            '\t\t(size %.3f %.3f)\n\t\t(layers "F.Cu" "F.Paste" "F.Mask")\n'
            '\t\t(roundrect_rratio 0.25)\n\t)' % (number, x, y, pad_x, pad_y))
    pads.append(
        '\t(pad "%s" smd rect\n\t\t(at 0 0)\n\t\t(size %.3f %.3f)\n'
        '\t\t(layers "F.Cu")\n\t\t(property pad_prop_heatsink)\n'
        '\t\t(zone_connect 2)\n\t)'
        % (netlist.DRIVER_PINS["EPAD"], ep_x, ep_y))
    height = mask_window_height_mm()
    for centre in mask_window_centres_mm():
        pads.append(
            '\t(pad "" smd rect\n\t\t(at 0 %.4f)\n\t\t(size %.3f %.3f)\n'
            '\t\t(layers "F.Mask")\n\t)' % (centre, ep_x, height))
        pads.append(
            '\t(pad "" smd rect\n\t\t(at 0 %.4f)\n\t\t(size %.3f %.3f)\n'
            '\t\t(layers "F.Paste")\n\t)' % (centre, ep_x, height))
    marker = (
        '\t(fp_line\n\t\t(start %.3f %.3f)\n\t\t(end %.3f %.3f)\n'
        '\t\t(stroke\n\t\t\t(width 0.12)\n\t\t\t(type default)\n\t\t)\n'
        '\t\t(layer "F.SilkS")\n\t)'
        % (-court_x, -court_y, -court_x + 0.8, -court_y))
    outline = [_outline("F.CrtYd", court_x, court_y, 0.05),
               _outline("F.Fab", body_x, body_y, 0.1)]
    return "\n".join(_footprint_header(
        HTSSOP_FOOTPRINT_NAME,
        "HTSSOP-28 with exposed pad 2.75x6.2 mm; mask and paste cut into "
        "%d windows so the board's thermal vias land on mask dams"
        % HTSSOP_MASK_WINDOWS,
        "HTSSOP TSSOP exposed pad thermal vias", "smd",
        -court_y - 1.0, court_y + 1.0, 1.0, 0.15, 31)
        + outline + [marker] + pads + [')']) + "\n"


def sym_lib_table_text():
    return ('(sym_lib_table\n\t(version 7)\n'
            '\t(lib (name "%s")(type "KiCad")'
            '(uri "${KIPRJMOD}/library/%s.kicad_sym")'
            '(options "")(descr ""))\n)\n'
            % (LIBRARY_NAME, LIBRARY_NAME))


def fp_lib_table_text():
    return ('(fp_lib_table\n\t(version 7)\n'
            '\t(lib (name "%s")(type "KiCad")'
            '(uri "${KIPRJMOD}/library/%s.pretty")(options "")(descr ""))\n)\n'
            % (LIBRARY_NAME, LIBRARY_NAME))


def artifacts():
    return {
        SYMBOL_LIB_PATH: symbol_library_text(),
        os.path.join(FOOTPRINT_DIR, X1SON_FOOTPRINT_NAME + ".kicad_mod"):
            x1son_footprint_text(),
        os.path.join(FOOTPRINT_DIR, KF128_FOOTPRINT_NAME + ".kicad_mod"):
            kf128_footprint_text(),
        os.path.join(FOOTPRINT_DIR, INDUCTOR_FOOTPRINT_NAME + ".kicad_mod"):
            inductor_footprint_text(),
        os.path.join(FOOTPRINT_DIR, HTSSOP_FOOTPRINT_NAME + ".kicad_mod"):
            htssop_footprint_text(),
        SYM_LIB_TABLE: sym_lib_table_text(),
        FP_LIB_TABLE: fp_lib_table_text(),
    }


def write():
    os.makedirs(FOOTPRINT_DIR, exist_ok=True)
    written = []
    for path, text in artifacts().items():
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        written.append(path)
    return sorted(written)


if __name__ == "__main__":
    for path in write():
        sys.stdout.write(path + "\n")
